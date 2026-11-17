# 开发实验室 AI 助手对话（前端）与流式输出

> 对应课程：第 21 节
> 对应项目：`agent-lab/lab-system-agent`
> 前置课程：第 20 节 实验室 AI 助手对话（后端）
> 本节目标：完成 AI 聊天页面，并把“一次性返回”升级为“边生成边显示”的 SSE 流式对话
> 整理日期：2026-11-17
> 阅读方式：先理解流式与 SSE，再看后端生成器，最后看前端 fetch 解析与页面状态。

---

## 第零章 本节完成了什么

第 20 节已经能调用大模型，但体验是：

```text
用户发送问题
    ↓
等待模型把整段回答生成完
    ↓
前端一次性显示全部文字
```

本节改成：

```text
用户发送问题
    ↓
后端建立 SSE 流
    ↓
模型每生成一小段，后端就转发一小段
    ↓
前端逐段追加到助手气泡
    ↓
用户看到文字逐步出现，并且可以中途停止
```

本节涉及两条链路：

1. **后端流式接口**：`POST /api/ai/chat/stream`
2. **前端聊天页**：`frontend/src/views/AIChat.vue`

### 0.1 涉及文件

| 文件 | 作用 |
|---|---|
| `backend/app/services/ai_services.py` | `build_messages`、`chat`、`stream_chat`、异步客户端 |
| `backend/app/api/ai.py` | 非流式 `/chat` 与流式 `/chat/stream` 路由 |
| `frontend/src/api/ai.js` | 非流式 `chatApi` 与流式 `chatStreamApi` |
| `frontend/src/views/AIChat.vue` | 聊天页面、逐字渲染、停止生成 |
| `frontend/src/layouts/Layout.vue` | “AI智能助手”菜单 |
| `frontend/src/router/index.js` | `/manager/ai-chat` 路由 |
| `docs/notes/future-upgrades-langgraph-and-sms.md` | 后续上下文管理、流式增强等规划 |

### 0.2 最终效果

- 左侧助手、右侧用户的气泡布局
- Enter 发送、Shift+Enter 换行、中文输入法不误发
- 等待时显示“正在思考…”
- 收到增量后逐段显示
- 可以“停止生成”
- 可以清空对话
- 出错时保留已生成内容并提示

---

## 第一章 为什么要流式

### 1.1 一次性返回的问题

非流式接口：

```python
res = client.chat.completions.create(..., stream=False)
return res.choices[0].message.content
```

后端必须等模型完整生成，才能返回。用户在这段时间内只看到 loading。

实测一次普通提问：

```text
首块（可见内容）: 约 5~6 秒
总耗时: 约 5~7 秒
```

如果不流式，用户要等 6 秒才看到第一个字；流式之后，第一个字到了就能显示。

### 1.2 三种方案对比

| 方案 | 方向 | 复杂度 | 适用 |
|---|---|---|---|
| 轮询 | 前端定时问“好了吗” | 低 | 不适合逐字展示 |
| WebSocket | 双向 | 高 | 双向实时通信 |
| SSE | 服务端 → 客户端单向 | 中 | 大模型流式输出 |

我们只需要“服务端持续推文字”，SSE 足够，而且仍然是普通 HTTP，部署简单。

### 1.3 SSE 是什么

SSE = Server-Sent Events，响应类型是：

```http
Content-Type: text/event-stream
```

服务端持续写文本，每个事件用空行分隔：

```text
event: delta
data: {"content": "实验"}

event: delta
data: {"content": "室预"}

event: done
data: {}
```

它不是新协议，也不是新服务器，仍然是 HTTP/1.1 连接，只是响应体持续输出。

---

## 第二章 整体链路

