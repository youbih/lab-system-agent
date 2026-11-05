//存储token 存储用户信息 获取token 用户信息 删除用户信息,token这些作用

//auth.js 定义了登录状态在前端的完整生命周期管理：登录成功后把 token 和用户信息存进浏览器；之后每次
//请求取出来用；退出或失效时清掉。
const TOKEN_KEY = 'token'
const USER_KEY = 'userInfo'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function getUserInfo() {
  const str = localStorage.getItem(USER_KEY)
  return str ? JSON.parse(str) : null
}

export function setUserInfo(userInfo) {
  localStorage.setItem(USER_KEY, JSON.stringify(userInfo))
}

export function removeUserInfo() {
  localStorage.removeItem(USER_KEY)
}

//登出
export function logout() {
  removeToken()
  removeUserInfo()
}
