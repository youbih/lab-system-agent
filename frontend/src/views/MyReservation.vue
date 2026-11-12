<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span style="font-size: 16px; font-weight: bold">我的预约记录</span>
          <div style="display: flex; gap: 10px">
            <el-select
              v-model="status"
              placeholder="全部状态"
              clearable
              style="width: 140px"
              @change="loadList(1)"
            >
              <el-option
                v-for="item in statusOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-button @click="loadList()">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
        v-loading="loading"
        empty-text="暂无预约记录"
      >
        <el-table-column prop="lab_name" label="实验室" min-width="120" />

        <el-table-column label="预约类型" width="120">
          <template #default="{ row }">
            <el-tag :type="typeTagType(row.reservation_type)">
              {{ typeText(row.reservation_type) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="设备" min-width="120">
          <template #default="{ row }">
            {{ row.equipment_name || '—' }}
          </template>
        </el-table-column>

        <el-table-column label="预约时间" min-width="180">
          <template #default="{ row }">
            <div>{{ formatDate(row.start_at) }}</div>
            <div style="color: #909399; font-size: 13px">
              {{ formatTimeRange(row.start_at, row.end_at) }}
            </div>
          </template>
        </el-table-column>

        <el-table-column label="备注" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.remark || '—' }}
          </template>
        </el-table-column>

        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 0"
              type="danger"
              link
              :loading="row.cancelling"
              @click="handleCancel(row)"
            >
              取消预约
            </el-button>
            <span v-else style="color: #c0c4cc">—</span>
          </template>
        </el-table-column>
      </el-table>

      <div style="display: flex; justify-content: center; margin-top: 16px">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadList()"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getReservationListApi, cancelReservationApi } from '@/api/reservation'
import {
  statusType,
  statusText,
  typeText,
  typeTagType,
  formatDate,
  formatTimeRange
} from '@/utils/reservation'

const statusOptions = [
  { value: 0, label: '待审核' },
  { value: 1, label: '已通过' },
  { value: 2, label: '已拒绝' },
  { value: 3, label: '已取消' }
]

const tableData = ref([])
const loading = ref(false)
const status = ref()
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)

const loadList = async (toPage) => {
  if (toPage) page.value = toPage
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value
    }
    if (status.value !== undefined && status.value !== null && status.value !== '') {
      params.status = status.value
    }

    const res = await getReservationListApi(params)
    if (res.code === 200) {
      tableData.value = res.data.list
      total.value = res.data.total
    }
  } catch (error) {
    console.error('加载预约记录失败', error)
  } finally {
    loading.value = false
  }
}

const handleCancel = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定取消「${row.lab_name}」${formatDate(row.start_at)} ${formatTimeRange(
        row.start_at,
        row.end_at
      )} 的预约吗？`,
      '取消预约',
      {
        type: 'warning',
        confirmButtonText: '确定取消',
        cancelButtonText: '再想想'
      }
    )
  } catch {
    return
  }

  row.cancelling = true
  try {
    const res = await cancelReservationApi(row.id)
    if (res.code === 200) {
      ElMessage.success('预约已取消')
      loadList()
    }
  } catch (error) {
    console.error('取消预约失败', error)
  } finally {
    row.cancelling = false
  }
}

onMounted(() => {
  loadList()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
