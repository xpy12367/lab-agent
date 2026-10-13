import traceback
import httpx
from langchain_openai import ChatOpenAI
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from collections.abc import Iterator
from typing import Any
from app.common.exceptions import BusinessException
from app.models.user import User
from app.schemas.ai import ChatRequest
from app.services import agent_tools
from app.config import settings

SYSTEM_PROMPT = """你是智能实验室预约系统的 Agent，回答要简洁。
你可以：
1. 使用 search_lab_docs 查询实验室的规则、安全、开放时间等问题
2. 使用 list_open_labs / list_lab_equipments  查询真实的实验室和设备
3. 再用户进行了预约确认后，使用 create_lab_reservation 来进行真实的预约落库
4. 使用 get_today 来进行日期的换算

## 必须遵守
当用户提到了 今天、明天、后天 等日期相关的问题，请先调用 get_today 来获取日期，**不要直接返回 我需要确定明天的具体日期**。

在提交预约之前必须向用户复述：实验室ID与名称（或设备ID和名称）、日期、开始时间、结束时间。并得到用户确认再进行实际操作。
用户没说【确认】【确认预约】【就这样预约】等确定性回复之前，不要调用 create_lab_reservation。
工作流的确认环节里如果缺少了 lab_id，请先 list_open_labs 查到了 lab_id 再创建，不要瞎写。
工作流的确认环节里如果缺少了 equipment_id，请先 list_lab_equipments 查到了 equipment_id 再创建，不要瞎写。

预约成功后状态是待审核，必须管理员确认后实验室（或设备）才能使用。
不要瞎编数据库里没有的实验室或者设备信息。
如果是问开放时间或者实验室规则，优先调用 search_lab_docs，不要凭空回复。
"""

# 工具英文名 → 页面上给人看的中文过程文案
TOOL_LABELS = {
    "search_lab_docs": "检索实验室知识库",
    "list_open_labs": "查询开放实验室",
    "list_lab_equipments": "查询实验室设备",
    "create_lab_reservation": "提交预约",
    "get_today": "获取今天日期",
}


def _chunk_text(chunk: Any) -> str:
    """从模型流式 chunk 里抠出纯文本。
    content 有时是 str，有时是 [{type, text}, ...] 这种块列表，要统一成字符串。
    """
    if chunk is None:
        return ""
    # chunk 可能是 AIMessageChunk，真正字在 .content
    content = getattr(
        chunk, "content", None
    )  # 用字符串名字(chunk)去取对象("content")的属性,没有就返回None。
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text") or "")
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts)
    return str(content) if content is not None else ""


def _tool_output_preview(output: Any, limit: int = 200) -> str:
    """把工具结果收成短预览，避免整段 JSON 刷到前端过程区。"""
    # LangGraph 里工具结果经常是 ToolMessage，正文在 .content
    if isinstance(output, ToolMessage):
        output = output.content
    text = output if isinstance(output, str) else str(output)
    # 太长就截断，末尾加省略号
    return text if len(text) <= limit else text[:limit] + "…"


def _build_history(data: ChatRequest) -> list:
    """前端只传 user/assistant 文本，转成 LangChain 消息对象。"""
    history = []
    for message in data.messages or []:
        if message.role == "user" and message.content.strip():
            history.append(HumanMessage(content=message.content.strip()))
        elif message.role == "assistant" and message.content.strip():
            history.append(AIMessage(content=message.content.strip()))
    if not history:
        raise BusinessException(message="请输入您要对话的内容")
    return history


