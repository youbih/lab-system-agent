# Vue 封装 axios 并实现前后端联调

> 对应课程:第 08 节
> 对应项目:`agent-lab/lab-system-agent/frontend`
> 涉及文件:`src/utils/request.js`、`src/utils/auth.js`、`src/utils/user.js`、`src/api/auth.js`、`src/router/index.js`、`src/views/Login.vue`
> 阅读建议：按小节阅读，配合项目源码与示例理解执行过程。

---

## 阅读说明：代码版本与讲解方式

这份笔记根据原课程记录与当前项目源码整理，不代表拥有每节课的完整历史快照。保留原记录中的课程重点和排错经历；历史代码、当前实现、建议改进会分别说明。未在对话或原记录中确认的测试，不写成新增的实测结论。

代码按“完整片段 → 按执行顺序拆解 → 输入/返回值例子 → 页面或接口效果”阅读。仅有一两行的导入、配置或重复片段使用紧接代码的说明，避免反复展开相同逻辑。

**本节版本对应：** 保留假登录到真实请求的历史对照；登录函数、路由守卫和用户状态模块的详细讲解使用当前源码，并明确后续增加的能力。当前 Vite 配置可将同源 /api 代理到后端，不能把所有请求都描述成浏览器直连跨域。

---

## 第零章 这节课在干什么

前面几节课,前端和后端是各自独立的"孤岛":

```
前端:页面能看,但数据是写死的
后端:接口能调,但只能用 curl/docs 玩
```

这节课的任务就是**把两个孤岛连起来**——让登录页点一下按钮,真的去调后端的登录接口,拿到 token,存好,跳转主页。

但"连起来"不是简单地在页面里写个请求就完事。这节课的核心价值在于**怎么连得规范、连得可维护**,为此引入了三层结构:

```
页面(Login.vue)          ← 只管:用户点了登录,我就调 loginApi
   ↓
API 层(api/auth.js)      ← 只管:登录接口的地址、方法、参数
   ↓
请求层(utils/request.js) ← 只管:怎么发请求(贴 token、统一处理错误)
   ↓
后端 FastAPI
```

---

## 第一章 为什么不直接在页面里用 axios

先看不封装的写法(裸用 axios):

```javascript
// 如果每个页面都这样写:
import axios from 'axios'

const res = await axios.post('http://localhost:8000/api/auth/login', form, {
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
})
if (res.data.code === 200) { ... }
else if (res.data.code === 401) { /* 跳登录页 */ }
```

**这段代码怎样执行：** 这是“在页面直接使用 Axios”的对照示例：页面自己拼 URL、设置认证头并解析多层返回。它可以工作，但每个页面都这样写会重复配置。本节把它拆成页面、api 函数和公共 request 三层；不要把对照里的临时写法复制回当前页面。


问题:

| 问题 | 后果 |
|---|---|
| 后端地址硬编码在每个页面 | 换环境要改几十处 |
| 每个请求手动贴 token | 重复劳动,漏一个就 401 |
| 每个响应手动判断 code、处理 401 | 业务代码被淹没在样板里 |
| 接口地址散落各页面 | 后端改路径,前端全文搜索替换 |

**封装的目的:把"每个请求都要做的事"集中到一处,页面只关心业务。**

---

## 第二章 请求层：request.js(本课核心)

这个文件是前端所有请求的"总出口"。分三部分看。

### 2.1 创建 axios 实例

```javascript
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",   // 后端地址,从环境变量读
  timeout: 30000                                 // 30 秒无响应就放弃
})
```

**按执行顺序拆解：**

#### 第一步：创建独立请求实例

```javascript
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 30000
})
```

axios 是导入的库，create 返回配置独立的实例。service 是我们命名的变量，后续拦截器注册在它上面。此行只创建请求工具，还没有向后端发请求。

#### 第二步：确定地址和超时

```javascript
baseURL: import.meta.env.VITE_API_BASE_URL || ""
```

配置了后端根地址时，接口路径与它组合；空字符串时使用浏览器当前源，当前开发环境再由 Vite 的 /api 代理转发。timeout 的单位是毫秒，30000 表示请求超时阈值 30 秒。

#### 第三步：导出供 api 模块使用

```javascript
export default service
```

当前源码在文件末尾默认导出实例。api 文件可将它导入为 request；变量名不同，但仍指向同一个已注册拦截器的实例。VITE_ 配置可在浏览器代码中读取，不能放服务器秘密。

**把结果连起来：** 建立一个公共请求实例，把配置与通用处理放到页面外。


- **`axios.create()`**:不是直接用全局 axios,而是造一个"定制版实例"。好处:配置独立,不影响别处
- **`baseURL`**:所有请求的公共前缀。接口里只写 `/api/auth/login`,实际发出去的是 `baseURL + url`
- **`import.meta.env.VITE_API_BASE_URL`**:读 `.env.development` 里的配置(Vite 规定必须以 `VITE_` 开头才暴露给前端)
  - ⚠️ 改 `.env` 后必须重启 `npm run dev` 才生效(热更新不管环境变量)
