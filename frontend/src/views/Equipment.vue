<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">设备管理</div>
      </template>
      <div class="search-bar">
        <el-input
          v-model="params.keywords"
          placeholder="请输入设备名称查询"
          clearable
          class="search-input"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select
          v-model="params.labId"
          placeholder="按所属实验室筛选"
          clearable
          filterable
          class="lab-filter"
          @change="handleSearch"
        >
          <el-option v-for="lab in labOptions" :key="lab.id" :label="lab.name" :value="lab.id" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button type="success" :icon="Plus" @click="handleCreate">新增设备</el-button>
      </div>
      <el-table
        v-loading="loading"
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
      >
        <el-table-column prop="lab_name" label="所属实验室" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.lab_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="name" label="设备名称" min-width="150" show-overflow-tooltip />
        <el-table-column label="图片" width="120" align="center">
          <template #default="{ row }">
            <img v-if="row.img" :src="row.img" :alt="row.name + '图片'" class="table-cover" />
            <span v-else class="empty-cover">暂无图片</span>
          </template>
        </el-table-column>
        <el-table-column prop="spec" label="规格型号" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.spec || '—' }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="90" align="center" />
        <el-table-column prop="description" label="简介" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '在用' : '停用' }}
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
      :title="form.id ? '编辑设备' : '新增设备'"
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
        <el-form-item label="所属实验室" prop="lab_id">
          <el-select
            v-model="form.lab_id"
            placeholder="请选择所属实验室"
            filterable
            style="width: 100%"
          >
            <el-option v-for="lab in labOptions" :key="lab.id" :label="lab.name" :value="lab.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="设备名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入设备名称" maxlength="50" />
        </el-form-item>
        <el-form-item label="规格型号" prop="spec">
          <el-input v-model="form.spec" placeholder="例如：Olympus BX53" maxlength="100" />
        </el-form-item>
        <el-form-item label="数量" prop="quantity">
          <el-input-number
            v-model="form.quantity"
            :min="0"
            :precision="0"
            controls-position="right"
          />
        </el-form-item>
        <el-form-item label="设备图片" prop="img">
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
                <img v-if="form.img" :src="form.img" alt="设备图片预览" class="cover-preview" />
                <div v-else class="cover-placeholder">
                  <el-icon><Plus /></el-icon>
                  <span>上传图片</span>
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
              >移除图片</el-button
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
            placeholder="请输入设备简介"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">在用</el-radio>
            <el-radio :value="0">停用</el-radio>
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
import {
  getEquipmentPageList,
  createEquipmentApi,
  updateEquipmentApi,
  deleteEquipmentApi
} from '@/api/equipment'
import { getLabPageList } from '@/api/lab'
import { uploadFileApi } from '@/api/file'

const params = reactive({ page: 1, pageSize: 10, keywords: '', labId: null })
const tableData = ref([])
const total = ref(0)
const loading = ref(false)
const labOptions = ref([])
const formRef = ref()
const dialogVisible = ref(false)
const formLoading = ref(false)
const coverUploading = ref(false)

const createEmptyForm = () => ({
  id: null,
  lab_id: null,
  name: '',
  spec: '',
  quantity: 1,
  description: '',
  img: '',
  status: 1
})
const form = reactive(createEmptyForm())

const rules = {
  lab_id: [{ required: true, type: 'number', message: '请选择所属实验室', trigger: 'change' }],
  name: [
    { required: true, whitespace: true, message: '请输入设备名称', trigger: 'blur' },
    { max: 50, message: '设备名称不能超过50个字符', trigger: 'blur' }
  ],
  spec: [{ max: 100, message: '规格型号不能超过100个字符', trigger: 'blur' }],
  quantity: [
    { required: true, type: 'number', message: '请输入数量', trigger: 'change' },
    { type: 'integer', min: 0, message: '数量必须是非负整数', trigger: 'change' }
  ],
  description: [{ max: 500, message: '简介不能超过500个字符', trigger: 'blur' }],
  img: [{ max: 100, message: '图片地址不能超过100个字符', trigger: 'change' }],
  status: [
    { required: true, type: 'enum', enum: [0, 1], message: '请选择设备状态', trigger: 'change' }
  ]
}

// 实验室下拉数据源：拉一页足够多的实验室，筛选框和表单下拉共用。
const loadLabOptions = async () => {
  try {
    const res = await getLabPageList({ page: 1, page_size: 100 })
    if (res.code === 200) {
      labOptions.value = res.data?.list ?? []
    }
  } catch (error) {
    console.error('加载实验室选项失败', error)
  }
}

// 分页查询设备，沿用公共请求层的鉴权和错误提示。
const load = async () => {
  loading.value = true
  try {
    const res = await getEquipmentPageList({
      page: params.page,
      page_size: params.pageSize,
      keywords: params.keywords.trim(),
      lab_id: params.labId || undefined
    })
    if (res.code === 200) {
      tableData.value = res.data?.list ?? []
      total.value = res.data?.total ?? 0
    }
  } catch (error) {
    console.error('加载设备列表失败', error)
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
    lab_id: row.lab_id,
    name: row.name ?? '',
    spec: row.spec ?? '',
    quantity: row.quantity ?? 1,
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
    ElMessage.error('图片只能上传JPG、PNG、GIF或WebP格式')
    return false
  }
  if (file.size > 2 * 1024 * 1024) {
    ElMessage.error('图片大小不能超过2MB')
    return false
  }
  return true
}

// 先上传取得URL并预览，点击保存后才更新设备的img字段。
const handleCoverUpload = async ({ file }) => {
  coverUploading.value = true
  try {
    const res = await uploadFileApi(file)
    if (res.code !== 200) {
      throw new Error(res.message || '图片上传失败')
    }
    if (!res.data?.url) {
      ElMessage.error('上传结果没有返回图片地址')
      throw new Error('缺少图片地址')
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
    // 显式提交设备字段，避免把ID或lab_name等只读字段发送给后端。
    const data = {
      lab_id: form.lab_id,
      name: form.name.trim(),
      spec: form.spec.trim(),
      quantity: form.quantity,
      description: form.description ?? '',
      img: form.img ?? '',
      status: form.status
    }
    const res = form.id ? await updateEquipmentApi(form.id, data) : await createEquipmentApi(data)
    if (res.code === 200) {
      dialogVisible.value = false
      ElMessage.success(form.id ? '设备更新成功' : '设备新增成功')
      await load()
    }
  } catch (error) {
    console.error('保存设备失败', error)
  } finally {
    formLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除设备[${row.name}]？`, '确认删除', { type: 'warning' })
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除确认失败', error)
    }
    return
  }
  try {
    const res = await deleteEquipmentApi(row.id)
    if (res.code === 200) {
      ElMessage.success('设备删除成功')
      if (tableData.value.length === 1 && params.page > 1) {
        params.page -= 1
      }
      await load()
    }
  } catch (error) {
    console.error('删除设备失败', error)
  }
}

const handleSearch = async () => {
  params.page = 1
  await load()
}

onMounted(() => {
  loadLabOptions()
  load()
})
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
.lab-filter {
  width: 200px;
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
