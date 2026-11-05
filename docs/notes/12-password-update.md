# 开发用户修改密码功能

> 对应课程：第 12 节
> 对应项目：`agent-lab/lab-system-agent`
> 涉及文件：
> - 后端：`app/schemas/user.py`、`app/api/user.py`、`app/services/user_services.py`
> - 后端复用：`app/utils/password.py`、`app/dependencies/auth.py`、`app/common/exceptions.py`
> - 前端：`src/views/Password.vue`（新增）、`src/api/user.js`、`src/layouts/Layout.vue`、`src/router/index.js`
>
> 验证方式：curl 调用接口 + 浏览器表单联调
> 阅读时间：约 30 分钟

---

## 第零章 这节课干了什么

开发“当前登录用户修改自己的密码”的完整功能：输入原密码、新密码和确认密码，提交后由后端验证并保存，前端提示成功并跳转登录页。

```text
登录获取 token
    ↓
打开修改密码页面，填写表单
    ↓
前端检查必填项、两次新密码是否一致
    ↓
携带 token 提交原密码和新密码
    ↓
后端检查原密码正确、新旧密码不同
    ↓
新密码做哈希，提交数据库修改
    ↓
前端提示成功，清除本地登录信息，跳转登录页
```

本课继续使用上一课的表单开发模式，但不回显密码，也不需要修改数据库表结构：直接更新已有 `users.password` 字段。

---

## 第一章 后端：请求参数与接口

### 1.1 schemas/user.py：定义请求参数

```python
class PasswordUpdateRequest(BaseModel):
    """修改密码的请求参数"""
    old_password: str
    new_password: str
```

两个字段都没有默认值，因此都是必填字符串。请求示例：

```json
{
  "old_password": "当前密码",
  "new_password": "新密码"
}
```

这里不需要 `user_id`，因为修改谁由 token 决定；也不需要 `confirm_password`，因为当前接口将“两次新密码一致”的交互检查放在前端完成。

注意：当前 schema 只规定类型和必填，没有配置长度、复杂度等额外规则，不要把尚未实现的校验当成已有功能。

### 1.2 api/user.py：接收请求并调用业务层

需要引入请求模型：

```python
from app.schemas.user import PasswordUpdateRequest
```

接口代码：

```python
@router.put("/password")
def update_password(
    data: PasswordUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_services.update_password(db, current_user, data)
    return Response.success()
```

路由路径由三部分组成：

```text
api/__init__.py 的 /api
    + user.py 的 /user
    + 接口的 /password
    = PUT /api/user/password
```

| 参数 | 来源与作用 |
|---|---|
| `data` | FastAPI 按 `PasswordUpdateRequest` 解析、校验请求体 |
| `current_user` | 鉴权依赖解析 token，并从数据库查询当前用户 |
| `db` | 数据库会话，用于提交本次修改 |

接口层负责接收请求、获取依赖、调用服务和包装响应。业务判断放在 `services` 中。

---

## 第二章 后端：修改密码的业务逻辑

### 2.1 services/user_services.py

```python
from app.utils.password import verify_password, hash_password
from app.common.exceptions import BusinessException


def update_password(db: Session, user: User, data: PasswordUpdateRequest):
    """修改用户的密码"""
    if not verify_password(data.old_password, user.password):
        raise BusinessException(message="原密码错误")

    if data.old_password == data.new_password:
        raise BusinessException(message="新密码不能与旧密码一致")

    user.password = hash_password(data.new_password)
    db.commit()
```

执行顺序：

```text
原密码验证通过？
    ↓ 是
新密码与原密码不同？
    ↓ 是
生成新密码哈希 → 赋值 → commit
```

**先判断原密码，再判断新旧密码是否相同。** 如果输入的原密码本身不正确，即使两个输入框填写相同，也会先返回“原密码错误”。

### 2.2 hash_password 和 verify_password 在哪里

它们定义在 `backend/app/utils/password.py`：

```python
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"), hashed_password.encode("utf-8")
    )
```

| 函数 | 用途 |
|---|---|
| `hash_password` | 将明文密码转换成带盐的 bcrypt 哈希，用于存入数据库 |
| `verify_password` | 检查输入的明文密码是否匹配数据库中的哈希 |