- **`timeout`**:防止请求永远卡住(我们调试时就是靠它暴露问题的)

### 2.2 请求拦截器：出门前的"安检"

```javascript
service.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (err) => Promise.reject(err)
)
```

**按执行顺序拆解：**

#### 第一步：注册请求前回调

```javascript
service.interceptors.request.use((config) => {
```

这不是立即发送请求，而是告诉 Axios：以后使用这个实例发请求前，先执行回调。config 是本次请求配置，含 URL、方法、数据和请求头。

#### 第二步：读取当前保存的 token

```javascript
const token = getToken()
```

getToken 来自项目 utils/auth.js，读取 localStorage。每个请求前都重新读取，所以登录后保存的新 token 可以用于后续请求。

#### 第三步：有 token 才添加认证头

```javascript
if (token) {
  config.headers.Authorization = `Bearer ${token}`
}
```

模板字符串将 token 拼成 Bearer 认证头；没有 token 时跳过。登录接口也可能附带旧 token，但后端是否使用它取决于该接口的依赖。不要把实际 token 写死在源码。

#### 第四步：把修改后的配置交还 Axios

```javascript
return config
```

返回配置后，Axios 才能继续发送请求。第二个回调中的 Promise.reject(err) 把配置阶段的失败向调用链传播，不代表把异常变成成功数据。

**把结果连起来：** 页面不用逐次拼认证头，所有通过这个实例发送的请求都会经过同一处理。


**每个请求发出之前**,自动执行一次:从 localStorage 取 token,有就贴到请求头。

效果:任何页面发任何请求,都不用再手写 `Authorization` 头 —— 这就是"集中处理"的威力。

### 2.3 响应拦截器：进门前的"分拣台"

```javascript
service.interceptors.response.use(
  (res) => {
    const data = res.data          // 剥掉 axios 外壳,拿到后端 JSON
    if (data.code !== 200) {
      ElMessage.error(data.message || '请求失败')   // 统一弹错误提示
      if (data.code === 401) {
        logout()                   // 清空本地登录状态
        router.push('/login')      // 踢回登录页
        return Promise.reject(data)
      }
    }
    return data                    // 正常:把数据交给调用方
  },
  (err) => {
    // HTTP 层面的错误(网络断、500 等)
    if (err.response) {
      if (err.response.status === 401) {
        logout()
        router.push('/login')
      } else {
        ElMessage.error(err.response.data?.message || '请求失败')
      }
    } else {
      ElMessage.error('网络异常,请检查后端服务')
    }
    return Promise.reject(err)
  }
)
```

**按执行顺序拆解：**

#### 第一步：取得后端业务响应

```javascript
const data = res.data
```

这一步的 res 是 Axios 响应，res.data 才是后端 JSON。假设后端 JSON 是 {code:200,data:{token,user}}，这里的 data 就是整个 JSON；不是只取出了 token。

#### 第二步：检查业务码并显示错误

```javascript
if (data.code !== 200) {
  ElMessage.error(data.message || "请求失败")
}
```

HTTP 请求成功不等于业务成功。例如账号密码错误可以使用 HTTP 200、业务码 400。当前实现对非 401 业务错误提示后仍 return data，页面必须通过 res.code === 200 判断是否进入成功分支。

#### 第三步：对业务 401 清理登录状态

```javascript
if (data.code === 401) {
  logout()
  router.push("/login")
  return Promise.reject(data)
}
```

调用自定义 logout 删除本地凭据，Vue Router 跳转登录页，reject 让等待该请求的页面走异常路径。当前实际源码还会额外显示一条登录失效提示。

#### 第四步：把业务 JSON 返回页面

```javascript
return data
```

所以页面 await loginApi(form) 得到的是后端 JSON，可以读取 res.code、res.data。若漏掉 return，Promise 会以 undefined 完成，页面随后读取字段就可能报错。

#### 第五步：处理 HTTP 或网络错误

```javascript
if (err.response) {
  // 按 err.response.status 判断 HTTP 错误
} else {
  ElMessage.error("网络异常,请检查后端服务")
}
return Promise.reject(err)
```

第二个回调处理 Axios 判为失败的请求。存在 response 通常表示收到非成功 HTTP 响应；HTTP 401 也会清理并跳转。没有 response 时可能是断网、超时或浏览器阻止读取等，当前文案统一显示网络异常。reject 继续传播，页面 finally 仍可收尾。

**把结果连起来：** 拦截器统一提示并转换响应结构，但不替代页面的成功判断和异常收尾。


它干四件事:

1. **剥壳**:axios 的响应是 `res.data`,后端业务数据又包一层 `data.data` —— 拦截器统一剥掉,调用方直接拿业务体
2. **统一报错**:`code !== 200` 自动弹错误消息,页面不用管
3. **401 自动处理**:token 过期/无效 → 自动清空 + 跳登录页(回忆 JWT 课的"过期被动下线")
4. **网络异常兜底**:后端挂了/断网 → 显示统一错误提示，仍需页面收尾和日志定位

