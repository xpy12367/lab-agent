# 实验室智能预约系统 + AI 助手（lab-agent）

基于 **FastAPI + MySQL + Vue3** 的实验室预约管理系统，并在业务系统之上叠加
**RAG 知识库问答** 与 **LangGraph Agent（Function Calling + SSE 流式）**。

AI 助手不是独立 Demo：它通过工具直接读写真实业务库，与页面预约共用同一套业务校验规则。

## 系统架构

```
前端（Vue3 + Element Plus）
   │ HTTP / SSE
   ▼
FastAPI ──┬─ 业务 API    用户 / 实验室 / 设备 / 预约
          └─ AI API      POST /api/ai/chat/stream   （SSE 流式）
             │
             ▼
        LangGraph Agent
             │
      ┌──────┴───────┐
      │ agent 节点    │  调用大模型，决定「回答」还是「调工具」
      │ tools 节点    │  ToolNode 执行工具，结果回灌给 agent
      └──────┬───────┘
             │ tools_condition 条件边：有 tool_call 继续，无则 END
             ▼
        Service 层（与页面接口共用）
             ├─ MySQL      用户、实验室、设备、预约
             ├─ ChromaDB   知识库向量（预约规则 / 安全规范 / 开放时间 / 设备使用）
             └─ 大模型      OpenAI 兼容接口（DeepSeek / 通义千问等）
```

**一句话概括**：页面打业务接口走 MySQL；AI 助手既查库、也查知识库，也能直接落库提交预约。

## 目录结构

```
backend/
  app/
    api/           路由层（auth / user / lab / equipment / reservation / ai / files）
    services/
      agent_service.py   LangGraph 图构建 + SSE 事件流（stream_agent）
      agent_tools.py     @tool 工具集（5 个）
      ai_service.py      早期手写 Function Calling 实现（保留作对照）
      kb_service.py      ChromaDB 向量检索
      reservation_service.py  预约业务（页面与 AI 共用）
    models/        SQLAlchemy 模型（user / lab / equipment / reservation）
    schemas/       Pydantic 请求响应模型
    dependencies/  JWT 鉴权与管理员权限校验
    common/        统一响应与全局异常处理
    utils/         JWT、bcrypt 密码哈希
    main.py        应用入口（lifespan 预热向量库 + 后台过期扫描任务）
  data/
    kb/            知识库原始 Markdown 文档
    chroma/        ChromaDB 持久化目录（运行期生成，已 gitignore）
frontend/          Vue3 + Vite + Element Plus 前端
```

## 核心功能

- **认证与权限**：JWT 无状态鉴权，`get_current_user` / `get_current_admin` 依赖注入式角色分级。
- **实验室与设备管理**：分页模糊查询、图片上传、状态维护（开放 / 关闭、正常 / 维修）。
- **预约业务**：完整状态流转「待审核 → 已通过 / 已拒绝 / 已取消」；创建预约时校验日期、时段是否
  落在实验室开放时间内，并用 `lab_id + date + 时段重叠` 条件查询做占用判定，避免重复预约。
- **过期自动回收**：后台 `asyncio` 常驻协程每分钟扫描一次，把已过期的待审核预约置为已取消。
- **AI 助手（LangGraph Agent）**：
  - **图编排**：`StateGraph(MessagesState)` + `agent` / `tools` 双节点，用内置 `tools_condition`
    条件边按「有无 tool_call」路由，`recursion_limit=10` 限制 agent ⇄ tools 往返次数。
  - **5 个工具**：`search_lab_docs`（知识库检索）、`list_open_labs`、`list_lab_equipments`、
    `get_today`（日期换算）、`create_lab_reservation`（真正落库提交预约）。
  - **RAG 作为工具调用**：检索不再预先注入 Prompt，而是由模型在需要时主动调用，减少无关上下文。
  - **SSE 流式可见**：`status → tool_start / tool_end → token → done`，前端逐字渲染回答，
    并把「正在查询开放实验室…」等工具执行过程展示出来。
  - **落库与页面同源**：`create_lab_reservation` 复用 `reservation_service.create_reservation`，
    并统一走 `ReservationCreateRequest` 入参模型，保证 AI 预约与页面预约校验一致。
  - **容错**：工具内部异常统一转为结构化 JSON 错误回传，不中断对话。
