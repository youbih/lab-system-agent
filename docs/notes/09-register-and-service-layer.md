# 开发注册功能 + 后端 Service 层重构

> 对应课程:第 09 节
> 对应项目:`agent-lab/lab-system-agent`
> 涉及文件:
> - 前端:`src/views/Register.vue`、`src/api/auth.js`
> - 后端:`app/schemas/auth.py`、`app/api/auth.py`、`app/services/auth_services.py`(新增!)
> 阅读建议：按小节阅读，配合项目源码与示例理解执行过程。

---

## 阅读说明：代码版本与讲解方式

这份笔记根据原课程记录与当前项目源码整理，不代表拥有每节课的完整历史快照。保留原记录中的课程重点和排错经历；历史代码、当前实现、建议改进会分别说明。未在对话或原记录中确认的测试，不写成新增的实测结论。

代码按“完整片段 → 按执行顺序拆解 → 输入/返回值例子 → 页面或接口效果”阅读。仅有一两行的导入、配置或重复片段使用紧接代码的说明，避免反复展开相同逻辑。

**本节版本对应：** 注册与登录服务当前仍在 auth_services.py。页面提交讲解采用当前 Register.vue；普通注册固定为学生身份。原笔记保留的前后重构示例用于理解演变，不表示它们应同时复制进源码。

---

## 第零章 这节课干了什么

两件事:

1. **新功能**:注册(前端注册页 + 后端注册接口,完整闭环)
2. **重构**:把登录/注册的业务逻辑从 api 层抽到 **service 层**(本课最有价值的部分)

完成后的架构:

```
前端(浏览器,localhost:5173)            后端(集群,localhost:8000)
─────────────────────────────         ─────────────────────────────

Register.vue(注册页:表单+校验)
   │
   ▼
api/auth.js 的 registerApi(form)
   │  封装:POST /api/auth/register
   ▼
utils/request.js(请求层)
   │  拼地址:baseURL + url
   │  拦截器:贴 token、超时控制
   │
   ═══════════ 前后端连接点 ═══════════
   HTTP POST http://localhost:8000/api/auth/register
   ├─ 网络路径:浏览器 → VSCode 端口转发 → 集群 FastAPI
   ├─ 浏览器直连跨源接口时按 CORS 检查；同源 Vite 代理走另一条路径
   └─ 契约一致:URL+方法、JSON 格式、统一返回格式
   ═══════════════════════════════════
   │
   ▼
api/auth.py(接口层:收发)
   @router.post("/register")
   只用两行:调 service、包响应
   │
   ▼
services/auth_services.py(业务层:干活)
   查重 → 密码 bcrypt 哈希 → 构造 User → db.add/commit
   │
   ▼
MySQL(用户落库,密码是 60 位哈希)
```

---

## 第一章 前端：注册页(Register.vue)

### 1.1 和登录页的关系