async def stream_agent(db: Session, current_user: User, data: ChatRequest):
    """生成器：边跑 Agent 边 yield 事件，供 SSE 推给前端。
    事件类型：status / tool_start / tool_end / token / done / error
    """
    try:
        history = _build_history(data)
        agent = build_agent(db, current_user)
        # *history：把列表拆开，和 SystemMessage 拼成完整 messages
        inputs = {"messages": [SystemMessage(content=SYSTEM_PROMPT), *history]}
        # yield = 先交出这一条，函数暂停；前端收到后再继续往下跑
        yield {"type": "status", "message": "正在思考…"}
        # stream_events：图每走一步（调工具、吐字）都会冒出一个内部事件
        async for event in agent.astream_events(
            inputs,
            version="v2",
            config={"recursion_limit": 10},  # agent⇄tools 来回上限，防空转
        ):
            print("event:", event.get("event"),event.get("name"))
            kind = event.get("event")  # 事件类型
            if kind == "on_tool_start":  # 工具调用开始
                name = event.get("name") or ""  # 工具英文名
                yield {
                    "type": "tool_start",
                    "name": name,
                    "label": TOOL_LABELS.get(name, name),  # 没有中文映射就退回英文名
                    # 用name作为key去查TOOL_LABELS，没有就退回name它本身
                }
            elif kind == "on_tool_end":  # 工具调用结束
                name = event.get("name") or ""
                yield {
                    "type": "tool_end",
                    "name": name,
                    "label": TOOL_LABELS.get(name, name),
                    # 只给预览；完整结果仍在图内部 messages 里给模型用
                    "preview": _tool_output_preview(
                        (event.get("data") or {}).get("output")
                    ),
                }
            elif kind == "on_chat_model_stream":  # 最终模型返回的token
                # 只收 agent 节点的字；其它内部节点的噪声丢掉
                meta = event.get("metadata") or {}
                if meta.get("langgraph_node") not in (None, "agent"):
                    continue
                text = _chunk_text((event.get("data") or {}).get("chunk"))
                if text:
                    yield {"type": "token", "content": text}
        # 正常跑完：不要在 done 里再带一份全文，前端已经用 token 拼好了
        yield {"type": "done"}  # 通知前端对话结束
    except BusinessException as exc:
        # 流已经是 SSE，错误也要用 yield，别 raise 成普通 JSON
        yield {"type": "error", "message": exc.message}
    except Exception as exc:
        traceback.print_exc()
        yield {"type": "error", "message": "大模型调用失败，请稍后重试"}


def build_agent(db: Session, current_user: User):
    """构建大模型对话"""
    tools = agent_tools.build_tools(db, current_user)
    llm = ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        temperature=0,
        streaming=True,  # 打开流式，stream_events 才能收到逐字 token
        # trust_env=False：不读 HTTP_PROXY/HTTPS_PROXY/NO_PROXY 等环境变量。
        # 否则 httpx 解析 NO_PROXY 里的非法值（如带方括号的 [::1]）会直接抛
        # httpx2.InvalidURL，客户端在“构造阶段”就崩，网络请求根本发不出去。
        http_client=httpx.Client(trust_env=False),
    ).bind_tools(tools)

    async def agent_node(state: MessagesState):
        """langGraph 执行的工作流 的节点"""
        response = await llm.ainvoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)  # 调用大模型的节点
    graph.add_node("tools", ToolNode(tools))  # tool call的节点
    graph.add_edge(START, "agent")  # 流程的起点，call LLM
    graph.add_conditional_edges(
        "agent",
        tools_condition,  # tools_condition:内置的路由条件函数，用来判断是否有 tool_call
    )  # 看有无 tool_call  有就继续call  没有就END 输出
    graph.add_edge("tools", "agent")  # 让agent看tool调用的结果
    return graph.compile()


# def run_agent(db: Session, current_user: User, data: ChatRequest):
#     """运行大模型对话"""
#     if not data.messages:
#         raise BusinessException(message="对话内容为空")
#     history = []
#     for message in data.messages:
#         if message.role == "user" and message.content.strip():
#             history.append(HumanMessage(content=message.content.strip()))
#         elif message.role == "assistant" and message.content.strip():
#             history.append(AIMessage(content=message.content.strip()))
#     if not history:
#         raise BusinessException(message="请输入您要对话的内容")

#     agent = build_agent(db, current_user)
#     try:
#         result = agent.invoke(
#             {"messages": [SystemMessage(content=SYSTEM_PROMPT), *history]},
#             config={"recursion_limit": 10},
#         )  # 设置对话循环的上限是10轮
#     except BusinessException:
#         raise
#     except Exception:
#         raise BusinessException(message="大模型调用失败，请稍后重试")

#     messages = result.get("messages") or []
#     if not messages:
#         raise BusinessException(message="大模型没有任何返回内容")
#     for message in reversed(
#         messages
#     ):  # reversed(messages): 从后往前遍历，因为大模型返回的是最新的一条消息
#         if isinstance(message, AIMessage) and message.content.strip():
#             # isinstance(对象, 类型),用来判断一个对象「是不是某种类型」
#             content = message.content.strip()
#             if isinstance(content, list):
#                 content = "".join(
#                     (
#                         part.get("text", "") if isinstance(part, dict) else str(part)
#                     )  # 如果 part 是字典，就取出它的 text 字段；否则把 part 直接当字符串用。
#                     for part in content
#                 )
#             if str(content).strip():
#                 return str(content).strip()
