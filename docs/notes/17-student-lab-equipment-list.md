# 开发学生端:实验室列表 + 设备列表

> 对应课程:第 17 节
> 对应项目:`agent-lab/lab-system-agent/frontend`
> 涉及文件:`src/views/LabList.vue`(新)、`src/views/LabEquipment.vue`(新)、`src/router/index.js`、`src/layouts/Layout.vue`
> 前置课程:15(实验室管理)、16(设备管理)
> 阅读时间:约 30 分钟

---

## 第零章 这节课在干什么

前面做的都是**管理端**(管理员增删改查)。这节课做**学生端**:只读的浏览界面。

```
管理端(已有)                    学生端(本课)
实验室管理(Lab.vue)      →    实验室列表(LabList.vue)
设备管理(Equipment.vue)  →    设备列表(LabEquipment.vue)
可增删改                        只读 + 查看 + 预约(占位)
```

核心设计原则:**接口可以共用,视图必须分开**。同一个 `GET /api/lab/list` 接口,管理员看到的是可编辑表格,学生看到的是卡片画廊。真正的权限防线在后端(`get_current_admin` 管写操作)。

---

## 第一章 实验室列表页(LabList.vue)

### 1.1 页面结构:卡片画廊

```
[搜索框] [查询] [重置]
┌────────┬────────┬────────┬────────┐
│ 封面图  │ 封面图  │ 封面图  │ 封面图  │
│ 名称 开放│        │        │        │
│ 📍位置  │        │        │        │
│ 👥容量  │        │        │        │
│ 🕐时间  │        │        │        │
│ [查看设备][预约] │        │        │
└────────┴────────┴────────┴────────┘
              < 1 2 3 > 分页
```

### 1.2 响应式卡片网格

```html
<el-row :gutter="20">
  <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="lab in labList" :key="lab.id">
    <el-card>...</el-card>
  </el-col>
</el-row>
```

栅格的四档含义:手机屏幕 1 列、小平板 2 列、中屏 3 列、大屏 4 列 —— 一次写好,各种设备自适应。

### 1.3 封面图:比例统一的关键

```html
<div style="width: 100%; aspect-ratio: 16 / 9; overflow: hidden">
  <el-image :src="lab.img ? baseURL + lab.img : defaultCover" fit="cover" />
</div>
```

- `aspect-ratio: 16/9`:卡片封面统一 16:9,不管原图什么比例都不"奇怪"
- `fit="cover"`:图片裁剪填满(可能裁掉边缘,但布局整齐)
- 没图时用兜底图;图片加载失败显示"暂无封面"占位

### 1.4 搜索 + 清空自动恢复

```javascript
const loadList = async (toPage) => {
  if (toPage) page.value = toPage     // 搜索时回到第 1 页
  ...
  params: { page, page_size, keywords: keywords.value || undefined }
}

// 搜索框被清空(点 × 或删完)→ 自动恢复完整列表
watch(keywords, (val) => {
  if (!val) loadList(1)
})
```

**`watch` 新知识点**:被监视的值变化时执行动作。和 `computed`(算出新值)是响应式家族的兄弟。

---

## 第二章 设备列表页(LabEquipment.vue,学生只读)

### 2.1 页面结构

```
[返回] 数学实验室 [共 12 台设备]      [搜索框] [查询]
┌──────────────────────────────────────────┐
│ 📍 位置   👥 容量   🕐 开放时间           │ ← 实验室信息条(query 传参)
├──────────────────────────────────────────┤
│ 图片 │ 名称 │ 规格 │ 数量 │ 状态 │ [预约]  │
└──────────────────────────────────────────┘
```

### 2.2 图片预览(el-image 自带能力)

```html
<el-image
  :src="row.img ? baseURL + row.img : defaultImg"
  :preview-src-list="row.img ? [baseURL + row.img] : []"
  preview-teleported
  :hide-on-click-modal="true"
/>
```

- `preview-src-list`:传 URL 数组就开启点击放大(支持多图切换)
- `preview-teleported`:预览层挂到 body,不被表格裁剪
- 没图时给空数组 → 不可预览(调试时注意:功能没反应先看数据是不是 NULL)

### 2.3 预约按钮(占位)

```html
<el-button :disabled="row.status !== 1 || row.quantity <= 0" @click="goReserve(row)">
  预约
</el-button>
```

```javascript
const goReserve = (equipment) => {
  ElMessage.info(`「${equipment.name}」预约功能开发中,敬请期待`)
}
```