> ⚠️ 本课最大的坑:**拦截器必须 return**。不写 `return data`,调用方拿到的就是 `undefined`(我们被这个坑过:按钮永远"登录中")。

### 2.4 两层 code 的判断逻辑

```
拦截器收到响应,按顺序判断:

① HTTP 层通了吗?          (err.response 存在与否)
② 业务层 code === 200 吗?  (后端统一格式里的 code)
③ code === 401 吗?         (token 失效 → 跳登录)
```

这正是后端第 07 课"双层语义"在前端的对应实现 —— **前后端的契约在这里合拢**。

---

## 第三章 API 层：api/auth.js

```javascript
import request from '@/utils/request'

export function loginApi(data) {
  return request({
    url: '/api/auth/login',
    method: 'post',
    data
  })
}
```

**按执行顺序拆解：**

#### 第一步：导入公共实例

```javascript
import request from "@/utils/request"
```

@ 是项目配置的 src 别名。request 是本地导入名称，指向上节创建的 Axios 实例，不是另一个请求库。

#### 第二步：把业务参数放进请求体

```javascript
return request({
  url: "/api/auth/login",
  method: "post",
  data
})
```

调用 loginApi(form) 后，形参 data 接收表单对象。对象中的 data 简写等于 data: data；此处是 POST JSON 请求体。return 把请求 Promise 交给页面，页面才能 await。

#### 第三步：等待拦截器处理后返回

```javascript
const res = await loginApi(form)
```

这行是页面中的调用示意，不是 API 模块的新增顶层代码。请求经过 request 拦截器、后端和 response 拦截器，最终得到统一业务 JSON。

**把结果连起来：** API 函数集中管理路径与请求方法，页面专注表单和成功后的操作。


**把每个后端接口封装成一个函数。** 看似只是"又包了一层",价值在于:

- 页面不需要知道接口的路径、方法、参数细节 —— 只调 `loginApi(form)`
- 后端改路径时,只改这一个文件
- 所有接口集中在 `api/` 目录,项目的"接口清单"一目了然

以后接口多了会长成这样:

```javascript
// api/auth.js
export const loginApi = (data) => request.post('/api/auth/login', data)
export const registerApi = (data) => request.post('/api/auth/register', data)

// api/user.js
export const getUserList = (params) => request.get('/api/user/list', { params })
```

**这段代码怎样执行：** 这是语法和未来扩展示意，不表示第 08 节已开发注册和用户列表。request.post(url, data) 对应配置式的 post/data；request.get(url, {params}) 将条件放进 URL。当前实际用户分页函数叫 getUserPageList，见第 13 节。


---

## 第四章 页面的使用：Login.vue

这一课对 Login.vue 的模板(template)没动,改的是 `<script setup>` —— 登录逻辑从"假装登录"变成"真登录"。

### 4.1 改造前 vs 改造后

```javascript
// ── 改造前(第 06 课时):假登录,自娱自乐 ──
const login = () => {
  loadingValue.value = true
  setTimeout(() => {                    // 假装等了 2 秒网络
    ElMessage.success('登录成功')        // 不管输什么都"成功"
    router.push('/manager/home')
  }, 2000)
}

// ── 改造后(本课):真登录,走完整链路 ──
const login = async () => {
  loadingValue.value = true
  const res = await loginApi(form)      // 真的发请求给后端
  loadingValue.value = false
  if (res.code === 200) {               // 真的判断结果
    saveLoginData(res.data)             // 真的存 token
    ElMessage.success('登录成功')
    router.push('/manager/home')
  }
}
```

**这段代码怎样执行：** 这是一段历史对照：setTimeout 只是延时后显示成功，没有验证账号密码；异步版本开始真正调用后端。下面第 4.3 小节已改为当前源码中的完整登录函数，以 formRef 校验和 finally 收尾为准。两段同名 const 不能在同一作用域一起执行。


### 4.2 新增的 import

```javascript
import { loginApi } from '@/api/auth'      // 从 API 层拿"登录"函数
import { useUser } from '@/utils/user'     // 从状态层拿"存登录数据"的能力
const { saveLoginData } = useUser()        // 解构出需要的函数
```

**这段代码怎样执行：** 两个 import 引入项目自己定义的请求与组合式函数。useUser() 返回包含状态和多个操作的对象，花括号解构取出 saveLoginData；此时只是获取函数，并没有执行保存。真正执行发生在登录接口成功之后。


- `@` 是路径别名 = `src/` 目录(vite.config.js 里配的)
- `useUser()` 这种写法叫**组合式函数(Composable)**,Vue 3 的标志性模式:把可复用逻辑打包成 use 开头的函数,用解构取出需要的部分

### 4.3 登录函数的执行流程

