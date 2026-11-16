# 开发实验室 AI 助手对话（后端）

> 对应课程：第 20 节
> 对应项目：`agent-lab/lab-system-agent`
> 前置课程：第 19 节 我的预约与预约审核
> 本节目标：登录用户可以通过后端接口与大模型对话，助手能解释系统规则，但不能查询真实数据或代替用户操作
> 整理日期：2026-11-13
> 阅读方式：先理解大模型调用涉及的概念，再按“配置 → Schema → Service → API → 联调”的顺序看代码，最后看排错复盘。

---

## 第零章 这节课完成了什么

第 19 节结束后，系统的预约、取消、审核、过期处理都已经闭环。本节新增一个后端 AI 助手接口：

```text
学生已登录
    ↓
POST /api/ai/chat，携带 JWT 和对话消息
    ↓
FastAPI 校验登录状态和请求格式
    ↓
ai_services.chat() 组装 system 提示词 + 历史消息
    ↓
OpenAI SDK 通过 HTTPS 调用 OpenCode Go 网关
    ↓
网关转发给 DeepSeek V4.1 Flash
    ↓
返回回答文本，按统一格式 { code, message, data } 返回
```

助手能做的事：

- 解释预约流程、时间规则、状态含义
- 解释取消规则、过期规则
- 引导用户去「实验室列表」「我的预约」查看数据

助手不能做的事：

- 查不到数据库里的真实实验室、设备、预约
- 不能替用户提交预约、取消预约或审核
- 不会编造某个实验室的开放时间或空闲情况

### 0.1 本节涉及哪些文件

| 文件 | 作用 |
|---|---|
| `backend/.env` | 存放 LLM 的 Key、模型名、接口地址（不提交） |
| `backend/app/config.py` | `Settings` 增加 `LLM_API_KEY / LLM_MODEL / LLM_BASE_URL` |
| `backend/requirements.txt` | 增加 `openai==3.14.1` |
| `backend/app/schemas/ai.py` | 定义 `ChatMessage`、`ChatRequest` |
| `backend/app/services/ai_services.py` | 创建客户端、系统提示词、调用大模型 |
| `backend/app/api/ai.py` | 定义 `POST /api/ai/chat`，做登录校验 |
| `backend/app/api/__init__.py` | 注册 AI router |
| `frontend` | 本节不涉及，后续课程再做对话页面 |

---

## 第一章 先理解几个概念

这一节比前面的 CRUD 难，主要难在“我们不是在直接调用某个函数，而是在通过 HTTP 调用一个外部模型服务”。先把概念拆开。

### 1.1 大模型不是本地代码，而是一个 HTTP 服务

数据库查询是“本地进程通过驱动访问 MySQL”，而大模型调用是：

```text
你的后端  ──HTTPS 请求──>  模型网关  ──>  模型服务
         <──JSON 响应──
```

所以你真正要做的是：

1. 按对方要求的格式发一个 HTTP 请求
2. 从返回的 JSON 里取出回答

`openai` 这个 Python 包就是帮你“组装请求、发送请求、解析响应”的工具。

### 1.2 什么是 OpenAI 兼容协议

业内很多模型服务都提供一套和 OpenAI 相同的接口格式，核心是：

```http
POST /chat/completions
Authorization: Bearer <API Key>
Content-Type: application/json

{
  "model": "模型名",
  "messages": [
    { "role": "system", "content": "系统设定" },
    { "role": "user", "content": "用户问题" }
  ]
}
```

响应大致是：

```json
{
  "choices": [
    {
      "message": { "role": "assistant", "content": "模型回答" }
    }
  ],
  "usage": { "prompt_tokens": 305, "completion_tokens": 178, "total_tokens": 483 }
}
```

只要服务支持这套协议，就可以用同一个 SDK，只改 `base_url` 和 `model`。OpenCode Go/Zen、vLLM、DeepSeek 官方、很多本地模型服务都支持。

### 1.3 SDK、client、请求三者的区别

这是最容易混淆的地方：

