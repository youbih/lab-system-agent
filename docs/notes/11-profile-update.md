# 开发用户修改个人信息功能

> 对应课程:第 11 节
> 对应项目:`agent-lab/lab-system-agent`
> 涉及文件:
> - 后端:`app/schemas/user.py`(UserUpdateRequest)、`app/api/user.py`、`app/services/user_services.py`
> - 前端:`src/views/Profile.vue`、`src/api/user.js`、`src/api/file.js`(新增)、`src/layouts/Layout.vue`
> 阅读建议：按小节阅读，配合项目源码与示例理解执行过程。

---

## 阅读说明：代码版本与讲解方式

这份笔记根据原课程记录与当前项目源码整理，不代表拥有每节课的完整历史快照。保留原记录中的课程重点和排错经历；历史代码、当前实现、建议改进会分别说明。未在对话或原记录中确认的测试，不写成新增的实测结论。

代码按“完整片段 → 按执行顺序拆解 → 输入/返回值例子 → 页面或接口效果”阅读。仅有一两行的导入、配置或重复片段使用紧接代码的说明，避免反复展开相同逻辑。

**本节版本对应：** 第 11 节原记录使用 profile.vue、GET /info、PUT /update；当前源码已改为 Profile.vue 与 GET/PUT /me。下文主示例按当前接口阅读，保留历史差异说明；新增 status 展示属于第 13 节，不当作本节新增功能。

---

## 第零章 这节课干了什么

做出完整的"个人中心"页:查看并修改自己的资料(姓名/邮箱/手机号),上传头像,右上角实时显示头像和名字。

这是第一个**完整的"编辑类"功能**,模式以后反复用:

```
回显(查) → 修改(填) → 校验 → 保存(改) → 状态同步
```

---

## 第一章 后端：更新接口

### 1.1 契约：UserUpdateRequest(schemas/user.py)

```python
class UserUpdateRequest(BaseModel):
    name: str | None = None       # 全部可选:用户想改哪个传哪个
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None
```

**按执行顺序拆解：**

#### 第一步：允许部分字段不提供

```python
name: str | None = None
email: str | None = None
phone: str | None = None
avatar: str | None = None
```

UserUpdateRequest 来自项目 schema，继承 BaseModel。每个字段既允许 None，又有默认 None；用户只改名称时可以只发送 name。接口不是因此自动更新，还要在 service 中读取这些字段并写入 ORM 对象。

#### 第二步：只暴露可修改字段

模型不接收 username、role、password 作为可修改字段；密码有单独接口。current_user 决定更新对象，不能靠前端的 disabled 输入框实现权限保护。

**把结果连起来：** 请求 schema 限定资料修改输入，具体如何忽略 None 由 service 决定。


**全部字段可选**是"部分更新"的前提:用户只改名字时,不用把其他字段也传一遍。

### 1.2 接口层(api/user.py)

```python
@router.put("/me")
def update_user_info(data: UserUpdateRequest,
                     current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """更新当前登录用户信息"""
    res = user_services.update_user_info(db, current_user, data)
    return Response.success(data=res)
```

**按执行顺序拆解：**

#### 第一步：接收资料与当前登录用户

```python
@router.put("/me")
def update_user_info(data: UserUpdateRequest,
                     current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
```

这里采用当前路径，历史笔记用 /update。data 从 JSON 解析；current_user 经 token 验证查出；db 用于提交。即使客户端传了另一个 id，当前服务仍使用依赖确定的用户。

#### 第二步：调用业务并包装返回

```python
res = user_services.update_user_info(db, current_user, data)
return Response.success(data=res)
```

res 是 service 返回的 UserResponse，外层成功响应再放入 data。服务抛异常时不执行成功返回；正常时前端可以从 res.data 读取更新后的资料。

**把结果连起来：** HTTP 接口负责接收与认证，更新字段和数据库提交在 service。


注意:**改的是"当前登录用户"**(current_user 从 token 里查出来),不接受前端传 user_id —— 否则任何人都能改别人的资料,这是越权漏洞。

### 1.3 业务层(services/user_services.py)