占位但做了个真实设计:**停用或库存为 0 时按钮禁用** —— 比"点了才提示"体验好。

---

## 第三章 页面间传参与状态保持(本课进阶点)

### 3.1 跳转传参:URL query

```javascript
// LabList.vue 跳转时,把实验室信息都带上
router.push({
  path: '/manager/labequipment',
  query: { lab_id, lab_name, location, capacity, open_time, close_time }
})

// LabEquipment.vue 接收
route.query.lab_id      // 数字要 Number() 转换
route.query.lab_name    // 直接显示
```

**query 传参的特点**:简单、刷新不丢、可分享链接;但数据暴露在 URL 里,只适合展示性数据。数据复杂时改用"带 id 过去,落地后再调接口"。

### 3.2 返回时保持页码(状态同步到 URL)

问题:第 2 页点进设备页,返回时回到了第 1 页。

解法:**把页码写进 URL**,返回时 URL 还带着它:

```javascript
// ① 初始化时从 URL 读页码
const page = ref(Number(route.query.page) || 1)

// ② 页码变化时写回 URL
watch(page, (val) => {
  router.replace({ query: { ...route.query, page: val } })
})
```

```javascript
// LabEquipment.vue 的返回:回退而不是重新跳
const goBack = () => {
  if (window.history.length > 1) router.back()
  else router.push('/manager/lablist')   // 直接输网址进来的兜底
}
```

**这是列表页的标配做法**:翻页时地址栏跟着变(?page=2),刷新/返回/分享链接都不丢状态。淘宝、谷歌翻页都是这个模式。

---

## 第四章 权限:菜单按角色显示(Layout.vue)

```html
<el-menu-item index="/manager/lablist" v-if="userInfo?.role === 'student'">实验室列表</el-menu-item>
<el-menu-item index="/manager/lab" v-if="userInfo?.role === 'admin'">实验室管理</el-menu-item>
<el-menu-item index="/manager/equipment" v-if="userInfo?.role === 'admin'">设备列表管理</el-menu-item>
```

`v-if` 按角色控制菜单渲染:学生只见"实验室列表",管理员全见。

三层权限防线(至此全部集齐):

```
v-if 控制菜单渲染       → 看不见(界面层)
路由守卫 beforeEach     → 进不去(路由层)
后端 get_current_admin  → 拿不到数据(安全层,真正的防线)
```

---

## 第五章 踩坑实录

| 坑 | 症状 | 解法 |
|---|---|---|
| 封面比例奇怪 | 原图比例各异 | 容器固定 `aspect-ratio: 16/9` + `fit="cover"` |
| 点图片不能预览 | 设备 img 全是 NULL | 功能没坏,是没数据;先查数据再怀疑代码 |
| 返回丢页码 | 组件重挂载,page 重置为 1 | 页码同步到 URL query |
| 学生看到管理菜单 | 忘了加 v-if | `v-if="userInfo?.role === 'admin'"` |
| 菜单点了空白 | index 是旧路径 /equ | 路由改名后菜单要同步改 |

---

## 术语表

| 术语 | 一句话解释 |
|---|---|
| watch | 监视响应式值的变化并执行动作 |
| aspect-ratio | CSS 属性,固定元素宽高比 |
| el-image preview | Element Plus 图片预览(preview-src-list) |
| URL query | 地址栏 ? 后面的参数,可用来在页面间传参/存状态 |
| router.back() | 回退到上一个历史记录(保留当时 URL) |
| 视图分离 | 同一数据,不同角色给不同页面(管理员可编辑/学生只读) |

---

## 本章自检清单

- [ ] 能说出学生端和管理端为什么是两个页面而不是一个页面加判断
- [ ] 能用 el-row/el-col 写出响应式卡片网格
- [ ] 能解释 aspect-ratio + fit=cover 解决什么问题
- [ ] 会用 watch 做"清空搜索框自动恢复"
- [ ] 能解释页码同步到 URL 的原理和好处
- [ ] 会用 el-image 的 preview-src-list 做图片预览
- [ ] 能画出三层权限防线(菜单/路由守卫/后端依赖)
- [ ] 知道 query 传参适合什么、不适合什么

---

## 下一课预告

预约功能(正式版):时间段选择、冲突校验(同一设备同一时间不能重复预约)、预约记录列表。后端核心是**时间区间重叠判断**。
