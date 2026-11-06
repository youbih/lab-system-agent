# 统一响应格式 + 全局异常处理

> 对应课程:第 07 节
> 对应项目:`agent-lab/lab-system-agent/backend`
> 涉及文件:`app/common/response.py`、`app/common/exceptions.py`、`app/main.py`
> 阅读建议：按小节阅读，配合项目源码与示例理解执行过程。

---

## 阅读说明：代码版本与讲解方式

这份笔记根据原课程记录与当前项目源码整理，不代表拥有每节课的完整历史快照。保留原记录中的课程重点和排错经历；历史代码、当前实现、建议改进会分别说明。未在对话或原记录中确认的测试，不写成新增的实测结论。

代码按“完整片段 → 按执行顺序拆解 → 输入/返回值例子 → 页面或接口效果”阅读。仅有一两行的导入、配置或重复片段使用紧接代码的说明，避免反复展开相同逻辑。

**本节版本对应：** Response 和四类异常处理器仍是当前源码的基础；第 13 节新增的 PageResponse 属于后续分页课程，不当作本节已经实现。根接口和 Swagger 表单登录有各自返回格式，并非所有接口都套用业务响应模型。

---

## 第零章 先搞清楚：这一课在解决什么痛点

在学这节课之前,我们的接口是这样返回错误的:

```python
# 每个接口自己手写错误返回
if not user:
    return {"code": 400, "message": "账号或密码错误"}
if user.status != 1:
    return {"code": 403, "message": "账号已被禁用"}
```

**这段代码怎样执行：** 这是改造前的历史片段：函数分别检查用户是否存在、状态是否正常，然后在各个分支手写字典。它描述了业务失败，却没有统一 HTTP 状态码、默认 data 或框架错误格式；本节就是把这件事集中管理。


问题:

1. **重复** —— 每个接口都要手写一堆 `{"code":..., "message":...}` 字典
2. **不一致** —— 你手写 400,框架自己抛的错误(404、422)却是另一个格式 `{"detail": "Not Found"}`,前端要处理两套格式
3. **传错难** —— 错误发生在深层函数里时,要一层层往外 return,代码又臭又长

这一课的两个武器就是解决这三个问题的:

```
武器 1: Response 类      → 解决"重复"(返回格式统一封装)
武器 2: 异常 + 处理器    → 解决"传错难"和"不一致"(错误统一收口)
```

---

## 第一章 统一响应格式：Response 类

### 1.1 目标

让所有接口的返回都长一个样:

```json
{"code": 200, "message": "操作成功", "data": {"id": 3}}
```

三个字段的约定:

| 字段 | 含义 | 例子 |
|---|---|---|
| `code` | 业务状态码(不是 HTTP 状态码!) | 200 成功 / 400 参数错 / 403 没权限 / 500 服务器错 |
| `message` | 给人看的提示信息 | "账号或密码错误" |
| `data` | 真正的数据内容 | 用户信息、token 等,失败时为 null |

### 1.2 代码(`app/common/response.py`)

```python
from typing import Any
from pydantic import BaseModel


class Response(BaseModel):
    """统一封装的返回格式"""
    code: int
    message: str
    data: Any = None          # Any = 任意类型(注意是大写,来自 typing)

    @classmethod
    def success(cls, message: str = "请求成功", data: Any = None):
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, code: int = 500, message: str = "操作失败"):
        return cls(code=code, message=message, data=None)
```

**按执行顺序拆解：**

#### 第一步：声明统一字段

```python
class Response(BaseModel):
    code: int
    message: str
    data: Any = None
```

`Response` 是项目自定义的 Pydantic 模型，不是浏览器 Response，也不是 FastAPI 的响应基类。code、message 必须提供；data 允许不同类型，没提供时为 None，JSON 中显示为 null。

#### 第二步：通过类方法构造成功对象

```python
@classmethod
def success(cls, message: str = "请求成功", data: Any = None):
    return cls(code=200, message=message, data=data)
```

