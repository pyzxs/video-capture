import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { apiUrl } from './api/index.js'

const app = createApp(App)
app.use(router)
app.config.globalProperties.$apiUrl = apiUrl
app.mount('#app')
