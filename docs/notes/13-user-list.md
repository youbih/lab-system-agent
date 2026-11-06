# 开发用户列表展示功能

> 对应课程：第 13 节
> 对应项目：`agent-lab/lab-system-agent`
> 涉及文件：
> - 前端重点：`src/views/User.vue`
> - 前端配套：`src/api/user.js`、`src/router/index.js`、`src/layouts/Layout.vue`
> - 后端：`app/api/user.py`、`app/services/user_services.py`、`app/dependencies/auth.py`、`app/common/response.py`、`app/schemas/user.py`
>
> 验证方式：curl 查询 + 浏览器查看列表、搜索与状态展示
> 阅读时间：约 30 分钟

---

## 第零章 这节课干了什么

把用户管理占位页面扩展为可以展示数据的列表页，支持分页查询，以及按账号或姓名搜索，并在后端限制管理员访问。

本课重点确实是 `User.vue`：它将查询框、表格、分页组件与后端数据连接起来。

```text
打开用户管理页
    ↓
onMounted 调用 load
    ↓
GET /api/user/list，携带分页参数和 token
    ↓
后端验证管理员身份，筛选并分页查询
    ↓
返回 data.list 和 data.total
    ↓
前端更新表格数据和分页总数
```

相比上一课的“填写表单并保存”，本课的模式是：

```text
维护查询条件 → 发起查询 → 展示列表 → 搜索或翻页 → 重新查询
```

本课完成的是展示与查询，没有实现前端新增、编辑、删除用户或切换状态的接口操作。课堂中的新增测试用户、禁用与恢复，是直接操作数据库进行的验证。

---

## 第一章 前端重点：User.vue 的整体结构

### 1.1 template：页面有哪些部分

```text
el-card（用户管理卡片）
├── 标题
├── 查询区域
│   ├── 关键词输入框
│   └── 查询按钮
├── el-table（绑定 tableData）
│   ├── 账号、名称
│   ├── 头像
│   ├── 邮箱、手机号
│   ├── 角色
│   └── 状态标签
└── el-pagination（绑定当前页、每页条数和总数）
```

`<template>` 决定页面如何展示，`<script setup>` 保存数据、组织请求并处理交互。表格显示来自接口的数据，没有在模板中直接查询数据库。

### 1.2 script setup：四组核心状态

```javascript
import { getUserPageList } from '@/api/user'
import { ref, reactive, onMounted } from 'vue'

const params = reactive({
  page: 1,
  pageSize: 10,
  keywords: ''
})
const tableData = ref([])
const loading = ref(false)
const total = ref(0)
```

| 变量 | 保存什么 | 用在哪里 |
|---|---|---|
| `params` | 当前页、每页条数、搜索关键词 | 请求参数、输入框和分页组件 |
| `tableData` | 当前页的用户对象数组 | `el-table` 的 `data` |
| `loading` | 是否正在加载 | `v-loading` 遮罩 |
| `total` | 符合筛选条件的用户总数 | 分页组件计算总页数 |

`tableData` 与 `total` 不是一回事。共有 25 人、每页 10 人时，第一页 `tableData.length` 可以是 10，`total` 则是 25。

---

## 第二章 加载数据：load 与 onMounted

### 2.1 load：统一的数据加载入口

```javascript
const load = async () => {
  loading.value = true
  try {
    const res = await getUserPageList({
      page: params.page,
      page_size: params.pageSize,
      keywords: params.keywords
    })

    if (res.code === 200) {
      tableData.value = res.data?.list
      total.value = res.data?.total
    }
  } finally {
    loading.value = false
  }
}
```

这个函数的作用是：**按照当前查询条件请求用户列表，再把返回结果交给表格和分页组件显示。** 下面按照实际执行顺序拆开理解。

#### 第一步：定义一个异步函数

```javascript
const load = async () => {
```

`load` 是我们自己取的函数名，不是 Vue 内置工具。整句是在定义函数，写 `load()` 才是调用函数。

`async` 表示这是异步函数，可以在里面使用 `await` 等待请求结果。等待期间浏览器仍然可以处理其他工作，并不是整个网页被暂停。

#### 第二步：开启加载提示

```javascript
loading.value = true
```

`loading` 通过 `ref(false)` 定义，所以在 JavaScript 中使用 `.value` 读写它的值。表格绑定了：