```python
def update_user_info(db: Session, user: User, data: UserUpdateRequest):
    user_dict = data.model_dump(exclude_none=True)   # 排除所有值为 None 的字段
    for field, value in user_dict.items():
        setattr(user, field, value)                   # 逐个写到 ORM 对象上
    db.commit()
    db.refresh(user)                                  # 读回落库后的最新状态
    return UserResponse.model_validate(user)
```

**按执行顺序拆解：**

#### 第一步：把请求模型转成待更新字典

```python
user_dict = data.model_dump(exclude_none=True)
```

例如只提交 name，其他默认 None 不出现在字典中。显式提交 email:null 也会被排除，因此这里是“忽略所有 None”，不是严格区分“没传”和“传了 null”；当前写法不能用 null 清空数据库列。

#### 第二步：逐个属性赋值给 ORM 用户

```python
for field, value in user_dict.items():
    setattr(user, field, value)
```

假设字典是 {"name":"新名字"}，本次相当于 user.name="新名字"。field 是属性名字符串，value 是新值；并非每个字段都要手写一行。数据来自限定好的请求模型。

#### 第三步：提交并刷新数据库状态

```python
db.commit()
db.refresh(user)
```

commit 让变更持久化；refresh 再查询最新字段。两者不是同一动作，保存是否成功不依赖必须 refresh；这里刷新后会继续组装并返回用户响应。

#### 第四步：转换为返回模型

```python
return UserResponse.model_validate(user)
```

从已更新 ORM 对象读取响应模型声明字段。API 再把结果放入统一响应的 data，前端拿它同步用户状态；数据库的 password 不会作为该响应模型字段返回。

**把结果连起来：** 输入模型 → 去掉 None → 动态赋值 → 提交/刷新 → 返回用户资料。


三个关键点:

| 技巧 | 作用 |
|---|---|
| `model_dump(exclude_none=True)` | 没传的字段(None)不参与更新,不会把已有值覆盖成 NULL |
| `setattr` 循环 | 动态赋值,不用每个字段写一行 |
| `db.refresh(user)` | 拿落库后的最新状态(如自动更新的 update_time) |

---

## 第二章 前端：API 层新增

### 2.1 api/user.js

```javascript
export function getUserInfo() {
  return request({ url: '/api/user/me', method: 'get' })
}

export function updateUserInfo(data) {
  return request({ url: '/api/user/me', method: 'put', data })
}
```

**按执行顺序拆解：**

#### 第一步：加载个人资料

```javascript
return request({ url: "/api/user/me", method: "get" })
```

getUserInfo 来自 src/api/user.js，调用后端；不要与 utils/auth.js 中读取 localStorage 的同名函数混淆。这里两个接口都按当前源码使用 /me，历史 /info、/update 只在版本说明保留。

#### 第二步：保存资料

```javascript
return request({ url: "/api/user/me", method: "put", data })
```

同一路径用不同 HTTP 方法区分查询和修改。PUT 的 data 是 JSON 请求体，GET 此处不需要提交用户 ID。两个请求都会经过公共 token 拦截器。

**把结果连起来：** 页面使用 API 函数，不必在组件中重复写 URL 与认证头。


### 2.2 api/file.js(新)：文件上传

```javascript
export function uploadFileApi(file) {
  const formData = new FormData()        // 浏览器内置的表单打包器
  formData.append('file', file)          // 键名 'file' 必须和后端参数名一致
  return request({
    url: '/api/files/upload',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' }   // 文件上传专用格式
  })
}
```

**按执行顺序拆解：**

#### 第一步：创建文件表单容器

```javascript
const formData = new FormData()
```

FormData 是浏览器原生工具，不需要从 Vue 导入。此时只有空容器，并没有开始上传。file 参数应是真正的 File/Blob 对象，不是用户电脑上的路径字符串。

#### 第二步：按后端字段名装入文件

```javascript
formData.append("file", file)
```

键名 file 与后端 upload(file: UploadFile) 对应。若改成其他键名，框架可能认为缺少必填文件，返回 422。

