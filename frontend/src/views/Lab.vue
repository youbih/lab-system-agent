<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">实验室管理</div>
      </template>
      <div class="search-bar">
        <el-input
          v-model="params.keywords"
          placeholder="请输入实验室名称查询"
          clearable
          class="search-input"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button type="success" :icon="Plus" @click="handleCreate">新增实验室</el-button>
      </div>
      <el-table
        v-loading="loading"
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
      >
        <el-table-column prop="name" label="实验室名称" min-width="150" show-overflow-tooltip />
        <el-table-column label="封面" width="120" align="center">
          <template #default="{ row }">
            <img v-if="row.img" :src="row.img" :alt="row.name + '封面'" class="table-cover" />
            <span v-else class="empty-cover">暂无封面</span>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="位置" min-width="150" show-overflow-tooltip />
        <el-table-column prop="capacity" label="容量（人）" width="110" align="center" />
        <el-table-column label="开放时间" width="160" align="center">
          <template #default="{ row }">
            {{
              row.open_time && row.close_time ? `${row.open_time} — ${row.close_time}` : '未设置'
            }}
          </template>
        </el-table-column>
        <el-table-column prop="description" label="简介" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '开放' : '关闭' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" text @click="handleEdit(row)">编辑</el-button>
              <el-button type="danger" text @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination">
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

    <el-dialog
      v-model="dialogVisible"
      :title="form.id ? '编辑实验室' : '新增实验室'"
      width="600px"
      :close-on-click-modal="!formLoading && !coverUploading"
      :close-on-press-escape="!formLoading && !coverUploading"
      :show-close="!formLoading && !coverUploading"
    >
      <el-form
        ref="formRef"
        :rules="rules"
        :model="form"
        :disabled="formLoading"
        label-width="100px"
      >
        <el-form-item label="实验室名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入实验室名称" maxlength="50" />
        </el-form-item>
        <el-form-item label="位置" prop="location">
          <el-input v-model="form.location" placeholder="例如：教学楼 A 座 301" maxlength="100" />
        </el-form-item>
        <el-form-item label="容量（人）" prop="capacity">
          <el-input-number
            v-model="form.capacity"
            :min="0"
            :precision="0"
            controls-position="right"
          />
        </el-form-item>
        <el-form-item label="开始时间" prop="open_time">
          <el-time-picker
            v-model="form.open_time"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="请选择开放开始时间"
            style="width: 100%"
            @change="validateOpeningHours"
          />
        </el-form-item>
        <el-form-item label="结束时间" prop="close_time">
          <el-time-picker
            v-model="form.close_time"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="请选择开放结束时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="封面" prop="img">
          <div>
            <el-upload
              class="cover-uploader"
              :http-request="handleCoverUpload"
              :before-upload="beforeCoverUpload"
              :show-file-list="false"
              :disabled="coverUploading || formLoading"
              accept="image/jpeg,image/png,image/gif,image/webp"
            >
              <div v-loading="coverUploading" class="cover-upload-content">
                <img v-if="form.img" :src="form.img" alt="实验室封面预览" class="cover-preview" />
                <div v-else class="cover-placeholder">
                  <el-icon><Plus /></el-icon>
                  <span>上传封面</span>
                </div>
              </div>
            </el-upload>
            <div class="upload-tip">支持 JPG、PNG、GIF、WebP，大小不超过 2 MB；保存后生效。</div>
            <el-button
              v-if="form.img"
              type="danger"
              link
              :disabled="coverUploading || formLoading"
              @click="form.img = ''"
              >移除封面</el-button
            >
          </div>
        </el-form-item>
        <el-form-item label="简介" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="请输入实验室简介"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">开放</el-radio>
            <el-radio :value="0">关闭</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="formLoading || coverUploading" @click="dialogVisible = false"
          >取消</el-button
        >
        <el-button
          type="primary"
          :loading="formLoading"
          :disabled="coverUploading"
          @click="handleSave"
          >保存</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import { getLabPageList, createLabApi, updateLabApi, deleteLabApi } from '@/api/lab'
import { uploadFileApi } from '@/api/file'

const params = reactive({ page: 1, pageSize: 10, keywords: '' })
const tableData = ref([])
const total = ref(0)
const loading = ref(false)
const formRef = ref()
const dialogVisible = ref(false)
const formLoading = ref(false)
const coverUploading = ref(false)

const createEmptyForm = () => ({
  id: null,
  name: '',
  location: '',
  capacity: 0,
  open_time: '08:00',
  close_time: '18:00',
  description: '',
  img: '',
  status: 1
})
const form = reactive(createEmptyForm())
const timePattern = /^([01]\d|2[0-3]):[0-5]\d$/

const validateCloseTime = (rule, value, callback) => {
  if (!value || !timePattern.test(value)) {
    callback(new Error('请选择有效的结束时间'))
  } else if (timePattern.test(form.open_time) && value <= form.open_time) {
    callback(new Error('结束时间必须晚于开始时间'))
  } else {
    callback()
  }
}