```javascript
const login = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loadingValue.value = true
  try {
    const res = await loginApi(form)

    if (res.code === 200) {
      saveLoginData(res.data)
      ElMessage.success('登录成功')
      await router.push('/manager/home')
    }
  } finally {
    loadingValue.value = false
  }
}
```

**按执行顺序拆解：**

#### 第一步：校验表单，失败就停止

```javascript
const valid = await formRef.value.validate().catch(() => false)
if (!valid) return
```

formRef 是表单实例的 ref，validate 来自 Element Plus。校验通过得到真值；失败的 Promise 被转换为 false，随后 return。这样空表单不会发送登录请求。

#### 第二步：开启加载并等待接口

```javascript
loadingValue.value = true
const res = await loginApi(form)
```

这两句分处 loading 和 try 代码中。按钮绑定 :loading="loadingValue"，因此请求期间显示加载；form 是当前账号密码。await 暂停本异步函数的后续逻辑，不会冻结整个浏览器。

#### 第三步：成功后保存登录数据

```javascript
if (res.code === 200) {
  saveLoginData(res.data)
}
```

res 已由拦截器转成后端 JSON。res.data 是 {token,user}，传给我们自己的状态函数；它同时更新 localStorage 和共享 userInfo，让后续请求有 token、页面有用户信息。

#### 第四步：提示并跳转主页

```javascript
ElMessage.success("登录成功")
await router.push("/manager/home")
```

ElMessage 来自 Element Plus，router 是项目路由实例。只有成功分支才执行这两步；密码错误时不会跳主页。

#### 第五步：无论结果如何都结束加载

```javascript
finally {
  loadingValue.value = false
}
```

网络失败时也能恢复按钮。finally 不吞异常，错误提示主要由请求拦截器负责。当前源码没有额外 catch 在这里转化异常。

**把结果连起来：** 点击登录 → 前端校验 → 发请求 → 保存 token/用户 → 跳主页 → 恢复按钮。


### 4.4 关键理解点（结合当前完整实现）

1. **`await` 的含义**：等待当前 Promise，暂停本异步函数后续步骤，浏览器仍可处理其他工作(JS 教程第 7 章的实战落地)
2. **`res.code === 200` 是业务码**:拦截器剥壳后,res 直接是后端统一格式 —— 前后端契约在此合拢
3. **失败路径为什么空着**:密码错时后端返回 code 400,响应拦截器已经统一弹了错误提示,页面只写成功路径
4. **`saveLoginData(res.data)`**:res.data 就是 `{token, user}`,传进去后 token/user 存进 localStorage(持久化),userInfo 的 ref 更新(页面即时响应)

### 4.5 finally 收尾结构回顾（当前源码已采用）

历史简化版本在请求抛错后可能执行不到恢复按钮的语句。当前完整源码已使用 finally；下面再单独看收尾结构：

```javascript
const login = async () => {
  loadingValue.value = true
  try {
    const res = await loginApi(form)
    if (res.code === 200) { /* 成功流程 */ }
  } finally {
    loadingValue.value = false   // 无论成败都恢复按钮
  }
}
```

**这段代码怎样执行：** 这是 finally 收尾结构的局部示意，成功流程被注释省略。当前完整 login 已采用校验加 try/finally，不再是尚未使用的建议；即使 await 请求抛出异常，也会运行 finally，结束按钮加载。


---

## 第五章 前端门卫：路由守卫

```javascript
// 当前 router/index.js 的返回值写法
router.beforeEach((to, from) => {
  const token = getToken()
  if (to.path === '/login' || to.path === '/register') {
    return true
  } else {
    return token ? true : '/login'
  }
})
```

**按执行顺序拆解：**

#### 第一步：每次导航读取目标与 token

```javascript
router.beforeEach((to, from) => {
  const token = getToken()
```

beforeEach 是 Vue Router 的导航钩子。to 表示要去的路由，from 表示当前路由。getToken 读取本地字符串，不向后端验证 token。此处按当前源码使用返回值写法，原笔记 next 写法属于历史版本。

#### 第二步：放行登录和注册页面

```javascript
if (to.path === "/login" || to.path === "/register") {
  return true
}
```

这两页允许未登录用户访问，否则会把想登录的人也拦在外面。返回 true 继续导航，并不是返回 HTTP 成功响应。

#### 第三步：其他页面检查是否保存了 token

```javascript
return token ? true : "/login"
```

有字符串则暂时放行，没有就重定向登录页。它不代表 token 有效，也不检查管理员权限；过期和用户状态仍由后端接口判断。

**把结果连起来：** 前端守卫改善导航体验，真正的数据访问权限以服务器认证和授权为准。


### 5.1 它在什么位置、什么时候执行

```
用户在地址栏输入 /manager/home
  或代码里 router.push('/manager/home')
       ↓
  【beforeEach 守卫 ← 在这里拦截!每次跳转必经】
       ↓ 放行
  路由匹配 → 加载对应组件 → 页面渲染
```

`beforeEach` = "每次导航之前"。路由导航可以由菜单、输入网址后的应用初始化或 router.push 等触发；已确认的导航会经过相应守卫，重复导航等情况另有处理。