```text
浏览器 AIChat.vue
    │ fetch POST /api/ai/chat/stream
    │ Authorization: Bearer <JWT>
    │ {"messages":[...]}
    ▼
FastAPI /api/ai/chat/stream
    │ build_messages(data)  ← 先校验，失败返回普通业务错误
    │ StreamingResponse(stream_chat(messages, session_id))
    ▼
ai_services.stream_chat
    │ AsyncOpenAI.create(..., stream=True)
    ▼
OpenCode Go 网关
    │ 逐块返回 SSE
    ▼
stream_chat 读取 chunk
    │ 取 delta.content
    │ 包装成自己的 SSE 事件
    ▼
FastAPI 逐块写出
    ▼
前端 fetch + ReadableStream
    │ 按 \n\n 拆事件
    │ 把 delta.content 追加到助手气泡
    ▼
用户看到文字逐步出现
```

---

## 第三章 后端改造回顾

### 3.1 统一消息组装：`build_messages`

```python
def build_messages(data: ChatRequest) -> list[dict]:
    if not data.messages:
        raise BusinessException(message="对话内容为空")

    history = []
    for message in data.messages:
        if message.role in ("user", "assistant") and message.content.strip():
            history.append(message.model_dump())

    if not history:
        raise BusinessException(message="请输入您要对话的内容")

    return [
        ChatMessage(role="system", content=SYSTEM_PROMPT).model_dump(),
        *history,
    ]
```

职责：

- 校验空消息
- 只保留 `user` / `assistant`
- 过滤空内容
- 加上固定的 system 提示词
- 返回 OpenAI SDK 能直接使用的 `list[dict]`

非流式和流式共用这一份逻辑，避免行为不一致。

### 3.2 同步客户端与异步客户端

```python
def get_client() -> OpenAI:
    ...

def get_async_client() -> AsyncOpenAI:
    ...
```

- `get_client()`：非流式接口使用
- `get_async_client()`：流式接口使用
- 流式连接时间长，异步客户端不会阻塞事件循环
- 流式客户端设置 `max_retries=0`，避免已经输出部分内容后重试导致重复

### 3.3 统一函数签名（方案 B）

```python
def chat(messages: list[dict], session_id: str):
    ...

async def stream_chat(messages: list[dict], session_id: str):
    ...
```

两个函数都只接收“已经组装好的消息”，不再接收 `ChatRequest`。

API 层负责：

```python
messages = ai_services.build_messages(data)
```

这样分层清晰：

```text
API 层：HTTP 请求、鉴权、消息组装
Service 层：只负责调用模型
```

### 3.4 `stream_chat` 逐行理解

```python
async def stream_chat(messages: list[dict], session_id: str):
    client = get_async_client()
    try:
        stream = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            stream=True,
            extra_headers={
                "x-opencode-session": session_id,
                "User-Agent": "lab-system-agent/1.0",
            },
        )
```

- `async def` + 内部 `yield` → 异步生成器
- 调用这个函数时不会立即执行，只返回生成器对象
- `stream=True`：要求服务端逐块返回
- `x-opencode-session`：OpenCode Go 路由和缓存需要
- 缺这个头会返回 400 `MissingSessionID`

```python
        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                content = getattr(delta, "content", None)
                if content:
                    payload = json.dumps(
                        {"content": content},
                        ensure_ascii=False,
                    )
                    yield f"event: delta\ndata: {payload}\n\n"

            yield "event: done\ndata: {}\n\n"

        finally:
            await stream.close()
```

- `chunk.choices` 可能为空（如 usage 块），跳过
- `delta.content` 是最终回答的增量
- `ensure_ascii=False` 保留中文，不转成 `\uXXXX`
- `\n\n` 是 SSE 事件分隔符
- 循环结束后发送 `done`
- `finally` 关闭上游流，客户端断开时能及时停止

```python
    except BusinessException as exc:
        payload = json.dumps({"message": exc.message}, ensure_ascii=False)
        yield f"event: error\ndata: {payload}\n\n"
    except Exception:
        payload = json.dumps(
            {"message": "大模型调用失败，请稍后重试"},
            ensure_ascii=False,
        )
        yield f"event: error\ndata: {payload}\n\n"
    finally:
        await client.close()
```