| 名称 | 是什么 |
|---|---|
| `openai` | 安装的 Python 包，也就是 SDK |
| `OpenAI` | SDK 里的一个类 |
| `OpenAI(api_key=..., base_url=...)` | 用这个类创建出来的客户端对象，保存了地址、Key、超时等配置 |
| `client.chat.completions.create(...)` | 用客户端真正发起一次 HTTP 请求 |
| 返回值 `res` | 本次请求的响应对象 |

可以类比：

- SDK = 工具箱
- 客户端 = 按配置组装好的工具
- `create()` = 真正动手干活
- `res` = 干完活拿回来的结果

**创建客户端不会发请求，也不会扣费**；只有调用 `create()` 才会真正访问网络。

### 1.4 base_url 和 model 分别决定什么

- `base_url`：请求发到哪里，例如 `https://opencode.ai/inference/go/openai/v1`
- `model`：由哪个模型处理，例如 `deepseek-v4.1-flash`

SDK 会在 `base_url` 后面自动拼上 `/chat/completions`，所以：

```text
base_url = https://opencode.ai/inference/go/openai/v1
最终请求 = https://opencode.ai/inference/go/openai/v1/chat/completions
```

**不要把 `/chat/completions` 写进 `base_url`**，否则会变成 `/chat/completions/chat/completions`，直接 404。

### 1.5 messages 里的角色

| 角色 | 含义 |
|---|---|
| `system` | 系统设定，告诉模型“你是谁、能做什么、不能做什么” |
| `user` | 用户说的话 |
| `assistant` | 模型之前说过的话，用于多轮对话 |

本节把系统提示词固定放在第一条，用户历史放在后面：

```python
messages=[
    {"role": "system", "content": SYSTEM_PROMPT},
    *history,
]
```

### 1.6 模型 ID 中的 1017 是什么

我们用的是 `deepseek-v4.1-flash`。

`1017` 是 DeepSeek-V4.1-Flash 在 2026-10-17 发布的 checkpoint 版本号，**不是 API 模型 ID**。OpenCode Go/Zen 上模型 ID 仍然是：

```text
deepseek-v4.1-flash
```

写成 `deepseek-v4.1-flash-1017` 反而会找不到模型。

### 1.7 OpenCode Go 的两个特殊要求

OpenCode Go 是按订阅额度提供的模型网关，除了标准的 `Authorization` 之外，还要求：

1. **`x-opencode-session`**：标识一段对话，用于路由和 prompt 缓存
2. **自定义 `User-Agent`**：标识调用方是自己的应用，而不是通用 SDK

缺少 `x-opencode-session` 时，网关会返回：

```json
{
  "error": {
    "type": "MissingSessionID",
    "message": "Request is missing x-opencode-session and cannot be routed efficiently."
  }
}
```

HTTP 状态是 **400**。这不是 Key 错误，也不是模型不存在，而是请求头不完整。本项目用 `user-{用户ID}` 作为会话 ID，保证同一用户的对话稳定复用。

---

## 第二章 配置层

### 2.1 `.env` 增加三个变量

```env
LLM_API_KEY=<你的 OpenCode 密钥>
LLM_MODEL=deepseek-v4.1-flash
LLM_BASE_URL=https://opencode.ai/inference/go/openai/v1
```

说明：

- `.env` 已在 `.gitignore` 中，不会提交
- `LLM_BASE_URL` 只写到 `/v1`，不要带 `/chat/completions`
- 如果你用的是旧的 Go 地址，`https://opencode.ai/zen/go/v1` 带上 session 头也能用
- Zen 按量付费与 Go 订阅是两套计费，同一个 Key 可用，但地址和额度不同

### 2.2 `app/config.py` 增加字段

```python
class Settings(BaseSettings):
    DATABASE_URL: str

    JWT_SECRET_KEY: str
    JWT_EXPIRE_HOURS: int = 24
    JWT_ALGORITHM: str = "HS256"

    LLM_API_KEY: str
    LLM_MODEL: str
    LLM_BASE_URL: str

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8"
    )
```

要点：

- pydantic-settings 会自动把 `.env` 里的键名映射到同名字段
- 三个字段都没有默认值，缺任何一个都会在启动时校验失败
- 这样代码里统一用 `settings.LLM_MODEL`，不需要到处读环境变量

### 2.3 `requirements.txt` 增加依赖