#### 第三步：返回上传请求 Promise

```javascript
return request({
  url: "/api/files/upload",
  method: "post",
  data: formData,
  headers: { "Content-Type": "multipart/form-data" }
})
```

data 是 FormData，所以不是普通 JSON。上面保留源码中的 Content-Type；实际发送还需要 multipart boundary，浏览器/Axios 会处理相应编码，通常也可让浏览器自动决定该头。函数返回后，调用方用 await 取得上传结果。

**把结果连起来：** 选择文件 → 封装 FormData → 上传 → 返回可访问 URL，尚未保存用户头像字段。


知识点:

- `FormData`:浏览器自带,不用 import
- `append('file', file)`:键名与后端 `upload(file: UploadFile)` 的参数名是契约点
- 文件上传的 Content-Type 是 `multipart/form-data`,和普通 JSON 请求不同

---

## 第三章 前端：个人信息页(Profile.vue)

### 3.1 页面结构

```
el-card(个人信息卡片)
└── el-form(带 rules 校验)
    ├── 头像(el-upload + 自定义上传)
    ├── 账号(disabled,不让改)
    ├── 名称(prop="name",必填)
    ├── 角色(只读,computed 翻译:admin→管理员)
    ├── 邮箱(prop="email",格式校验)
    ├── 手机号(prop="phone",正则校验)
    └── 保存修改按钮
```

### 3.2 回显：页面打开时自动填数据

```javascript
const loadUserInfo = async () => {
  loading.value = true
  try {
    const res = await getUserInfo()
    if (res.code === 200) {
      Object.assign(form, res.data)
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadUserInfo()
})
```

**按执行顺序拆解：**

#### 第一步：定义资料加载函数并开启遮罩

```javascript
const loadUserInfo = async () => {
  loading.value = true
```

loadUserInfo 是自己定义的函数，async 允许等待网络请求。loading 通过 ref 定义，模板 v-loading="loading" 随它显示加载遮罩；这里没有修改按钮的 submitting 状态。

#### 第二步：请求后端当前用户资料

```javascript
const res = await getUserInfo()
```

这里应调用从 @/api/user 导入的接口函数。token 决定当前用户，页面不需要传 ID。await 等响应后，res 是响应拦截器返回的统一业务 JSON。

#### 第三步：成功时把同名字段写回表单

```javascript
if (res.code === 200) {
  Object.assign(form, res.data)
}
```

例如后端 data.name 为“新名字”，就更新 form.name；邮箱、手机号等也按键赋值。Object.assign 保留原响应式 form 对象，输入框通过 v-model 立即显示已有值。额外键如 id/status 也会被复制，不是自动只挑初始字段。

#### 第四步：最后结束加载

```javascript
finally {
  loading.value = false
}
```

成功或异常都结束遮罩。首次进入组件时，onMounted 的回调调用这个函数；以后每次改输入值，不会因此自动再次执行 onMounted。

**把结果连起来：** 页面挂载 → 后端读取资料 → 写入 form → 输入框回显 → 关闭遮罩。


- `onMounted`:组件挂载完成时触发一次
- `Object.assign(form, res.data)`:同名属性批量赋值,省得逐字段写

### 3.3 保存：校验 + 提交 + 状态同步

```javascript
const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const res = await updateUserInfo(form)
    if (res.code === 200) {
      updateUser(res.data)
      ElMessage.success('更新成功喵喵')
    }
  } finally {
    submitting.value = false
  }
}
```

**按执行顺序拆解：**

#### 第一步：点击保存后校验表单

```javascript
const valid = await formRef.value.validate().catch(() => false)
if (!valid) return
```

validate 是 Element Plus 表单方法，检查 rules 中关联到 prop 的规则。比如名称必填不满足则提前退出，不向后端保存。formRef 不是表单数据本身。

#### 第二步：开启提交加载并等待保存

```javascript
submitting.value = true
const res = await updateUserInfo(form)
```

submitting 绑定按钮，loading 绑定页面，两者用途不同。updateUserInfo 将整个 form 发送到当前资料 PUT 接口，后端 schema/service 限定真正可改字段。