`@classmethod` 让我们可以直接调用 `Response.success(...)`，此时 cls 指向 Response 类。函数将固定业务码 200 与传入消息、数据组装成一个模型对象；这里没有发送网络请求。

#### 第三步：通过类方法构造失败对象

```python
@classmethod
def error(cls, code: int = 500, message: str = "操作失败"):
    return cls(code=code, message=message, data=None)
```

调用者可指定 code/message，data 固定为空。例如 `Response.error(code=400, message="账号或密码错误")` 构造失败模型；如果没有传 code，就使用默认业务码 500。

#### 第四步：交给框架或处理器序列化

```python
Response.success(data={"id": 3})
```

这会得到 code=200、默认消息和 data={id:3} 的模型。接口直接返回模型可由 FastAPI 编码；JSONResponse 的 content 则使用 `.model_dump()` 转成字典。类方法本身不会决定 HTTP 状态码。

**把结果连起来：** 业务代码不再重复手写三个字段，前端可以按同一结构读取结果。


### 1.3 逐行理解

**`class Response(BaseModel)`** —— 继承 Pydantic 的 BaseModel,自动获得字段校验能力:`code` 必须是 int,`data` 可以是任意类型(`Any`)。

**`@classmethod` + `cls`** —— 类方法,属于"类本身"而不是实例:

```python
# cls 就是 Response 这个类本身
cls(code=200, message=message, data=data)
# 等价于
Response(code=200, message=message, data=data)
```

**这段代码怎样执行：** 调用类方法时，`cls` 指向调用它的类，所以这里 `cls(...)` 相当于构造 Response 实例。这个片段用于解释语法；不应在模块顶层直接复制没有定义 cls、message、data 的表达式。


可以把 `success()` / `error()` 理解成**两条快速生产线**:你说"要个成功响应",它帮你把 `code=200` 这种固定项自动填好。

### 1.4 使用对比

```python
# 以前:手写字典,字段名写错没人管
return {"code": 200, "message": "ok", "data": {...}}

# 现在：通过模型统一字段；字段校验与额外字段策略由模型配置决定
return Response.success(message="登录成功", data={...})
return Response.error(code=400, message="账号或密码错误")
```

**这段代码怎样执行：** 这是不同写法的对照，不是连续运行的三条 return。接口选择其中一条返回结果；success 帮你填业务码，error 帮你填空 data。Pydantic 会检查声明字段，但默认可能忽略多余字段，因此不能笼统认为任何字段拼错都会立刻报错。


---

## 第二章 全局异常处理

### 2.1 核心思想：错误"抛"出来,框架统一接

```
旧模式(return):                新模式(raise):
函数发现错误 → 手写错误返回       函数发现错误 → raise 抛出去就不管了
每个函数各管各的           →      FastAPI 接住 → 交给对应处理器
                                  → 统一转成 Response 格式
```

这就像公司里的"投诉箱":任何员工发现投诉,扔进去就行,专门的客服部(处理器)统一处理、统一格式回复。

### 2.2 自定义业务异常(`app/common/exceptions.py`)

```python
class BusinessException(Exception):
    """自定义的业务异常"""

    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(message)
```

**按执行顺序拆解：**

#### 第一步：声明可抛出的异常类型

```python
class BusinessException(Exception):
```

这是项目定义的类，继承 Python 的 Exception，才能通过 raise 抛出。定义一个异常类并不会自动让前端看到提示，还需要后面的处理器和注册。

#### 第二步：保存这次错误的信息

```python
self.message = message
self.code = code
```

例如创建 `BusinessException(message="账号或密码错误", code=400)`，这两个值会保存在异常实例上。后面的处理器通过 `exc.message` 和 `exc.code` 取回。

#### 第三步：初始化父类

```python
super().__init__(message)
```

把消息传给 Exception 的初始化方法，支持正常的异常字符串和日志显示。`self` 指具体这一次创建的异常对象，不是当前登录用户。

