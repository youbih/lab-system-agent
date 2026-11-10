<template>
  <ReserveDialog
    v-model:visible="reserveVisible"
    :lab-id="selectedLab.id"
    :lab-name="selectedLab.name"
  />
  <div>
    <!-- 顶部:搜索区 -->

    <div style="display: flex; gap: 10px; margin-bottom: 20px">
      <el-input
        v-model="keywords"
        placeholder="按实验室名称搜索"
        clearable
        style="width: 300px"
        @keyup.enter="loadList(1)"
      />
      <el-button type="primary" @click="loadList(1)">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <!-- 卡片列表 -->
    <el-row :gutter="20" v-loading="loading">
      <el-col
        v-for="lab in labList"
        :key="lab.id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
        style="margin-bottom: 20px"
      >
        <el-card :body-style="{ padding: '0px' }" shadow="hover">
          <!-- 封面:固定 16:9 比例,图片裁剪填满,比例统一不奇怪 -->
          <div style="width: 100%; aspect-ratio: 16 / 9; overflow: hidden">
            <el-image
              :src="lab.img ? baseURL + lab.img : defaultCover"
              fit="cover"
              style="width: 100%; height: 100%; display: block"
            >
              <template #error>
                <div class="img-placeholder">暂无封面</div>
              </template>
            </el-image>
          </div>

          <div style="padding: 14px">
            <!-- 名称 + 状态 -->
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-size: 16px; font-weight: bold">{{ lab.name }}</span>
              <el-tag :type="lab.status === 1 ? 'success' : 'danger'" size="small">
                {{ lab.status === 1 ? '开放' : '关闭' }}
              </el-tag>
            </div>

            <!-- 位置 / 容量 / 开放时间 -->
            <div class="info-line">
              <el-icon><Location /></el-icon>
              <span>{{ lab.location || '位置待定' }}</span>
            </div>
            <div class="info-line">
              <el-icon><User /></el-icon>
              <span>容纳 {{ lab.capacity }} 人</span>
            </div>
            <div class="info-line">
              <el-icon><Clock /></el-icon>
              <span>{{ lab.open_time || '?' }} - {{ lab.close_time || '?' }}</span>
            </div>

            <!-- 操作按钮 -->
            <div style="display: flex; gap: 10px; margin-top: 12px">
              <el-button size="small" @click="goEquipment(lab)">查看设备</el-button>
              <el-button
                size="small"
                type="primary"
                :disabled="lab.status !== 1"
                @click="goReserve(lab)"
              >
                预约
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 空数据提示 -->
    <el-empty v-if="!loading && labList.length === 0" description="没有找到相关实验室" />

    <!-- 分页 -->
    <div style="display: flex; justify-content: center; margin-top: 10px">
      <el-pagination
        v-model:current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadList()"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { Location, User, Clock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter, useRoute } from 'vue-router'
import { getLabPageList } from '@/api/lab'
import defaultCover from '@/assets/imgs/logo.png'
import ReserveDialog from '@/components/ReserveDialog.vue'
const router = useRouter()
const route = useRoute()
const reserveVisible = ref(false)
const selectedLab = ref({})
const goEquipment = (lab) => {
  router.push({
    path: '/manager/labequipment',
    query: {
      lab_id: lab.id,
      lab_name: lab.name,
      location: lab.location || '',
      capacity: lab.capacity ?? '',
      open_time: lab.open_time || '',
      close_time: lab.close_time || ''
    }
  })
}

const goReserve = (lab) => {
  selectedLab.value = lab
  reserveVisible.value = true
}

const baseURL = import.meta.env.VITE_API_BASE_URL

const keywords = ref('')
const labList = ref([])
const loading = ref(false)
const page = ref(Number(route.query.page) || 1) // 从 URL 恢复页码(返回时保持)
const pageSize = ref(8)
const total = ref(0)

const loadList = async (toPage) => {
  if (toPage) page.value = toPage
  loading.value = true
  try {
    const res = await getLabPageList({
      page: page.value,
      page_size: pageSize.value,
      keywords: keywords.value || undefined
    })
    if (res.code === 200) {
      labList.value = res.data.list
      total.value = res.data.total
    }
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  keywords.value = ''
  loadList(1)
}

// 搜索框被清空时(点 × 或手动删完),自动恢复完整列表
watch(keywords, (val) => {
  if (!val) loadList(1)
})

// 页码变化时同步到 URL,这样从设备页返回能保持页码
watch(page, (val) => {
  router.replace({ query: { ...route.query, page: val } })
})

onMounted(() => {
  loadList()
})
</script>

<style scoped>
.info-line {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  color: #606266;
  font-size: 14px;
}
.img-placeholder {
  width: 100%;
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  color: #909399;
}
</style>
