// 令牌与用户信息本地存储（localStorage）
const TOKEN_KEY = 'oa_access_token'
const REFRESH_KEY = 'oa_refresh_token'
const USER_KEY = 'oa_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function setToken(token) {
  token && localStorage.setItem(TOKEN_KEY, token)
}
export function getRefresh() {
  return localStorage.getItem(REFRESH_KEY) || ''
}
export function setRefresh(token) {
  token && localStorage.setItem(REFRESH_KEY, token)
}
export function setUser(user) {
  user && localStorage.setItem(USER_KEY, JSON.stringify(user))
}
export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem(USER_KEY)
}
export function persistAuth({ access, refresh, user }) {
  setToken(access)
  setRefresh(refresh)
  if (user) setUser(user)
}
