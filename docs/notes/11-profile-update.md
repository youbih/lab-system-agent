# 开发用户修改个人信息功能

> 对应课程:第 11 节
> 对应项目:`agent-lab/lab-system-agent`
> 涉及文件:
> - 后端:`app/schemas/user.py`(UserUpdateRequest)、`app/api/user.py`、`app/services/user_services.py`
> - 前端:`src/views/profile.vue`、`src/api/user.js`、`src/api/file.js`(新增)、`src/layouts/Layout.vue`
> 阅读时间:约 30 分钟

---

## 第零章 这节课干了什么

做出完整的"个人中心"页:查看并修改自己的资料(姓名/邮箱/手机号),上传头像,右上角实时显示头像和名字。

这是第一个**完整的"编辑类"功能**,模式以后反复用:

```
回显(查) → 修改(填) → 校验 → 保存(改) → 状态同步
```

---

## 第一章 后端:更新接口

### 1.1 契约:UserUpdateRequest(schemas/user.py)

```python
class UserUpdateRequest(BaseModel):
    name: str | None = None       # 全部可选:用户想改哪个传哪个
    email: str | None = None
    phone: str | None = None
    avatar: str | None = None
```

**全部字段可选**是"部分更新"的前提:用户只改名字时,不用把其他字段也传一遍。

### 1.2 接口层(api/user.py)

```python
@router.put("/update")
def update_user_info(data: UserUpdateRequest,
                     current_user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """更新当前登录用户信息"""
    res = user_services.update_user_info(db, current_user, data)
    return Response.success(data=res)
```

注意:**改的是"当前登录用户"**(current_user 从 token 里查出来),不接受前端传 user_id —— 否则任何人都能改别人的资料,这是越权漏洞。

### 1.3 业务层(services/user_services.py)

```python
def update_user_info(db: Session, user: User, data: UserUpdateRequest):
    user_dict = data.model_dump(exclude_none=True)   # 只取用户传了的字段
    for field, value in user_dict.items():
        setattr(user, field, value)                   # 逐个写到 ORM 对象上
    db.commit()
    db.refresh(user)                                  # 读回落库后的最新状态
    return UserResponse.model_validate(user)
```

三个关键点:

| 技巧 | 作用 |
|---|---|
| `model_dump(exclude_none=True)` | 没传的字段(None)不参与更新,不会把已有值覆盖成 NULL |
| `setattr` 循环 | 动态赋值,不用每个字段写一行 |
| `db.refresh(user)` | 拿落库后的最新状态(如自动更新的 update_time) |

---

## 第二章 前端:API 层新增

### 2.1 api/user.js

```javascript
export function getUserInfo() {              // GET /api/user/info
  return request({ url: '/api/user/info', method: 'get' })
}

export function updateUserInfo(data) {       // PUT /api/user/update
  return request({ url: '/api/user/update', method: 'put', data })
}
```

### 2.2 api/file.js(新):文件上传

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

知识点:

- `FormData`:浏览器自带,不用 import
- `append('file', file)`:键名与后端 `upload(file: UploadFile)` 的参数名是契约点
- 文件上传的 Content-Type 是 `multipart/form-data`,和普通 JSON 请求不同

---

## 第三章 前端:个人信息页(profile.vue)

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

### 3.2 回显:页面打开时自动填数据

```javascript
const loadUserInfo = async () => {
  loading.value = true
  try {
    const res = await getUserInfo()
    if (res.code === 200) {
      Object.assign(form, res.data)   // 批量把返回字段抄进 form
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadUserInfo()                       // 页面挂载后自动执行
})
```

- `onMounted`:组件挂载完成时触发一次
- `Object.assign(form, res.data)`:同名属性批量赋值,省得逐字段写

### 3.3 保存:校验 + 提交 + 状态同步

```javascript
const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)  // 校验
  if (!valid) return
  submitting.value = true
  try {
    const res = await updateUserInfo(form)
    if (res.code === 200) {
      updateUser(res.data)              // 同步全局状态(右上角名字立刻变)
      ElMessage.success('更新成功')
    }
  } finally {
    submitting.value = false
  }
}
```

### 3.4 头像上传(el-upload)

```html
<el-upload
  class="avatar-uploader"
  :http-request="handleFileUpload"     <!-- 自定义上传:不走默认 action -->
  :show-file-list="false"
  accept="image/jpeg,image/png,image/gif,image/webp"
>
  <img v-if="imageUrl" :src="imageUrl" class="avatar" />
  <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
</el-upload>
```

```javascript
const handleFileUpload = async ({ file }) => {
  const res = await uploadFileApi(file)
  if (res.code === 200) {
    form.avatar = res.data?.url     // 存 url,随表单一起提交
  }
}
```

- `accept` 白名单:`image/jpeg` 同时覆盖 .jpg/.jpeg(同义)
- `:http-request` 自定义上传,走我们封装的 uploadFileApi
- 上传只是拿到 url 存进 form.avatar,**点"保存修改"才真正入库** —— 两步分离

### 3.5 角色显示:computed 翻译

```javascript
const roleLabel = computed(() => {
  return form.role === 'admin' ? '管理员' : form.role === 'student' ? '学生' : '未知角色'
})
```

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

```html
<img :src="userInfo?.avatar ? 'http://localhost:8000' + userInfo.avatar : logoUrl" />
<div>{{ userInfo?.name }}</div>
```

知识点:

- avatar 存的是相对路径 `/uploads/xxx`,显示时要拼后端地址
- 动态绑定图片要 `:src`(带冒号才是表达式);本地兜底图要 `import logoUrl from '@/assets/imgs/logo.png'`
- `userInfo?.name`:可选链,未登录时 null 不报错
- 因为 userInfo 是响应式的,profile 页保存成功后右上角**不用刷新**就变了

---

## 第五章 踩坑实录(本课真实发生)

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

## 第六章 常见问题

**Q1: 为什么更新接口不接受 user_id 参数?**
安全设计。改谁由 token 决定(current_user),前端传 user_id 就能改别人的资料(越权)。

**Q2: `Object.assign(form, res.data)` 和逐个赋值有什么区别?**
功能等价,前者省代码。注意它是"同名覆盖":res.data 里多的字段(如 id)也会抄进 form,一般无害。

**Q3: 上传头像后没点保存,刷新页面会怎样?**
文件已经在服务器 uploads/ 里了,但数据库 avatar 字段没更新 → 刷新后头像框还是空的。文件成为"孤儿文件",需要定期清理(生产环境的考量)。

**Q4: `disabled` 和 `readonly` 的区别?**
disabled 的输入框变灰不可交互;readonly 可以选中复制。账号这种不该改的用 disabled。

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| 回显 | 编辑页打开时先把已有数据填进表单 |
| 部分更新 | 只更新传了的字段(exclude_none=True) |
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