```vue
<el-table :data="tableData" v-loading="loading">
```

模板会自动解包这个 ref。值变为 `true` 后，表格出现加载遮罩，让用户知道请求正在处理。

#### 第三步：进入 try，使用当前条件请求后端

```javascript
try {
  const res = await getUserPageList({
    page: params.page,
    page_size: params.pageSize,
    keywords: params.keywords
  })
```

`getUserPageList` 是我们在 `src/api/user.js` 中定义并导入的请求函数。传入的对象包含本次查询条件。

假设当前数据是：

```javascript
params.page = 1
params.pageSize = 10
params.keywords = '哈'
```

本次传给请求函数的对象就相当于：

```javascript
{
  page: 1,
  page_size: 10,
  keywords: '哈'
}
```

请求函数通过 Axios 的 `params` 将它组织成 GET 查询参数。等价的请求含义是：

```text
GET /api/user/list?page=1&page_size=10&keywords=哈
```

实际请求中的中文会进行 URL 编码。左边的 `page_size` 是后端要求的参数名，右边的 `params.pageSize` 是前端保存的值，两者可以不同，但映射必须正确。

`await` 等待请求完成，再把请求函数返回的结果赋给 `res`。项目的公共响应拦截器返回的是响应 JSON，所以这里可以直接读取 `res.code` 和 `res.data`。如果请求抛出异常，后面的成功判断不会执行，控制流程会经过 `finally`。

#### 第四步：判断业务是否成功

```javascript
if (res.code === 200) {
```

这里判断的是后端响应 JSON 中的业务码，不是 HTTP 状态码。只有业务码为 `200`，才进入下面的数据更新逻辑。

例如搜索“哈”，后端的响应结构可以理解为：

```javascript
{
  code: 200,
  message: '请求成功',
  data: {
    list: [
      { id: 3, username: 'ccc', name: '哈牛魔', status: 1 },
      { id: 1, username: 'admin', name: '哈基米', status: 1 }
    ],
    total: 2
  }
}
```

这个示例省略了角色、头像等其他用户字段，用于说明结构。

#### 第五步：更新当前页列表与总数

```javascript
tableData.value = res.data?.list
total.value = res.data?.total
```

第一句把当前页用户数组保存到 `tableData`。表格的 `:data="tableData"` 随之更新，显示查询到的用户。

第二句把符合条件的总条数保存到 `total`。分页组件的 `:total="total"` 随之更新，用于显示总数和计算页数。

这里两个变量也都由 `ref()` 定义，因此在 JavaScript 中通过 `.value` 赋值。Vue 会根据这些响应式数据更新页面，不需要手动刷新网页。

`res.data?.list` 中的 `?.` 是可选链：如果 `res.data` 是 `null` 或 `undefined`，表达式返回 `undefined`，避免直接访问属性报错。它不会自动补空数组，正常响应仍需包含正确的列表和总数。

#### 第六步：关闭加载提示

```javascript
} finally {
  loading.value = false
}
```

正常完成或抛出异常时，都会执行 `finally`，因此加载遮罩可以结束。`finally` 负责收尾，不等同于 `catch`，不会自动处理或吞掉异常。

#### 把整个过程连起来

```text
调用 load()
    ↓
loading = true，表格显示加载遮罩
    ↓
读取 params 当前值，发送查询请求
    ↓
await 等待响应
    ↓
业务成功时更新 tableData 和 total
    ↓
finally 将 loading 设为 false，结束加载
```

页面第一次打开、用户搜索和切换页码时，都复用这个函数。它每次读取最新的 `params`，所以不需要为这三种操作分别再写一份查询逻辑。

### 2.2 onMounted：进入页面自动查询

```javascript
onMounted(() => {
  load()
})
```

`onMounted` 是从 Vue 导入的生命周期钩子；它接收的 `() => { load() }` 是我们传给 Vue 的回调函数。Vue 在组件挂载完成后调用这个回调，再由回调调用我们自己定义的 `load()`。

因此用户进入页面就会发起首次查询，无需先点击“查询”。通常每次创建并挂载该组件时执行一次，不会在每次输入关键词或更新表格时重复执行；搜索和翻页重新查询来自另外绑定的事件。

---

## 第三章 查询框：输入、搜索与清空

