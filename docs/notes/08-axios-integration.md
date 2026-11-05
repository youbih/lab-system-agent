# Vue 封装 axios 并实现前后端联调

> 对应课程:第 08 节
> 对应项目:`agent-lab/lab-system-agent/frontend`
> 涉及文件:`src/utils/request.js`、`src/utils/auth.js`、`src/utils/user.js`、`src/api/auth.js`、`src/router/index.js`、`src/views/Login.vue`
> 阅读时间:约 35 分钟

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

问题:

| 问题 | 后果 |
|---|---|
| 后端地址硬编码在每个页面 | 换环境要改几十处 |
| 每个请求手动贴 token | 重复劳动,漏一个就 401 |
| 每个响应手动判断 code、处理 401 | 业务代码被淹没在样板里 |
| 接口地址散落各页面 | 后端改路径,前端全文搜索替换 |

**封装的目的:把"每个请求都要做的事"集中到一处,页面只关心业务。**

---

## 第二章 请求层:request.js(本课核心)

这个文件是前端所有请求的"总出口"。分三部分看。

### 2.1 创建 axios 实例

```javascript
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,   // 后端地址,从环境变量读
  timeout: 30000                                 // 30 秒无响应就放弃
})
```

- **`axios.create()`**:不是直接用全局 axios,而是造一个"定制版实例"。好处:配置独立,不影响别处
- **`baseURL`**:所有请求的公共前缀。接口里只写 `/api/auth/login`,实际发出去的是 `baseURL + url`
- **`import.meta.env.VITE_API_BASE_URL`**:读 `.env.development` 里的配置(Vite 规定必须以 `VITE_` 开头才暴露给前端)
  - ⚠️ 改 `.env` 后必须重启 `npm run dev` 才生效(热更新不管环境变量)
- **`timeout`**:防止请求永远卡住(我们调试时就是靠它暴露问题的)

### 2.2 请求拦截器:出门前的"安检"

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

**每个请求发出之前**,自动执行一次:从 localStorage 取 token,有就贴到请求头。

效果:任何页面发任何请求,都不用再手写 `Authorization` 头 —— 这就是"集中处理"的威力。

### 2.3 响应拦截器:进门前的"分拣台"

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

它干四件事:

1. **剥壳**:axios 的响应是 `res.data`,后端业务数据又包一层 `data.data` —— 拦截器统一剥掉,调用方直接拿业务体
2. **统一报错**:`code !== 200` 自动弹错误消息,页面不用管
3. **401 自动处理**:token 过期/无效 → 自动清空 + 跳登录页(回忆 JWT 课的"过期被动下线")
4. **网络异常兜底**:后端挂了/断网 → 友好提示而不是白板报错

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

## 第三章 API 层:api/auth.js

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

---

## 第四章 页面的使用:Login.vue

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

### 4.2 新增的 import

```javascript
import { loginApi } from '@/api/auth'      // 从 API 层拿"登录"函数
import { useUser } from '@/utils/user'     // 从状态层拿"存登录数据"的能力
const { saveLoginData } = useUser()        // 解构出需要的函数
```

- `@` 是路径别名 = `src/` 目录(vite.config.js 里配的)
- `useUser()` 这种写法叫**组合式函数(Composable)**,Vue 3 的标志性模式:把可复用逻辑打包成 use 开头的函数,用解构取出需要的部分

### 4.3 登录函数的执行流程

```javascript
const login = async () => {
  loadingValue.value = true        // ① 按钮进入"登录中"转圈状态

  const res = await loginApi(form) // ② 发请求(await 等待结果)
  //   背后一整条链:loginApi → request.js → 拦截器 → 后端 → 响应拦截器剥壳
  //   返回时 res 已经是 {code, message, data}

  loadingValue.value = false       // ③ 请求结束,按钮恢复

  if (res.code === 200) {          // ④ 判断业务结果(注意:是业务码不是 HTTP 状态码)
    saveLoginData(res.data)        // ⑤ 存 token + 用户信息(双层写入)
    ElMessage.success('登录成功')   // ⑥ 弹提示
    router.push('/manager/home')   // ⑦ 跳主页
  }
  // ⑧ 失败情况不用写:响应拦截器已统一弹过错误提示
}
```