### 5.2 返回值与早期 next 写法的对照

当前主示例与下面说明都以 return 写法为准；早期 next 回调只在末尾作等价行为对照，不要把两套控制方式混在同一次守卫调用中。

**`const token = getToken()`** —— 去 localStorage 看有没有登录凭证。注意它只看"有没有",不验真伪:验真伪是后端守门员的事(前端门卫只查"带没带证",后端闸机才查"证是不是假的")。

**`if (to.path === '/login' || to.path === '/register')`** —— 白名单:登录页和注册页本身不需要登录就能看(否则成了"要登录才能登录"的死循环)。`to` 是"要去哪里"。

**`return token ? true : '/login'`** —— 三元表达式:

```
token 存在   → return true      → 放行
token 不存在 → return '/login'  → 强制改道去登录页
```

> 顺带:`return true` 等价于 `next()`(放行),`return '/login'` 等价于 `next('/login')`(重定向)。当前源码使用直接 return；这里仅比较控制效果，不在同一回调混用两种方式。

### 5.3 生活类比：小区门禁

```
你要进小区(访问页面)
  → 门口保安(beforeEach)查门禁卡(getToken)
    ├─ 你是来物业办公室办事的(/login、/register)→ 不用卡,直接进
    ├─ 有卡(token 存在)→ 抬杆放行(return true)
    └─ 没卡 → "请先去物业办公室登记"(return '/login')
```

保安**只查"有没有卡",不查"卡是不是真的"** —— 卡的防伪验证由后端的 get_current_user 完成。

### 5.4 和后端守门员 `get_current_user` 的关系：

| | 前端路由守卫 | 后端 get_current_user |
|---|---|---|
| 管什么 | 页面能不能看 | 数据能不能拿 |
| 性质 | 体验层(防君子) | 安全层(防小人) |
| 能绕过吗 | 能(curl 直接调接口) | 不能(验签+查库) |

两层都要有:只有后端没有前端,用户会看到一个空壳页面;只有前端没有后端,伪造请求就能拿数据。

### 5.5 实际效果(可自己验证)

1. 没登录时,地址栏直接输 `http://localhost:5173/manager/home` → 被弹回 `/login`
2. 登录后输 `/login` → 能进(白名单);输 `/manager/home` → 正常进入
3. 点"退出登录"后,`logout()` 清掉 token,再想进管理页面就会被拦回登录页 —— 登录状态管理的闭环完成

---

## 第六章 utils 三件套：auth.js / user.js / request.js

这三个文件是前端的"后勤部",各管一件事:

```
utils/
├── auth.js      存储层 —— 管 token 和用户信息在浏览器里的存取删
├── request.js   请求层 —— 管所有 HTTP 请求怎么发(axios 封装)
└── user.js      状态层 —— 管登录状态和页面的同步(响应式)
```

### 6.1 auth.js —— 保险柜管理员

```javascript
const TOKEN_KEY = 'token'      // 键名统一在此定义
const USER_KEY = 'userInfo'

export function getToken() { return localStorage.getItem(TOKEN_KEY) }
export function setToken(token) { localStorage.setItem(TOKEN_KEY, token) }
export function removeToken() { localStorage.removeItem(TOKEN_KEY) }

export function getUserInfo() {
  const str = localStorage.getItem(USER_KEY)
  return str ? JSON.parse(str) : null        // 取出:字符串 → 对象
}
export function setUserInfo(userInfo) {
  localStorage.setItem(USER_KEY, JSON.stringify(userInfo))  // 存入:对象 → 字符串
}
export function removeUserInfo() { localStorage.removeItem(USER_KEY) }

export function logout() {
  removeToken()
  removeUserInfo()
}
```

**按执行顺序拆解：**

#### 第一步：固定存储键名

```javascript
const TOKEN_KEY = "token"
const USER_KEY = "userInfo"
```

这些只是本地存储项的名称，不是实际 token 或用户。统一常量避免保存时叫 userInfo、读取时却拼成别的键。

#### 第二步：存取删除 token 字符串

```javascript
localStorage.setItem(TOKEN_KEY, token)
localStorage.getItem(TOKEN_KEY)
localStorage.removeItem(TOKEN_KEY)
```

这是三个不同函数内部的核心动作，不是建议连续写在一起。localStorage 是浏览器内置工具，无需 import。读取不存在的键返回 null。

#### 第三步：用户对象与字符串互转

```javascript
JSON.stringify(userInfo)
JSON.parse(str)
```

用户对象先转为字符串再存储，读取时解析回对象。getUserInfo 在没有字符串时返回 null；已有字符串被损坏时 JSON.parse 可能抛错，当前没有专门捕获。

#### 第四步：退出时删除本地两项

```javascript
export function logout() {
  removeToken()
  removeUserInfo()
}
```