```txt
openai==3.14.1
```

锁版本的原因：

- 大版本升级可能改变参数或返回结构
- 不同环境安装到不同版本时，问题很难复现
- 本项目的 `get_client().chat.completions.create()` 依赖 3.x 的行为

### 2.4 配置层最常见的三个坑

1. **键名重复**：

   ```env
   LLM_BASE_URL=LLM_BASE_URL=https://...
   ```

   解析后地址会变成 `LLM_BASE_URL=https://...`，SDK 会报“缺少 http/https 协议”。

2. **地址写到完整接口**：

   ```env
   LLM_BASE_URL=https://opencode.ai/inference/go/openai/v1/chat/completions
   ```

   会重复拼接，导致 404。

3. **`.env` 没保存或服务没重启**：FastAPI 进程只在启动时读取配置，改完必须重启。

### 2.5 建议补充 `.env.example`

当前 `.env.example` 只有数据库和 JWT 占位符。建议补上：

```env
# OpenCode Go / Zen
LLM_API_KEY=REPLACE_WITH_YOUR_OPENCODE_API_KEY
LLM_MODEL=deepseek-v4.1-flash
LLM_BASE_URL=https://opencode.ai/inference/go/openai/v1
```

这样别人克隆项目后知道要配置哪些项，同时不会泄露真实 Key。

---

## 第三章 Schema 层

`app/schemas/ai.py`：

```python
from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
```

### 3.1 为什么用消息列表而不是单个字符串

因为大模型对话是多轮的：

```json
{
  "messages": [
    { "role": "user", "content": "实验室怎么预约？" },
    { "role": "assistant", "content": "先进入实验室列表……" },
    { "role": "user", "content": "那设备呢？" }
  ]
}
```

前端每次把完整历史传上来，后端才能理解“那设备呢”指代什么。

### 3.2 role 没有限制成枚举，是故意的

Schema 里 `role` 是普通字符串，真正的过滤放在 service：

```python
if message.role in ("user", "assistant") and message.content.strip():
    history.append(message.model_dump())
```

这样做的目的：

- 客户端即使传了 `system` 消息也会被丢弃，不能覆盖服务端固定的系统提示词
- 空内容不会被送给模型
- 过滤逻辑集中在一处

### 3.3 空消息的两种处理

- `messages` 为空列表 → “对话内容为空”
- 列表非空但全是空内容或非法角色 → “请输入您要对话的内容”

这两层判断可以避免把无意义请求发给模型，节省费用。

### 3.4 可以扩展的字段

如果以后前端需要区分多个对话，可以加：

```python
class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    conversation_id: str | None = None
```

后端用 `user-{id}:{conversation_id}` 作为 session，缓存效果更好。本节暂时不需要。

---

## 第四章 Service 层（重点）

文件：`app/services/ai_services.py`

### 4.1 `get_client()`

```python
def get_client() -> OpenAI:
    if not settings.LLM_API_KEY:
        raise BusinessException(message="未获取到大模型的API Key")
    return OpenAI(api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)
```

职责只有两个：

1. 检查 Key 是否配置
2. 按配置创建客户端

注意：

- 这里**没有发网络请求**，创建对象几乎不耗时
- 每次对话新建一个 client 是可以的，HTTP 连接由 SDK 内部管理
- Key 只在后端使用，绝不能返回给前端或写进日志

### 4.2 `SYSTEM_PROMPT` 的作用

系统提示词是给模型的“岗位说明书”。本项目的提示词做了四件事：

1. 定义身份：智能实验室预约系统助手
2. 描述流程：实验室必选、设备可选、提交后待审核、管理员审核
3. 描述规则：取消、过期、时间限制、实验室独占
4. 划清边界：查不到真实数据、不能代操作、不要编造

关键点：

- **提示词必须和代码规则同步**。第 19 节里已通过预约不能取消，提示词就不能写“已通过也能取消”。
- **提示词不是权限控制**。它只能降低模型乱说的概率，真正的权限仍由后端接口校验。

### 4.3 `chat()` 的完整流程