**把结果连起来：** 异常对象携带业务错误信息，抛出后由 FastAPI 调用注册的处理函数。


- 继承 `Exception` → 获得"可以被 raise / 被捕获"的能力
- `__init__` 里存下 `message` 和 `code`,处理器后面要读
- `super().__init__(message)` → 把信息也交给父类,日志打印时才正常

**业务代码里的用法:**

```python
raise BusinessException(message="账号或密码错误", code=400)
```

**这段代码怎样执行：** 先构造业务异常对象，再由 raise 中断当前正常执行路径。后续的数据库提交或成功返回不会继续执行，除非上层有其他捕获逻辑。类需从 `app.common.exceptions` 导入，处理器会把消息与业务码包装成响应。


注意:`code` 不传的话用默认值 500 —— "密码错误"是用户的问题,应该传 400。(我们做过控制变量实验验证过这个默认值的行为)

### 2.3 四个异常处理器：一张完整的"错误网"

```python
async def business_exception_handler(request, exc: BusinessException):
    """① 业务异常:你自己 raise 的"""
    return JSONResponse(
        status_code=200,   # HTTP 层保持 200,业务对错看 body 的 code
        content=Response.error(code=exc.code, message=exc.message).model_dump(),
    )

async def http_exception_handler(request, exc: HTTPException):
    """② HTTP 异常:框架抛的(404 路由不存在、405 方法不对等)"""
    return JSONResponse(
        status_code=exc.status_code,
        content=Response.error(code=exc.status_code, message=str(exc.detail)).model_dump(),
    )

async def validation_exception_handler(request, exc: RequestValidationError):
    """③ 参数校验异常:请求体缺字段、类型不对(422)"""
    return JSONResponse(
        status_code=422,
        content=Response.error(code=422, message="请求参数校验错误").model_dump(),
    )

async def global_exception_handler(request, exc: Exception):
    """④ 兜底:所有没预料到的意外(代码 bug、数据库断连等)"""
    return JSONResponse(
        status_code=500,
        content=Response.error(code=500, message="服务器内部错误").model_dump(),
    )
```

**按执行顺序拆解：**

#### 第一步：业务异常读取自定义属性

```python
content=Response.error(code=exc.code, message=exc.message).model_dump()
```

框架把原请求作为 request、异常对象作为 exc 传入处理器。Response.error 构造模型，model_dump 转成字典，JSONResponse 将它编码为 JSON。这里 HTTP 状态码固定 200，业务码来自异常。

#### 第二步：HTTP 异常保留状态码

```python
status_code=exc.status_code
```

例如路由不存在时，HTTP 状态码与业务 code 都可为 404。历史示例将 detail 转为 str；当前源码直接传入 detail，现有鉴权和路由错误主要使用字符串消息。

#### 第三步：请求校验失败返回 422

```python
content=Response.error(code=422, message="请求参数校验错误").model_dump()
```

缺少必填字段或字段类型不符合 schema 时，框架产生 RequestValidationError。处理器返回统一文案；当前不会把所有原始字段错误逐项返回给前端。

#### 第四步：未预期异常统一兜底

```python
status_code=500
```

例如代码调用不存在的方法，通用处理器返回“服务器内部错误”。客户端收到的统一信息不足以判断根因，开发时还需要看服务端堆栈。不能把统一响应当成已经解决了异常。

**把结果连起来：** 不同错误进入对应处理器，HTTP 状态码与 JSON 业务码分别设置，前端都读取 code/message/data。


四个处理器的分工:

| 处理器 | 接住什么 | 触发场景 |
|---|---|---|
| ① business | `BusinessException` | 你主动 raise 的业务错误 |
| ② http | `HTTPException` | 路由不存在(404)、方法不允许(405)、守门员抛的 401 |
| ③ validation | `RequestValidationError` | 请求参数不符合 Pydantic 模型(缺字段、类型错) |
| ④ global | `Exception`(所有异常的老祖宗) | 任何漏网的意外,兜底 |

