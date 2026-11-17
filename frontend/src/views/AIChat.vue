<template>
  <div class="ai-chat">
    <el-card class="chat-card">
      <template #header>
        <div class="chat-header">
          <div class="chat-header-text">
            <span class="chat-title">AI 智能助手</span>
            <span class="chat-subtitle">
              可以问我预约、取消、审核规则；具体实验室信息请到「实验室列表」查看
            </span>
          </div>
          <el-button link type="primary" :disabled="messages.length <= 1" @click="handleClear">
            清空对话
          </el-button>
        </div>
      </template>

      <!-- 消息列表：新消息追加后自动滚动到底部 -->
      <div ref="listRef" class="chat-list">
        <div
          v-for="(item, index) in messages"
          :key="index"
          class="chat-row"
          :class="item.role === 'user' ? 'is-user' : 'is-assistant'"
        >
          <el-avatar v-if="item.role !== 'user'" :size="34" class="avatar">AI</el-avatar>

          <div class="bubble" :class="item.role === 'user' ? 'bubble-user' : 'bubble-assistant'">
            <!-- 还没收到第一个 delta 时显示思考状态 -->
            <span v-if="item.pending && !item.content" class="thinking">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>正在思考…</span>
            </span>
            <template v-else>{{ item.content }}</template>
          </div>

          <el-avatar v-if="item.role === 'user'" :size="34" class="avatar user-avatar">
            {{ userInitial }}
          </el-avatar>
        </div>
      </div>

      <!-- 输入区：Enter 发送，Shift + Enter 换行 -->
      <div class="chat-input">
        <el-input
          v-model="input"
          type="textarea"
          :rows="3"
          resize="none"
          maxlength="1000"
          show-word-limit
          placeholder="请输入问题，Enter 发送，Shift + Enter 换行"
          @keydown="handleKeydown"
        />
        <div class="input-actions">
          <span class="input-tip">AI 回答仅供参考，具体数据请以系统页面为准</span>
          <el-button v-if="loading" type="danger" plain @click="handleStop"> 停止生成 </el-button>
          <el-button v-else type="primary" :disabled="!input.trim()" @click="handleSend">
            发送
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { chatStreamApi } from '@/api/ai'
import { useUser } from '@/utils/user'

// 开场白只用于展示，也会作为历史消息一起发送，模型能把它当成自己说过的话
const GREETING =
  '您好，我是实验室 AI 助手。可以问我预约、取消、审核规则；具体实验室信息和预约记录请到「实验室列表」「我的预约」查看。'

const { userInfo } = useUser()

// 用户头像显示姓名首字
const userInitial = computed(() => (userInfo.value?.name || '我').slice(0, 1))

// role 为 user / assistant，和后端 ChatMessage 保持一致
const messages = ref([{ role: 'assistant', content: GREETING }])
const input = ref('')
const loading = ref(false)
const listRef = ref(null)
// 用于中断正在进行的流式请求
const controller = ref(null)

// 等 DOM 更新完成后再滚动，否则拿不到新气泡的高度
const scrollToBottom = async () => {
  await nextTick()
  const el = listRef.value
  if (el) {
    el.scrollTop = el.scrollHeight
  }
}

// delta 可能很密集，用 requestAnimationFrame 合并滚动，避免频繁触发布局
let scrollFrame = null
const scheduleScroll = () => {
  if (scrollFrame) return
  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = null
    scrollToBottom()
  })
}

const handleSend = async () => {
  const text = input.value.trim()

  // 空内容或正在等待回答时不允许重复发送
  if (!text || loading.value) {
    return
  }

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true

  // 先基于"当前已有消息 + 新问题"生成历史，避免把后面插入的空助手消息也发给后端
  const payload = messages.value.map(({ role, content }) => ({ role, content }))

  // 插入空的助手消息，后面把流式 delta 不断追加进去
  const reply = reactive({ role: 'assistant', content: '', pending: true })
  messages.value.push(reply)
  scrollToBottom()

  const abortController = new AbortController()
  controller.value = abortController

  try {
    await chatStreamApi(
      { messages: payload },
      {
        signal: abortController.signal,
        onEvent: ({ event, data }) => {
          if (event === 'delta') {
            reply.pending = false
            reply.content += data.content || ''
            scheduleScroll()
          } else if (event === 'done') {
            reply.pending = false
            if (!reply.content) {
              reply.content = '（模型没有返回内容）'
            }
          } else if (event === 'error') {
            reply.pending = false
            const message = data?.message || 'AI 回答失败'
            ElMessage.error(message)
            if (!reply.content) {
              reply.content = message
            }
          }
        }
      }
    )
  } catch (error) {
    if (error.name === 'AbortError') {
      // 用户主动停止，保留已经生成的内容
      if (!reply.content) {
        reply.content = '（已停止生成）'
      }
    } else {
      console.error('AI 流式对话失败', error)
      ElMessage.error(error.message || 'AI 对话失败')
      if (!reply.content) {
        reply.content = 'AI 对话失败，请稍后重试'
      }
    }
  } finally {
    reply.pending = false
    loading.value = false
    controller.value = null
    scrollToBottom()
  }
}

const handleStop = () => {
  controller.value?.abort()
}

// 中文输入法组合期间按 Enter 不应该发送
const handleKeydown = (event) => {
  if (event.isComposing) {
    return
  }
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

const handleClear = async () => {
  try {
    await ElMessageBox.confirm('确定清空当前对话吗？', '清空对话', {
      type: 'warning',
      confirmButtonText: '确定清空',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  // 如果正在生成，先中断流，避免清空后还有回调往旧消息里写内容
  controller.value?.abort()
  messages.value = [{ role: 'assistant', content: GREETING }]
  input.value = ''
  loading.value = false
  scrollToBottom()
}

onMounted(() => {
  scrollToBottom()
})

onBeforeUnmount(() => {
  controller.value?.abort()
  if (scrollFrame) {
    cancelAnimationFrame(scrollFrame)
  }
})
</script>

<style scoped>
.ai-chat {
  max-width: 960px;
  margin: 0 auto;
}

.chat-card {
  display: flex;
  flex-direction: column;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.chat-header-text {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.chat-title {
  font-size: 16px;
  font-weight: bold;
}

.chat-subtitle {
  color: #909399;
  font-size: 12px;
}

.chat-list {
  height: calc(100vh - 340px);
  min-height: 360px;
  overflow-y: auto;
  padding: 12px 8px;
  background-color: #f7f8fa;
  border-radius: 6px;
}

.chat-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
}

.chat-row.is-user {
  justify-content: flex-end;
}

.chat-row.is-assistant {
  justify-content: flex-start;
}

.avatar {
  flex-shrink: 0;
  background-color: #409eff;
  font-size: 12px;
}

.user-avatar {
  background-color: #67c23a;
}

.bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.7;
  /* 保留模型输出里的换行，同时避免长单词撑破容器 */
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-assistant {
  background-color: #ffffff;
  border: 1px solid #ebeef5;
  color: #303133;
}

.bubble-user {
  background-color: #409eff;
  color: #ffffff;
}

.thinking {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #909399;
}

.chat-input {
  margin-top: 12px;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.input-tip {
  color: #909399;
  font-size: 12px;
}

@media (max-width: 768px) {
  .bubble {
    max-width: 80%;
  }

  .chat-subtitle {
    display: none;
  }

  .input-tip {
    display: none;
  }
}
</style>