#### 第三步：把服务器结果同步给共享状态

```javascript
if (res.code === 200) {
  updateUser(res.data)
  ElMessage.success("更新成功喵喵")
}
```

res.data 是后端返回的最新用户资料。updateUser 来自 useUser，既写 localStorage 又更新共享 userInfo ref，所以 Layout 的名称/头像不用整页刷新就能更新。只改局部 form 不一定能让其他组件知道。

#### 第四步：恢复保存按钮

```javascript
finally {
  submitting.value = false
}
```

所有经过提交的正常/异常路径都会收尾。失败时不调用 updateUser；错误信息主要由公共请求层显示。

**把结果连起来：** 本地表单是编辑中的值，后端保存成功后的资料才用来同步整个应用的用户显示。


### 3.4 头像上传(el-upload)

```vue
<el-upload
  class="avatar-uploader"
  :http-request="handleFileUpload"
  :show-file-list="false"
  accept="image/jpeg,image/png,image/gif,image/webp"
  :before-upload="beforeAvatarUpload"
>
  <img v-if="form.avatar" :src="form.avatar" class="avatar" />
  <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
</el-upload>
```

**按执行顺序拆解：**

#### 第一步：指定自定义上传函数

```vue
:http-request="handleFileUpload"
```

这是 el-upload 的配置片段，意思是让组件调用我们的 handleFileUpload，而不使用默认 action 上传。handleFileUpload 是函数引用，没有在模板求值时立即执行。

#### 第二步：限制选择并执行上传前检查

```vue
accept="image/jpeg,image/png,image/gif,image/webp"
:before-upload="beforeAvatarUpload"
```

accept 提供文件选择提示，beforeAvatarUpload 执行前端类型和大小判断。它们不能代替后端规则；用户仍能直接 curl 绕过页面。详细校验函数在本节后面补充。

#### 第三步：按表单头像值显示预览

```vue
<img v-if="form.avatar" :src="form.avatar" class="avatar" />
<el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
```

有头像 URL 时显示图片，没有则显示加号；show-file-list=false 隐藏组件默认列表。这里采用当前 form.avatar，原笔记 imageUrl 是早期示意名称，不能在没有定义时直接使用。

**把结果连起来：** 组件负责选择和展示，上传的请求逻辑仍由我们自己的函数实现。


```javascript
const handleFileUpload = async ({ file }) => {
  try {
    const res = await uploadFileApi(file)
    if (res.code === 200) {
      form.avatar = res.data?.url
    }
  } catch {}
}
```

**按执行顺序拆解：**

#### 第一步：接收组件传入的上传选项

```javascript
const handleFileUpload = async ({ file }) => {
```

参数花括号是解构：从组件给的选项对象里取出 file，而不是自己创建文件对象。组件触发上传时才调用这个函数。

#### 第二步：调用文件接口并保存 URL

```javascript
const res = await uploadFileApi(file)
if (res.code === 200) {
  form.avatar = res.data?.url
}
```

例如接口返回 /uploads/demo.jpg，就把这个路径存到表单的 avatar。响应式更新使页面出现预览。此处只更新前端 form，没有调用 updateUserInfo，因此还没有修改 users.avatar。

#### 第三步：理解当前错误处理边界

```javascript
catch {}
```

当前源码用空 catch 结束上传异常，公共拦截器通常已经显示请求错误，但此处没有回调标记或额外处理。不能把“没有继续抛异常”当成上传成功。

**把结果连起来：** 上传成功拿 URL，用户再点击保存资料，才把 URL 与用户记录关联。


- `accept` 白名单:`image/jpeg` 同时覆盖 .jpg/.jpeg(同义)
- `:http-request` 自定义上传,走我们封装的 uploadFileApi
- 上传只是拿到 url 存进 form.avatar,**点"保存修改"才真正入库** —— 两步分离

### 3.5 上传前校验：类型和体积