注册页 = 登录页的"加长版":多一个确认密码框 + 自定义校验规则。整体结构(container/box/form）完全一样。

### 1.2 核心新增：自定义校验器(两次密码一致)

固定规则（`required`）不够用时的武器:

```javascript
const validatePass = (rule, value, callback) => {
  if (value === '') {
    callback(new Error('请确认密码'))        // 失败:给 callback 一个 Error
  } else {
    if (value !== form.password) {
      callback(new Error('两次密码输入不一致'))
    } else {
      callback()                              // 通过:空调用 callback
    }
  }
}

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  confirmPassword: [{ validator: validatePass, trigger: 'blur' }]   // ← 自定义
}
```

**按执行顺序拆解：**

#### 第一步：定义校验器，交给表单调用

```javascript
const validatePass = (rule, value, callback) => {
```

validatePass 是项目自定义函数，不是 Vue 内置函数。把它配置在 confirmPassword 的 validator 后，Element Plus 调用它，value 就是确认密码输入框当前的值。rule 是当前规则，callback 是报告校验结果的函数。

#### 第二步：拒绝空值

```javascript
if (value === "") {
  callback(new Error("请确认密码"))
}
```

确认密码为空时，创建错误对象交给 callback，告诉表单此项未通过。这里没有向后端发请求，也没有在数据库写入任何内容。

#### 第三步：比较两次密码

```javascript
if (value !== form.password) {
  callback(new Error("两次密码输入不一致"))
} else {
  callback()
}
```

form.password 是第一次输入，value 是确认输入。不同就失败，相同就用不带参数的 callback 报告通过；例如第一次填测试密码 A、确认填 B，会被挡住。每条实际执行分支只调用一次 callback。

**把结果连起来：** 校验器只负责确认两次输入一致；账号是否重名和密码是否入库由后端决定。


**理解 callback 的约定**:`callback()` = 通过;`callback(new Error('...'))` = 失败并显示消息。这是 Element Plus 校验器的固定协议。

### 1.3 提交逻辑(沿用上节课的最佳实践)

```javascript
const register = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loadingValue.value = true
  try {
    const res = await registerApi(form)

    if (res.code === 200) {
      ElMessage.success('注册成功')
      await router.push('/login')
    }
  } finally {
    loadingValue.value = false
  }
}
```

**按执行顺序拆解：**

#### 第一步：先执行完整表单校验

```javascript
const valid = await formRef.value.validate().catch(() => false)
if (!valid) return
```

formRef 引用 el-form 实例，validate 检查账号/密码必填和确认密码。失败转换为 false，然后退出 register，不显示成功也不发送请求。

#### 第二步：开启按钮加载并提交

```javascript
loadingValue.value = true
const res = await registerApi(form)
```

第一句在 try 前，第二句在 try 内。页面按钮绑定 loadingValue；registerApi 是自定义 API 封装，发送 POST /api/auth/register。此处直接传整个 form，包括 confirmPassword；当前后端 schema 默认忽略这个额外字段，不会将它存为密码列。

#### 第三步：成功后提示并去登录

```javascript
if (res.code === 200) {
  ElMessage.success("注册成功")
  await router.push("/login")
}
```

响应拦截器已经返回业务 JSON，因此判断 res.code。注册成功不等于自动登录：本函数没有保存 token，而是提示后让用户登录。账号重名时业务码非 200，不执行这个分支。

#### 第四步：所有路径恢复按钮

```javascript
finally {
  loadingValue.value = false
}
```

请求抛出异常时也能结束按钮加载。finally 做收尾，不能把它理解成捕获错误；错误显示主要由公共请求层负责。

**把结果连起来：** 点注册 → 校验 → 发请求 → 成功则跳登录 → 按钮恢复；表单失败时则在最前面结束。


这套"校验前置 + 提前 return + try/finally 复位"就是上次优化出来的模板，直接复用。

### 1.4 `<router-link>` 替代 `<a>`

```html
<!-- 以前:整页刷新 -->
<a href="/login">登录</a>

<!-- 现在:SPA 内部跳转,不刷新 -->
<router-link to="/login">登录</router-link>
```

**这段代码怎样执行：** 两行是导航方案对照，实际使用其中一种。a 的 href 由浏览器执行普通页面导航，可能重新加载整个应用；router-link 使用已注册的 Vue Router 切换组件。to="/login" 对应的是页面路由，不是后端的登录接口路径。


区别：普通内部链接可能重新加载整个应用；router-link 进行路由导航，保留当前单页应用环境。内部导航通常用 router-link 或 router.push，外部网址、下载等仍可使用普通链接。

---

## 第二章 后端：注册接口的三层

### 2.1 契约层：RegisterRequest(schemas/auth.py)

```python
class RegisterRequest(BaseModel):
    username: str
    password: str
    name: str | None = None      # 可选字段:不给就是 None
```

**按执行顺序拆解：**

#### 第一步：声明必填字段

```python
username: str
password: str
```

RegisterRequest 是 Pydantic 请求模型，FastAPI 用它解析 JSON。两项无默认值，必须提供；缺少时会进入第 07 节的请求参数异常处理器，业务注册函数不会继续执行。

#### 第二步：声明可选名称

```python
name: str | None = None
```

允许 name 为字符串或 None，并提供默认 None。前端只提交账号密码时，service 可以使用账号做名称。这里还没有给字段配置长度等额外限制。

#### 第三步：区分输入与数据库模型

请求模型只说明允许接收什么，User 是数据库表模型。当前请求模型没有 role/status 字段，service 自己指定学生和正常状态，不由普通注册者选择管理员身份。

**把结果连起来：** POST JSON 先变成 RegisterRequest，业务层再决定怎样创建 User。


`str | None = None` 的含义:类型可以是字符串或 None,默认 None —— 前端的表单里没有"姓名"字段也能通过校验。

### 2.2 接口层：api/auth.py

```python
@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """注册"""
    auth_services.register(db, data)      # 业务全外包
    return Response.success(message="注册成功")
```

**按执行顺序拆解：**

#### 第一步：声明接口与依赖

```python
@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
```

总路径是 /api/auth/register。data 来自 JSON，db 来自会话依赖；RegisterRequest 和服务模块都要导入。此函数不是 Vue 的 register，而是后端路由函数，同名不代表同一个函数。

#### 第二步：把业务交给服务函数

```python
auth_services.register(db, data)
```

API 将会话和已解析参数传给 service。service 在发现重名时 raise；异常会阻止下一句成功响应，交给全局异常处理器。正常返回时才继续。

#### 第三步：构造成功响应

```python
return Response.success(message="登录成功喵")
```

这句按当前源码展示，文案仍保留了复制痕迹，实际动作是注册。注册 service 没有显式返回用户对象，因此接口也不返回 token，data 默认 null。可后续把消息改成“注册成功”，本次不改业务源码。

**把结果连起来：** 接口层不再自己查重或算哈希，专注请求与响应。


接口层只剩两行:调 service、包响应。这就是分层的目标状态。

### 2.3 业务层：services/auth_services.py(本课核心)

```python
def register(db: Session, data: RegisterRequest):
    # ① 查重:用户名已存在?
    user = db.query(User).filter(User.username == data.username).first()
    if user:
        raise BusinessException(message="账户已存在")

    # ② 构造 ORM 对象(注意密码是哈希后的!)
    user_model = User(
        username=data.username,
        password=hash_password(data.password),     # bcrypt 加密,库里不存明文
        name=data.name or data.username,           # 兜底:没填名字就用账号
        role="student",                            # 默认角色
        status=1,                                  # 默认启用
    )

    # ③ 写入数据库
    db.add(user_model)
    db.commit()
```

**按执行顺序拆解：**

#### 第一步：根据账号查询并检查重名

```python
user = db.query(User).filter(User.username == data.username).first()
if user:
    raise BusinessException(message="账户已存在")
```

first() 返回 ORM 对象或 None。已有对象就抛业务异常，后面创建与提交都不会执行。当前异常没有显式传 code，沿用默认业务码 500；这不是数据库连接出错。

#### 第二步：构造待保存的 User 对象

```python
user_model = User(
    username=data.username,
    password=hash_password(data.password),
    name=data.name or data.username,
    role="student",
    status=1
)
```

构造时密码已做 bcrypt 哈希。name 为 None 或空字符串时，or 表达式选用账号。role 与 status 由服务端固定，防止客户端通过注册请求把自己设置为管理员。此时创建的是 Python ORM 对象，还没有完成持久化。

#### 第三步：加入会话并提交数据库

```python
db.add(user_model)
db.commit()
```

add 把对象纳入会话，commit 提交事务并持久化。若数据库错误导致失败，不应继续声称注册成功；通用异常处理器会返回失败，真实原因看后端日志。

#### 第四步：读取插入后的最新字段

```python
db.refresh(user_model)
```

按数据库中的当前值刷新 ORM 对象，例如生成的 ID。当前函数并没有继续返回 user_model，所以这里是源码保留的刷新动作，不应说每次插入都必须 refresh 才能保存。

**把结果连起来：** 查重通过 → 明文转哈希 → 构造学生用户 → add/commit 保存；刷新与保存是不同动作。


四个知识点:

| 知识点 | 说明 |
|---|---|
| 先查重 | 用户名唯一的业务规则,靠"先查一遍"实现(更严谨的做法是数据库加唯一索引兜底) |
| 密码必哈希 | `hash_password()` 上场,库里存的是 60 位 bcrypt 哈希 |
| `or` 兜底 | `data.name or data.username`:name 为空/None 时用 username —— Python 的短路特性 |
| 默认值 | role/status 在服务端写死,不接受前端传 —— **安全设计**:否则用户可以自己注册成 admin |

> ⚠️ 安全要点:注册接口**绝不能**接收前端传来的 role/status。谁都能注册成管理员的话,权限体系就形同虚设了。

---

## 第三章 本课最有价值的部分：Service 层重构

### 3.1 为什么要把业务逻辑从 api 层抽出来

之前登录逻辑写在 api 函数里,问题:

- 业务代码和 HTTP 代码混在一起,越长越乱
- 同一个能力(登录)被多处需要时只能复制粘贴 —— 我们实际遇到了:`/token`(Swagger 用）里复制了一份登录逻辑,改一处漏一处的风险

重构后的分层:

```
api 层(服务员):接请求、调 service、包响应
service 层(厨师):查库、验密码、签 token,不碰任何 HTTP 概念
```

**判断一段代码该放哪层,问一句:"换成命令行/Agent 工具来用这个功能,这段代码还能用吗?"**

- 能(查库、验密码、签 token)→ service 层
- 不能(解析请求体、包 HTTP 响应)→ api 层

### 3.2 重构前后的 api 层对比

```python
# ── 重构前:业务全在接口里 ──
@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(...)
    if not user or not verify_password(...): ...
    token = create_access_token(...)
    return {...}

# ── 重构后:两行 ──
@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    result = auth_services.login(db, data)
    return Response.success(message="登录成功", data=result)
```

**这段代码怎样执行：** 这段是分层前后的结构对比，省略号是讲解占位，不能直接当成完整可运行代码。重构后 API 调用 auth_services.login，服务函数继续执行原有查账号、验密码、验状态、签发 token 的顺序。改变的是职责位置，接口路径不必因此变化。


### 3.3 重构的回报：/token 端口的复用

```python
@router.post("/token", include_in_schema=False)
def login_for_docs(form: OAuth2PasswordRequestForm = Depends(), db = Depends(get_db)):
    data = LoginRequest(username=form.username, password=form.password)  # ① 格式翻译
    result = auth_services.login(db, data)                               # ② 复用同一个 service
    return {"access_token": result.token, "token_type": "bearer"}        # ③ OAuth2 格式包装
```

**按执行顺序拆解：**

#### 第一步：接收 OAuth2 表单

```python
form: OAuth2PasswordRequestForm = Depends()
```

Swagger 的 Authorize 使用表单字段，不是普通登录接口接收的 JSON。FastAPI 的表单依赖读取 username/password；表单和上传需要 python-multipart 依赖。

#### 第二步：转换为统一的请求模型

```python
data = LoginRequest(username=form.username, password=form.password)
```

将表单中两个字段重新组装成 LoginRequest，使普通 JSON 登录与文档登录可以共用同一服务函数，而不用各写一套密码判断。

#### 第三步：复用登录逻辑并按 OAuth2 返回

```python
result = auth_services.login(db, data)
return {"access_token": result.token, "token_type": "bearer"}
```

result 是 LoginResponse 模型，包含 token 与用户；这里挑出 token 放在 OAuth2 要求的顶层 access_token。这个接口不是统一业务 Response 的嵌套格式。include_in_schema=False 隐藏该接口的文档条目，但不会取消路径。

**把结果连起来：** 两个不同输入格式适配到同一业务流程，输出再按各自调用方约定包装。


**同一种能力,两种接口包装,业务逻辑只有一份。** 以后改登录规则,只改 service 一处,两个入口同时生效。

---

## 第四章 踩坑实录(本课实际发生)

| 坑 | 症状 | 原因/解法 |
|---|---|---|
| 注册页密码框上方多出"username"文字 | 页面显示游离文本 | `</el-form-item>` 闭合标签被拆行,`username` 成了标签外文本 |
| `import Login from './Login.vue'` | 冗余/潜在风险 | VSCode 自动导入刺客,删掉 |
| `router is not defined` | 注册成功但不跳转 | 用了 router 没 import |
| `RegisterRequest is not defined` | NameError | 新增 register 函数时忘了同步 import |
| 注册 admin 没有"账户已存在"提示 | 请求根本没到后端 | **后端没启动!**(8000 没监听)—— 排查先查服务活没活 |
| service 文件从 api 复制后一堆 HTTP import | 分层不干净 | 本项目 service 保留业务和数据处理，不需要为路由收发导入 Request/Response 等 HTTP 对象 |

**调试顺序口诀:服务活没活 → 请求发没发 → 后端返回啥 → 前端处理没。**

---

## 第五章 验证清单

以下命令是测试步骤，密码是占位值；本次文档修订不代表重新执行了这些写数据库操作。

```bash
# 1. 注册新用户
curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test01","password":"YOUR_TEST_PASSWORD"}'
# 预期:{"code":200,...}

# 2. 重复注册 → 应报"账户已存在"
curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test01","password":"YOUR_TEST_PASSWORD"}'

# 3. 数据库验证(密码是 60 位哈希,不是明文)
# SELECT id, username, role, status, CHAR_LENGTH(password) FROM users;

# 4. 新用户登录 → 应拿到 token
curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test01","password":"YOUR_TEST_PASSWORD"}'
```

前端页面验证:注册页空表单 → 红框;两次密码不一致 → 提示不一致;注册 bbb → 成功跳登录页 → 用 bbb 登录 → 进系统。

---

## 第六章 可改进点(知道就好,不急着改)

1. **注册成功的 message 写成了"登录成功喵"**(api/auth.py register 里)—— 应为"注册成功",复制粘贴痕迹
2. **"账户已存在"没传 code** → 用了默认值 500,语义上 400 更合适(`code=400`)
3. **查重靠"先查再插"**,并发极端情况下可能两人同时注册同名 —— 生产做法是数据库加唯一索引 `UNIQUE(username)` 兜底
4. `db.flush()` 写在 `commit()` 后面没有意义(flush 应该在 commit 前)

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| service 层 | 业务逻辑所在地,不碰 HTTP 概念 |
| 组合式函数(Composable) | use 开头的函数,打包可复用逻辑(useUser) |
| 自定义校验器(validator) | Element Plus 里 callback() 通过 / callback(Error) 失败 |
| 短路求值 `or` | `a or b`:a 为空/None 时取 b |
| 唯一索引 | 数据库层面的"不许重复"约束,比代码查重更可靠 |
| SPA 跳转 | router-link,不刷新页面只换组件 |

---

## 本章自检清单

- [ ] 能画出 api 层 / service 层的职责分工
- [ ] 能解释"换成命令行调用还能用吗"这个判断标准
- [ ] 能写出自定义校验器(callback 协议)
- [ ] 能解释为什么注册接口不能接收前端的 role 字段
- [ ] 能解释 `name or data.username` 的行为
- [ ] 能说出 `/token` 和 `/login` 如何共享同一个 service
- [ ] 知道密码入库必须是哈希
- [ ] 能独立完成"注册 → 登录"全流程验证
