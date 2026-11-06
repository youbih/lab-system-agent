<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">
          <span>用户管理</span>
        </div>
      </template>
      <div style="margin-bottom: 10px">
        <el-input
          placeholder="请输入账号或名称查询"
          v-model="params.keywords"
          style="width: 240px; margin-right: 8px"
          @keyup.enter="handleSearch"
          clearable
          @clear="handleSearch"
        ></el-input>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button type="success" :icon="Plus" @click="handleCreate">新增</el-button>
      </div>
      <el-table
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="username" label="账号" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="avatar" label="头像">
          <template #default="{ row }">
            <div style="min-height: 50px">
              <img
                v-if="row.avatar"
                style="display: block; width: 50px; height: 50px; border-radius: 50%"
                :src="row.avatar"
                alt=""
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="phone" label="手机号" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            {{ row.role === 'admin' ? '管理员' : '学生' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="操作" width="160" align="center">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; justify-content: center; gap: 8px">
              <el-button type="primary" text style="margin: 0" @click="handleEdit(row)"
                >编辑</el-button
              >
              <el-button type="danger" text style="margin: 0" @click="handleDelete(row)"
                >删除</el-button
              >
            </div>
          </template>
        </el-table-column>
      </el-table>
      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="params.page"
          v-model:page-size="params.pageSize"
          :total="total"
          background
          layout="total,prev,pager,next"
          @current-change="load"
        />
      </div>
    </el-card>
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑' : '新增'" width="450">
      <el-form
        ref="formRef"
        :rules="rules"
        :model="form"
        label-width="100px"
        style="width: 100%"
        v-loading="loading"
      >
        <el-form-item label="账号" prop="username">
          <el-input :disabled="!!form.id" v-model="form.username" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item v-if="!form.id" label="密码" prop="password">
          <el-input
            type="password"
            show-password
            v-model="form.password"
            placeholder="请输入密码喵"
          />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role">
            <el-option label="学生" value="student"> </el-option>
            <el-option label="管理员" value="admin"> </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">正常</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSave">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { getUserPageList, createUserApi, updateUserApi, deleteUserApi } from '@/api/user'
import { Loading } from '@element-plus/icons-vue'
import { ElDialog, ElMessageBox, ElPopover } from 'element-plus'
import { ElMessage } from 'element-plus'
import { ref, reactive, onMounted } from 'vue'
import { Search, Plus } from '@element-plus/icons-vue'
const params = reactive({
  page: 1,
  pageSize: 10,
  keywords: ''
})
const tableData = ref([])
const loading = ref(false)
const total = ref(0)
const formRef = ref()
const dialogVisible = ref(false)
const formLoading = ref(false)
const form = reactive({
  username: '',
  name: '',
  role: 'student',
  email: '',
  phone: '',
  avatar: '',
  status: 1,
  password: ''
})
//加载分页数据
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

const resetForm = () => {
  Object.assign(form, {
    id: null,
    username: '',
    name: '',
    role: 'student',
    email: '',
    phone: '',
    avatar: '',
    status: 1,
    password: ''
  })
}

const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const handleSearch = async () => {
  params.page = 1
  load()
}

onMounted(() => {
  load()
})

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 3, max: 10, message: '密码是3到10位', trigger: 'blur' }
  ],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式错误', trigger: 'blur' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '手机号格式错误', trigger: 'blur' }]
}

const handleSave = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  formLoading.value = true
  try {
    const res = form.id ? await updateUserApi(form.id, form) : await createUserApi(form)
    if (res.code === 200) {
      dialogVisible.value = false
      ElMessage.success('操作成功')
      load()
    }
  } finally {
    formLoading.value = false
  }
}

const handleEdit = (row) => {
  resetForm()
  Object.assign(form, {
    id: row.id,
    username: row.username,
    name: row.name,
    role: row.role,
    email: row.email,
    phone: row.phone,
    avatar: row.avatar,
    status: row.status
  })
  dialogVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确认删除用户[${row.username}]?`, '确认删除', { type: 'warning' })
    .then(async () => {
      const res = await deleteUserApi(row.id)
      if (res.code === 200) {
        ElMessage.success('删除用户成功')
        load()
      }
    })
    .catch((error) => {
      if (error !== 'cancel' && error !== 'close') {
        console.error('删除失败', error)
      }
    })
}
</script>