```javascript
const beforeAvatarUpload = (file) => {
  const imageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  if (!imageTypes.includes(file.type)) {
    ElMessage.error('只能上传图片')
    return false
  }
  if (file.size / 1024 / 1024 > 2) {
    ElMessage.error('上传图片大小不能超过2M')
    return false
  }
  return true
}
```

**按执行顺序拆解：**

#### 第一步：先检查浏览器报告的文件类型

```javascript
if (!imageTypes.includes(file.type)) {
  ElMessage.error("只能上传图片")
  return false
}
```

imageTypes 是允许的 MIME 类型数组，includes 判断本次 file.type 是否在其中。不符合就提示并返回 false，阻止组件继续上传。MIME 类型并不是经过内容鉴定的最终证据，后端仍要有自己的校验。

#### 第二步：再把字节换算成 MB 检查

```javascript
if (file.size / 1024 / 1024 > 2) {
  ElMessage.error("上传图片大小不能超过2M")
  return false
}
```

浏览器 File.size 的单位为字节，连续除以 1024 换算为 MiB 量级。这里头像页面限制为 2，而后端通用上传上限是 100，两者职责不同，不能只依赖前端限制。

#### 第三步：允许继续上传

```javascript
return true
```

前两个失败分支都没有触发，才返回 true。随后 el-upload 调用配置的自定义上传函数，开始真实网络请求。

**把结果连起来：** 选文件 → 类型检查 → 体积检查 → 允许后才请求上传接口。


### 3.6 角色显示：computed 翻译

```javascript
const roleLabel = computed(() => {
  return form.role === 'admin' ? '管理员' : form.role === 'student' ? '学生' : '未知角色'
})
```

**按执行顺序拆解：**

#### 第一步：建立计算属性

```javascript
const roleLabel = computed(() => {
```

computed 从 Vue 导入，roleLabel 是计算属性的 ref。传入函数读取响应式 form.role，Vue 会跟踪这个依赖。

#### 第二步：把角色代码映射成文字

```javascript
return form.role === "admin" ? "管理员" : form.role === "student" ? "学生" : "未知角色"
```

管理员显示“管理员”，学生显示“学生”，其他值显示“未知角色”。表达式只产生展示文案，不修改数据库角色，也不授予管理员权限。

#### 第三步：绑定只读展示

```javascript
<el-input :model-value="roleLabel" disabled />
```

这是 Vue 模板片段，绑定计算结果而不是允许用户编辑角色。资料请求填入 form.role 后，计算结果自动变化。disabled 属于交互限制，真正权限仍由后端决定。

**把结果连起来：** 回显角色代码 → 计算中文文案 → 页面自动显示。


数据库存机器码(admin/student),页面显示人话。computed:依赖变了自动重算。

---

## 第四章 Layout.vue 的联动

```javascript
// 跳转到个人信息页
const goPerson = () => {
  router.push('/manager/profile')
}

// 右上角实时头像 + 名字
const { userInfo } = useUser()
```

**这段代码怎样执行：** 这里保留原笔记的 goPerson 历史函数：调用时 router.push 切换到 /manager/profile；useUser 返回共享 userInfo 给布局显示。当前布局使用 @command="handleCommand" 处理下拉项，个人信息对应同一路径，不能只写函数却不绑定事件。


```html
<img :src="userInfo?.avatar ? 'http://localhost:8000' + userInfo.avatar : logoUrl" />
<div>{{ userInfo?.name }}</div>
```

**按执行顺序拆解：**

#### 第一步：按是否有头像选择图片地址

```html
:src="userInfo?.avatar ? 'http://localhost:8000' + userInfo.avatar : logoUrl"
```

这是属性片段，不是独立标签。冒号表示按 JavaScript 表达式求值；有相对头像路径时加后端地址，无头像时使用已导入的 logoUrl。当前硬编码 localhost 的限制需要在远程/部署时另外考虑。

#### 第二步：安全读取共享名称

```html
<div>{{ userInfo?.name }}</div>
```

userInfo 可能尚为空，可选链避免直接访问空值属性报错。它是 useUser 的共享 ref，模板自动解包；资料保存成功调用 updateUser 后，该名称会随响应式状态更新。

