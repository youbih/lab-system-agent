# JWT 用户认证：从概念到代码实现

> 对应课程：第 06 节
> 对应项目:`agent-lab/lab-system-agent/backend`
> 前置知识:FastAPI 基础路由、SQLAlchemy 基本查询、依赖注入(Depends)
> 阅读建议：按小节阅读，配合项目源码与示例理解执行过程。

---

## 阅读说明：代码版本与讲解方式

这份笔记根据原课程记录与当前项目源码整理，不代表拥有每节课的完整历史快照。保留原记录中的课程重点和排错经历；历史代码、当前实现、建议改进会分别说明。未在对话或原记录中确认的测试，不写成新增的实测结论。

代码按“完整片段 → 按执行顺序拆解 → 输入/返回值例子 → 页面或接口效果”阅读。仅有一两行的导入、配置或重复片段使用紧接代码的说明，避免反复展开相同逻辑。

**本节版本对应：** 第 06 节的登录 API 仍是业务与路由写在一起的历史代码；当前登录业务见 `services/auth_services.py`。查询个人资料历史路径为 `/api/user/info`，当前为 `/api/user/me`。

---

## 第零章 这节课干了什么

实现后端登录、密码哈希、JWT 签发与受保护接口的身份验证。前端登录联调主要在第 08 节，Service 分层在第 09 节，管理员鉴权在第 13 节，不混写为本节新增功能。

---

## 第一章 为什么需要"认证"

想象你的实验室预约系统上线后，任何人都能调用所有接口，会发生什么？

- 不登录就能预约实验室 → 不知道是谁约的
- 不登录就能删用户 → 谁都能搞破坏

所以接口必须分成两类：

```
开放接口:  浏览实验室列表、注册账号 …… 谁都能调
受保护接口: 预约、取消、管理用户 …… 必须先证明"你是谁"
```

**认证(Authentication)**,就是"证明你是谁"的过程。本章要解决的核心问题是:

> 用户登录一次之后，之后的每个请求，后端如何知道"还是这个人"？

---

## 第二章 从"固定口令"到 JWT

### 2.1 最原始的方案：固定 token

如果你在之前的练习里写过鉴权，大概长这样：

```python
VALID_TOKEN = "secret-token"
if credentials.credentials != VALID_TOKEN:
    raise HTTPException(401, "token 无效")
```

**这段代码怎样执行：** 这是固定口令方案的历史示意。先设定一个共享字符串，再比较请求携带的字符串；不一致就抛出 HTTP 异常，当前函数停止执行。`credentials` 来自此前的鉴权依赖，这个片段并没有创建它。它不能区分不同用户，不是当前 JWT 实现。


它能用，但有三个致命问题：

| 问题 | 说明 |
|---|---|
| 不知道"你是谁" | 所有人共用同一个 token，后端分不清张三李四 |
| 永不失效 | token 一旦泄露，永远可用 |
| 无法携带信息 | 它就是一串写死的字符，里面没有任何内容 |

### 2.2 JWT 的思路：把"身份信息"签进 token 里

JWT(JSON Web Token)是一段**自带内容、可验证签名**的字符串。长这样：

```
eyJhbGciOiJIUzI1NiJ9   .   eyJ1c2VyX2lkIjoxLCJleHAiOjE3OT...   .   JsSXp1BFoR5y9quq...
└── ① Header 头部 ──┘     └──── ② Payload 载荷 ────┘            └── ③ Signature 签名 ──┘
     (用什么算法签名)         (装的内容:user_id、过期时间)            (防伪印章)
```

头部和载荷使用 Base64URL 编码，签名字节也编码后展示，三部分用 `.` 连接。这种编码不保密；防篡改依赖密钥和签名校验。

**关键性质(必考):**