密码哈希不可逆，验证时不需要也不能“解密出原密码”。由于使用随机盐，同一明文重新做哈希可能得到不同结果，因此不能用“重新生成哈希再直接比较字符串”代替 `verify_password`。

### 2.3 BusinessException 的导入与用途

```python
from app.common.exceptions import BusinessException
```

业务规则不满足时抛出异常，由项目已注册的异常处理器转换成统一响应。前端的请求拦截器读取 `code`、`message` 并显示提示。

当前 `BusinessException` 默认业务码为 `500`，其处理器返回的 HTTP 状态码为 `200`。**HTTP 状态码和 JSON 中的业务 `code` 是两回事**，调试时要同时查看响应内容。

### 2.4 commit 后需要 refresh 吗

这里不需要：

```python
user.password = hash_password(data.new_password)
db.commit()
```

`commit()` 提交数据库事务；`refresh(user)` 是重新查询数据库，把最新字段加载到对象中。本接口没有继续读取或返回更新后的用户字段，所以没有必要额外刷新。

如果后续需要返回数据库生成或更新的字段，再根据需要读取或刷新。方法名是 `refresh`，不是 `reflash`。

---

## 第三章 前端：API 请求封装

在 `src/api/user.js` 新增：

```javascript
export function updatePassword(data) {
  return request({
    url: '/api/user/password',
    method: 'put',
    data
  })
}
```

该文件已有：

```javascript
import request from '@/utils/request'
```

前端 API 层封装“请求发到哪里、用什么方法、发送哪些数据”。底层 `utils/request.js` 再统一处理 Axios 配置、token 和响应提示。

当前 Vite 开发代理将 `/api` 请求转发到后端 `http://127.0.0.1:8000`。

---

## 第四章 前端：修改密码页面 Password.vue

### 4.1 页面结构

```text
el-card（修改密码卡片）
└── el-form（绑定 form 和 rules）
    ├── 原密码：oldPassword
    ├── 新密码：newPassword
    ├── 确认密码：confirmPassword
    └── 保存修改按钮：handleSubmit
```

输入框使用 `type="password"` 隐藏显示内容，`show-password` 提供切换可见性的按钮。

### 4.2 导入与响应式数据

```javascript
import { ref, reactive } from 'vue'
import { updatePassword } from '@/api/user'
import { ElMessage } from 'element-plus'
import { logout } from '@/utils/auth'
import router from '@/router'

const submitting = ref(false)
const formRef = ref()
const form = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})
```

| 变量 | 作用 |
|---|---|
| `form` | 保存三个输入框的值 |
| `formRef` | 保存表单组件实例，调用它的 `validate()` |
| `submitting` | 控制保存按钮的加载状态 |

`ref` 定义的值在 JavaScript 中通过 `.value` 访问；模板中通常自动解包。`reactive` 对象直接通过 `form.oldPassword` 等属性访问。

### 4.3 表单绑定：model、rules、prop、v-model

```vue
<el-form ref="formRef" :rules="rules" :model="form">
  <el-form-item label="原密码" prop="oldPassword">
    <el-input v-model="form.oldPassword" type="password" show-password />
  </el-form-item>
</el-form>
```

| 写法 | 作用 |
|---|---|
| `:model="form"` | 指定表单数据对象 |
| `:rules="rules"` | 指定表单校验规则 |
| `ref="formRef"` | 获取表单组件实例 |
| `prop="oldPassword"` | 将表单项关联到对应数据字段和规则 |
| `v-model="form.oldPassword"` | 输入框与字段双向绑定 |

`form` 的字段名、`rules` 的键名和表单项的 `prop` 要对应。

### 4.4 校验：必填与两次新密码一致

当前页面的自定义校验器：

```javascript
const validatePass = (rule, value, callback) => {
  if (value === '') {
    callback(new Error('请确认密码'))
  } else {
    if (value !== form.newPassword) {
      callback(new Error('两次密码输入不一致'))
    } else {
      callback()
    }
  }
}

const rules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [{ required: true, message: '请输入新密码', trigger: 'blur' }],
  confirmPassword: [{ validator: validatePass, message: '请确认新密码', trigger: 'blur' }]
}
```

