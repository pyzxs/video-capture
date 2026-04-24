import { createRouter, createWebHashHistory } from 'vue-router'

import VideoManager from '../views/VideoManager.vue'
import MaterialManager from '../views/MaterialManager.vue'
import MashupManager from '../views/MashupManager.vue'

const routes = [
  { path: '/', redirect: '/videos' },
  { path: '/videos', name: 'Videos', component: VideoManager, meta: { title: '原始视频管理' } },
  { path: '/materials', name: 'Materials', component: MaterialManager, meta: { title: '素材管理' } },
  { path: '/mashups', name: 'Mashups', component: MashupManager, meta: { title: '混剪视频管理' } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