```python
def chat(data: ChatRequest, session_id: str):
    """大模型对话"""
    if not data.messages:
        raise BusinessException(message="对话内容为空")

    history = []
    for message in data.messages:
        if message.role in ("user", "assistant") and message.content.strip():
            history.append(message.model_dump())

    if not history:
        raise BusinessException(message="请输入您要对话的内容")

    client = get_client()
    try:
        res = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                ChatMessage(role="system", content=SYSTEM_PROMPT).model_dump(),
                *history,
            ],
            extra_headers={
                "x-opencode-session": session_id,
                "User-Agent": "lab-system-agent/1.0",
            },
        )

        message = res.choices[0].message
        if not message or not message.content or not message.content.strip():
            raise BusinessException(message="大模型没有返回内容")
        return message.content
    except BusinessException:
        raise
    except Exception:
        raise BusinessException(message="大模型调用失败,请稍后重试")
```

逐步解释：

| 步骤 | 代码 | 为什么 |
|---|---|---|
| 1 | 检查 `data.messages` | 空请求直接拒绝，不浪费 token |
| 2 | 过滤角色和空内容 | 防止客户端覆盖 system，过滤无意义消息 |
| 3 | 组装 `history` | 保留多轮上下文 |
| 4 | 创建 client | 读取 Key 和地址 |
| 5 | `messages` 第一条放 system | 固定助手行为 |
| 6 | `extra_headers` 带 session 和 UA | 满足 OpenCode Go 的路由要求 |
| 7 | 取 `choices[0].message.content` | 标准响应结构 |
| 8 | 判空 | 有些模型可能返回空内容 |
| 9 | 异常分类 | 业务提示原样抛出，其他统一提示 |

### 4.4 为什么 session 头放在每次请求上

`session_id` 应该跟随“对话/用户”，而 client 是按请求创建的。两种写法都可行：

- 放进 `get_client(session_id)` 的 `default_headers`
- 放进 `create(extra_headers=...)`（本项目采用）

放在请求上的好处：

- client 的职责更单纯，只关心鉴权和地址
- 一个 client 以后可以服务多个 session
- 代码读起来能直接看到“这次请求属于哪个会话”

### 4.5 session ID 为什么用用户 ID

```python
session_id=f"user-{current_user.id}"
```

- 对同一用户稳定，网关可以做路由和 prompt 缓存
- 不需要前端额外传参数
- 缺点：同一用户同时开多个对话会共用一个 session。后续可加 `conversation_id` 细化。

### 4.6 同步函数会不会阻塞 FastAPI

不会。

```python
@router.post("/chat")
def chat(data: ChatRequest, current_user: User = Depends(get_current_user)):
```

这是普通 `def` 路由，FastAPI 会自动把它放到线程池执行，阻塞的是工作线程而不是事件循环。

如果以后改成 `async def`，就要把 `OpenAI` 换成 `AsyncOpenAI`，否则同步 HTTP 调用会卡住事件循环。

### 4.7 为什么每次都要传完整历史

后端**没有保存对话记录**，是无状态的。前端每轮把之前的消息一起传上来，后端只负责转发。

好处：

- 不需要建会话表
- 服务重启不会丢历史

代价：

- 消息越长，token 越多、越慢、越贵
- 历史里可能包含敏感内容，需要前端自己管理

后续如果要长期保存，可以建 `ai_conversations / ai_messages` 表。

### 4.8 常见错误类型对照

| 现象 | 可能原因 | 排查 |
|---|---|---|
| 400 `MissingSessionID` | 没传 `x-opencode-session` | 检查 `extra_headers` |
| 401 Unauthorized | API Key 错误或过期 | 检查 `.env` 的 `LLM_API_KEY` |
| 402 / 余额不足 | 订阅额度或余额用完 | 查看 OpenCode 控制台 |
| 404 Not Found | `base_url` 写错（多写或少写路径） | 只写到 `/v1` |
| 422 | 请求体结构不对（`messages` 不是列表等） | 检查前端/curl 的 JSON |
| `UnsupportedProtocol` | `LLM_BASE_URL` 缺少 `http(s)://` | 检查 `.env` 是否重复键名 |
| 连接超时 | 网络、代理、DNS | 先 `curl` 测网关 |
| 返回内容为空 | 模型异常或触发过滤 | 记录响应并提示重试 |