1. **载荷是"明文"的** —— 任何人都能解码看到内容。所以绝不放密码等敏感信息；当前载荷只放用户 ID 与过期时间；其他信息要按暴露风险决定
2. **签名是防伪的** —— 签名用"只有服务器知道的密钥"计算，任何人篡改载荷后，签名就对不上了，验签直接失败
3. **自包含、无状态** —— 后端不用存"谁登录着"，验签即可。这是它区别于传统 Session 的核心

### 2.3 安全三要素

| 要素 | 作用 | 我们的实现 |
|---|---|---|
| 密钥 `JWT_SECRET_KEY` | 签名的根基，泄露=任何人可伪造身份 | 存在 `.env`,不进 git |
| 过期时间 `exp` | 限制 token 泄露后的危害窗口 | `JWT_EXPIRE_HOURS` 配置 |
| 密码哈希 bcrypt | 数据库不明文存密码 | `utils/password.py` |

---

## 第三章 密码哈希：bcrypt

在讲登录之前，先解决一个前置问题：**数据库里的密码长什么样？**

### 3.1 为什么不能明文存密码

如果数据库泄露，所有用户的密码直接曝光。所以存的是"哈希"—— 一种**不可逆**的变换结果。

```
注册/初始化时:  "示例密码" --bcrypt--> "$2a$10$igTO5/Bv..8lRGJ0..."  (存入数据库)
验证时:         用户输入 "示例密码" --同样的算法--> 与库里的比对
```

注意方向不可逆：**从哈希推不出明文**。验证时不是解密，而是由 `checkpw` 根据已存哈希携带的盐和参数验证明文。不能重新随机生成哈希后直接比较字符串。

### 3.2 代码实现(`app/utils/password.py`)

```python
import bcrypt

def hash_password(password: str) -> str:
    """对密码加密(注册/初始化用户时用)"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    """验证密码(登录时用)"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
```

**按执行顺序拆解：**

#### 第一步：接收明文并转成字节

```python
password.encode("utf-8")
```

`hash_password`、`verify_password` 都是项目自己定义的函数。输入的 Python 字符串先编码成 bytes，因为 bcrypt 的这些接口接收字节。`password: str` 和 `-> str`/`-> bool` 是类型注解，不是在调用时自动生成密码。

#### 第二步：生成盐并计算哈希

```python
bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
```

`gensalt()` 生成随机盐，`hashpw()` 计算包含盐和参数信息的哈希，最后 `decode()` 转成可存入字符串列的文本。比如注册时输入某个测试密码，数据库保存的是 bcrypt 哈希，而不是该明文。

#### 第三步：验证输入是否匹配已存哈希

```python
bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
```

`password` 是登录时用户本次输入，`hashed_password` 是数据库已有值。`checkpw()` 根据已存哈希中的盐和参数检查是否匹配，返回 `True` 或 `False`。不是先解密，也不是重新随机生成一份哈希后直接比较文本。

**把结果连起来：** 注册/改密码调用 `hash_password` 保存；登录/校验原密码调用 `verify_password` 判断。


两个细节：

- `bcrypt.gensalt()` 生成随机"盐"，所以**同一个密码每次哈希结果都不同**(彩虹表攻击失效)
- 哈希是 60 个字符 —— 所以数据库里 `password` 字段必须是 `VARCHAR(255)` 之类，50 存不下(我们踩过这个坑)

---

## 第四章 JWT 工具函数(`app/utils/jwt.py`)

这是整个体系的"印章机"，只有两个函数：一个签发，一个解析。

```python
from datetime import datetime, timedelta
import jwt
from app.config import settings

def create_access_token(user_id: int) -> str:
    """创建 JWT token(登录成功时调用)"""
    expire = datetime.now() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {"user_id": user_id, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_access_token(token: str) -> dict:
    """解析 JWT token(守门员调用)"""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=settings.JWT_ALGORITHM)
```

**按执行顺序拆解：**

#### 第一步：读取配置并计算过期时刻

```python
expire = datetime.now() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
```

