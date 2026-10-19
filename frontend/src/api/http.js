import axios from 'axios'
import { ElMessage } from 'element-plus'
import { getToken, setToken, getRefresh, setRefresh, clearToken } from '@/utils/auth'
import { useUserStore } from '@/store/modules/user'
import router from '@/router'

const BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const service = axios.create({
  baseURL: BASE,
  timeout: 20000,
})

service.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers['Authorization'] = `Bearer ${token}`
  return config
})

let isRefreshing = false
let pendingQueue = []

function flushQueue(error) {
  pendingQueue.forEach((p) => (error ? p.reject(error) : p.resolve()))
  pendingQueue = []
}

async function doRefresh(originalConfig) {
  const refresh = getRefresh()
  if (!refresh) {
    clearToken()
    router.replace('/login')
    return Promise.reject(new Error('登录已过期'))
  }
  if (isRefreshing) {
    // 并发请求排队，刷新后统一重放
    return new Promise((resolve, reject) => {
      pendingQueue.push({ resolve: () => resolve(service(originalConfig)), reject })
    })
  }
  isRefreshing = true
  try {
    const resp = await axios.post(`${BASE}/accounts/auth/refresh/`, { refresh })
    const data = resp.data?.data || resp.data
    setToken(data.access)
    setRefresh(data.refresh)
    flushQueue(null)
    return service(originalConfig)
  } catch (e) {
    flushQueue(e)
    clearToken()
    useUserStore().reset()
    router.replace('/login')
    return Promise.reject(e)
  } finally {
    isRefreshing = false
  }
}

function isAuthError(body) {
  // 后端统一响应体：code 非 0，4010/401 视为令牌失效
  return body && typeof body.code === 'number' && (body.code === 4010 || body.code === 4004)
}

service.interceptors.response.use(
  (response) => {
    const body = response.data
    // 统一响应体 {code,msg,data}
    if (body && typeof body.code === 'number') {
      if (body.code === 0) return body.data
      if (isAuthError(body)) return doRefresh(response.config)
      ElMessage.error(body.msg || '请求失败')
      return Promise.reject(new Error(body.msg || 'error'))
    }
    return body
  },
  (error) => {
    const status = error.response?.status
    const body = error.response?.data
    if (status === 401 || isAuthError(body)) {
      return doRefresh(error.config || {})
    }
    ElMessage.error(error.message || '网络异常')
    return Promise.reject(error)
  },
)

// ---- 通用封装 ----
// 查询参数兼容层：项目内同时存在两种调用习惯，且都要支持
//   A) http.get(url, { params: { page: 1 } })  —— axios 配置对象（视图层多数写法）
//   B) http.get(url, { page: 1 })              —— 直接传查询参数（crud.js / modules.js 写法）
// 早期实现无条件再包一层 { params }，会把 A 变成 params[page]=1，
// 导致关键字、状态、分页等查询参数整体失效（后端收到的永远是空筛选默认值）。
const AXIOS_CONFIG_KEYS = [
  'params', 'headers', 'responseType', 'timeout', 'baseURL', 'withCredentials', 'signal',
  'auth', 'proxy', 'paramsSerializer', 'validateStatus', 'onUploadProgress',
  'onDownloadProgress', 'transformRequest', 'transformResponse', 'cancelToken',
]
function toAxiosConfig(arg) {
  if (arg == null || typeof arg !== 'object') return undefined
  return AXIOS_CONFIG_KEYS.some((k) => k in arg) ? arg : { params: arg }
}

export const http = {
  get: (url, params) => service.get(url, toAxiosConfig(params)),
  post: (url, data) => service.post(url, data),
  put: (url, data) => service.put(url, data),
  patch: (url, data) => service.patch(url, data),
  delete: (url, data) => service.delete(url, { data }),
}

// 便捷：列表接口（兼容 {list,total} 分页体）返回原始 data，由调用方解构
export const apiList = (url, params) => http.get(url, params)
export const apiGet = (url) => http.get(url)
export const apiCreate = (url, data) => http.post(url, data)
export const apiUpdate = (url, data) => http.put(url, data)
export const apiPatch = (url, data) => http.patch(url, data)
export const apiDelete = (url) => http.delete(url)

export default service