**把结果连起来：** 布局不需要再次读取编辑页的 form，它订阅共享用户信息即可同步显示。


知识点:

- avatar 存的是相对路径 `/uploads/xxx`,显示时要拼后端地址
- 动态绑定图片要 `:src`(带冒号才是表达式);本地兜底图要 `import logoUrl from '@/assets/imgs/logo.png'`
- `userInfo?.name`:可选链,未登录时 null 不报错
- 因为 userInfo 是响应式的,profile 页保存成功后右上角**不用刷新**就变了

---

## 第五章 踩坑实录（沿用原笔记记录）

原笔记的排错记录保留如下；本次没有重新执行数据库修改，也不将其视为所有问题已经在当前源码修复。

| 坑 | 症状 | 解法 |
|---|---|---|
| `reactivate` 拼写 | 白屏(运行时才炸) | 白屏先查 Console 的 ReferenceError |
| 手机号保存后刷新丢失 | 静默失败 | **模型里 email 写了两遍,phone 没有列**;模型+数据库两边都要改(ALTER TABLE) |
| `res.data?url` | 语法错误 | 可选链是 `?.`,点和问号不分家 |
| `import { getUserInfo } from '@/utils/auth'` | 数据回显不了 | 同名函数张冠李戴:调接口的来自 `@/api/`,读存储的来自 `@/utils/` |
| 重复声明 getUserInfo | 编译报错 | 同一作用域一个名字只能声明一次 |
| `src="userInfo.avatar"` 没冒号 | 头像不显示 | 动态值必须 `:src` |
| 头像框长方形 | 样式 | width/height 改成相等(正方形) |

---

## 第六章 当前源码检查补充与常见问题

**当前待注意：** Profile.vue 手机号表单项仍写为 `prob="phone"`，而 Element Plus 校验关联应为 `prop="phone"`；本次只记录，不改源码。当前“回显后直接显示”的头像相对路径依赖开发代理，Layout 中则使用显式后端前缀。历史个人资料路径 `/info`、`/update` 现在均用 `/me` 区分 GET 与 PUT；Profile 文件名也已经统一为大写。


**Q1: 为什么更新接口不接受 user_id 参数?**
安全设计。改谁由 token 决定(current_user),前端传 user_id 就能改别人的资料(越权)。

**Q2: `Object.assign(form, res.data)` 和逐个赋值有什么区别?**
功能等价,前者省代码。注意它是"同名覆盖":res.data 里多的字段(如 id)也会抄进 form,因此要知道 form 可能获得额外键，提交允许修改哪些字段仍由后端 schema 决定。

**Q3: 上传头像后没点保存,刷新页面会怎样?**
文件已经在服务器 uploads/ 里了,但数据库 avatar 字段没更新 → 刷新后头像框还是空的。文件成为"孤儿文件",需要定期清理(生产环境的考量)。

**Q4: `disabled` 和 `readonly` 的区别?**
disabled 的输入框变灰不可交互;readonly 可以选中复制。账号这种不该改的用 disabled。

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| 回显 | 编辑页打开时先把已有数据填进表单 |
| 部分更新 | 当前写法只更新值不为 None 的字段(exclude_none=True) |
| FormData | 浏览器内置的文件/表单打包器 |
| computed | 计算属性,依赖变化自动重算 |
| DTO | 数据传输对象(UserResponse 就是),控制对外暴露的字段 |
| 可选链 `?.` | 对象为 null/undefined 时安全返回 undefined 不报错 |

---

## 本章自检清单

- [ ] 能说出"编辑页五步走":回显→修改→校验→保存→同步
- [ ] 能解释 exclude_none=True 的作用
- [ ] 能解释为什么更新接口不收 user_id
- [ ] 能写 FormData 上传文件,知道键名要和后端参数名一致
- [ ] 能解释 computed 在角色翻译中的用法
- [ ] 知道 avatar 存相对路径、显示时拼 baseURL
- [ ] 能说出"模型改了数据库也要改"(ALTER TABLE)
- [ ] 知道同名函数在不同模块的区别(@/api vs @/utils)