### 4.9 安全和提示词注意事项

- API Key 只在 `.env`，不提交、不返回、不打印
- 客户端传的 `system` 消息会被丢弃，避免直接覆盖系统提示词
- 但用户仍可以在 `user` 内容里写“忽略上面的规则”，这属于提示词注入，**只能降低概率，不能彻底防住**
- 真正涉及数据或写操作的场景，不能只依赖提示词，必须用后端权限和接口校验
- 不要把未经处理的大模型输出直接当 HTML 渲染，前端应使用纯文本或做转义

### 4.10 建议补充的部分（当前未做）

```python
import logging

logger = logging.getLogger(__name__)
```

在 `except Exception` 里：

```python
    except Exception:
        logger.exception("大模型调用失败")
        raise BusinessException(message="大模型调用失败，请稍后重试")
```

否则像 400、超时、余额不足这些真实原因都会被统一提示掩盖，排查只能靠猜。

另外可以设置：

- `timeout=60`：避免请求长时间挂起
- `max_retries=1`：控制重试次数和费用
- `max_tokens=...`：限制回答长度

---

## 第五章 API 层

文件：`app/api/ai.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.common.response import Response
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai import ChatMessage, ChatRequest
from app.services import ai_services

router = APIRouter(prefix="/ai", tags=["AI相关的API"])


@router.post("/chat")
def chat(data: ChatRequest, current_user: User = Depends(get_current_user)):
    message = ai_services.chat(data, session_id=f"user-{current_user.id}")
    return Response.success(data=message)
```

### 5.1 为什么必须登录

`Depends(get_current_user)` 会：

1. 从 `Authorization: Bearer <token>` 取 token
2. 解析 JWT
3. 查数据库确认用户存在且状态正常

未登录或 token 失效会直接返回 401。这样可以：

- 防止匿名用户消耗模型额度
- 让 session ID 能绑定到具体用户

### 5.2 返回结构

```json
{
  "code": 200,
  "message": "请求成功",
  "data": "模型回答的文本"
}
```

`data` 直接是字符串，前端可以：

```js
const res = await chatApi({ messages })
// 直接显示 res.data
```

如果以后需要返回引用来源或 token 用量，可以把 `data` 改成对象：

```json
{
  "content": "……",
  "usage": { "prompt_tokens": 305, "completion_tokens": 178 }
}
```

### 5.3 注册路由

`app/api/__init__.py`：

```python
from app.api.ai import router as ai_router

api.include_router(ai_router)
```

`main.py` 里已有的 `app.include_router(api)` 会把 `/api/ai/chat` 注册进 FastAPI。

### 5.4 API 层不写业务逻辑

API 层只做：

- 接收和校验请求（Schema）
- 鉴权（依赖）
- 调用 service
- 包装统一响应

业务判断（空消息、角色过滤、session、模型调用）都放在 service，方便测试和复用。

---

## 第六章 一次请求的完整链路

```text
前端 / curl
  │  POST /api/ai/chat
  │  Authorization: Bearer <JWT>
  │  {"messages":[{"role":"user","content":"..."}]}
  ▼
uvicorn + FastAPI
  │  1. 路由匹配 /api/ai/chat
  │  2. get_current_user：校验 JWT、查用户
  │  3. ChatRequest：校验请求体结构
  ▼
ai_services.chat(data, session_id="user-7")
  │  4. 过滤消息、组装 system + history
  │  5. get_client()：读取 Key 和 base_url
  │  6. OpenAI SDK 发送 HTTPS 请求
  │     - Authorization: Bearer <LLM_API_KEY>
  │     - x-opencode-session: user-7
  │     - User-Agent: lab-system-agent/1.0
  ▼
OpenCode Go 网关
  │  7. 鉴权、路由、计费、转发
  ▼
DeepSeek V4.1 Flash
  │  8. 生成回答
  ▼
网关返回 choices[0].message.content
  ▼
ai_services.chat 返回文本
  ▼
Response.success(data=文本)
  ▼
前端收到 {"code":200,"message":"请求成功","data":"..."}
```

### 6.1 每一步失败分别会看到什么