### 4.4 关键理解点

1. **`await` 的含义**:发请求是异步的,`await` 让代码停在这等结果再继续(JS 教程第 7 章的实战落地)
2. **`res.code === 200` 是业务码**:拦截器剥壳后,res 直接是后端统一格式 —— 前后端契约在此合拢
3. **失败路径为什么空着**:密码错时后端返回 code 400,响应拦截器已经统一弹了错误提示,页面只写成功路径
4. **`saveLoginData(res.data)`**:res.data 就是 `{token, user}`,传进去后 token/user 存进 localStorage(持久化),userInfo 的 ref 更新(页面即时响应)

### 4.5 可选的健壮性改进

请求直接失败(如后端挂了)时,`loadingValue.value = false` 执行不到,按钮会卡在转圈。更稳的写法:

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

---

## 第五章 前端门卫:路由守卫

```javascript
// router/index.js
router.beforeEach((to, from, next) => {
  const token = getToken()
  if (to.path === '/login' || to.path === '/register') {
    return true                     // 登录/注册页:放行
  } else {
    return token ? true : '/login'  // 其他页:没 token 踢回登录页
  }
})
```

### 5.1 它在什么位置、什么时候执行

```
用户在地址栏输入 /manager/home
  或代码里 router.push('/manager/home')
       ↓
  【beforeEach 守卫 ← 在这里拦截!每次跳转必经】
       ↓ 放行
  路由匹配 → 加载对应组件 → 页面渲染
```

`beforeEach` = "每次导航之前"。不管是点菜单、输网址、还是代码跳转,只要 URL 要变,先过这一关。

### 5.2 逐行讲

**`const token = getToken()`** —— 去 localStorage 看有没有登录凭证。注意它只看"有没有",不验真伪:验真伪是后端守门员的事(前端门卫只查"带没带证",后端闸机才查"证是不是假的")。

**`if (to.path === '/login' || to.path === '/register')`** —— 白名单:登录页和注册页本身不需要登录就能看(否则成了"要登录才能登录"的死循环)。`to` 是"要去哪里"。

**`return token ? true : '/login'`** —— 三元表达式:

```
token 存在   → return true      → 放行
token 不存在 → return '/login'  → 强制改道去登录页
```

> 顺带:`return true` 等价于 `next()`(放行),`return '/login'` 等价于 `next('/login')`(重定向)。新版 vue-router 推荐直接 return,更简洁。

### 5.3 生活类比:小区门禁

```
你要进小区(访问页面)
  → 门口保安(beforeEach)查门禁卡(getToken)
    ├─ 你是来物业办公室办事的(/login、/register)→ 不用卡,直接进
    ├─ 有卡(token 存在)→ 抬杆放行(return true)
    └─ 没卡 → "请先去物业办公室登记"(return '/login')
```

保安**只查"有没有卡",不查"卡是不是真的"** —— 卡的防伪验证由后端的 get_current_user 完成。

### 5.4 和后端守门员 `get_current_user` 的关系:

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

## 第六章 utils 三件套:auth.js / user.js / request.js

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

要点:

- `localStorage` 是浏览器自带的全局对象(不用 import),**只能存字符串**
- 所以用户信息(对象)存取时要 `JSON.stringify` / `JSON.parse` 转换
- 键名用常量收敛(TOKEN_KEY),防止散落各处拼错
- `logout()` 是组合动作:token 和用户信息一起清

### 6.2 user.js —— 存储和页面之间的桥