- `value`：本次校验的确认密码值。
- `callback(new Error(...))`：表示校验失败。
- `callback()`：表示校验通过。
- `trigger: 'blur'`：输入框失去焦点时触发；提交时调用 `validate()` 也会检查表单。

上面保留的是当前源码。自定义校验规则中还写了固定 `message`，可能使展示的信息使用固定文案。如果后续希望展示校验器内不同的错误文案，可以考虑移除该固定 `message`；这是可调整点，本课没有改动。

前端当前没有单独检查“原密码与新密码相同”，所以**输入相同值后离开输入框，不一定立即提示**。后端会在提交后判断，前提是请求确实发出且原密码正确。

### 4.5 提交：校验、请求、成功后退出

```javascript
const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const res = await updatePassword({
      old_password: form.oldPassword,
      new_password: form.newPassword
    })
    if (res.code === 200) {
      ElMessage.success('修改密码成功')
      logout()
      await router.push('/login')
    }
  } finally {
    submitting.value = false
  }
}
```

几个要点：

1. 校验失败就 `return`，不发请求。
2. 前端的驼峰字段要映射成后端的下划线字段。
3. `confirmPassword` 不发送给当前接口。
4. 成功后清除本地登录信息，要求用户重新登录。
5. `finally` 负责结束加载状态，即使请求报错也会执行；它不等同于 `catch`，不会自动处理或吞掉异常。

当前 `logout()` 清除的是浏览器中保存的 token 和用户信息，不会自动撤销其他位置持有的旧 JWT。不要将“前端跳回登录页”等同于“所有旧 token 都失效”。

---

## 第五章 菜单入口与页面路由

### 5.1 Layout.vue：增加修改密码入口

```vue
<el-dropdown @command="handleCommand">
  <!-- 头像和用户名区域 -->
  <template #dropdown>
    <el-dropdown-menu>
      <el-dropdown-item command="profile">个人信息</el-dropdown-item>
      <el-dropdown-item command="password">修改密码</el-dropdown-item>
      <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
    </el-dropdown-menu>
  </template>
</el-dropdown>
```

```javascript
const handleCommand = (command) => {
  if (command === 'profile') {
    router.push('/manager/profile')
  } else if (command === 'password') {
    router.push('/manager/password')
  } else if (command === 'logout') {
    logout()
    router.push('/login')
  }
}
```

`command="password"` 是菜单项传出的值；父组件通过 `@command` 接收，再由 `router.push` 发起跳转。只写函数但不绑定事件，点击菜单不会执行该函数。

本课还删除了演示用的 `ElMessage(\`click on item${command}\`)`，因此点击菜单不再弹出 `click on itemprofile` 提示。

### 5.2 router/index.js：注册 Password 页面

在 `/manager` 的 `children` 中新增：

```javascript
{
  path: 'password',
  name: 'Password',
  component: () => import('@/views/Password.vue')
}
```

匹配 `/manager/password` 后，页面显示在 `Layout.vue` 的 `<router-view />` 中，顶部栏和侧边栏继续显示。

| 名称 | 含义 |
|---|---|
| `Password.vue` | 文件名 |
| `name: 'Password'` | 路由名称 |
| `/manager/password` | 前端页面地址 |
| `/api/user/password` | 后端请求地址 |

本课也把个人信息页统一命名为 `Profile.vue`，对应导入路径改为 `@/views/Profile.vue`；网址仍是 `/manager/profile`。Linux 文件名区分大小写，文件和导入路径要一致。

---

## 第六章 与个人信息页面的共同模式

觉得 `Profile.vue` 和 `Password.vue` 相似，是因为两者都是编辑表单。

| 环节 | Profile.vue | Password.vue |
|---|---|---|
| 初始数据 | 请求用户资料并回显 | 空密码表单，不回显密码 |
| 页面结构 | 卡片、表单、输入框、保存按钮 | 卡片、表单、输入框、保存按钮 |
| 校验 | 名称必填、邮箱和手机号格式 | 密码必填、确认密码一致 |
| 接口 | `updateUserInfo` | `updatePassword` |
| 成功后 | 同步共享用户信息，留在页面 | 清除本地登录信息，跳转登录页 |