流式响应一旦开始，HTTP 状态码已经发出，不能再返回 500，只能用 `event: error` 通知前端。

### 3.5 `reasoning_content` 与 token 预算

DeepSeek 的流里有两类字段：

| 字段 | 内容 | 是否展示 |
|---|---|---|
| `delta.reasoning_content` | 模型内部思考 | 不展示 |
| `delta.content` | 最终回答 | 展示 |

注意：**思考内容也计入 `completion_tokens`**。

开发时踩过一个坑：

```python
max_tokens=60
```

结果 60 个 token 全被思考过程用完，最终回答长度为 0，前端一个 delta 都收不到。

处理方式：

- 聊天场景不设置 `max_tokens`，或设置足够大的值（如 1024 / 2048）
- 只取 `delta.content`
- 如果想显示“正在思考”，可以单独发一个事件，但不要把思考内容直接展示

### 3.6 API 路由

```python
@router.post("/chat/stream")
async def chat_stream(
    data: ChatRequest, current_user: User = Depends(get_current_user)
):
    messages = ai_services.build_messages(data)

    return StreamingResponse(
        ai_services.stream_chat(
            messages,
            session_id=f"user-{current_user.id}",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

关键点：

1. **先 `build_messages`，再返回 `StreamingResponse`**
   - 空消息时仍然返回普通 JSON 业务错误
   - 不会出现“响应头已发出，才发现请求非法”
2. `media_type` 设置 `Content-Type: text/event-stream`
3. `Cache-Control: no-cache` 禁止缓存
4. `X-Accel-Buffering: no` 告诉 Nginx 不要缓冲
5. 路由是 `async def`
6. 鉴权依赖与普通对话一致

### 3.7 SSE 事件协议

本项目使用三种事件：

| 事件 | 数据 | 含义 |
|---|---|---|
| `delta` | `{"content": "..."}` | 一段新增文字 |
| `done` | `{}` | 回答结束 |
| `error` | `{"message": "..."}` | 流中发生错误 |

示例：

```text
event: delta
data: {"content": "实验室"}

event: delta
data: {"content": "预约系统"}