`datetime`、`timedelta` 来自 Python 标准库，`jwt` 来自 PyJWT，`settings` 是项目配置对象。这里计算过期时刻；配置默认时长为 24 小时，但环境变量可以覆盖。当前源码使用无时区的 `datetime.now()`，后续可统一使用 UTC 时区明确的时间来避免时区解释差异；本次只说明，没有改源码。

#### 第二步：构造载荷字典

```python
payload = {"user_id": user_id, "exp": expire}
```

假设登录用户 ID 为 3，载荷里的 `user_id` 就是 3；`exp` 是过期时间。载荷不包含密码，也不会通过用户名自动查数据库，因为用户身份已在调用这个函数之前确认。

#### 第三步：签名后返回字符串

```python
return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
```

`jwt.encode` 是库函数，`create_access_token` 是项目函数。库使用服务端密钥和配置算法生成签名，返回 token 字符串；载荷编码不等于加密，不能把敏感明文放进去。

#### 第四步：请求时验证并读回字典

```python
return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=settings.JWT_ALGORITHM)
```

`decode_access_token` 接收之后请求携带的 token。库验证签名和过期时间，成功则返回载荷字典；失败抛异常，由鉴权依赖统一转为登录失效响应。当前接口没有在这里比较密码。

**把结果连起来：** 登录时生成字符串；后续请求把它放在 Authorization 头中，由后端解码验证并取得用户 ID。


### 逐行理解 `create_access_token`

```python
expire = datetime.now() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
```

**这段代码怎样执行：** 这是上面函数的局部片段：右边先计算“现在加有效时长”，左边 `expire` 保存结果。它只产生一个时间值，此时还没有生成 token，也没有写入数据库。


过期时间 = 现在 + 配置的小时数。token 泄露后，攻击者最多用到这个时间为止。

```python
payload = {"user_id": user_id, "exp": expire}
```

**这段代码怎样执行：** Python 字典的键是 `"user_id"`、`"exp"`，值取自函数参数和上一行的时间变量。不同用户的 ID 不同；即使同一用户密码未变，登录时的过期时刻也可能不同，因此 token 也可能不同。


载荷：装什么由你定。最少要有"是谁"(user_id）和"何时过期"(exp)。

```python
jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=...)
```

**这段代码怎样执行：** 这行是签名调用的结构示意，`algorithm=...` 中的省略号不是项目实际配置。实际源码传入 `settings.JWT_ALGORITHM`。返回的是字符串，不是密码哈希；密钥来自后端配置，不能提交真实值到笔记。


用密钥签名，产出最终字符串。**这个密钥就是整个系统的命根子。**

### `decode` 其实做了两件事

`jwt.decode()` 不只是"解码"，它会同时：

1. **验签**：用同一个密钥重新算签名，对不上 → 抛异常
2. **检查过期**：当前时间超过 `exp` → 抛异常(ExpiredSignatureError)

所以守门员只要 `try/except` 包住它，就能挡住伪造和过期两种情况。

---

## 第五章 登录接口(`app/api/auth.py`)

现在把前面两件武器组装起来。本节的普通受保护请求通过 token 识别身份，登录时提交账号密码；后续注册和修改密码也会提交相应密码字段。

```python
@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    # ① 按账号查数据库
    user = db.query(User).filter(User.username == data.username).first()

    # ② 校验密码(bcrypt 哈希比对)
    if not user or not verify_password(data.password, user.password):
        return {"code": 400, "message": "账号或密码错误"}

    # ③ 校验账号状态
    if user.status != 1:
        return {"code": 403, "message": "账号已被禁用"}

    # ④ 签发 token
    token = create_access_token(user_id=user.id)

    # ⑤ 返回
    return {
        "code": 200,
        "message": "操作成功",
        "data": {"token": token, "user": UserResponse.model_validate(user)},
    }
```

**按执行顺序拆解：**

#### 第一步：匹配登录接口并取得参数

```python
@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
```

这是第 06 节将业务写在 API 函数中的历史版本。装饰器声明 POST 路径；FastAPI 将 JSON 请求体解析成 `LoginRequest`，通过 `get_db` 提供会话。当前代码在第 09 节之后把业务移到了 `auth_services.login`，下列业务顺序仍可对照理解。

#### 第二步：按账号找用户

```python
user = db.query(User).filter(User.username == data.username).first()
```

`data.username` 是本次输入的账号；`first()` 执行查询，返回一个 `User` ORM 对象或 `None`。不要把它理解成 JSON 用户列表。

#### 第三步：检查密码和状态

```python
if not user or not verify_password(data.password, user.password):
    return {"code": 400, "message": "账号或密码错误"}
```

Python 的 `or` 有短路行为：用户不存在时，不会继续读取 `user.password`。用户存在才用 bcrypt 校验。密码通过后再检查 `status`，禁用用户不会拿到 token。这里返回字典是历史写法，当前对应分支抛 `BusinessException`。

#### 第四步：签发并返回登录结果

```python
token = create_access_token(user_id=user.id)
```

身份确认后才签发 token。`UserResponse.model_validate(user)` 从 ORM 属性读取对外允许的字段；最终返回业务码、消息，以及包含 token 和用户资料的 data。前端拿到后才能保存登录状态。

**把结果连起来：** 输入账号密码 → 查到用户 → 验密码与状态 → 生成 token → 返回登录结果；任何失败分支都会提前结束。


### 设计细节解读

**为什么①和②合并成一句"账号或密码错误"？**
故意的安全设计。如果分开提示"账号不存在"/"密码错误"，攻击者就能探测哪些账号已注册。

**为什么 401 和 403 要区分？**
- `401 Unauthorized` = 我不知道你是谁（没登录/token 无效)
- `403 Forbidden` = 我知道你是谁，但你没权限（被禁用）