本项目新增类似功能时，可以按下面的流程思考：

```text
后端定义 schema、接口、service 并验证
    ↓
前端 api 封装请求
    ↓
编写 Vue 页面：数据 → 校验 → 提交 → 结果处理
    ↓
Layout 提供入口 + router 注册页面
    ↓
浏览器联调
```

这是方便理解的开发顺序，不是框架强制规定。详细说明见 [前后端分层与功能开发流程](./前后端分层与功能开发流程.md)。

---

## 第七章 curl 验证与本课实测记录

### 7.1 登录获取 token

以下是可替换参数的示例，不保存实际 token：

```bash
curl -sS -X POST 'http://localhost:8000/api/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{"username":"测试账号","password":"当前密码"}'
```

复制响应中的 `data.token`，用于下一个请求。

### 7.2 提交修改密码

这条请求会实际修改当前 token 对应账号的密码：

```bash
curl -sS -X PUT 'http://localhost:8000/api/user/password' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer 替换为登录获取的token' \
  -d '{"old_password":"当前密码","new_password":"新密码"}'
```

本课用户实际调用接口后，已收到：

```json
{"code":200,"message":"请求成功","data":null}
```

这表明修改接口执行成功。对话中尚未记录“旧密码登录失败、新密码登录成功”的实际结果，这一步作为后续验证保留，不能当成已经实测完成。

### 7.3 建议验证的分支

| 场景 | 预期 |
|---|---|
| 正确原密码 + 不同新密码 | 修改成功 |
| 错误原密码 | 提示“原密码错误” |
| 正确原密码 + 相同新密码 | 提示“新密码不能与旧密码一致” |
| 未携带 token | 鉴权失败 |
| 确认密码与新密码不同 | 前端阻止提交 |
| 修改成功后使用旧密码登录 | 登录失败 |
| 修改成功后使用新密码登录 | 登录成功 |

重复测试时，原密码必须使用账号**当前实际的密码**，不能一直使用修改前的旧值。

---

## 第八章 踩坑实录（本课实际遇到）

| 问题 | 原因或检查结果 | 处理方式 |
|---|---|---|
| `old_password: set` | 把字符串类型误写为集合类型 | 已改为 `old_password: str` |
| 不知道 `hash_password` 在哪里 | 密码工具已在项目中定义 | 从 `app.utils.password` 导入 |
| 不知道如何导入 `BusinessException` | 它是项目自定义异常 | 从 `app.common.exceptions` 导入 |
| curl 返回 404 | 运行服务的 OpenAPI 清单没有修改密码接口，但磁盘代码已有定义 | 重启后端加载最新代码，再调用成功 |
| `import {ref reactive}` 报错 | 两个导入名称之间缺少逗号 | 写成 `import { ref, reactive } from 'vue'` |
| `const from reactive(...)` 报错 | 缺少赋值等号；表单变量还容易与 `form` 混写 | 写成 `const form = reactive(...)` 并统一引用 |
| 调用 `updatePassword` 找不到函数 | 页面缺少导入 | 已补 `import { updatePassword } from '@/api/user'` |
| 成功分支还使用其他外部名称 | 缺少 `ElMessage`、`logout`、`router` 导入 | 已按实际使用补齐 |
| `/manager/passwprd` 无匹配路由 | 警告中的地址有拼写错误；检查时源码已使用 `password` | 进入正确地址、清空旧日志、重新操作确认是否复现 |
| 新旧密码相同但未看到提示 | 前端没有这项即时校验；当时页面还缺少请求函数导入 | 补齐导入，确认请求发出，再查看后端响应；不能把路由警告直接当作业务判断失败的原因 |
| 个人信息菜单点击不跳转 | 下拉组件未绑定 `@command` | 已补事件绑定 |
| 出现 `click on itemprofile` | 事件函数保留演示用消息提示 | 已删除该提示语句 |
| URL 已是 `/login`，画面仍是旧页 | 刷新后恢复，用户未看到控制台错误，未确认具体根因 | 先重新走完整登录退出流程；再次出现时记录新日志，不直接认定原因 |