### 3.1 查询区域的事件绑定

```vue
<el-input
  v-model="params.keywords"
  @keyup.enter="handleSearch"
  clearable
  @clear="handleSearch"
/>
<el-button type="primary" @click="handleSearch">查询</el-button>
```

| 写法 | 作用 |
|---|---|
| `v-model="params.keywords"` | 输入内容同步到查询条件 |
| `@keyup.enter` | 按回车执行搜索 |
| `clearable` | 显示清空输入内容的按钮 |
| `@clear` | 清空后重新搜索 |
| `@click` | 点击查询按钮执行搜索 |

当前不是每输入一个字就发请求；点击查询、按回车或清空输入时才会调用 `handleSearch`。

### 3.2 为什么搜索前把 page 重置为 1

```javascript
const handleSearch = async () => {
  params.page = 1
  load()
}
```

如果原来停留在第 5 页，新关键词只匹配两个人，继续查第 5 页就会得到空列表。因此，改变搜索条件后先回到第一页。

当前函数虽然声明为 `async`，但内部没有 `await load()`；它仍然会发起查询，只是外部等待 `handleSearch()` 时，不代表已经等待列表加载完成。这是当前写法的行为说明，本次没有调整。

---

## 第四章 表格：从数据数组到每一行

### 4.1 tableData 与 prop

```vue
<el-table :data="tableData" v-loading="loading">
  <el-table-column prop="username" label="账号" />
  <el-table-column prop="name" label="名称" />
</el-table>
```

`tableData` 中每个对象对应一行，`prop="username"` 表示这一列读取该对象的 `username` 字段，`label` 决定列标题。

```javascript
// 用于理解结构的示例，不是固定数据
tableData.value = [
  { id: 3, username: 'ccc', name: '哈牛魔', status: 1 },
  { id: 1, username: 'admin', name: '哈基米', status: 1 }
]
```

### 4.2 插槽中的 row 是什么

```vue
<el-table-column prop="role" label="角色">
  <template #default="{ row }">
    {{ row.role === 'admin' ? '管理员' : '学生' }}
  </template>
</el-table-column>
```

`#default` 是默认插槽的简写，`{ row }` 从表格传给插槽的数据中取出当前行对象。

第一行渲染时，`row` 就是第一位用户；第二行渲染时，`row` 就是第二位用户。它是前端普通对象，不是后端 ORM 对象。

自定义插槽适用于把角色代码翻译成中文、显示图片、设置状态颜色等场景。当前角色表达式把所有非 `admin` 值都显示为学生，是基于现有两种角色的简化写法。

### 4.3 头像显示

```vue
<template #default="{ row }">
  <img v-if="row.avatar" :src="row.avatar" alt="" />
</template>
```

`v-if` 只在头像字段有值时显示图片。当前头像路径是 `/uploads/...`，开发环境由 Vite 的 `/uploads` 代理转发到后端。

### 4.4 状态文字和颜色

```vue
<el-tag :type="row.status === 1 ? 'success' : 'danger'">
  {{ row.status === 1 ? '正常' : '禁用' }}
</el-tag>
```

| 状态 | 文字 | 标签类型 |
|---|---|---|
| 数字 `1` | 正常 | `success`，绿色 |
| 数字 `0` | 禁用 | `danger`，红色 |

这里使用严格比较 `===`，因此类型也要正确。尤其注意：若接口没有返回 `status`，则 `row.status` 是 `undefined`，也会走“禁用”分支，并不代表数据库用户真的被禁用。

本课通过在后端 `UserResponse` 中补充 `status: int`，解决了“页面全部显示禁用”的问题。

---

## 第五章 分页组件：翻页后重新查询

```vue
<el-pagination
  v-model:current-page="params.page"
  v-model:page-size="params.pageSize"
  :total="total"
  background
  layout="total,prev,pager,next"
  @current-change="load"
/>
```

| 配置 | 作用 |
|---|---|
| `v-model:current-page` | 当前页与 `params.page` 双向绑定 |
| `v-model:page-size` | 每页条数与 `params.pageSize` 绑定 |
| `:total` | 传入后端返回的符合条件总数 |
| `layout` | 显示总数、上一页、页码和下一页 |
| `@current-change="load"` | 页码变化时重新请求数据 |