const rules = {
  name: [
    { required: true, whitespace: true, message: '请输入实验室名称', trigger: 'blur' },
    { max: 50, message: '实验室名称不能超过50个字符', trigger: 'blur' }
  ],
  location: [
    { required: true, whitespace: true, message: '请输入实验室位置', trigger: 'blur' },
    { max: 100, message: '位置不能超过100个字符', trigger: 'blur' }
  ],
  capacity: [
    { required: true, type: 'number', message: '请输入容量', trigger: 'change' },
    { type: 'integer', min: 0, message: '容量必须是非负整数', trigger: 'change' }
  ],
  open_time: [
    { required: true, message: '请选择开始时间', trigger: 'change' },
    { pattern: timePattern, message: '时间格式应为HH:mm', trigger: 'change' }
  ],
  close_time: [{ validator: validateCloseTime, trigger: 'change' }],
  description: [{ max: 500, message: '简介不能超过500个字符', trigger: 'blur' }],
  img: [{ max: 100, message: '封面地址不能超过100个字符', trigger: 'change' }],
  status: [
    { required: true, type: 'enum', enum: [0, 1], message: '请选择开放状态', trigger: 'change' }
  ]
}

const validateOpeningHours = () => {
  if (formRef.value && form.close_time) {
    formRef.value.validateField('close_time').catch(() => {})
  }
}

// 分页查询实验室，沿用公共请求层的鉴权和错误提示。
const load = async () => {
  loading.value = true
  try {
    const res = await getLabPageList({
      page: params.page,
      page_size: params.pageSize,
      keywords: params.keywords.trim()
    })
    if (res.code === 200) {
      tableData.value = res.data?.list ?? []
      total.value = res.data?.total ?? 0
    }
  } catch (error) {
    console.error('加载实验室列表失败', error)
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  Object.assign(form, createEmptyForm())
}

const handleCreate = async () => {
  resetForm()
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}

const handleEdit = async (row) => {
  resetForm()
  Object.assign(form, {
    id: row.id,
    name: row.name ?? '',
    location: row.location ?? '',
    capacity: row.capacity ?? 0,
    open_time: row.open_time?.slice(0, 5) ?? '',
    close_time: row.close_time?.slice(0, 5) ?? '',
    description: row.description ?? '',
    img: row.img ?? '',
    status: row.status ?? 1
  })
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}

const beforeCoverUpload = (file) => {
  const imageTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
  if (!imageTypes.includes(file.type)) {
    ElMessage.error('封面只能上传JPG、PNG、GIF或WebP图片')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.error('封面大小不能超过2MB')
    return false
  }
  return true
}

// 先上传取得URL并预览，点击保存后才更新实验室的img字段。
const handleCoverUpload = async ({ file }) => {
  coverUploading.value = true
  try {
    const res = await uploadFileApi(file)
    if (res.code !== 200) {
      throw new Error(res.message || '封面上传失败')
    }
    if (!res.data?.url) {
      ElMessage.error('上传结果没有返回封面地址')
      throw new Error('缺少封面地址')
    }
    form.img = res.data.url
    return res.data
  } finally {
    coverUploading.value = false
  }
}

const handleSave = async () => {
  if (formLoading.value || coverUploading.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  formLoading.value = true
  try {
    // 显式提交实验室字段，避免把ID或复制自用户页面的字段发送给后端。
    const data = {
      name: form.name.trim(),
      location: form.location.trim(),
      capacity: form.capacity,
      open_time: form.open_time,
      close_time: form.close_time,
      description: form.description ?? '',
      img: form.img ?? '',
      status: form.status
    }
    const res = form.id ? await updateLabApi(form.id, data) : await createLabApi(data)
    if (res.code === 200) {
      dialogVisible.value = false
      ElMessage.success(form.id ? '实验室更新成功' : '实验室新增成功')
      await load()
    }
  } catch (error) {
    console.error('保存实验室失败', error)
  } finally {
    formLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除实验室[${row.name}]？`, '确认删除', { type: 'warning' })
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除确认失败', error)
    }
    return
  }
  try {
    const res = await deleteLabApi(row.id)
    if (res.code === 200) {
      ElMessage.success('实验室删除成功')
      if (tableData.value.length === 1 && params.page > 1) {
        params.page -= 1
      }
      await load()
    }
  } catch (error) {
    console.error('删除实验室失败', error)
  }
}

const handleSearch = async () => {
  params.page = 1
  await load()
}

onMounted(load)
</script>

<style scoped>
.search-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.search-input {
  width: 240px;
}
.search-bar :deep(.el-button + .el-button),
.action-buttons :deep(.el-button + .el-button) {
  margin-left: 0;
}
.table-cover {
  display: block;
  width: 96px;
  height: 64px;
  object-fit: cover;
  border-radius: 4px;
}
.empty-cover,
.upload-tip {
  color: #909399;
  font-size: 12px;
}
.action-buttons {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
.cover-uploader :deep(.el-upload) {
  display: block;
  overflow: hidden;
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
}
.cover-uploader :deep(.el-upload:hover) {
  border-color: #409eff;
}
.cover-upload-content,
.cover-preview {
  width: 200px;
  height: 125px;
}
.cover-preview {
  display: block;
  object-fit: cover;
}
.cover-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  height: 100%;
  color: #909399;
}
.upload-tip {
  margin-top: 6px;
  line-height: 1.5;
}
</style>