### 接口 404 的定位方法

打开 `http://localhost:8000/docs`，或者读取：

```bash
curl -sS --max-time 5 'http://localhost:8000/openapi.json'
```

确认当前服务是否注册了 `/api/user/password`。源码里有接口，并不代表旧进程已经加载了它。

停止旧服务后，在原来能正常运行后端的 Python 环境中启动：

```bash
cd /work/2025/liusiyu/agent-lab/lab-system-agent/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`--reload` 用于开发期间监听代码变化。集群上不同机器的 `localhost` 分别指向各自机器；curl 要在运行后端的节点执行，或使用正确的访问地址/端口转发。

---

## 第九章 常见问题

**Q1：为什么改密码不新增 model？**

因为 `User` 已经有 `password` 列，本次只是更新该列，不是新增数据结构。

**Q2：前端已经校验了，为什么后端还要判断？**

前端校验改善交互，用户也可以绕过页面直接用 curl 请求。原密码检查、新旧密码比较和数据库更新由后端负责。

**Q3：为什么确认密码不存进数据库？**

确认密码用于减少输入错误，不是需要保存的业务字段。数据库只保存最终新密码的哈希。

**Q4：为什么页面没有调用接口就不能看到后端的业务提示？**

后端判断只在收到请求后执行。页面缺少导入、前端校验失败或提交事件未绑定，都可能使请求没有发出。排查时同时看 Console 和 Network。

**Q5：博主输入函数后为什么自动出现 import？**

可能使用了编辑器的导入补全，也可能配置了构建工具自动导入。若顶部出现显式 `import`，通常是编辑器补全；若源码没有导入仍能使用，需要检查项目是否有相应自动导入配置。本项目当前这些名称使用显式导入。

可了解 Vue (Official)、`unplugin-auto-import` 和 `unplugin-vue-components`；本课没有安装或配置这些新工具。

**Q6：修改密码后跳转登录页，旧 token 一定不能用了吗？**

不能这样推断。当前代码只清除本地存储，没有实现所有已签发 JWT 的统一撤销。这是当前实现的边界。

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| 密码哈希 | 将明文密码转换为不可逆的验证数据 |
| 盐（salt） | 哈希时加入的随机数据，使同一密码可以得到不同哈希 |
| `commit` | 提交数据库事务，使修改持久化 |
| `refresh` | 重新查询数据库，刷新 ORM 对象字段 |
| 自定义校验器 | 根据业务规则检查表单值的函数 |
| `v-model` | Vue 的数据双向绑定 |
| `prop` | 本课表单项中用于关联字段与校验规则的属性 |
| `router-view` | 匹配到的路由组件显示的位置 |
| 业务码 | 响应 JSON 中的 `code`，与 HTTP 状态码分开判断 |
| OpenAPI | 描述当前后端接口、参数和响应结构的文档格式 |

---

## 本章自检清单

- [ ] 能写出修改密码请求的两个字段及其类型
- [ ] 能解释为什么修改自己的密码不接收 `user_id`
- [ ] 知道 `hash_password`、`verify_password` 和 `BusinessException` 的导入位置
- [ ] 能解释先验证原密码、再比较新旧密码的顺序
- [ ] 能解释为什么本接口只需要 `commit`，不需要 `refresh`
- [ ] 能在前端 API 层封装 `PUT /api/user/password`
- [ ] 能解释 `form`、`formRef`、`rules`、`submitting` 的作用
- [ ] 能说明前端驼峰字段与后端下划线字段的对应关系
- [ ] 知道使用外部函数前需要导入，除非项目明确配置自动导入
- [ ] 能把菜单 command、事件处理函数、router 路由和 Vue 页面连接起来
- [ ] 能区分 `/manager/password` 与 `/api/user/password`
- [ ] 能通过 `/docs` 或 `/openapi.json` 检查运行服务的接口是否更新
- [ ] 已补做旧密码登录失败、新密码登录成功的验证
- [ ] 知道当前退出逻辑清除本地登录信息，并未撤销全部旧 JWT