**为什么查库后才签发 token?**
token 里的 user_id 必须对应一个真实、启用的用户，否则签出去的就是"废票"。

---

## 第六章 守门员(`app/dependencies/auth.py`)

登录之后，每个受保护接口都要回答同一个问题："这个请求是谁发的？"—— 这就是守门员的职责。

### 6.1 取 token 的装置

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
```

**这段代码怎样执行：** `OAuth2PasswordBearer` 是 FastAPI 提供的工具，`oauth2_scheme` 是我们创建的依赖对象。把它放进 `Depends(...)` 后，框架从请求头提取 Bearer token。`tokenUrl` 指定文档授权流程使用的登录入口，并不会替每次业务请求重新登录。


声明："token 从请求头 `Authorization: Bearer xxx` 里取"。`Depends(oauth2_scheme)` 会自动完成这个动作。`tokenUrl` 只影响 Swagger 文档的 Authorize 按钮行为。

### 6.2 三道关卡

```python
def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    # 关卡一:验真伪 + 验有效期
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(401, "登录已失效，请重新登录")

    # 关卡二:载荷里有用户 ID 吗
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(401, "无效的登录凭证")

    # 关卡三:用户在库里还存在、没被禁用吗
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.status != 1:
        raise HTTPException(401, "用户被禁用")
    return user
```

**按执行顺序拆解：**

#### 第一步：先由依赖提供 token 和数据库会话

```python
token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
```

FastAPI 在调用函数前准备参数。`get_current_user` 是项目函数；`Depends` 是框架工具。缺少所需认证信息时，可能在进入函数体前就被认证依赖拒绝。

#### 第二步：验证签名与有效期

```python
try:
    payload = decode_access_token(token)
except Exception:
    raise HTTPException(401, "登录已失效，请重新登录")
```

成功时 `payload` 是字典；失败时抛出 HTTP 401，不会再往下查询。`try/except` 是处理异常的 Python 语法，不是另一次网络请求。

#### 第三步：从载荷取用户 ID

```python
user_id = payload.get("user_id")
```

`dict.get()` 在键不存在时返回 `None`。后面的 `if not user_id` 会拒绝缺少身份标识的载荷；这里没有使用前端额外传来的 user_id。

#### 第四步：查库并返回当前用户

```python
user = db.query(User).filter(User.id == user_id).first()
if not user or user.status != 1:
    raise HTTPException(401, "用户被禁用")
