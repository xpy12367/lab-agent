import traceback

from openai import OpenAI
from app.common.exceptions import BusinessException
from app.config import settings
from app.schemas.ai import ChatMessage, ChatRequest
from app.services import kb_service
import json
from sqlalchemy.orm import Session
from app.services import equipment_service, lab_service
from app.services.kb_service import search

SYSTEM_PROMPT = """你是智能实验室预约系统的助手，回答要简洁。
如果下面提供了实验室资料，请依据资料回答规则、安全、文档里的开放时间说明。
查询当前有哪些开放实验室、某实验室有哪些设备时，必须调用工具，不要编造。
你不能替用户提交预约，也不能直接改数据库。
如果用户要预约，请说明去「实验室列表」选择后提交，等待管理员审核。
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_open_labs",
            "description": "查询当前开放中的实验室列表，可以按名称关键字来筛选",
            "parameters": {
                "type": "object",
                "properties": {
                    "keywords": {
                        "type": "string",
                        "description": "实验室的名称关键字，可以为空",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_lab_equipments",
            "description": "查询某个实验室下的设备列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "lab_id": {
                        "type": "integer",
                        "description": "实验室 ID",
                    },
                    "keywords": {
                        "type": "string",
                        "description": "设备名称的关键字，可以为空",
                    },
                },
            },
        },
    },
]


def run_tool(db: Session, name: str, arguments: str) -> str:
    """调用工具

    参数说明：
    - db：数据库会话，工具内部要查库
    - name：大模型想调用的工具名（对应 TOOLS 里的 name）
    - arguments：大模型给出的参数，是 JSON 字符串（不是字典！）

    返回值：始终返回一个 JSON 字符串，出错也返回 JSON，方便回传给大模型
    """
    # 第 1 步：解析大模型给的参数
    # arguments 是字符串形式，如 '{"keywords":"化学"}'，需要转成字典才能按 key 取值
    # arguments or "{}"：以防传进来是空字符串/None，兜底成空字典 "{}"
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        # 大模型偶尔会给出非法 JSON，这时直接返回错误信息，不要继续往下走
        return json.dumps(
            {"error": "参数不是合法的json"}, ensure_ascii=False
        )  # json.loads :把json字符串转化成字典
        # ensure_ascii=False 让中文原样输出（否则会变成 \uXXXX 转义）

    # 第 2 步：按工具名分派到不同的处理逻辑
    try:
        if name == "list_open_labs":
            # args.get("keywords") 取出关键字；可能为 None 或空串
            # .strip() 去掉首尾空格；再用 `or None` 把空串统一成 None，
            # 这样下游的"是否过滤"判断更简单（空串和 None 都表示不过滤）
            keywords = (args.get("keywords") or "").strip() or None

            # 复用普通的分页查询逻辑：只查第 1 页、每页 10 条、状态为 1（开放中）
            page = lab_service.get_lab_page_list(
                db, page=1, page_size=10, keywords=keywords, status=1
            )

            # 把 ORM 对象"瘦身"成只含关键字段的字典
            # 目的：减少回传给大模型的 token，也让数据结构更清晰
            rows = [
                {
                    "id": item.id,
                    "name": item.name,
                    "location": item.location,
                    "capacity": item.capacity,
                    "open_time": item.open_time,
                    "close_time": item.close_time,
                }  for item in page.list
            ]
            # ensure_ascii=False 让中文原样输出（否则会变成 \uXXXX 转义）
            return json.dumps({"total": page.total, "labs": rows}, ensure_ascii=False)

        if name == "list_lab_equipments":
            lab_id = args.get("lab_id")
            # 这个工具必须有 lab_id，缺了就返回明确错误，让大模型知道要补参数
            if not lab_id:
                return json.dumps(
                    {"error": "参数缺少实验室 lab_id"}, ensure_ascii=False
                )
            keywords = (args.get("keywords") or "").strip() or None

            # int(lab_id)：大模型可能把数字传成字符串 "3"，这里强制转成整数
            page = equipment_service.get_equipment_page_list(
                db, page=1, page_size=10, lab_id=int(lab_id), keywords=keywords
            )

            rows = [
                {
                    "id": item.id,
                    "name": item.name,
                    "lab_id": item.lab_id,
                    "lab_name": item.lab_name,
                    "spec": item.spec,
                    "quantity": item.quantity,
                    "status": item.status,
                }  for item in page.list
            ]
            return json.dumps(
                {"total": page.total, "equipments": rows}, ensure_ascii=False
            ) # ensure_ascii=False 让中文原样输出（否则会变成 \uXXXX 转义）

        # 走到这里说明大模型报了一个我们没定义过的工具名
        return json.dumps({"error": f"未找到工具：{name}"}, ensure_ascii=False)

    except Exception as exc:
        # 兜底：工具内部任何异常都转成 JSON 错误返回，
        # 保证不会因为工具出错而中断整个对话流程
        return json.dumps({"error": exc.message}, ensure_ascii=False)


def get_client() -> OpenAI:
    """创建OPENAI的客户端"""
    if not settings.LLM_API_KEY:
        raise BusinessException(message="未获取到大模型的API Key")
    return OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)


def chat(db: Session, data: ChatRequest):
    """大模型对话"""
    if not data.messages:
        raise BusinessException(message="对话内容为空")
    history = []
    for message in data.messages:
        if message.role in ("user", "assistant") and message.content.strip():
            history.append(message.model_dump())
    if not history:
        raise BusinessException(message="请输入您要对话的内容")
    # next():取出用户最新的一条提问内容
    question = next(
        (item["content"] for item in reversed(history) if item["role"] == "user"), ""
    )  # reversed():倒序遍历历史记录
    knowledge = kb_service.search(query=question)
    print(f"检索到的向量库的内容：{knowledge}")
    system_prompt = SYSTEM_PROMPT
    if knowledge:
        system_prompt += "\n\n以下是检索到的实验室的资料：\n" + knowledge
    client = get_client()
    messages = [
        {"role": "system", "content": system_prompt},
        *history,
    ]
    try:
        for _ in range(3):
            res = client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            msg = res.choices[0].message
            tool_calls = msg.tool_calls or []
            if not tool_calls:  # 没有工具调用 则直接返回大模型的输出结果内容
                content = msg.content
                if not content or not content.strip():
                    raise BusinessException(message="大模型没有返回内容")
                return content
            messages.append(  # 有工具调用
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        } for call in tool_calls
                    ],
                }
            )
            for call in tool_calls:
                result = run_tool(db, call.function.name, call.function.arguments)
                messages.append(
                    {"role": "tool", "content": result, "tool_call_id": call.id}
                )
    except Exception as exc:
        traceback.print_exc()
        raise BusinessException(message="大模型调用失败，请稍后重试")
