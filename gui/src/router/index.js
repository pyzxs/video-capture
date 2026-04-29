import { createRouter, createWebHashHistory } from 'vue-router'

import VideoManager from '../views/video/VideoManager.vue'
import MaterialManager from '../views/material/MaterialManager.vue'
import MashupManager from '../views/mashup/MashupManager.vue'
import MashupEditor from '../views/mashup/MashupEditor.vue'
import SettingsView from '../views/settings/Settings.vue'
import AgentsView from '../views/agent/Agents.vue'
import NotesView from '../views/note/Notes.vue'
import ProfilePage from '../views/profile/ProfilePage.vue'

const routes = [
  { path: '/', redirect: '/videos' },
  { path: '/videos', name: 'Videos', component: VideoManager, meta: { title: '原始视频管理' } },
  { path: '/materials', name: 'Materials', component: MaterialManager, meta: { title: '素材管理' } },
  { path: '/mashups', name: 'Mashups', component: MashupManager, meta: { title: '混剪视频管理' } },
  { path: '/mashups/editor/:id?', name: 'MashupEditor', component: MashupEditor, meta: { title: '混剪编辑器' } },
  { path: '/notes', name: 'Notes', component: NotesView, meta: { title: '笔记管理' } },
  { path: '/agents', name: 'Agents', component: AgentsView, meta: { title: '智能体管理' } },
  { path: '/settings', name: 'Settings', component: SettingsView, meta: { title: '系统配置' } },
  { path: '/profile', name: 'Profile', component: ProfilePage, meta: { title: '用户信息' } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
