import request from '@/utils/request'
/**
 * 分页模糊查询设备列表
 */
export function getEquipmentPageList(params) {
  return request({
    url: '/api/equipment/list',
    method: 'get',
    params
  })
}

/**
 * 新增设备
 */
export function createEquipmentApi(data) {
  return request({
    url: '/api/equipment',
    method: 'post',
    data
  })
}

/**
 * 更新设备
 */
export function updateEquipmentApi(equipmentId, data) {
  return request({
    url: `/api/equipment/${equipmentId}`,
    method: 'put',
    data
  })
}

/**
 * 删除设备
 */
export function deleteEquipmentApi(equipmentId) {
  return request({
    url: `/api/equipment/${equipmentId}`,
    method: 'delete'
  })
}