event: done
data: {}
```

---

## 第四章 前端 API 层

### 4.1 为什么不能用 axios

浏览器里的 axios 默认使用 XHR，XHR 不会把响应体分块交给 JS：

```text
axios 请求 → 等整个响应接收完 → then 回调
```

即使后端在逐块发送，axios 也会等流结束才返回。

另外项目的 `utils/request.js` 拦截器按 JSON 处理：

```js
const data = res.data
if (data.code !== 200) { ... }
```

SSE 是文本流，不是 JSON，会被误判。

所以流式请求必须用原生 `fetch` + `ReadableStream`。

### 4.2 为什么不用 EventSource

`EventSource` 有两个限制：

1. 只能发 GET
2. 不能自定义 `Authorization` 头

我们的接口需要 JWT，而且是 POST，所以用 fetch 读取流，再手动解析 SSE。

### 4.3 `chatStreamApi`

```js
export async function chatStreamApi(data, { signal, onEvent } = {}) {
  const res = await fetch(`${BASE_URL}/api/ai/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`
    },
    body: JSON.stringify(data),
    signal
  })

  if (!res.ok) {
    let message = `请求失败(${res.status})`
    try {
      const err = await res.json()
      message = err.message || message
    } catch {}
    throw new Error(message)
  }

  if (!res.body) {
    throw new Error('当前浏览器不支持流式响应')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    let separatorIndex
    while ((separatorIndex = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)

      let eventName = 'message'
      const dataLines = []

      for (const line of rawEvent.split('\n')) {
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim())
        }
      }

      if (!dataLines.length) continue

      const text = dataLines.join('\n')
      let payload = text
      try {
        payload = JSON.parse(text)
      } catch {}

      onEvent?.({ event: eventName, data: payload })
    }
  }
}
```

逐步解释：

1. `fetch` 用 POST，带 JSON 和 JWT
2. `res.body.getReader()` 拿到流读取器
3. `TextDecoder` 负责把二进制块转成字符串
4. `{ stream: true }` 允许一个 UTF-8 字符跨块
5. `buffer` 保存未处理完的文本
6. SSE 事件用 `\n\n` 分隔
7. 每个事件解析 `event:` 和 `data:` 行
8. `data:` 可能是 JSON，也可能是纯文本
9. 通过 `onEvent` 把事件交给页面

### 4.4 为什么要 `AbortSignal`

停止生成时：

```js
const controller = new AbortController()
fetch(..., { signal: controller.signal })
```

调用 `controller.abort()`：

- 前端停止读取
- 请求被取消
- 后端生成器被关闭
- 上游模型连接也会关闭，避免继续计费

---

## 第五章 前端页面实现

### 5.1 页面状态

```js
const messages = ref([{ role: 'assistant', content: GREETING }])
const input = ref('')
const loading = ref(false)
const controller = ref(null)
```

| 状态 | 作用 |
|---|---|
| `messages` | 对话列表 |
| `input` | 输入框 |
| `loading` | 是否正在生成 |
| `controller` | 用于中断流 |

### 5.2 发送流程

关键顺序：

```text
1. 校验输入
2. 推入用户消息
3. 用"当前消息"生成 payload
4. 推入空的助手消息
5. 调用 chatStreamApi
6. 收到 delta 就追加内容
7. done / error / abort 处理
8. finally 清理 loading
```

为什么 payload 要在插入空助手消息之前生成？

因为插入的助手消息内容为空：

```json
{"role": "assistant", "content": ""}
```

如果先插入再生成 payload，会把这个空消息也发给后端：

- 后端会过滤空内容，通常没事
- 但语义上不干净
- 某些模型对连续 assistant 消息更敏感

正确写法：

```js
messages.value.push({ role: 'user', content: text })

const payload = messages.value.map(({ role, content }) => ({ role, content }))

const reply = reactive({ role: 'assistant', content: '', pending: true })
messages.value.push(reply)
```

### 5.3 收到 delta

```js
if (event === 'delta') {
  reply.pending = false
  reply.content += data.content || ''
  scheduleScroll()
}
```

- `pending` 表示还没收到第一段内容
- 收到第一段后，“正在思考…”切换成实际文字
- 后续每段继续追加
- 滚动用 `requestAnimationFrame` 合并，避免频繁布局

### 5.4 done / error / abort

```js
} else if (event === 'done') {
  reply.pending = false
  if (!reply.content) {
    reply.content = '（模型没有返回内容）'
  }
} else if (event === 'error') {
  reply.pending = false
  const message = data?.message || 'AI 回答失败'
  ElMessage.error(message)
  if (!reply.content) reply.content = message
}
```

abort：

```js
if (error.name === 'AbortError') {
  if (!reply.content) reply.content = '（已停止生成）'
}
```

注意：

- `AbortError` 是用户主动停止，不应弹错误提示
- 已经有部分内容时，保留已生成的部分
- 其它错误才提示失败

### 5.5 思考状态

模板中：

```vue
<span v-if="item.pending && !item.content" class="thinking">
  <el-icon class="is-loading"><Loading /></el-icon>
  <span>正在思考…</span>
</span>
<template v-else>{{ item.content }}</template>
```

因为 DeepSeek 的思考过程会持续几秒，第一个 `delta.content` 到达前一直显示“正在思考…”。

### 5.6 停止生成

```js
const handleStop = () => {
  controller.value?.abort()
}
```

按钮：

```vue
<el-button v-if="loading" type="danger" plain @click="handleStop">
  停止生成
</el-button>
<el-button v-else type="primary" :disabled="!input.trim()" @click="handleSend">
  发送
