export const statusType = (status) => {
  return { 0: 'warning', 1: 'success', 2: 'danger', 3: 'info', 4: 'info' }[status] || 'info'
}

export const statusText = (status) => {
  return (
    {
      0: '待审核',
      1: '已通过',
      2: '已拒绝',
      3: '已取消',
      4: '已过期'
    }[status] || '未知'
  )
}

export const typeText = (type) => {
  return { 0: '仅实验室', 1: '仅设备', 2: '实验室+设备' }[type] || '未知'
}

export const typeTagType = (type) => {
  return { 0: 'success', 1: 'primary', 2: 'warning' }[type] || 'info'
}

export const formatDate = (value) => {
  return value ? value.slice(0, 10) : '—'
}

export const formatTimeRange = (start, end) => {
  if (!start || !end) return '—'
  return `${start.slice(11, 16)} - ${end.slice(11, 16)}`
}