return user
```

查询当前账号是否仍存在、状态是否为正常。成功返回的是 `User` 对象，FastAPI 将它注入业务接口的 `current_user` 参数。禁用账号会使其后续受保护请求被拒绝；这不等于建立了所有单个 JWT 的撤销机制。

**把结果连起来：** 认证依赖返回用户对象，业务接口复用它；不需要每个接口重写一套解析 token 的代码。


**关卡三存在的理由**:JWT 的软肋是"不增加服务端状态时难以单独撤销一个已签发 token"。查库这步让管理员禁用账号后立即生效，用数据库状态控制账号的后续访问；不是将 token 自身从全系统销毁。

### 6.3 它什么时候执行

**不在登录时，而在之后的每个受保护请求里。** 靠依赖注入自动触发：

```python
@router.get("/info")
def get_user_info(current_user: User = Depends(get_current_user)):
    ...
```

**这段代码怎样执行：** 这个带省略号的片段只演示依赖挂载位置，不是完整业务实现。`Depends(get_current_user)` 会先执行鉴权，再将返回的 ORM 用户对象赋给 `current_user`。历史路径 `/info` 对应当前源码中的 `/me`。


请求到达 → FastAPI 先执行 `get_current_user` → 三关全过，`return user` 的结果塞进 `current_user` 参数 → 业务函数才开始跑。任何一关 raise，业务函数压根不会执行。

---

## 第七章 受保护接口(`app/api/user.py`)

守门员就位后，业务接口自己变得非常干净：

```python
router = APIRouter(prefix="/user", tags=["用户信息"])

@router.get("/info")
def get_user_info(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {
        "code": 200,
        "message": "请求成功",
        "data": UserResponse.model_validate(current_user),
    }
```

**按执行顺序拆解：**

#### 第一步：拼接接口路径

```python
router = APIRouter(prefix="/user", tags=["用户信息"])
```

`APIRouter` 是 FastAPI 的路由分组工具。历史的 `/info` 与 `/user`、总路由 `/api` 拼成 `/api/user/info`；当前路径已统一成 `/api/user/me`。

#### 第二步：先获取当前用户

```python
current_user: User = Depends(get_current_user)
```

这是参数声明，不是手动调用；鉴权通过才进入函数体。它决定要读取哪个用户，无需接受客户端任意指定的账号 ID。

#### 第三步：转换成响应数据

```python
UserResponse.model_validate(current_user)
```

从数据库对象提取响应模型声明的属性，作为 data 返回。例如 ORM 对象带 password，但响应模型没有该字段，就不会作为用户响应字段输出密码。当前源码还会通过 service 和 Response.success 包装，这是后续课程的重构。

**把结果连起来：** 浏览器携带 token 查询自己的资料，数据库对象先转成响应模型，再由框架序列化。


注意这个函数里**没有任何一行鉴权代码** —— 鉴权全部外包给了依赖。想给新接口加保护，只需在参数里加 `Depends(get_current_user)`，一行搞定。

---

## 第八章 全景流程图

### 第一次交互：登录并获取 token

```
前端                    后端
 | POST /api/auth/login  |
 | {username, password}  |
 | --------------------> | 查库 → bcrypt 校验 → 检查 status
 |                       | → create_access_token(user_id)
 | <-------------------- |
 |    { token: "eyJ..." }|
 | 前端把 token 存起来    |
 |   (localStorage)      |
```

### 之后每一次交互：刷令牌

```
前端                    后端
 | GET /api/user/info    |
 | Authorization: Bearer eyJ... |
 | --------------------> | oauth2_scheme 取出 token
 |                       | get_current_user 三道关卡:
 |                       |   ① 验签+验过期
 |                       |   ② 取 user_id
 |                       |   ③ 查库确认状态
 |                       | 通过 → 执行业务函数
 | <-------------------- |
 |   { code:200, data }  |
```

### 类比

- 账号密码用于登录确认身份；普通受保护查询之后携带 token，密码修改仍会提交原/新密码
- JWT = 工牌：进门后全程刷它；工牌上有防伪章（签名）和有效期（exp)
- 守门员查库 = 闸机联网确认"这人没离职"

---

## 第九章 验证步骤（使用当前接口）

以下为可执行思路与预期分支，不表示本次文档修订重新执行了测试。使用测试账号，替换密码/token 占位值；状态修改会写数据库，确认对象后再操作。

登录函数有 4 条路径，每条都能用 curl 验证：

```bash
# 分支 1:账号不存在 → 400
curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"nobody","password":"YOUR_TEST_PASSWORD"}'