logout 复用前面的项目函数。它没有通知后端撤销 JWT，也没有直接修改 useUser 模块里的 ref。当前应用通过随后跳转和后续状态加载完成相应展示。

**把结果连起来：** 浏览器刷新后仍可读回已存数据，但 localStorage 自身不会让 Vue 组件自动重绘。


要点:

- `localStorage` 是浏览器自带的全局对象(不用 import),**只能存字符串**
- 所以用户信息(对象)存取时要 `JSON.stringify` / `JSON.parse` 转换
- 键名用常量收敛(TOKEN_KEY),防止散落各处拼错
- `logout()` 是组合动作:token 和用户信息一起清

### 6.2 user.js —— 存储和页面之间的桥

```javascript
// 仅供页面 setup 函数使用
import { ref } from 'vue'
import { getUserInfo, setToken, setUserInfo } from './auth'

const userInfo = ref(getUserInfo()) // 响应式对象 可以随时更新最新的值

export function useUser() {
  function saveLoginData(data) {
    setToken(data.token)
    setUserInfo(data.user)
    userInfo.value = data.user
  }

  function updateUser(user) {
    setUserInfo(user)
    userInfo.value = user
  }

  function reloadUser() {
    userInfo.value = getUserInfo()
  }
  return {
    userInfo,
    saveLoginData,
    updateUser,
    reloadUser
  }
}
```

**按执行顺序拆解：**

#### 第一步：模块初始化时读回共享状态

```javascript
const userInfo = ref(getUserInfo())
```

这行位于 useUser 函数外，导入模块时创建共享 ref，初始值从 localStorage 读取。因此多个页面调用 useUser 可以拿到同一份响应式 userInfo。

#### 第二步：登录成功同时写存储与状态

```javascript
setToken(data.token)
setUserInfo(data.user)
userInfo.value = data.user
```

data 是登录接口 data 内的 {token,user}。前两句负责刷新后仍保留，第三句负责当前页面立即看到新用户。只有存储而不更新 ref，现有页面不一定自动更新。

#### 第三步：资料更新或重新读取

```javascript
function updateUser(user) {
  setUserInfo(user)
  userInfo.value = user
}
```

updateUser 是第 11 节资料编辑时复用的能力，不当作第 08 节必定已经新增；这里展示当前完整模块，避免原笔记返回一个未定义的函数。reloadUser 则是从存储读回 ref。

#### 第四步：把状态和函数交给页面

```javascript
return { userInfo, saveLoginData, updateUser, reloadUser }
```

useUser 返回对象，页面按需解构。它不是 HTTP 请求；调用 useUser 只是取得共享状态和操作，调用 saveLoginData 才真正保存。

**把结果连起来：** 持久存储负责跨刷新保留，响应式 ref 负责当前页面显示，两者由组合式函数协调。


**它在本项目中的主要作用**：localStorage 变了页面不知道(不响应式),`ref` 变了页面才自动更新。saveLoginData/updateUser 同时写存储和更新 ref；reloadUser 只从存储读回，不能说每个函数都在写存储。

- 登录时:写柜子 + 更新 ref,页面右上角立刻显示用户名
- 刷新后:`ref(getUserInfo())` 从柜子读回登录状态,页面恢复

### 6.3 request.js —— 所有请求的总出口

```javascript
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",   // 后端地址从 .env 读
  timeout: 30000
})

// 请求拦截器:发出去之前,自动贴 token
service.interceptors.request.use((config) => {
  const token = getToken()                       // 调 auth.js
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截器:回来之后,剥壳 + 统一错误处理
service.interceptors.response.use(
  (res) => {
    const data = res.data
    if (data.code !== 200) { /* 弹错误提示;401 → logout + 跳登录页 */ }
    return data              // ⚠️ 必须 return,否则调用方拿到 undefined
  },
  (err) => { /* 网络异常兜底 */ }
)
```

**这段代码怎样执行：** 这是公共请求层的缩略回顾，注释位置省略了完整错误分支，不能拿它覆盖真实 request.js。创建实例只配置工具；请求拦截器返回 config，响应成功回调返回业务 JSON。完整的两种 401 和错误传播请按第 2.3 小节逐步阅读。


### 6.4 三者的协作全景

```
                    ┌──────────────────────────────────┐
                    │           页面层                  │
                    │  Login.vue / Layout.vue 等        │
                    └───┬──────────────┬───────────────┘
        登录成功时调      │              │    发请求时调
                        ▼              ▼
                    user.js      api/auth.js(loginApi)
                  (状态层)            │
                        │              ▼
                        │       request.js(请求层)
                        │              │
                        ▼              ▼
                    auth.js ←──────────┘
                    (存储层)    拦截器里 getToken()/logout()
                        │
                        ▼
                  localStorage
```

三个典型时刻:

| 时刻 | 流程 |
|---|---|
| 登录成功 | 页面 → `saveLoginData` → auth.js 存柜子 + ref 更新页面 |
| 发请求 | 页面 → `loginApi()` → request.js 拦截器 → `getToken()` 贴头 → 后端 |
| token 过期 | 后端 401 → 响应拦截器 → `logout()` 清空 → 跳登录页 |