```text
点击第 2 页 → params.page 更新为 2 → load 发请求 → 替换 tableData
```

这里是服务端分页，不是前端先取全部用户再做数组切片。当前布局没有 `sizes`，所以没有让用户选择每页条数的控件。

---

## 第六章 前端 API 与路由配套

### 6.1 src/api/user.js

```javascript
export function getUserPageList(params) {
  return request({
    url: '/api/user/list',
    method: 'get',
    params
  })
}
```

这里使用 Axios 的 `params`，将条件放进 URL 查询字符串，例如：

```text
/api/user/list?page=1&page_size=10&keywords=...
```

它与此前修改密码请求的 `data` 不同：`data` 用于请求体，`params` 用于 URL 查询参数。token 仍由公共请求拦截器自动附加。

### 6.2 用户管理页面路由

在 `/manager` 的 `children` 中增加：

```javascript
{ path: 'user', name: 'User', component: () => import('@/views/User.vue') }
```

`Layout.vue` 原有 `/manager/user` 菜单入口，通过路由匹配后将 `User.vue` 显示到布局的 `<router-view />` 中。

页面路由 `/manager/user` 与数据接口 `/api/user/list` 的用途不同：前者打开页面，后者获取数据。

---

## 第七章 后端：管理员校验与分页查询

### 7.1 get_current_admin：限制谁能查询

```python
def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise BusinessException(message="无权限访问", code=403)
    return current_user
```

先复用 `get_current_user` 验证 token、读取用户和检查状态，再判断当前角色是否为管理员。

`BusinessException` 从 `app.common.exceptions` 导入。查询服务不属于鉴权依赖模块，不应从 `app.dependencies.auth` 导入。

### 7.2 API 接收参数并传给 service

```python
@router.get("/list")
def get_user_list(
    page: int = 1,
    page_size: int = 10,
    keywords: str | None = None,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    res = user_services.get_user_page_list(db, page, page_size, keywords)
    return Response.success(data=res)
```

虽然函数体没有直接使用 `current_user`，依赖仍会执行，负责拦截没有权限的请求。

当前参数没有添加 `page >= 1`、`page_size >= 1` 或最大每页条数的约束，这是后续可完善的地方。

### 7.3 Service：关键词、总数与当前页

```python
from sqlalchemy import or_


def get_user_page_list(
    db: Session,
    page: int,
    page_size: int,
    keywords: str | None = None
):
    query = db.query(User)
    if keywords:
        query = query.filter(
            or_(
                User.username.ilike(f"%{keywords}%"),
                User.name.ilike(f"%{keywords}%")
            )
        )
    total = query.count()
    items = (
        query.order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PageResponse(
        list=[UserResponse.model_validate(item) for item in items],
        total=total
    )
```

`or_` 将两个条件组合为“账号包含关键词，或者姓名包含关键词”。`%` 表示任意长度字符，`ilike` 表达不区分大小写的匹配意图，实际 SQL 由数据库方言处理。

总数在分页前计算，因此统计的是全部匹配记录。排序必须放在 `offset`、`limit` 前；本课实际遇到了顺序错误导致的 SQLAlchemy 异常。

| 页码 | 每页条数 | offset 跳过条数 |
|---|---|---|
| 1 | 10 | 0 |
| 2 | 10 | 10 |
| 3 | 10 | 20 |

### 7.4 query、items 与返回结构

| 对象 | 类型/含义 |
|---|---|
| `query` | SQLAlchemy `Query` 对象，保存正在构建的查询条件 |
| `total` | `count()` 返回的整数 |
| `items` | `all()` 返回的 `list[User]`，每一项是 ORM 用户对象 |
| `UserResponse.model_validate(item)` | 按响应模型提取并校验用户字段 |
| `PageResponse` | 包装当前页列表与总数 |

```python
# 列表推导式的展开写法
user_list = []
for item in items:
    user_list.append(UserResponse.model_validate(item))
return PageResponse(list=user_list, total=total)
```

`UserResponse` 使用 `ConfigDict(from_attributes=True)`，因此能从 ORM 对象属性读取字段，并包含本课补充的 `status: int`。没有在响应模型中声明的密码字段不会作为该模型的字段输出。

当前分页模型：

```python
class PageResponse(BaseModel):
    list: Any = []
    total: int = 0
```