| 失败位置 | HTTP | 返回 |
|---|---|---|
| 没有 token | 401 | `Not authenticated` |
| token 失效或用户被禁用 | 401 | `登录已失效，请重新登录` / `用户被禁用` |
| 请求体不是合法 JSON 或结构不对 | 422 | `请求参数校验错误` |
| 消息为空 | 200 | `code=500`，`对话内容为空` |
| 模型 Key 错误 | 200 | `code=500`，`大模型调用失败,请稍后重试` |
| 缺少 session 头 | 200 | 同上（真实原因被包装） |
| 模型返回空 | 200 | `code=500`，`大模型没有返回内容` |

注意：项目里的 `BusinessException` 统一返回 HTTP 200，真正的业务错误码放在 `code` 字段里；前端 `request.js` 会根据 `code !== 200` 弹出提示。

---

## 第七章 联调与验证

### 7.1 启动前检查

1. `backend/.env` 三个 LLM 变量正确
2. `openai==3.14.1` 已安装
3. 服务已重启（uvicorn 没有 `--reload` 时必须手动重启）
4. `/openapi.json` 里能看到 `/api/ai/chat`

### 7.2 获取 token

```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"你的账号","password":"你的密码"}'
```

取返回里的 `data.token`。

### 7.3 单轮对话

```bash
curl -s -X POST http://127.0.0.1:8000/api/ai/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"实验室怎么预约？"}]}'
```

### 7.4 多轮对话

```bash
curl -s -X POST http://127.0.0.1:8000/api/ai/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role":"user","content":"实验室怎么预约？"},
      {"role":"assistant","content":"先进入实验室列表选择实验室……"},
      {"role":"user","content":"那设备呢？"}
    ]
  }'
```

### 7.5 实际验证结果

本节用学生账号测试了四个问题，回答都符合实现规则：

| 问题 | 模型回答摘要 | 是否正确 |
|---|---|---|
| 明天 14:00-15:00 预约，提前多久？能否只预约设备？ | 至少提前 1 小时、最多 7 天、整点/半点、至少 30 分钟；不能只预约设备，设备必须随实验室一起选，实验室时段独占 | ✅ |
| 已通过的预约还能取消吗？ | 不能，只有待审核可以取消 | ✅ |
| 一直没审核，结束时间过了会怎样？ | 自动变成「已过期」，不需要管理员再处理 | ✅ |
| 帮我查数学实验室明天是否有空并直接预约 | 无法查询真实数据、不能代操作，引导去「实验室列表」查看并提交 | ✅ |

### 7.6 排错顺序

1. 先看 HTTP 状态：401 查 token，422 查 JSON
2. 再看 `code` 和 `message`：业务错误还是调用失败
3. 如果统一提示“调用失败”，**绕过 service 直接用同样的 Key 调一次**，把真实异常打印出来
4. 检查 `.env` 是否有重复键名、地址是否多写路径
5. 检查 `x-opencode-session` 是否发送
6. 检查服务是否真的重启

---

## 第八章 本节踩过的坑

这些都是开发过程中真实出现过的，记录下来避免重复：

### 8.1 模块名 `ai_service` 与 `ai_services`

`api/ai.py` 里写成 `from app.services import ai_service`，但文件是 `ai_services.py`。

现象：`ImportError`，整个后端无法启动，因为 `api/__init__.py` 会导入这个 router。

### 8.2 `message` 与 `messages`

OpenAI SDK 的参数是 `messages`。写成 `message=` 会直接 `TypeError`。

### 8.3 `ChatMessage(...),model_dump()` 的逗号

写成逗号会得到一个元组，而不是调用方法。必须是 `ChatMessage(...).model_dump()`。

### 8.4 没有接收返回值

`client.chat.completions.create(...)` 前面少了 `res =`，后面却用 `res.choices`，会 `NameError`。

### 8.5 `content=res.choices[0].message,content`

逗号让它变成元组赋值，而且 `content` 在右边还没定义。正确写法是：

```python
content = res.choices[0].message.content
```

### 8.6 缩进错误

`IndentationError` 是 Python 最先报出来的问题，先修语法，再谈逻辑。

### 8.7 `except Exception` 吞掉业务异常