```javascript
import { ref } from 'vue'
import { getUserInfo, setToken, setUserInfo } from './auth'   // 复用 auth.js

const userInfo = ref(getUserInfo())   // 关键:响应式变量,初始值从存储里读

export function useUser() {
  function saveLoginData(data) {
    setToken(data.token)          // ① 存进 localStorage(持久化)
    setUserInfo(data.user)        // ①
    userInfo.value = data.user    // ② 更新 ref → 页面立刻刷新
  }
  function reloadUser() {
    userInfo.value = getUserInfo()  // 从存储重新读 → 刷新响应式
  }
  return { userInfo, saveLoginData, updateUser, reloadUser }
}
```

**它存在的唯一理由**:localStorage 变了页面不知道(不响应式),`ref` 变了页面才自动更新。所以每个函数都是"双重动作" —— 一边写存储,一边更新 ref。

- 登录时:写柜子 + 更新 ref,页面右上角立刻显示用户名
- 刷新后:`ref(getUserInfo())` 从柜子读回登录状态,页面恢复

### 6.3 request.js —— 所有请求的总出口

```javascript
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,   // 后端地址从 .env 读
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

## 第七章 后端配置:CORS 跨域

### 6.1 什么是"源"(Origin)

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

### 6.2 同源策略:为什么浏览器要拦

浏览器的安全规定:网页里的 JavaScript 发起的请求,默认只能发给"同源"的后端。

假设没有它:你登录了银行网站(浏览器存着凭证),这时误入一个恶意网站,它的 JS 就能偷偷以你的身份调银行接口转账。同源策略堵的就是这个漏洞。

**CORS(跨域资源共享)是官方的"白名单豁免"机制:后端通过响应头声明"我允许哪些源",浏览器看到声明才放行。**

> 关键认知:**CORS 是"浏览器执法、后端表态"。** 所以 curl、Apifox 调接口永远没有跨域问题,只有浏览器里的 JS 会被拦。它保护的是用户,不是服务器。

### 6.3 预检请求(Preflight)

登录请求是 `POST` + `Content-Type: application/json` + 自定义头(Authorization)—— 这种"非简单请求"浏览器会**先发 OPTIONS 探路**:

```
浏览器: OPTIONS /api/auth/login   (问:5173 来的 POST 你收吗?)
后端:   200 + Access-Control-Allow-Origin: http://localhost:5173  (收!)
浏览器: 好,那我真发了 → POST /api/auth/login
```

预检通过才发真正的请求。

### 6.4 我们的代码(main.py)

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

`allow_headers=["*"]` 很关键:`Authorization: Bearer xxx` 是自定义头,不放行就会被预检拦下。

### 6.5 中间件的位置

`add_middleware` 加的是全局中间件,包裹所有路由:

```
请求 → CORSMiddleware → 路由 → 业务函数
         ↑ 每个请求先经过它:
           - OPTIONS 预检 → 它直接回答,不进路由
           - 正常请求 → 它在响应头上"盖章"(Access-Control-Allow-Origin)
```

### 6.6 删掉它会怎样

浏览器 F12 Console 立刻报经典错误:

```
Access to XMLHttpRequest at 'http://localhost:8000/api/auth/login'
from origin 'http://localhost:5173' has been blocked by CORS policy...
```

但同一时刻 curl 照样能调通 —— "CORS 是浏览器执法"的铁证。

### 6.7 面试标准答案(升级版)

> 跨域是浏览器同源策略的限制:协议、域名、端口任一不同即跨域。前后端分离项目里前端 5173、后端 8000 必然跨域。我们的解法是后端加 CORSMiddleware 白名单放行;生产环境更常见的是用 Nginx 反向代理把前后端收到同一个域名下(如 /api 前缀转发),从源头消灭跨域。另外 CORS 只是浏览器层面的限制,不影响 curl 等工具 —— 它保护的是用户而不是服务器。

---

## 第八章 全景流程图:一次登录的完整旅程

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
一处判断业务码(`data.code === 401`,后端自定义),一处判断 HTTP 状态码(`err.response.status === 401`,HTTP 协议层)。双保险,因为两种 401 都可能出现。

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