</el-button>
```

### 5.7 清空对话

清空时要先中断正在进行的流：

```js
controller.value?.abort()
messages.value = [{ role: 'assistant', content: GREETING }]
input.value = ''
loading.value = false
```

否则清空后，旧流的回调还会往已经不在列表里的对象写内容。

### 5.8 输入框与中文输入法

```js
const handleKeydown = (event) => {
  if (event.isComposing) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}
```

- Enter 发送
- Shift+Enter 换行
- `isComposing` 避免中文输入法选词时误发送

---

## 第六章 完整数据流

```text
用户输入问题，按 Enter
    ↓
messages 推入 user 消息
    ↓
payload = 当前完整历史 + 新问题
    ↓
插入空的 assistant 消息（pending）
    ↓
chatStreamApi -> fetch POST /api/ai/chat/stream
    ↓
后端 build_messages 校验并组装 system + 历史
    ↓
stream_chat 调 AsyncOpenAI，stream=True
    ↓
模型逐块返回
    ↓
后端取 delta.content，包装 SSE
    ↓
前端 reader.read() 收到文本块
    ↓
按 \n\n 拆事件，JSON 解析
    ↓
delta.content 追加到 assistant 气泡
    ↓
done：结束；error：提示；abort：停止
```

---

## 第七章 测试与验证

### 7.1 后端 `curl -N`

```bash
curl -N -X POST http://127.0.0.1:8000/api/ai/chat/stream \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"请用一句话介绍实验室预约系统"}]}'
```

实际结果：

```text
HTTP 200
content-type: text/event-stream; charset=utf-8

event: delta
data: {"content": "在线"}

event: delta
data: {"content": "预约实验室，管理员审核，"}

event: delta
data: {"content": "状态全程可查。"}

