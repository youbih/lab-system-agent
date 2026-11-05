# JWT 用户认证：从概念到代码实现

> 对应项目:`agent-lab/lab-system-agent/backend`
> 前置知识:FastAPI 基础路由、SQLAlchemy 基本查询、依赖注入(Depends)
> 阅读时间:约 40 分钟 · 建议配合实际代码边看边试

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

### 2.1 最原始的方案:固定 token

如果你在之前的练习里写过鉴权，大概长这样：

```python
VALID_TOKEN = "secret-token"
if credentials.credentials != VALID_TOKEN:
    raise HTTPException(401, "token 无效")
```

它能用，但有三个致命问题：

| 问题 | 说明 |
|---|---|
| 不知道"你是谁" | 所有人共用同一个 token，后端分不清张三李四 |
| 永不失效 | token 一旦泄露，永远可用 |
| 无法携带信息 | 它就是一串写死的字符，里面没有任何内容 |

### 2.2 JWT 的思路：把"身份信息"签进 token 里

JWT(JSON Web Token)是一段**自带内容、且无法伪造**的字符串。长这样：

```
eyJhbGciOiJIUzI1NiJ9   .   eyJ1c2VyX2lkIjoxLCJleHAiOjE3OT...   .   JsSXp1BFoR5y9quq...
└── ① Header 头部 ──┘     └──── ② Payload 载荷 ────┘            └── ③ Signature 签名 ──┘
     (用什么算法签名)         (装的内容:user_id、过期时间)            (防伪印章)
```

三段都是 Base64 编码，用 `.` 连接。

**关键性质(必考):**

1. **载荷是"明文"的** —— 任何人都能解码看到内容。所以绝不放密码等敏感信息；放 `user_id`、`role` 这种没问题
2. **签名是防伪的** —— 签名用"只有服务器知道的密钥"计算，任何人篡改载荷后，签名就对不上了，验签直接失败
3. **自包含、无状态** —— 后端不用存"谁登录着"，验签即可。这是它区别于传统 Session 的核心

### 2.3 安全三要素

| 要素 | 作用 | 我们的实现 |
|---|---|---|
| 密钥 `JWT_SECRET_KEY` | 签名的根基，泄露=任何人可伪造身份 | 存在 `.env`,不进 git |
| 过期时间 `exp` | 限制 token 泄露后的危害窗口 | `JWT_EXPIRE_HOURS` 配置 |
| 密码哈希 bcrypt | 数据库不明文存密码 | `utils/password.py` |

---

## 第三章 密码哈希:bcrypt

在讲登录之前，先解决一个前置问题：**数据库里的密码长什么样？**

### 3.1 为什么不能明文存密码

如果数据库泄露，所有用户的密码直接曝光。所以存的是"哈希"—— 一种**不可逆**的变换结果。

```
注册/初始化时:  "示例密码" --bcrypt--> "$2a$10$igTO5/Bv..8lRGJ0..."  (存入数据库)
验证时:         用户输入 "示例密码" --同样的算法--> 与库里的比对
```

注意方向不可逆：**从哈希推不出明文**。验证时不是"解密"，而是"重新算一遍再比对"。

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

### 逐行理解 `create_access_token`

```python
expire = datetime.now() + timedelta(hours=settings.JWT_EXPIRE_HOURS)
```

过期时间 = 现在 + 配置的小时数。token 泄露后，攻击者最多用到这个时间为止。

```python
payload = {"user_id": user_id, "exp": expire}
```

载荷：装什么由你定。最少要有"是谁"(user_id）和"何时过期"(exp)。

```python
jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=...)
```

用密钥签名，产出最终字符串。**这个密钥就是整个系统的命根子。**

### `decode` 其实做了两件事

`jwt.decode()` 不只是"解码"，它会同时：

1. **验签**：用同一个密钥重新算签名，对不上 → 抛异常
2. **检查过期**：当前时间超过 `exp` → 抛异常(ExpiredSignatureError)

所以守门员只要 `try/except` 包住它，就能挡住伪造和过期两种情况。

---

## 第五章 登录接口(`app/api/auth.py`)

现在把前面两件武器组装起来。**登录是账号密码唯一出现的地方**，之后全程用 token。

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

**关卡三存在的理由**:JWT 的软肋是"签发后无法主动作废"。查库这步让管理员禁用账号后立即生效，用一次查询换来"可撤销"。

### 6.3 它什么时候执行

**不在登录时，而在之后的每个受保护请求里。** 靠依赖注入自动触发：

```python
@router.get("/info")
def get_user_info(current_user: User = Depends(get_current_user)):
    ...
```

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

注意这个函数里**没有任何一行鉴权代码** —— 鉴权全部外包给了依赖。想给新接口加保护，只需在参数里加 `Depends(get_current_user)`，一行搞定。

---

## 第八章 全景流程图

### 第一次交互：登录(账号密码只出现这一次)

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

- 账号密码 = 身份证：只在入场登记时出示一次
- JWT = 工牌：进门后全程刷它；工牌上有防伪章（签名）和有效期（exp)
- 守门员查库 = 闸机联网确认"这人没离职"

---

## 第九章 自己验证一遍(分支覆盖)

登录函数有 4 条路径，每条都能用 curl 验证：

```bash
# 分支 1:账号不存在 → 400
curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"nobody","password":"YOUR_TEST_PASSWORD"}'

# 分支 2:密码错误 → 400
curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"wrong"}'

# 分支 4:正常登录 → 200,复制返回的 token
curl -X POST http://127.0.0.1:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"YOUR_TEST_PASSWORD"}'

# 守门员:带 token 访问 → 200
curl http://127.0.0.1:8000/api/user/info -H "Authorization: Bearer <token>"

# 守门员:不带 token → 401
curl http://127.0.0.1:8000/api/user/info

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
- [ ] 能解释"账号密码只用一次，之后全程刷 token"
