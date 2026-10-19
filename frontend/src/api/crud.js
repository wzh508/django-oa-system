import { http } from './http'

// 通用 CRUD（DRF router 风格，baseUrl 以 / 结尾）
export const crud = {
  list: (base, params) => http.get(base, params),
  get: (base, id) => http.get(`${base}${id}/`),
  create: (base, data) => http.post(base, data),
  update: (base, id, data) => http.put(`${base}${id}/`, data),
  remove: (base, id) => http.delete(`${base}${id}/`),
  // 自定义动作
  action: (url, data, method = 'post') =>
    method === 'get' ? http.get(url) : http.post(url, data),
}
