import request from '@/utils/request'

/**
 * 创建预约
 */
export function createReservationApi(data) {
  return request({
    url: '/api/reservation',
    method: 'post',
    data
  })
}

/**
 * 分页查询预约列表
 */
export function getReservationListApi(params) {
  return request({
    url: '/api/reservation/list',
    method: 'get',
    params
  })
}

/**
 * 取消预约
 */
export function cancelReservationApi(reservationId) {
  return request({
    url: `/api/reservation/${reservationId}/cancel`,
    method: 'put'
  })
}

/**
 * 审核预约
 */
export function auditReservationApi(reservationId, status) {
  return request({
    url: `/api/reservation/${reservationId}/audit`,
    method: 'put',
    data: { status }
  })
}
