<template>
  <div>
    <!-- 顶部:标题 + 搜索 -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
      <div style="display: flex; align-items: center; gap: 12px">
        <el-button @click="goBack">返回</el-button>
        <span style="font-size: 18px; font-weight: bold">{{ labName || '设备列表' }}</span>
        <el-tag v-if="total > 0" type="info" size="small">共 {{ total }} 台设备</el-tag>
      </div>
      <div style="display: flex; gap: 10px">
        <el-input
          v-model="keywords"
          placeholder="按设备名称搜索"
          clearable
          style="width: 240px"
          @keyup.enter="load(1)"
        />
        <el-button type="primary" @click="load(1)">查询</el-button>
      </div>
    </div>

    <!-- 实验室信息条:位置 / 容量 / 开放时间 -->
    <div class="lab-info-bar">
      <span class="lab-info-item">
        <el-icon><Location /></el-icon>
        {{ route.query.location || '位置待定' }}
      </span>
      <span class="lab-info-item">
        <el-icon><User /></el-icon>
        容纳 {{ route.query.capacity || 0 }} 人
      </span>
      <span class="lab-info-item">
        <el-icon><Clock /></el-icon>
        {{ route.query.open_time || '?' }} - {{ route.query.close_time || '?' }}
      </span>
    </div>

    <!-- 设备表格(只读,学生视角) -->
    <el-table :data="tableData" v-loading="loading" stripe>
      <el-table-column label="图片" width="90" align="center">
        <template #default="{ row }">
          <el-image
            :src="row.img ? baseURL + row.img : defaultImg"
            :preview-src-list="row.img ? [baseURL + row.img] : []"
            :hide-on-click-modal="true"
            preview-teleported
            fit="cover"
            :style="{
              width: '56px',
              height: '56px',
              borderRadius: '6px',
              cursor: row.img ? 'zoom-in' : 'default'
            }"
          />
        </template>
      </el-table-column>
      <el-table-column prop="name" label="设备名称" min-width="140" />
      <el-table-column prop="spec" label="规格型号" min-width="120">
        <template #default="{ row }">{{ row.spec || '-' }}</template>
      </el-table-column>
      <el-table-column prop="quantity" label="数量" width="100" align="center" />
      <el-table-column prop="status" label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
            {{ row.status === 1 ? '可用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" align="center">
        <template #default="{ row }">
          <el-button
            size="small"
            type="primary"
            :disabled="row.status !== 1 || row.quantity <= 0"
            @click="goReserve(row)"
          >
            预约
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && tableData.length === 0" description="该实验室暂无设备" />

    <!-- 分页 -->
    <div style="display: flex; justify-content: center; margin-top: 16px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="load()"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Location, User, Clock } from '@element-plus/icons-vue'
import { getEquipmentPageList } from '@/api/equipment'
import defaultImg from '@/assets/imgs/logo.png'

const baseURL = import.meta.env.VITE_API_BASE_URL

const route = useRoute()
const router = useRouter()

const labId = Number(route.query.lab_id) || null
const labName = route.query.lab_name || ''

const keywords = ref('')
const tableData = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

const load = async (toPage) => {
  if (toPage) page.value = toPage
  loading.value = true
  try {
    const res = await getEquipmentPageList({
      page: page.value,
      page_size: pageSize.value,
      keywords: keywords.value || undefined,
      lab_id: labId || undefined
    })
    if (res.code === 200) {
      tableData.value = res.data.list
      total.value = res.data.total
    }
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  // 有历史记录就回退(保留 lablist 的页码等状态),否则回列表页
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/manager/lablist')
  }
}

// 预约占位:后续课程实现真正的预约功能
const goReserve = (equipment) => {
  ElMessage.info(`「${equipment.name}」预约功能开发中,敬请期待`)
}

// 搜索框被清空时(点 × 或手动删完),自动恢复完整列表
watch(keywords, (val) => {
  if (!val) load(1)
})

onMounted(() => {
  load()
})
</script>

<style scoped>
.lab-info-bar {
  display: flex;
  gap: 24px;
  padding: 10px 14px;
  margin-bottom: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  color: #606266;
  font-size: 14px;
}
.lab-info-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