- **启动优化**：`lifespan` 中用 `asyncio.to_thread` 预热向量模型（约 15s），
  避免首个请求超过前端超时。

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 配置环境变量（键名参见 .env.example）
copy .env.example .env          # 然后填入真实的数据库与 API Key
```

创建数据库（MySQL）：

```sql
CREATE DATABASE lab_agent DEFAULT CHARACTER SET utf8mb4;
```

启动服务（首次启动会自动建表）：

```bash
uvicorn app.main:app --reload
```

- 接口文档：http://127.0.0.1:8000/docs

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

- 前端地址：http://localhost:5173（已配置 `/api` 代理到 `127.0.0.1:8000`）

## 主要 API

| 分组 | 端点 |
| --- | --- |
| 认证 | `POST /api/auth/register`、`POST /api/auth/login` |
| 当前用户 | `GET /api/user/me`、`PUT /api/user/me`、`PUT /api/user/password` |
| 用户管理（管理员） | `GET /api/user/list`、`POST /api/user`、`PUT /api/user/{id}`、`DELETE /api/user/{id}` |
| 实验室 | `GET /api/lab/list`、`GET /api/lab/{id}`、`POST /api/lab`、`PUT /api/lab/{id}`、`DELETE /api/lab/{id}` |
| 设备 | `GET /api/equipment/list`、`POST /api/equipment`、`PUT /api/equipment/{id}`、`DELETE /api/equipment/{id}` |
| 预约 | `GET /api/reservation/list`、`POST /api/reservation`、`PUT /api/reservation/{id}/cancel`、`PUT /api/reservation/{id}/audit` |
| 文件 | `POST /api/files/upload` |
| **AI 助手** | **`POST /api/ai/chat/stream`（SSE 流式）** |

SSE 事件类型：

```jsonc
{"type": "status",     "message": "正在思考…"}
{"type": "tool_start", "name": "list_open_labs", "label": "查询开放实验室"}
{"type": "tool_end",   "name": "list_open_labs", "label": "查询开放实验室", "preview": "…"}
{"type": "token",      "content": "实"}
{"type": "done"}
{"type": "error",      "message": "大模型调用失败，请稍后重试"}
```

## 知识库说明

`backend/data/kb/` 下的 Markdown 文档会在向量库为空时自动导入。当前包含：

| 文档 | 内容 |
| --- | --- |
| 预约规则.md | 预约与取消的时间规则 |
| 安全规范.md | 实验室安全要求 |
| 开放时间.md | 各实验室开放时段 |
| 设备使用.md | 设备使用与维护说明 |

检索流程：`bge-small-zh-v1.5` 向量化 → ChromaDB 相似度查询（最多 5 条）→
把向量距离换算为 `1/(1+dist)` 相似度 → 过滤 `< 0.5` 的低相关片段 → 取 Top-2 返回。

> 注意：目前仅在集合为空时导入，修改文档后需删除 `backend/data/chroma/` 重新生成。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 后端 | Python 3 · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Uvicorn |
| 数据库 | MySQL（PyMySQL 驱动） |
| 鉴权 | JWT（PyJWT）· OAuth2PasswordBearer · bcrypt |
| Agent 编排 | LangGraph（StateGraph / ToolNode / tools_condition）· LangChain Core / OpenAI |
| RAG | ChromaDB · Sentence-Transformers（`BAAI/bge-small-zh-v1.5`） |
| 前端 | Vue3（组合式 API）· Vite · Element Plus · Axios · marked + DOMPurify |

## 已知限制

- 预约查重是「先查后插」的应用层校验，高并发下仍有竞态窗口；生产环境应加数据库唯一约束或行锁。
- 知识库仅在集合为空时导入，尚未实现文档变更自动同步。
- SSE 会话无断线重连与消息补偿，网络中断后需重新提问。
- 前端基于 Element Plus 管理后台模板改造，主要用于验证后端接口。