从①到④是"从具体到宽泛":前三类精确打击,最后一张网兜住一切 —— 为应用内这些常见错误提供统一格式；连接中断、代理错误、响应已经开始发送等情况，不一定还能由这些处理器返回该格式。

### 2.4 一个处理器长什么样

以业务处理器为例,FastAPI 规定的签名是固定的:

```python
async def xxx_handler(request: Request, exc: 异常类型):
    #           ↑ 原始请求    ↑ 被抛出的异常对象本人
```

**这段代码怎样执行：** 这是处理器签名的结构示意，`异常类型` 需要替换为真实异常类，并补上函数体后才能执行。request 是原始请求，exc 是此次异常对象；不是当前用户和数据库对象。async 表示处理器是异步函数，不要求其中一定有网络请求。


`exc` 身上带着抛异常时存的信息(`exc.code`、`exc.message`),处理器读出来,包进 `Response.error(...)`,转成 JSON 返回。

---

## 第三章 注册：让处理器生效(`app/main.py`)

**定义了 ≠ 生效了。** 必须注册进 FastAPI 的"异常对照表":

```python
app = FastAPI()

app.add_exception_handler(BusinessException, business_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)
```

**按执行顺序拆解：**

#### 第一步：创建应用对象

```python
app = FastAPI()
```

app 是本项目运行的 FastAPI 应用。仅仅定义四个异常处理函数不会自动启用它们，需要把它们注册到这个应用。

#### 第二步：注册异常类型与处理函数的对应关系

```python
app.add_exception_handler(BusinessException, business_exception_handler)
```

第一个参数是异常类，第二个参数是函数对象，没有写括号立即执行。意思是以后遇到这类异常，由框架调用右边的函数；其他三行同理。

#### 第三步：为框架 HTTP 错误注册父类

```python
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
```

Starlette 的 HTTPException 是 FastAPI HTTPException 的父类。这样既能接住路由产生的 404/405，也能处理我们主动抛出的 HTTP 异常。

**把结果连起来：** 请求执行时出现异常 → 框架按异常类型选择处理器 → 形成统一响应。


每一行的意思:"FastAPI,遇到左边这种异常,交给右边这个函数处理。"

### ⚠️ 大坑：HTTPException 有两个版本

```
starlette.exceptions.HTTPException    ← 父类,框架自己抛 404 用它
    └── fastapi.HTTPException          ← 子类,我们代码里 raise 用它
```

匹配规则:**注册父类能接住子类,注册子类接不住父类。**

框架抛 404 时用的是父类对象,所以注册时必须用 starlette 的那个:

```python
from starlette.exceptions import HTTPException as StarletteHTTPException
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
```

**这段代码怎样执行：** 导入时用 `as` 起别名，避免与 FastAPI 的同名 HTTPException 混淆。注册的关键是实际传入的异常类；仅在函数参数里写类型注解，并不会替代 app.add_exception_handler 的注册。


(注解里用哪个都行,这里的处理器注解用于说明参数类型；处理器分派依赖注册的异常类。FastAPI 路由参数的类型注解还会参与解析和校验，不能一概而论。)

---

## 第四章 全景流程图

### 正常请求

```
请求 → 路由 → 依赖(鉴权等) → 业务函数 → Response.success(...) → 统一格式返回
```

### 出错请求(四种错误,一个出口)

```
                        ┌─ 你 raise BusinessException ──→ ① business handler
请求 → 业务执行中出错 ──┼─ 框架抛 HTTPException(404)──→ ② http handler
                        ├─ 参数不合法(422)───────────→ ③ validation handler
                        └─ 意外 bug ─────────────────→ ④ global handler
                                                          ↓
                                        统一格式 {"code","message","data"}
```

---

## 第五章 改造前后的代码对比

以登录接口为例:

