import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // A 401 from a normal page means the login expired: clear it and go to
    // the login page. But a 401 from the login/register/reset forms just
    // means wrong details, which the form itself shows; reloading the page
    // there would hide the error message.
    const url = error.config?.url || ''
    const isAuthForm = url.startsWith('/auth/')
    if (error.response && error.response.status === 401 && !isAuthForm) {
      localStorage.removeItem('token')
      if (window.location.pathname !== '/login') {
        const next = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.href = `/login?next=${next}`
      }
    }
    return Promise.reject(error)
  }
)

export function useApi() {
  return api
}

export default api