这是本课的简单结构；以后可以收紧列表元素类型。完整响应为 `Response` 包裹 `PageResponse`：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": {
    "list": [
      {"id": 3, "username": "ccc", "name": "哈牛魔", "status": 1},
      {"id": 1, "username": "admin", "name": "哈基米", "status": 1}
    ],
    "total": 2
  }
}
```

上面省略了角色、头像等其他用户字段，用于说明层次；前端读的是 `res.data.list`，不是直接读 `res.list`。

---

## 第八章 curl 验证与本课实际结果

### 8.1 管理员登录获取 token

```bash
curl -sS -X POST 'http://localhost:8000/api/auth/login' \
  -H 'Content-Type: application/json' \
  -d '{"username":"你的管理员账号","password":"当前密码"}'
```

复制响应中的 `data.token`。笔记不保存实际密码或完整 token。

### 8.2 查询第一页

```bash
curl -sS 'http://localhost:8000/api/user/list?page=1&page_size=10' \
  -H 'Authorization: Bearer 替换为管理员token'
```

### 8.3 搜索“哈”

```bash
curl -sS -G 'http://localhost:8000/api/user/list' \
  -H 'Authorization: Bearer 替换为管理员token' \
  --data-urlencode 'page=1' \
  --data-urlencode 'page_size=10' \
  --data-urlencode 'keywords=哈'