**记忆口诀:auth.js 管"存",request.js 管"传",user.js 管"显"。**

---

## 第七章 后端配置：CORS 跨域

### 7.1 什么是"源"(Origin)

浏览器把一个地址的三个部分合起来叫"源":

```
http://localhost:5173
└─┬─┘   └───┬───┘ └┬─┘
 协议      域名    端口
```

**三个全部相同 = 同源,任何一个不同 = 跨域。** 本项目:

```
前端页面: http://localhost:5173   (Vue)
后端接口: http://localhost:8000   (FastAPI)
                        ↑
              端口不同 → 跨域!
```

### 7.2 同源策略：为什么浏览器要拦

浏览器的安全规定:网页里的 JavaScript 发起的请求,跨源读取响应会受同源策略与 CORS 规则约束；部分跨源请求可以发出，但脚本未必能读取响应。

假设没有它:你登录了银行网站(浏览器存着凭证),这时误入一个恶意网站,它的 JS 就能偷偷以你的身份调银行接口转账。同源策略堵的就是这个漏洞。

**CORS(跨域资源共享)是官方的"白名单豁免"机制:后端通过响应头声明"我允许哪些源",浏览器看到声明才放行。**

> 关键认知:**CORS 是"浏览器执法、后端表态"。** 所以 curl、Apifox 调接口永远没有跨域问题,只有浏览器里的 JS 会被拦。它保护的是用户,不是服务器。

### 7.3 预检请求(Preflight)

登录请求是 `POST` + `Content-Type: application/json` + 自定义头(Authorization)—— 这种"非简单请求"浏览器会**先发 OPTIONS 探路**:

```
浏览器: OPTIONS /api/auth/login   (问:5173 来的 POST 你收吗?)
后端:   200 + Access-Control-Allow-Origin: http://localhost:5173  (收!)
浏览器: 好,那我真发了 → POST /api/auth/login
```

预检通过才发真正的请求。

### 7.4 我们的代码(main.py)

```python
from starlette.middleware.cors import CORSMiddleware

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",      # localhost 和 127.0.0.1 是两个不同的源,都写上
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # ① 白名单:哪些源可以来
    allow_credentials=True,       # ② 允许带 cookie/凭证
    allow_methods=["*"],          # ③ 允许所有方法:GET/POST/PUT/DELETE...
    allow_headers=["*"],          # ④ 允许所有请求头(我们的 Authorization 就靠这条)
)
```

**按执行顺序拆解：**

#### 第一步：声明允许的网页来源

```python
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
```

这是浏览器页面的源，不是数据库地址。协议、主机、端口不同就是不同源，所以两种主机名分别列出。列表中的地址也不是当前用户身份验证。

#### 第二步：将 CORS 中间件安装到应用

```python
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```

这是配置注册，启动时执行；后续请求由中间件处理所需 CORS 头。允许 methods/headers 是浏览器跨域访问规则，不等于接口授权给任何人。

#### 第三步：浏览器检查响应头

浏览器直连 8000 时，符合条件的请求可能先预检，再据服务端头决定是否让脚本读取响应。当前空 baseURL 加 Vite 代理使浏览器访问同源 /api，此时开发代理路径不依赖同一套浏览器跨域流程。curl 本身不执行浏览器 CORS 限制。

**把结果连起来：** CORS 与 token 鉴权职责不同：前者协调浏览器跨源读取，后者决定谁能访问数据。


`allow_headers=["*"]` 很关键:`Authorization: Bearer xxx` 是自定义头,不放行就会被预检拦下。

### 7.5 中间件的位置

`add_middleware` 加的是全局中间件,包裹所有路由:

```
请求 → CORSMiddleware → 路由 → 业务函数
         ↑ 每个请求先经过它:
           - OPTIONS 预检 → 它直接回答,不进路由
           - 正常请求 → 它在响应头上"盖章"(Access-Control-Allow-Origin)
```

### 7.6 浏览器直连跨源接口时删掉它会怎样

浏览器 F12 Console 立刻报经典错误:

```
Access to XMLHttpRequest at 'http://localhost:8000/api/auth/login'
from origin 'http://localhost:5173' has been blocked by CORS policy...
```

但同一时刻 curl 照样能调通 —— "CORS 是浏览器执法"的铁证。

### 7.7 面试标准答案(升级版)

> 跨域是浏览器同源策略的限制:协议、域名、端口任一不同即跨域。前后端分离项目里浏览器直连不同端口时属于跨源；通过同源开发代理转发 /api 则是另一条请求路径。我们的解法是后端加 CORSMiddleware 白名单放行;生产环境更常见的是用 Nginx 反向代理把前后端收到同一个域名下(如 /api 前缀转发),从源头消灭跨域。另外 CORS 只是浏览器层面的限制,不影响 curl 等工具 —— 它保护的是用户而不是服务器。

---