```python
# ── 改造前 ──
if not user or not verify_password(...):
    return {"code": 400, "message": "账号或密码错误"}     # 手写字典
if user.status != 1:
    return {"code": 403, "message": "账号已被禁用"}
return {"code": 200, "message": "操作成功", "data": {"id": 3}} # 手写成功返回

# ── 改造后 ──
if not user or not verify_password(...):
    raise BusinessException(message="账号或密码错误", code=400)  # 抛出去
if user.status != 1:
    raise BusinessException(message="账号被禁用", code=403)
return Response.success(data={...})                              # 用生产线
```

**这段代码怎样执行：** 这是重构前后两种业务片段：历史版本直接返回失败字典；改造后先检查并 raise，全部通过才构造成功响应。省略号是讲解占位，不是完整登录函数。后续第 09 节再把这些判断移到 service，接口只负责调用和包装。


对比可见:**错误不再手写格式,成功不再重复 200**。而且别忘了,框架自己的错误(404/422)也被收进同一个格式了。

---

## 第六章 验证清单(自己动手)

重启服务后逐个验证:

```bash
# ① 业务异常:错误密码 → {"code":400,"message":"账号或密码错误"}
curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"wrong"}'

# ② HTTP 异常:不存在的路由 → {"code":404,...}
curl http://127.0.0.1:8000/api/xxx

# ③ 参数校验异常:缺 body → {"code":422,...}
curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{}'

# 成功路径:正常登录 → {"code":200,...}
curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"YOUR_TEST_PASSWORD"}'
```

**判断标准:所有返回都长一个样(三个字段),没有任何 `{"detail":...}` 格式的漏网之鱼。**

---

## 第七章 常见问题

**Q1:为什么业务错误的 HTTP 状态码返回 200,不是 400/403?**
这是"双层语义"设计:HTTP 状态码表示传输层("服务器正常处理了"),body 里的 code 表示业务层("具体什么错")。前端只需看 body 的 code,规则统一。
(注意:这套约定不是唯一正确答案,另一派做法是业务码和 HTTP 状态码一致。面试时能说出两种流派的取舍即可。)

**Q2:raise 之后函数后面的代码还执行吗?**
不执行。`raise` 和 `return` 一样会立刻结束当前函数,异常一路向上抛,直到被 FastAPI 的处理器接住。

**Q3:`exc: HTTPException` 这个注解不写会怎样?**
能跑,但编辑器不知道 exc 有哪些属性,补全和类型提示就没了。在这个处理器参数上，注解用于说明类型，分派依赖注册；但路由参数注解会被 FastAPI 用于请求解析和校验。

**Q4:为什么我改了代码接口行为没变?**
服务没有 --reload 时,改完代码必须 Ctrl+C 重启。(集群 inotify 配额满,--reload 用不了。)

**Q5:`code` 和 HTTP 的 `status_code` 什么关系?**
`status_code` 是 HTTP 协议层的(200/404/500),`code` 是我们自己定义的业务层。在 business handler 里两者可以不同(HTTP 200 + code 403)。

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| 统一响应格式 | 所有接口返回同样的外壳:{code, message, data} |
| 业务异常(BusinessException) | 自定义的异常类型,用来在业务代码里"抛出错误" |
| 异常处理器(handler) | 接住某种异常、转成响应的函数 |
| 注册(add_exception_handler) | 告诉 FastAPI"遇到 X 异常交给 Y 处理" |
| classmethod | 类方法,cls 指类本身,常用于"快捷构造" |
| Any | typing 里的"任意类型"标记(大写!) |
| 双层语义 | HTTP 状态码管传输,body 里的 code 管业务 |

---

## 本章自检清单

- [ ] 能默写出统一返回的三个字段及含义
- [ ] 能说清 success/error 为什么用 classmethod
- [ ] 能解释"raise 之后谁接住、在哪里接住"
- [ ] 能列出四个异常处理器各自接住什么
- [ ] 能解释为什么注册 HTTP 异常要用 starlette 的版本
- [ ] 能用 curl 验证全部四类错误的返回格式
- [ ] 能说出"HTTP 状态码 200 + body code 403"这种设计的好处