event: done
data: {}
```

首块约 5.07 秒，总耗时约 5.10 秒，共 3 个 delta。

### 7.2 后端接口验证

| 用例 | 结果 |
|---|---|
| 非流式 `/api/ai/chat` | 200，正常返回 |
| 流式 `/api/ai/chat/stream` | 200，`text/event-stream` |
| 空 messages | `application/json`，`对话内容为空` |
| 无 token | 401 |
| 模拟模型异常 | `event: error` |

### 7.3 前端验证清单

| 用例 | 预期 |
|---|---|
| 提问规则问题 | 先“正在思考…”，再逐段出现 |
| 点击停止生成 | 中断，保留已生成内容 |
| 清空对话 | 中断流并恢复到开场白 |
| 空输入 | 发送按钮禁用 |
| 中文输入法回车 | 不误发送 |
| 后端关闭 | 前端提示请求失败 |
| 刷新页面 | 对话丢失（当前无持久化） |

---

## 第八章 踩坑复盘

### 8.1 axios 不能流式

最初把流式接口也写成 axios：

```js
export function chatApiStream(data) {
  return request({ url: '/api/ai/chat/stream', method: 'post', data })
}
```

现象：接口能通，但前端始终等完整响应，没有逐字效果。

原因：浏览器 axios 基于 XHR，会缓冲整个响应；拦截器还按 JSON 解析 SSE 文本。

解决：用 `fetch` + `ReadableStream`。

### 8.2 `done` 事件写成空 f-string

```python
yield f"event:delta\ndata:{}\n\n"
```

报错：

```
SyntaxError: f-string: empty expression not allowed
```

`{}` 会被当成插值表达式。这里应该是普通字符串：

```python
yield "event: done\ndata: {}\n\n"
```

### 8.3 `ensure_ascii` 拼写成 `ensuer_ascii`

错误分支里：

```python
json.dumps({...}, ensuer_ascii=False)
```

运行时报：

```
TypeError: JSONEncoder.__init__() got an unexpected keyword argument 'ensuer_ascii'
```

结果模型异常时 `event: error` 发不出去，前端直接断流。

### 8.4 User-Agent 拼写错误

```python
"User-Agent": "lab-system=agent/1.0"
```

`=` 写成了 `-`，虽然不一定导致失败，但请求头不规范。

### 8.5 模块级测试代码

一度把测试代码放在 `ai_services.py` 底部：

```python
asyncio.run(main())
```

后果：

- 每次导入模块都会真实调用一次大模型
- 后端启动变慢、产生费用
- 网络异常时后端直接启动失败
- 那个莫名其妙的 `ok` 输出就是它打印的

测试代码应放在独立脚本，不要放在会被业务导入的模块里。

### 8.6 `max_tokens` 被思考过程吃光

```python
max_tokens=60
```

结果：

```text
可见内容 0 字
思考内容 286 字
```

解决：不设置 `max_tokens`，或设置足够大的值。

### 8.7 校验必须在流开始之前

错误做法：

```python
return StreamingResponse(stream_chat(data, ...))
```

在生成器里才 `build_messages(data)`。空消息时响应头已经发出，无法返回普通业务错误。

正确做法：

```python
messages = build_messages(data)
return StreamingResponse(stream_chat(messages, ...))
```

### 8.8 服务未重启

uvicorn 没有 `--reload` 时，改代码不会生效。表现为：

- 新路由 404
- 流式行为没变化
- 提示词没更新

### 8.9 停止生成不能当错误

`AbortError` 是用户主动停止，不应弹“调用失败”。

### 8.10 清空对话要先中断流

否则旧流回调会继续写已移除的消息对象。

---

## 第九章 设计取舍与后续

### 9.1 为什么保留非流式接口

- 浏览器或网络不支持流式时可以降级
- 调试方便
- 后续脚本调用更简单

### 9.2 为什么后端仍然无状态

当前每次发送完整历史，后端不保存会话。优点是实现简单；缺点是：

- 请求体越来越大
- 刷新丢失
- 成本随轮次增长

后续做上下文管理时，`build_messages` 会成为唯一改动入口。

### 9.3 为什么先纯文本

模型输出属于不可信内容，直接 `v-html` 有 XSS 风险。当前用纯文本 + `white-space: pre-wrap`。

如果要做 Markdown：

- `markdown-it` 解析
- `DOMPurify` 清洗
- 代码高亮
- 链接安全属性

### 9.4 停止生成的边界

- 停止后保留已生成内容
- 后端生成器被关闭，停止计费
- 不清空会话历史

### 9.5 后续可以做的事

- 上下文持久化、窗口、摘要
- Markdown 与代码高亮
- 历史会话列表、多会话
- 401 自动跳转登录
- 流式失败自动降级到非流式接口
- 限流与费用统计

这些已经记录在 `docs/notes/future-upgrades-langgraph-and-sms.md`。

---

## 第十章 验收清单

| 用例 | 预期 |
|---|---|
| 未登录访问聊天页 | 跳转登录 |
| 正常提问 | 逐段显示回答 |
| 首字前显示 | “正在思考…” |
| 停止生成 | 中断并保留内容 |
| 清空对话 | 中断并恢复开场白 |
| 空输入 | 不能发送 |
| 中文输入法回车 | 不误发送 |
| 后端返回 error 事件 | 前端提示错误 |
| 网络断开 | 前端提示失败 |
| 后端空 messages | 普通 JSON 错误，不是 SSE |
| 刷新页面 | 历史丢失（预期） |

---

## 附：关键代码索引

| 位置 | 内容 |
|---|---|
| `ai_services.py` | `build_messages`、`chat`、`stream_chat` |
| `api/ai.py` | `/chat`、`/chat/stream` |
| `frontend/src/api/ai.js` | `chatApi`、`chatStreamApi` |
| `frontend/src/views/AIChat.vue` | 消息状态、逐字渲染、停止生成 |
| `frontend/src/layouts/Layout.vue` | AI 助手菜单 |
| `frontend/src/router/index.js` | `/manager/ai-chat` 路由 |
