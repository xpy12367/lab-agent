// 仅供页面  setup 函数使用
import { ref } from 'vue'
import { getUserInfo, setToken, setUserInfo } from './auth'

const userInfo = ref(getUserInfo()) // 响应式对象 可以随时更新最新的值

export function useUser() {
  function saveLoginData(data) {
    setToken(data.token)
    setUserInfo(data.user)
    userInfo.value = data.user
  } //登录成功后调用，一次性保存 token + 用户信息，同时更新页面里的响应式数据

  function updateUser(user) {
    setUserInfo(user)
    userInfo.value = user
  } //更新用户信息（改了昵称之类）

  function reloadUser() {
    userInfo.value = getUserInfo()
  } //从 localStorage 重新读一遍用户信息，刷新到页面上

  return {
    userInfo,
    saveLoginData,
    updateUser,
    reloadUser
  }
}