# 分支 2:密码错误 → 400
curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"wrong"}'

# 分支 4:正常登录 → 200,复制返回的 token
curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"YOUR_TEST_PASSWORD"}'

# 守门员:带 token 访问 → 200
curl http://127.0.0.1:8000/api/user/me -H "Authorization: Bearer <token>"

# 守门员:不带 token → 401
curl http://127.0.0.1:8000/api/user/me

# 守门员:篡改 token 一位 → 401(验签失败)
```

分支 3（账号被禁用）需要先把用户 status 改成 0 再测，测完记得改回来：

```sql
UPDATE users SET status=0 WHERE id=1;   -- 测试 → 应返回 403
UPDATE users SET status=1 WHERE id=1;   -- 恢复
```

---

## 第十章 常见问题(FAQ)

**Q1:token 里为什么不放密码？**
载荷是 Base64 编码，谁都能解码看内容。放 user_id 无妨，放密码就是裸奔。签名只保证"不可篡改"，不保证"不可见"。

**Q2：为什么登录接口用 POST，而验证身份的 GET 请求却不用带 body?**
HTTP 请求分三部分：请求行、请求头、请求体。账号密码是"要提交的数据"，放 body(POST);token 是"关于请求本身的元信息"，放请求头 `Authorization`,GET/POST 都能带。

**Q3:Swagger docs 里怎么测受保护接口？**
登录接口返回顶层要有 `access_token` 和 `token_type`(OAuth2 规范），然后点右上角 Authorize 按钮输账号密码即可。表单格式和 JSON 格式的差异会导致 422，所以项目里专门加了一个 `/api/auth/token` 表单入口给 Swagger 用。

**Q4:token 过期了用户会怎么样？**
守门员关卡一抛 401 "登录已失效"。前端收到 401 应自动跳转登录页重新登录。过期时间长短是安全与体验的权衡。

**Q5：想实现"退出登录"怎么办？**
纯 JWT 无法主动作废单个 token。常见做法：前端删 token（名义退出）+ 短过期时间（兜底）；要严格踢人就引入服务端黑名单/白名单（通常存 Redis)。

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| JWT | 自带内容、带防伪签名的字符串令牌 |
| Payload | JWT 里装内容的部分(user_id、exp) |
| 签名(Signature) | 用密钥算出的防伪印章 |
| bcrypt | 密码哈希算法，带随机盐，不可逆 |
| Bearer Token | 请求头携带 token 的标准格式：`Authorization: Bearer xxx` |
| 依赖注入(Depends) | FastAPI 机制：声明需要什么，框架自动准备好(守门员靠它挂载) |
| RBAC | 基于角色的权限控制（本项目中 role 字段的雏形) |

---

## 本章自检清单

- [ ] 能画出 JWT 的三段结构，说清每段的作用
- [ ] 能说清"为什么数据库不能明文存密码"
- [ ] 能口述登录接口的四个分支
- [ ] 能口述守门员的三道关卡，以及关卡三为什么必要
- [ ] 能用 curl 独立完成"登录 → 带 token 访问 → 不带 token 看 401"
- [ ] 能解释 401 和 403 的区别
- [ ] 能解释登录提交密码、普通查询携带 token，以及当前改密码不撤销旧 token 的边界