“模型没有返回内容”本身是 `BusinessException`，如果先被 `except Exception` 接住，就会变成“调用失败”。

解决：

```python
    except BusinessException:
        raise
    except Exception:
        ...
```

### 8.8 `x-opencode-session`

OpenCode Go 要求这个头。没有它时返回 400 `MissingSessionID`，但 service 会把它包装成“调用失败”，很难看出来。

### 8.9 `.env` 键名重复

```env
LLM_BASE_URL=LLM_BASE_URL=https://...
```

看起来只是多写了几个字符，实际会让地址缺少协议，SDK 抛 `UnsupportedProtocol`。

### 8.10 `py_compile` 查不出运行时问题

`py_compile` 只校验语法，不校验导入和名字是否存在。更有效的检查：

```bash
python -c "import app.api.ai"
```

### 8.11 服务没有重启

uvicorn 没加 `--reload` 时，改代码不会生效。表现为：

- 新路由 404
- 新提示词没变化
- 改了 `.env` 但地址没变

### 8.12 1017 不是模型 ID

`deepseek-v4.1-flash-1017` 是 checkpoint 名称，OpenCode Go/Zen 的模型 ID 是 `deepseek-v4.1-flash`。

---

## 第九章 设计取舍与后续升级

### 9.1 为什么不做对话持久化

本节的目标是“跑通链路”，无状态实现最简单：

- 不需要新表
- 不需要处理会话生命周期
- 前端传完整历史即可

代价是每次都要发送全部历史，token 会随轮次增长。

### 9.2 后续可以做的方向

| 方向 | 说明 |
|---|---|
| 会话持久化 | 建 `ai_conversations`、`ai_messages`，只传 `conversation_id` |
| 流式输出 | 使用 SSE 或流式响应，边生成边显示 |
| Function Calling | 让模型调用“查询实验室/设备/预约”的工具函数，真正查数据 |
| RAG | 把实验室介绍、设备说明做成向量检索，回答更准确 |
| 权限过滤 | 工具调用必须带当前用户 ID，只返回该用户有权查看的数据 |
| 操作确认 | 涉及预约/取消时，先生成“待确认操作”，用户确认后再执行 |
| 限流与计费 | 按用户限制每日调用次数，记录 token 成本 |
| 提示词版本管理 | 把提示词抽到独立文件/配置，方便评审和回滚 |
| 日志与审计 | 记录请求、耗时、错误原因，便于排查 |

### 9.3 一个重要的设计原则

**提示词负责“说话方式”，代码负责“能不能做”。**

- 想限制模型乱说：改提示词
- 想限制用户越权：改接口和权限
- 想保证数据正确：让模型调用受权限约束的工具，而不是让它自由发挥

---

## 第十章 验收清单

| 用例 | 预期 |
|---|---|
| 未登录调用 `/api/ai/chat` | 401 |
| `messages` 为空 | `对话内容为空` |
| 只有空内容消息 | `请输入您要对话的内容` |
| 正常单轮提问 | 返回回答文本 |
| 多轮追问 | 能结合上文回答 |
| 问预约规则 | 回答与系统规则一致 |
| 问已通过能否取消 | 回答“不能” |
| 问过期记录 | 回答自动变“已过期” |
| 要求查真实数据/代预约 | 拒绝并引导到页面查看 |
| 客户端传 `system` 消息 | 被过滤，不覆盖系统提示词 |
| 模型 Key 错误 | 统一提示“调用失败”（建议加日志） |
| 缺少 session 头 | 400 `MissingSessionID`（需检查请求头） |

---

## 附：关键代码索引

| 位置 | 内容 |
|---|---|
| `app/config.py` | LLM 三个配置字段 |
| `app/schemas/ai.py` | `ChatMessage`、`ChatRequest` |
| `app/services/ai_services.py` | `SYSTEM_PROMPT`、`get_client`、`chat` |
| `app/api/ai.py` | `POST /api/ai/chat`、登录依赖、session ID |
| `app/api/__init__.py` | 注册 AI router |
| `backend/.env` | Key、模型、地址（不提交） |
| `backend/requirements.txt` | `openai==3.14.1` |