```

`-G` 将参数附加到 GET 请求 URL 中，`--data-urlencode` 处理中文编码。参数名必须是后端声明的 `keywords`。

### 8.4 验证分页与权限

只有少量测试数据时，可以设置 `page_size=1`，分别查询第 1、2 页，观察返回用户变化。总数应保持为同一条件下的全部匹配数。

学生权限测试需要先登录学生账号，再用其自己的 token 查询相同接口。`username=bbb` 或 `keywords=bbb` 只是筛选条件，不会改变请求者身份。预期业务响应为：

```json
{"code":403,"message":"无权限访问","data":null}
```

### 8.5 已确认与未确认的结果

| 验证 | 本课记录 |
|---|---|
| 管理员查询列表 | curl 已成功返回列表及总数 |
| 搜索“哈” | 修正后返回“哈牛魔”“哈基米”，`total=2`，未包含 bbb |
| 创建测试用户 ccc | 已创建为学生，密码使用 bcrypt 哈希保存 |
| 状态展示 | bbb 临时改为 0 后，用户确认页面显示正确；随后恢复为 1 |
| 学生账号拒绝访问 | 已提供测试步骤，对话中未记录最终执行响应 |
| 多页翻页 | 当前代码已绑定页码事件，尚未记录多页数据的完整实测结果 |

不要把“代码已写”或“预期结果”当成已经执行的测试结果。

### 8.6 第 13 节上传前检查（2026-11-06）

- 前端使用本机已安装的 Node 24.16.0 执行 Vite 生产构建，构建成功；存在资源块超过 500 kB 的提示，不影响本次构建完成。
- 后端 Python 文件通过语法检查。
- 使用独立的 SQLite 内存数据库验证了按 ID 降序分页、按账号/姓名筛选、空结果、状态字段返回，以及响应不含密码字段。
- 直接调用管理员鉴权函数，确认管理员通过、学生抛出业务码 403。该项是函数级验证，不替代携带学生 token 的完整 HTTP 测试。
- 没有为上述检查连接实际 MySQL、修改真实用户或重新执行浏览器操作；实际 HTTP 与页面验证记录仍按上一小节区分。

---

## 第九章 踩坑实录

| 问题 | 原因 | 处理方式 |
|---|---|---|
| `get_user_page` 和 `get_user_page_list` 不一致 | 定义与调用名称不同 | 按用户约定统一为 `get_user_page_list` |
| 从鉴权模块导入分页服务 | 函数不在该模块中 | 删除错误导入，通过 `user_services.get_user_page_list` 调用 |
| 查询接口返回 404 | 当前运行进程没有加载新增路由 | 检查 `/docs` 或 `/openapi.json`，重新加载后端 |
| 查询接口返回 500 | 在 `offset/limit` 后调用 `order_by` | 改为先排序、后分页 |
| `Query` 没有 `query` 属性 | 链式调用误写 `.query.offset(...)` | 删除多余 `.query`，直接 `.offset(...)` |
| 搜索“哈”仍出现 bbb | curl 传 `name`，接口接收 `keywords`，筛选条件未触发 | 统一请求参数名为 `keywords` |
| 使用 `User.keywords` | 把请求参数名误当成模型字段 | 改为 `User.username`，与 `User.name` 组合搜索 |
| 导入 `operator.or_` | 导入了 Python 运算工具，而非此处所需 SQL 组合函数 | 使用 `from sqlalchemy import or_` |
| 所有用户都显示禁用 | `UserResponse` 没返回 `status`，前端拿到 `undefined` | 在响应模型中增加 `status: int` |
| 标签使用 `error` | 不符合此处 Element Plus 标签类型 | 改为 `danger` |

权限问题通常查看 token、角色和账号状态；404 检查路由是否存在；500 则查看后端具体堆栈。不要将所有错误都当成“缺少导入”。

---

## 第十章 当前可完善点（本次不修改代码）

1. 查询框早期曾写“请输入账号或密码查询”，当前已改为“请输入账号或名称查询”，与搜索逻辑一致。密码不是本接口的搜索字段。
2. 后端可增加页码、每页条数的上下限校验。
3. `tableData.value`、`total.value` 可在响应缺失时提供合理默认值，避免得到 `undefined`。
4. 当前 `User.vue` 中 `Loading`、`ElDialog`、`ElPopover` 没有被使用，可在后续清理。
5. 页面路由守卫目前只检查是否有 token，没有单独限制管理员进入用户页面；真正的管理员限制由后端接口执行。后续可以增加前端菜单与路由体验上的控制，后端鉴权仍需保留。
6. 如果以后允许选择每页条数，需要增加对应分页布局与事件处理。

---

## 常见问题

**Q1：为什么主要在写 User.vue，却仍需要后端？**

用户看到的查询框、表格、状态和分页都由 Vue 页面负责，因此前端代码占比明显。数据筛选、排序、分页和权限判断仍由后端完成。

**Q2：修改数据库状态后，页面为什么要重新查询？**

页面保存的是上一次请求返回的快照，没有实时订阅数据库。刷新页面或重新加载列表后才会显示新状态。

**Q3：token 是密码加密的结果吗？**

不是。项目先验证密码，成功后将用户 ID 和过期时间用服务器密钥签名生成 JWT。它有有效期；当前修改密码不会自动撤销旧 JWT。

**Q4：为什么有时 list 是空的，但 total 不为 0？**

可能是查询了超出结果范围的页码。`total` 统计全部匹配数，`list` 只包含当前页，所以搜索时需要回到第 1 页。

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| Query 对象 | SQLAlchemy 用于构建查询的对象 |
| 服务端分页 | 由数据库查询当前页记录，前端不先取全部数据 |
| offset | 跳过前面多少条记录 |
| limit | 本次最多取多少条记录 |
| 模糊查询 | 按关键词匹配字段的一部分 |
| `or_` | 将多个 SQL 条件用“或”连接 |
| row | 表格插槽传入的当前行数据对象 |
| 作用域插槽 | 父组件使用子组件提供的数据自定义展示内容 |
| `v-model:current-page` | 将组件当前页与页面状态双向绑定 |
| total | 符合条件的全部记录数，而非当前页条数 |

---

## 本章自检清单

- [ ] 能画出 User.vue 的查询区、表格、分页区结构
- [ ] 能解释 params、tableData、loading、total 各自负责什么
- [ ] 能说明 onMounted 为什么调用 load
- [ ] 能解释 GET 请求中的 params 与请求体 data 的区别
- [ ] 知道 pageSize 与 page_size 的映射关系
- [ ] 能解释为什么搜索前将页码设为 1
- [ ] 能解释表格的 prop、插槽的 row 与后端字段的关系
- [ ] 能说明 status 缺失时为什么错误显示为禁用
- [ ] 能把分页组件页码变化与重新请求连接起来
- [ ] 能解释 query、items、UserResponse、PageResponse 的区别
- [ ] 能写出先筛选、统计总数、排序、分页的查询结构
- [ ] 能区分查询条件与请求者身份
- [ ] 已自行补做学生权限拒绝和多页翻页验证
- [ ] 知道 bbb 的临时禁用状态已经恢复为正常
