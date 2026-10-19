import { http } from './http'

export const authApi = {
  login: (data) => http.post('/accounts/auth/login/', data),
  logout: (refresh) => http.post('/accounts/auth/logout/', { refresh }),
  menus: () => http.get('/accounts/auth/menus/'),
  myPermissions: () => http.get('/accounts/auth/my_permissions/'),
  profile: () => http.get('/accounts/auth/profile/'),
  changePassword: (data) => http.post('/accounts/auth/change_password/', data),
  captcha: () => http.get('/accounts/auth/captcha/'),
  loginConfig: () => http.get('/accounts/auth/login-config/'),
  updateProfile: (data) => http.patch('/accounts/auth/profile/', data),
}