## 第八章 全景流程图：一次登录的完整旅程

```
用户点"登录"
  ↓
Login.vue: login() → loginApi(form)
  ↓
api/auth.js: request({url:'/api/auth/login', ...})
  ↓
request.js 请求拦截器: (登录时还没 token,跳过贴头)
  ↓
浏览器发 POST http://localhost:8000/api/auth/login
  ↓  (CORS 预检 → 后端白名单放行)
FastAPI: 查库 → bcrypt 校验 → 签发 JWT → 统一格式返回
  ↓
request.js 响应拦截器: code===200 → 剥壳 → 返回 data
  ↓
Login.vue: user.js 的 saveLoginData()
  ├── auth.js: token/userInfo 存进 localStorage(持久化)
  └── user.js: userInfo.value 更新(响应式,页面即时刷新)
  ↓
router.push('/manager/home')
  ↓
路由守卫: getToken() → 有 token → 放行
  ↓
进入主页面,右上角显示"管理员"
```

之后的每个请求:

```
任意页面发请求 → 请求拦截器自动贴 Authorization → 后端守门员验 token
  → 正常:返回数据
  → token 过期: 401 → 响应拦截器自动 logout + 跳登录页
```

---

## 第九章 本课踩坑实录(联调的高频考点)

这节课调试过程中实际踩过的坑,每一个都是前后端联调的经典案例:

| 坑 | 症状 | 解法 |
|---|---|---|
| 端口转发没建/失效 | 浏览器转圈打不开页面 | VSCode 端口面板检查;手动 ssh -L |
| Clash 代理劫持 localhost | 页面能开但 API 超时 | 代理绕过列表加 `localhost;127.*` |
| `.env` 里 `http"//` 笔误 | 报 URL 含 `%22` 的 404 | env 是纯文本,冒号别写成引号 |
| 改 `.env` 没重启 vite | 配置不生效 | env 只在启动时读取 |
| 响应拦截器没 return | 按钮永远"登录中" | 拦截器必须 `return data` |
| CORS 没配 | 浏览器报 CORS policy 错 | 后端 CORSMiddleware 白名单 |
| 路由守卫忘 import getToken | 页面整个白屏打不开 | 检查 import 区 |

**调试方法论(本课最值钱的收获):**

```
页面不正常
  → F12 Console 看红色报错
  → Network 看请求发没发、发去哪、什么状态
  → 集群侧 curl 验证后端本身好不好
  → 一层层缩小范围:浏览器 → 转发通道 → 代理 → 后端
```

---

## 第十章 常见问题

**Q1:baseURL 里 localhost 和 127.0.0.1 有区别吗?**
浏览器眼里它们是**两个不同的源**(影响 CORS 和代理绕过规则)。推荐统一用 `localhost`,并把 CORS 白名单和代理绕过列表都配齐。

**Q2:token 存 localStorage 安全吗?**
教学项目够用。生产环境要注意 XSS 风险(恶意脚本可读 localStorage),更严格的方案是 HttpOnly Cookie + CSRF 防护。面试能讲出这个权衡即可。

**Q3:拦截器里的 401 判断为什么有两处?**
一处判断业务码(`data.code === 401`,后端自定义),一处判断 HTTP 状态码(`err.response.status === 401`,HTTP 协议层)。双保险,因为两种 401 都可能出现。非 401 业务失败在当前实现中只提示后返回 JSON，页面仍需判断 code。

**Q4:为什么要 `Promise.reject(err)`?**
让错误继续向调用方传播,页面的 `try/catch` 才能感知"这次请求失败了"。吞掉错误会让页面以为成功了。

**Q5:这个封装和直接 fetch 比好在哪?**
axios 提供了拦截器、超时、自动 JSON 解析、错误分类等;fetch 太原始,什么都要手写。拦截器机制是 axios 的核心价值。

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| axios 实例 | `axios.create()` 造出的定制版请求器,配置独立 |
| 拦截器 | 请求发出前/响应返回后自动执行的钩子函数 |
| baseURL | 所有请求地址的公共前缀 |
| 环境变量(.env) | 按环境区分的配置文件,前端只暴露 `VITE_` 开头的 |
| 路由守卫(beforeEach) | 每次页面跳转前执行的前端门卫 |
| Promise.reject | 把错误继续往下传,让调用方能 catch |
| 三层结构 | 页面 → API 层 → 请求层,职责分离 |

---

## 本章自检清单

- [ ] 能画出"页面 → API 层 → 请求层 → 后端"的分层图
- [ ] 能说清两个拦截器各自做什么
- [ ] 能解释"两层 data"(res.data.data)
- [ ] 能解释 401 的两处判断(业务码 + HTTP 状态码)
- [ ] 能口述登录的完整流程(从点按钮到进主页)
- [ ] 能解释前端守卫和后端守门员为什么都需要
- [ ] 知道改 .env 要重启 vite、拦截器必须 return
- [ ] 会用 F12 的 Console + Network 排查联调问题
