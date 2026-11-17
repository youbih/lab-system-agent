import request from '@/utils/request'
import { getToken } from '@/utils/auth'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

//AI对话请求（非流式，保留作为降级方案）
export function chatApi(data) {
  return request({
    url: '/api/ai/chat',
    method: 'post',
    data,
    // 大模型首字延迟和生成时间可能超过 30 秒，适当放长超时
    timeout: 60000
  })
}

/**
 * AI 对话请求（SSE 流式）
 * 浏览器里的 axios 会缓冲整个响应，拿不到增量内容，所以这里用原生 fetch 读取 ReadableStream
 *
 * @param {Object} data 请求体，例如 { messages: [...] }
 * @param {Object} options
 * @param {AbortSignal} options.signal 用于停止生成
 * @param {(event: { event: string, data: any }) => void} options.onEvent 每收到一个 SSE 事件时回调
 */
export async function chatStreamApi(data, { signal, onEvent } = {}) {
  const res = await fetch(`${BASE_URL}/api/ai/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`
    },
    body: JSON.stringify(data),
    signal
  })

  if (!res.ok) {
    let message = `请求失败(${res.status})`
    try {
      const err = await res.json()
      message = err.message || message
    } catch {
      // 非 JSON 响应时使用默认提示
    }
    throw new Error(message)
  }

  if (!res.body) {
    throw new Error('当前浏览器不支持流式响应')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE 事件之间用空行分隔
    let separatorIndex
    while ((separatorIndex = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, separatorIndex)
      buffer = buffer.slice(separatorIndex + 2)

      let eventName = 'message'
      const dataLines = []

      for (const line of rawEvent.split('\n')) {
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim())
        }
      }

      if (!dataLines.length) continue

      const text = dataLines.join('\n')
      let payload = text
      try {
        payload = JSON.parse(text)
      } catch {
        // 不是 JSON 时保留原始文本
      }

      onEvent?.({ event: eventName, data: payload })
    }
  }
}
