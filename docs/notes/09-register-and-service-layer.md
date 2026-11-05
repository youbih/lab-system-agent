# 开发注册功能 + 后端 Service 层重构

> 对应课程:第 09 节
> 对应项目:`agent-lab/lab-system-agent`
> 涉及文件:
> - 前端:`src/views/Register.vue`、`src/api/auth.js`
> - 后端:`app/schemas/auth.py`、`app/api/auth.py`、`app/services/auth_services.py`(新增!)
> 阅读时间:约 30 分钟

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
   ├─ 前置检查:CORS 预检(后端白名单放行 5173)
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

## 第一章 前端:注册页(Register.vue)

### 1.1 和登录页的关系

注册页 = 登录页的"加长版":多一个确认密码框 + 自定义校验规则。整体结构(container/box/form）完全一样。

### 1.2 核心新增:自定义校验器(两次密码一致)

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

**理解 callback 的约定**:`callback()` = 通过;`callback(new Error('...'))` = 失败并显示消息。这是 Element Plus 校验器的固定协议。

### 1.3 提交逻辑(沿用上节课的最佳实践)

```javascript
const register = async () => {
  const valid = await formRef.value.validate().catch(() => false)  // 校验
  if (!valid) return                                               // 不过就 return

  loadingValue.value = true
  try {
    const res = await registerApi(form)
    if (res.code === 200) {
      ElMessage.success('注册成功')
      await router.push('/login')      // 注册成功 → 跳登录页
    }
  } finally {
    loadingValue.value = false
  }
}
```

这套"校验前置 + 提前 return + try/finally 复位"就是上次优化出来的模板，直接复用。

### 1.4 `<router-link>` 替代 `<a>`

```html
<!-- 以前:整页刷新 -->
<a href="/login">登录</a>

<!-- 现在:SPA 内部跳转,不刷新 -->
<router-link to="/login">登录</router-link>
```

区别:`<a>` 会让浏览器重新加载整个应用（白闪 + 状态丢失）;`<router-link>` 只切换组件（无刷新、毫秒级）。单页应用（SPA）里页面间跳转永远用 `router-link`。

---

## 第二章 后端:注册接口的三层

### 2.1 契约层:RegisterRequest(schemas/auth.py)

```python
class RegisterRequest(BaseModel):
    username: str
    password: str
    name: str | None = None      # 可选字段:不给就是 None
```

`str | None = None` 的含义:类型可以是字符串或 None,默认 None —— 前端的表单里没有"姓名"字段也能通过校验。

### 2.2 接口层:api/auth.py

```python
@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    """注册"""
    auth_services.register(db, data)      # 业务全外包
    return Response.success(message="注册成功")
```

接口层只剩两行:调 service、包响应。这就是分层的目标状态。

### 2.3 业务层:services/auth_services.py(本课核心)

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

四个知识点:

| 知识点 | 说明 |
|---|---|
| 先查重 | 用户名唯一的业务规则,靠"先查一遍"实现(更严谨的做法是数据库加唯一索引兜底) |
| 密码必哈希 | `hash_password()` 上场,库里存的是 60 位 bcrypt 哈希 |
| `or` 兜底 | `data.name or data.username`:name 为空/None 时用 username —— Python 的短路特性 |
| 默认值 | role/status 在服务端写死,不接受前端传 —— **安全设计**:否则用户可以自己注册成 admin |

> ⚠️ 安全要点:注册接口**绝不能**接收前端传来的 role/status。谁都能注册成管理员的话,权限体系就形同虚设了。

---

## 第三章 本课最有价值的部分:Service 层重构

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

### 3.3 重构的回报:/token 端口的复用

```python
@router.post("/token", include_in_schema=False)
def login_for_docs(form: OAuth2PasswordRequestForm = Depends(), db = Depends(get_db)):
    data = LoginRequest(username=form.username, password=form.password)  # ① 格式翻译
    result = auth_services.login(db, data)                               # ② 复用同一个 service
    return {"access_token": result.token, "token_type": "bearer"}        # ③ OAuth2 格式包装
```

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
| service 文件从 api 复制后一堆 HTTP import | 分层不干净 | service 层不该 import Request/Response/路由相关 |

**调试顺序口诀:服务活没活 → 请求发没发 → 后端返回啥 → 前端处理没。**

---

## 第五章 验证清单

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
