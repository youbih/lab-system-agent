<!-- views 通常放路由页面，components 放页面中复用的部分 -->
<template>
  <div>
    <el-dialog
      :model-value="visible"
      title="预约"
      width="450"
      :close-on-click-modal="!loading"
      :close-on-press-escape="!loading"
      :show-close="!loading"
      @update:model-value="emit('update:visible', $event)"
      @closed="handleClosed"
    >
      <el-form
        ref="formRef"
        :rules="rules"
        :model="form"
        label-width="80px"
        style="width: 100%; padding-right: 30px; padding-top: 16px"
        v-loading="loading"
      >
        <el-form-item label="实验室">
          <span>{{ props.labName }}</span>
        </el-form-item>

        <el-form-item label="设备" prop="equipmentId">
          <el-select
            v-model="form.equipmentId"
            placeholder="不预约设备（仅使用实验室）"
            clearable
            :loading="equipmentLoading"
            style="width: 100%"
          >
            <el-option
              v-for="item in equipmentOptions"
              :key="item.id"
              :label="item.status === 1 ? item.name : `${item.name}（维修中）`"
              :value="item.id"
              :disabled="item.status !== 1"
            />
          </el-select>
          <div style="color: #909399; font-size: 12px; line-height: 1.5; margin-top: 4px">
            不选设备表示仅预约实验室；选择设备会同时占用实验室和该设备
          </div>
        </el-form-item>

        <el-form-item label="预约日期" prop="date">
          <el-date-picker
            v-model="form.date"
            type="date"
            placeholder="请选择预约日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
            @change="revalidateTimes"
          />
        </el-form-item>

        <el-form-item label="开始时间" prop="startTime">
          <el-time-select
            v-model="form.startTime"
            start="00:00"
            step="00:30"
            end="23:30"
            :editable="false"
            placeholder="请选择开始时间（北京时间）"
            style="width: 100%"
            @change="revalidateTimes"
          />
        </el-form-item>

        <el-form-item label="结束时间" prop="endTime">
          <el-time-select
            v-model="form.endTime"
            start="00:00"
            step="00:30"
            end="23:30"
            :editable="false"
            placeholder="请选择结束时间（北京时间）"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="备注" prop="remark">
          <el-input
            v-model="form.remark"
            type="textarea"
            placeholder="请输入备注"
            maxlength="255"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="loading" @click="emit('update:visible', false)"> 取消 </el-button>

        <el-button type="primary" :loading="loading" @click="handleSubmit"> 提交预约 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createReservationApi } from '@/api/reservation'
import { getEquipmentPageList } from '@/api/equipment'
const props = defineProps({
  visible: Boolean,
  labId: Number,
  labName: String,
  equipmentId: Number,
  equipmentName: String
})

const emit = defineEmits(['update:visible'])
const formRef = ref()
const form = reactive({
  equipmentId: null,
  date: '',
  startTime: '',
  endTime: '',
  remark: ''
})

const equipmentOptions = ref([])
const equipmentLoading = ref(false)

const loadEquipmentOptions = async () => {
  if (!props.labId) return
  equipmentLoading.value = true
  try {
    const res = await getEquipmentPageList({
      lab_id: props.labId,
      page: 1,
      page_size: 100
    })
    if (res.code === 200) {
      const list = res.data.list
      if (props.equipmentId && !list.some((item) => item.id === props.equipmentId)) {
        list.unshift({
          id: props.equipmentId,
          name: props.equipmentName || '已选设备',
          status: 1
        })
      }
      equipmentOptions.value = list
    }
  } catch (error) {
    console.error('加载设备列表失败', error)
  } finally {
    equipmentLoading.value = false
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      form.equipmentId = props.equipmentId ?? null
      loadEquipmentOptions()
    }
  }
)

// 只允许整点或半点，例如 09:00、09:30
const timePattern = /^([01]\d|2[0-3]):(00|30)$/
// 将预约日期和时间组合起来，按北京时间计算
const getTimestamp = (date, time) => {
  return new Date(`${date}T${time}:00+08:00`).getTime()
}
// 校验开始时间
const validateStartTime = (rule, value, callback) => {
  if (!value) {
    return callback()
  }

  if (!timePattern.test(value)) {
    return callback(new Error('开始时间只能选择整点或半点'))
  }

  // 日期未选时，交给日期的 required 规则提示
  if (!form.date) {
    return callback()
  }

  const start = getTimestamp(form.date, value)
  const now = Date.now()

  if (!Number.isFinite(start)) {
    return callback(new Error('请选择有效的预约日期和时间'))
  }

  if (start < now + 60 * 60 * 1000) {
    return callback(new Error('请至少提前1小时预约'))
  }

  if (start > now + 7 * 24 * 60 * 60 * 1000) {
    return callback(new Error('最多只能提前7天预约'))
  }

  callback()
}

// 校验结束时间
const validateEndTime = (rule, value, callback) => {
  if (!value) {
    return callback()
  }

  if (!timePattern.test(value)) {
    return callback(new Error('结束时间只能选择整点或半点'))
  }

  if (!form.date || !form.startTime) {
    return callback()
  }

  const start = getTimestamp(form.date, form.startTime)
  const end = getTimestamp(form.date, value)

  if (!Number.isFinite(start) || !Number.isFinite(end)) {
    return callback(new Error('请选择有效的预约日期和时间'))
  }

  if (end <= start) {
    return callback(new Error('结束时间必须晚于开始时间'))
  }

  if (end - start < 30 * 60 * 1000) {
    return callback(new Error('单次预约至少30分钟'))
  }

  callback()
}

const rules = {
  date: [
    {
      required: true,
      message: '请选择预约日期',
      trigger: 'change'
    }
  ],
  startTime: [
    {
      required: true,
      message: '请选择开始时间',
      trigger: 'change'
    },
    {
      validator: validateStartTime,
      trigger: 'change'
    }
  ],
  endTime: [
    {
      required: true,
      message: '请选择结束时间',
      trigger: 'change'
    },
    {
      validator: validateEndTime,
      trigger: 'change'
    }
  ],
  remark: [
    {
      max: 255,
      message: '备注不能超过255个字符',
      trigger: 'blur'
    }
  ]
}
const loading = ref(false)
const handleSubmit = async () => {
  if (loading.value || !formRef.value) {
    return
  }

  // 先校验表单；不通过时，表单会显示具体错误
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  // 防止组件没有收到预约对象
  if (!props.labId) {
    ElMessage.error('缺少实验室信息，请重新选择')
    return
  }

  // 防止校验等待期间重复提交
  if (loading.value) {
    return
  }

  loading.value = true

  try {
    const res = await createReservationApi({
      lab_id: props.labId,
      equipment_id: form.equipmentId || null,
      reservation_type: form.equipmentId ? 2 : 0,
      start_at: `${form.date}T${form.startTime}:00`,
      end_at: `${form.date}T${form.endTime}:00`,
      remark: form.remark
    })

    if (res.code === 200) {
      ElMessage.success('预约提交成功，请等待审核')
      emit('update:visible', false)
    }
  } catch (error) {
    // 请求错误提示已经由 request.js 的拦截器处理
    console.error('提交预约失败', error)
  } finally {
    loading.value = false
  }
}
const handleClosed = () => {
  formRef.value?.resetFields()
}

// 日期或开始时间变化时，重新检查已填写的时间
const revalidateTimes = () => {
  if (form.startTime) {
    formRef.value?.validateField('startTime').catch(() => {})
  }

  if (form.endTime) {
    formRef.value?.validateField('endTime').catch(() => {})
  }
}
</script>
