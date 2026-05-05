<template>
  <header class="app-header">
    <div class="header-logo">
      <img src="/video-capture.ico" width="22" height="22" class="logo-icon" alt="" />
      <span class="header-title">Video Capture</span>
    </div>
    <div class="header-controls">
      <button class="header-btn" @click="minimizeWindow" title="最小化">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="5" y1="12" x2="19" y2="12"/></svg>
      </button>
      <button class="header-btn" @click="maximizeWindow" title="最大化">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="5" width="14" height="14" rx="1"/></svg>
      </button>
      <button class="header-btn header-btn-close" @click="closeWindow" title="关闭">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="6" y1="6" x2="18" y2="18"/><line x1="6" y1="18" x2="18" y2="6"/></svg>
      </button>
    </div>
  </header>
  <div class="app-container">
    <aside class="sidebar">
      <nav>
        <router-link to="/videos" class="nav-item" active-class="active" title="原始视频管理">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9l5 3-5 3V9z"/>
          </svg>
          <span>原始视频管理</span>
        </router-link>
        <router-link to="/materials" class="nav-item" active-class="active" title="素材管理">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="22 3 22 15 16 15 16 21 2 21 2 3 22 3" /><line x1="6" y1="7" x2="18" y2="7" /><line x1="6" y1="11" x2="18" y2="11" /><line x1="6" y1="15" x2="10" y2="15" />
          </svg>
          <span>素材管理</span>
        </router-link>
        <router-link to="/mashups" class="nav-item" active-class="active" title="混剪视频管理">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M15 8a5 5 0 0 1 0 8" /><path d="M18.3 4.7a9 9 0 0 1 0 14.6" /><rect x="2" y="6" width="10" height="12" rx="1" />
          </svg>
          <span>混剪视频管理</span>
        </router-link>
        <router-link to="/notes" class="nav-item" active-class="active" title="笔记管理">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
          </svg>
          <span>笔记管理</span>
        </router-link>
        <router-link to="/agents" class="nav-item" active-class="active" title="智能体管理">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"/><path d="M16 14H8a4 4 0 0 0-4 4v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2a4 4 0 0 0-4-4z"/><path d="M20 10l-2 2 2 2"/><path d="M4 10l2 2-2 2"/>
          </svg>
          <span>智能体管理</span>
        </router-link>
        <router-link to="/settings" class="nav-item" active-class="active" title="系统配置">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          <span>系统配置</span>
        </router-link>
      </nav>
      <div class="sidebar-bottom">
        <router-link to="/profile" class="nav-item" active-class="active" title="用户信息">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
          </svg>
          <span>用户信息</span>
        </router-link>
      </div>
    </aside>

    <!-- 二级菜单 - 文件夹 -->
    <aside v-if="showSubSidebar" class="sub-sidebar">
      <div class="sub-sidebar-header">
        <span>文件夹</span>
        <button class="btn btn-sm btn-default" @click="handleCreateFolder" title="新建文件夹">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
      </div>
      <div class="sub-sidebar-tree">
        <div class="sub-sidebar-item" :class="{ active: selectedFolderId === null }" @click="selectedFolderId = null">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <span>全部</span>
        </div>
        <div v-for="f in folders" :key="f.id" class="sub-sidebar-item"
             :class="{ active: selectedFolderId === f.id }"
             @click="selectedFolderId = f.id">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <span class="sub-sidebar-name">{{ f.name }}</span>
          <span class="sub-sidebar-count">{{ folderCount(f) }}</span>
          <div class="sub-sidebar-actions">
            <button class="btn-icon" @click.stop="handleRenameFolder(f)" title="重命名">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            </button>
            <button class="btn-icon btn-icon-danger" @click.stop="handleDeleteFolder(f)" title="删除">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      </div>
    </aside>

    <main class="main-content">
      <router-view />
    </main>
    <ToastMessage />
    <ConfirmDialog />
    <PromptDialog />

    <!-- 资源下载进度对话框 -->
    <div v-if="showResourceDialog" class="modal-overlay">
      <div class="modal resource-dialog" :class="{ 'resource-error': resourceError, 'resource-done': resourceReady }">
        <!-- 图标区 -->
        <div class="resource-icon">
          <!-- 下载中 -->
          <svg v-if="!resourceReady && !resourceError" class="resource-icon-svg downloading" viewBox="0 0 64 64" width="64" height="64" fill="none">
            <circle cx="32" cy="32" r="28" stroke="var(--accent-light)" stroke-width="2.5" opacity="0.3"/>
            <circle cx="32" cy="32" r="28" stroke="var(--accent)" stroke-width="2.5" stroke-dasharray="176" stroke-dashoffset="176" stroke-linecap="round">
              <animate attributeName="stroke-dashoffset" from="176" to="0" dur="1.4s" repeatCount="indefinite"/>
            </circle>
            <path d="M32 20v18M24 32l8 8 8-8" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <!-- 完成 -->
          <svg v-if="resourceReady" class="resource-icon-svg done" viewBox="0 0 64 64" width="64" height="64" fill="none">
            <circle cx="32" cy="32" r="28" fill="#ecfdf5" stroke="#10b981" stroke-width="2.5"/>
            <path d="M20 32l8 8 16-16" stroke="#10b981" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <!-- 错误 -->
          <svg v-if="resourceError" class="resource-icon-svg error" viewBox="0 0 64 64" width="64" height="64" fill="none">
            <circle cx="32" cy="32" r="28" fill="#fef2f2" stroke="#ef4444" stroke-width="2.5"/>
            <path d="M24 24l16 16M40 24l-16 16" stroke="#ef4444" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>

        <!-- 标题 -->
        <h3 class="resource-title">
          {{ resourceError ? '下载失败' : (resourceReady ? '准备就绪' : '正在准备必要资源') }}
        </h3>

        <!-- 描述 -->
        <p class="resource-desc" v-if="!resourceReady && !resourceError">
          首次启动需下载运行环境，包含视频处理工具和语音识别模型，仅需一次。
        </p>
        <p class="resource-desc" v-if="resourceReady">
          所有资源已就绪，可以开始使用了。
        </p>
        <p class="resource-desc error-desc" v-if="resourceError">
          {{ resourceError }}
        </p>

        <!-- 下载清单 -->
        <div class="resource-list" v-if="!resourceReady && !resourceError">
          <div class="resource-item">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/></svg>
            <span>ffmpeg / ffplay / ffprobe 视频处理工具</span>
            <span class="resource-item-size">~560 MB</span>
          </div>
          <div class="resource-item">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"/><path d="M16 14H8a4 4 0 0 0-4 4v2h16v-2a4 4 0 0 0-4-4z"/></svg>
            <span>Whisper 语音识别模型 (base)</span>
            <span class="resource-item-size">~280 MB</span>
          </div>
        </div>

        <!-- 进度条 -->
        <div class="resource-progress" v-if="!resourceReady && !resourceError">
          <div class="resource-progress-track">
            <div class="resource-progress-fill" :style="{ width: resourcePercent + '%' }">
              <div class="resource-progress-shimmer"></div>
            </div>
          </div>
          <div class="resource-progress-info">
            <span class="resource-percent">{{ resourcePercent }}%</span>
            <span class="resource-mb">{{ (resourceProgress / 1048576).toFixed(1) }} / {{ (resourceTotal / 1048576).toFixed(1) }} MB</span>
            <span class="resource-elapsed" v-if="resourceProgress > 0">{{ downloadElapsed }}</span>
          </div>
        </div>

        <!-- 按钮 -->
        <div class="resource-actions">
          <template v-if="resourceReady">
            <button class="btn btn-success btn-lg" @click="showResourceDialog = false">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="9 18 15 12 9 6"/></svg>
              开始使用 Video Capture
            </button>
          </template>
          <template v-if="resourceError">
            <button class="btn btn-outline btn-lg" @click="showResourceDialog = false">跳过</button>
            <button class="btn btn-primary btn-lg" @click="retryDownload">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 1 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>
              重新下载
            </button>
          </template>
        </div>

        <!-- 手动安装 -->
        <div class="resource-manual" v-if="!resourceReady">
          <span>自动下载失败？</span>
          <a href="#" @click.prevent="openManualInstall">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            手动安装
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { computed, watch, ref, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import ToastMessage from './components/ToastMessage.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import PromptDialog from './components/PromptDialog.vue'
import { useFolders } from './composables/useFolders.js'
import { useToast } from './composables/useToast.js'
import { folderApi, resourceApi } from './api/index.js'

export default {
  name: 'App',
  components: { ToastMessage, ConfirmDialog, PromptDialog },
  setup() {
    const route = useRoute()
    const toast = useToast()
    const { folders, selectedFolderId, loadFolders } = useFolders()

    const folderRoutes = ['Videos', 'Materials', 'Mashups']
    const showSubSidebar = computed(() => folderRoutes.includes(route.name))

    const folderTypeMap = {
      Videos: 'video',
      Materials: 'material',
      Mashups: 'generated',
    }

    watch(() => route.name, (name) => {
      if (folderRoutes.includes(name)) {
        selectedFolderId.value = null
        loadFolders(folderTypeMap[name])
      }
    })

    const handleCreateFolder = async () => {
      const name = await toast.prompt('请输入文件夹名称', '新建文件夹', '')
      if (!name) return
      try {
        await folderApi.create(name, folderTypeMap[route.name])
        await loadFolders(folderTypeMap[route.name])
        toast.success('文件夹已创建')
      } catch (e) {
        toast.error('创建失败')
      }
    }

    const handleRenameFolder = async (f) => {
      const name = await toast.prompt('请输入新名称', '重命名文件夹', f.name)
      if (!name || name === f.name) return
      try {
        await folderApi.update(f.id, name)
        await loadFolders(folderTypeMap[route.name])
        toast.success('已重命名')
      } catch (e) {
        toast.error('重命名失败')
      }
    }

    const handleDeleteFolder = async (f) => {
      if (!await toast.confirm(`确定删除文件夹「${f.name}」？文件夹内的内容将变为未分类。`)) return
      try {
        await folderApi.remove(f.id)
        if (selectedFolderId.value === f.id) {
          selectedFolderId.value = null
        }
        await loadFolders(folderTypeMap[route.name])
        toast.success('文件夹已删除')
      } catch (e) {
        toast.error('删除失败')
      }
    }

    const folderCount = (f) => {
      const key = folderTypeMap[route.name]
      if (key === 'video') return f.video_count ?? ''
      if (key === 'material') return f.material_count ?? ''
      if (key === 'generated') return f.generated_count ?? ''
      return ''
    }

    // ── 资源下载状态 ──
    const showResourceDialog = ref(false)
    const resourceReady = ref(false)
    const resourceProgress = ref(0)
    const resourceTotal = ref(0)
    const resourceError = ref('')
    let _pollTimer = null

    const resourcePercent = computed(() => {
      if (resourceTotal.value <= 0) return 0
      return Math.min(Math.round(resourceProgress.value * 100 / resourceTotal.value), 100)
    })

    const _downloadStart = ref(0)
    const downloadElapsed = ref('')
    let _elapsedTimer = null

    function _startElapsed() {
      _downloadStart.value = Date.now()
      _elapsedTimer = setInterval(() => {
        const s = Math.floor((Date.now() - _downloadStart.value) / 1000)
        downloadElapsed.value = s < 60 ? `${s} 秒` : `${Math.floor(s / 60)} 分 ${s % 60} 秒`
      }, 1000)
    }

    function _stopElapsed() {
      if (_elapsedTimer) { clearInterval(_elapsedTimer); _elapsedTimer = null }
    }

    async function checkAndDownload() {
      try {
        const { data } = await resourceApi.status()
        if (data.ready) {
          resourceReady.value = true
          showResourceDialog.value = false
          return
        }
        showResourceDialog.value = true
        resourceError.value = data.error || ''
        resourceProgress.value = data.progress || 0
        resourceTotal.value = data.total || 0

        if (!data.downloading && !data.error) {
          await resourceApi.download()
          _startPolling()
        } else if (data.downloading) {
          _startPolling()
        }
      } catch (e) {
        showResourceDialog.value = true
        resourceError.value = '无法连接服务器，请检查 CMS 地址配置'
      }
    }

    function _startPolling() {
      if (_pollTimer) return
      _startElapsed()
      _pollTimer = setInterval(async () => {
        try {
          const { data } = await resourceApi.status()
          resourceProgress.value = data.progress || 0
          resourceTotal.value = data.total || 0
          resourceError.value = data.error || ''

          if (data.ready) {
            clearInterval(_pollTimer)
            _pollTimer = null
            _stopElapsed()
            resourceReady.value = true
          } else if (data.error) {
            clearInterval(_pollTimer)
            _pollTimer = null
            _stopElapsed()
          }
        } catch (e) {
          // ignore poll errors
        }
      }, 800)
    }

    async function retryDownload() {
      resourceError.value = ''
      resourceProgress.value = 0
      resourceTotal.value = 0
      downloadElapsed.value = ''
      try {
        await resourceApi.download()
        _startPolling()
      } catch (e) {
        resourceError.value = '下载请求失败: ' + (e.message || e)
      }
    }

    const MANUAL_URL = 'https://github.com/pyzxs/video-capture-install/releases/tag/model'

    function openManualInstall() {
      if (window.electronAPI?.openExternal) {
        window.electronAPI.openExternal(MANUAL_URL)
      } else {
        window.open(MANUAL_URL, '_blank')
      }
    }

    onMounted(() => {
      checkAndDownload()
    })

    onBeforeUnmount(() => {
      if (_pollTimer) {
        clearInterval(_pollTimer)
        _pollTimer = null
      }
      _stopElapsed()
    })

    return {
      showSubSidebar,
      folders,
      selectedFolderId,
      folderCount,
      handleCreateFolder,
      handleRenameFolder,
      handleDeleteFolder,
      minimizeWindow: () => window.electronAPI?.minimize(),
      maximizeWindow: () => window.electronAPI?.maximize(),
      closeWindow: () => window.electronAPI?.close(),
      showResourceDialog,
      resourceReady,
      resourceProgress,
      resourceTotal,
      resourceError,
      resourcePercent,
      downloadElapsed,
      retryDownload,
      openManualInstall,
    }
  },
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --accent: #6c5ce7;
  --accent-light: #a29bfe;
  --accent-bg: rgba(108,92,231,0.08);
  --bg: #f0f2f5;
  --card-bg: #ffffff;
  --text: #1a1a2e;
  --text-secondary: #6b7280;
  --border: #e5e7eb;
  --radius: 10px;
  --radius-sm: 6px;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

/* ── App Header ── */
.app-header {
  height: 40px;
  background: #fff;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  -webkit-app-region: drag;
  user-select: none;
  flex-shrink: 0;
}
.header-logo {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-logo .logo-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}
.header-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}
.header-controls {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
  -webkit-app-region: no-drag;
}
.header-btn {
  width: 36px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.12s;
}
.header-btn:hover { background: #f3f4f6; color: var(--text); }
.header-btn-close:hover { background: #ef4444; color: #fff; }

.app-container { display: flex; height: calc(100vh - 40px); }

/* ── Sidebar ── */
.sidebar {
  width: 62px;
  background: #fff;
  color: var(--text);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  user-select: none;
  overflow: hidden;
  border-right: 1px solid var(--border);
}

nav { flex: 1; padding: 12px 0; display: flex; flex-direction: column; align-items: center; gap: 2px; }
.sidebar-bottom { padding: 8px 0; border-top: 1px solid var(--border); display: flex; flex-direction: column; align-items: center; }
.nav-item {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  border-radius: 10px;
  transition: all 0.15s ease;
}
.nav-item:hover { background: #f0f2f5; color: var(--text); }
.nav-item.active { background: #dcfce7; color: #16a34a; border-radius: 50%; }
.nav-item.router-link-exact-active { background: #dcfce7; color: #16a34a; border-radius: 50%; }
.nav-item svg { flex-shrink: 0; opacity: 0.7; }
.nav-item.active svg { opacity: 1; }
.nav-item.router-link-exact-active svg { opacity: 1; }
.nav-item span { display: none; }
.status-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.online { background: #4ade80; box-shadow: 0 0 6px rgba(74,222,128,0.4); }
.status-dot.offline { background: #f87171; box-shadow: 0 0 6px rgba(248,113,113,0.4); }
.status-dot.checking { background: #fbbf24; box-shadow: 0 0 6px rgba(251,191,36,0.4); }
.status-text { line-height: 1; }

/* ── Sub Sidebar ── */
.sub-sidebar {
  width: 135px;
  background: #fff;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
  border-right: 1px solid var(--border);
}
.sub-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 12px;
  border-bottom: 1px solid var(--border);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.sub-sidebar-tree {
  flex: 1;
  overflow-y: auto;
  padding: 6px 4px;
}
.sub-sidebar-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 6px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text);
  transition: background 0.15s;
  position: relative;
}
.sub-sidebar-item:hover { background: #f3f4f6; }
.sub-sidebar-item.active {
  background: #eef2ff;
  color: var(--accent);
  font-weight: 500;
}
.sub-sidebar-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sub-sidebar-name:not(:last-child) {
  margin-right: 2px;
}
.sub-sidebar-count {
  font-size: 10px;
  color: var(--text-secondary);
  background: #f3f4f6;
  padding: 0 4px;
  border-radius: 6px;
  line-height: 16px;
  flex-shrink: 0;
}
.sub-sidebar-actions {
  display: none;
  gap: 1px;
  align-items: center;
  flex-shrink: 0;
}
.sub-sidebar-item:hover .sub-sidebar-actions {
  display: flex;
}
.sub-sidebar-item:hover .sub-sidebar-count {
  display: none;
}
.sub-sidebar .btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 1px;
  border-radius: 3px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all 0.15s;
  width: 18px;
  height: 18px;
}
.sub-sidebar .btn-icon:hover { background: #e5e7eb; color: var(--text); }
.sub-sidebar .btn-icon-danger:hover { background: #fee2e2; color: #dc2626; }
.sub-sidebar .btn-sm { padding: 4px 6px; font-size: 12px; border-radius: 5px; }

/* ── Main Content ── */
.main-content { flex: 1; overflow-y: auto; background: var(--bg); padding: 1px 3px; }

/* ── Scrollbar ── */
.main-content::-webkit-scrollbar,
.sub-sidebar-tree::-webkit-scrollbar { width: 4px; }
.main-content::-webkit-scrollbar-track,
.sub-sidebar-tree::-webkit-scrollbar-track { background: transparent; }
.main-content::-webkit-scrollbar-thumb,
.sub-sidebar-tree::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
.main-content::-webkit-scrollbar-thumb:hover,
.sub-sidebar-tree::-webkit-scrollbar-thumb:hover { background: #9ca3af; }

/* ── Global Shared Styles ── */
.view-container { width: 100%; }
.panel {
  background: var(--card-bg);
  box-shadow: var(--shadow);
  padding: 16px 20px;
  margin-bottom: 10px;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.view-header h2 {
  font-size: 16px;
  font-weight: 400;
  color: var(--text);
  letter-spacing: -0.3px;
}
.header-actions { display: flex; gap: 10px; align-items: center; }

/* Cards */
.card {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
}

/* Tables */
.data-table { width: 100%; border-collapse: collapse; }
.data-table thead { background: #f9fafb; }
.data-table th {
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid var(--border);
}
.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid #f3f4f6;
  font-size: 14px;
  color: var(--text);
}
.data-table tbody tr { transition: background 0.12s; }
.data-table tbody tr:hover td { background: #f8f9ff; }
.data-table tbody tr:last-child td { border-bottom: none; }
.content-cell {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--text-secondary);
}
.empty { text-align: center; color: var(--text-secondary); padding: 48px 16px !important; font-size: 14px; }
.actions { display: flex; gap: 6px; flex-wrap: wrap; }

/* Loading */
.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: var(--text-secondary);
  font-size: 14px;
  gap: 10px;
}
.loading::before {
  content: '';
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  padding: 7px 14px;
  transition: all 0.15s ease;
  white-space: nowrap;
  line-height: 1.4;
}
.btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.btn:active:not(:disabled) { transform: translateY(0); }
.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.btn-sm { padding: 5px 10px; font-size: 12px; border-radius: 5px; }

/* Icon-only buttons: 透明背景，黑色图标，hover 时显示浅色底 */
.btn:has(svg:only-child) {
  background: transparent !important;
  border: none;
  padding: 6px;
  box-shadow: none;
  color: #1a1a2e !important;
}
.btn:has(svg:only-child):hover:not(:disabled) {
  background: rgba(0,0,0,0.06) !important;
  box-shadow: none;
  transform: none;
}
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover:not(:disabled) { background: #5a4bd1; }
.btn-success { background: #10b981; color: #fff; }
.btn-success:hover:not(:disabled) { background: #059669; }
.btn-danger { background: #ef4444; color: #fff; }
.btn-danger:hover:not(:disabled) { background: #dc2626; }
.btn-info { background: #3b82f6; color: #fff; }
.btn-info:hover:not(:disabled) { background: #2563eb; }
.btn-default { background: #f3f4f6; color: #374151; border: 1px solid var(--border); }
.btn-default:hover:not(:disabled) { background: #e5e7eb; }
.btn-warning { background: #f59e0b; color: #fff; }
.btn-warning:hover:not(:disabled) { background: #d97706; }

/* Inputs */
.search-input {
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  width: 240px;
  font-size: 13px;
  background: var(--card-bg);
  color: var(--text);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.search-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(108,92,231,0.12);
}
.search-input::placeholder { color: #9ca3af; }

.filter-select {
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  background: var(--card-bg);
  color: var(--text);
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.filter-select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(108,92,231,0.12);
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.45);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: overlay-in 0.15s ease;
}
@keyframes overlay-in { from { opacity: 0; } to { opacity: 1; } }
.modal {
  background: var(--card-bg);
  border-radius: 14px;
  padding: 28px;
  width: 520px;
  max-height: 82vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15);
  animation: modal-in 0.2s ease;
}
@keyframes modal-in { from { opacity: 0; transform: scale(0.96) translateY(8px); } to { opacity: 1; transform: scale(1) translateY(0); } }
.modal-wide { width: 780px; }
.modal h3 { font-size: 17px; font-weight: 700; color: var(--text); }
.modal-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 20px; line-height: 1.5; }

/* Modal header: title left, actions right */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.modal-header h3 { margin: 0; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 50ch; }
.modal-header .modal-actions {
  display: flex;
  gap: 6px;
  margin: 0;
}

.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; }

/* Form */
.form { display: flex; flex-direction: column; gap: 14px; }
.form label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}
.form input, .form select, .form textarea {
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  background: #f9fafb;
  color: var(--text);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  font-family: inherit;
}
.form input:focus, .form select:focus, .form textarea:focus {
  border-color: var(--accent);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(108,92,231,0.1);
}

/* Tag / Badge */
.tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  background: #eef2ff;
  color: var(--accent);
}
.status-badge {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}
.status-badge.created { background: #eef2ff; color: #4f46e5; }
.status-badge.processing { background: #fff7ed; color: #ea580c; }
.status-badge.completed { background: #ecfdf5; color: #059669; }
.status-badge.failed { background: #fef2f2; color: #dc2626; }

/* Upload progress */
.upload-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 4px 0 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

/* ── Resource Download Dialog ── */
.resource-dialog {
  width: 480px;
  text-align: center;
  padding: 36px 32px 28px;
}

.resource-icon { margin-bottom: 16px; }
.resource-icon-svg { display: inline-block; }
.resource-icon-svg.downloading { animation: resource-pulse 2s ease-in-out infinite; }
.resource-icon-svg.done { animation: resource-pop 0.4s ease; }
.resource-icon-svg.error { animation: resource-pop 0.3s ease; }

@keyframes resource-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.06); opacity: 0.85; }
}
@keyframes resource-pop {
  from { transform: scale(0.7); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.resource-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  margin-bottom: 8px;
}

.resource-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 20px;
}

.error-desc {
  color: #dc2626;
  background: #fef2f2;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
}

/* 下载清单 */
.resource-list {
  background: #f9fafb;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 20px;
  text-align: left;
}

.resource-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text);
}
.resource-item:first-child { padding-top: 0; }
.resource-item:last-child { padding-bottom: 0; }
.resource-item + .resource-item { border-top: 1px solid #f0f0f0; }
.resource-item svg { flex-shrink: 0; color: var(--text-secondary); }
.resource-item span:first-of-type { flex: 1; }
.resource-item-size {
  font-size: 11px;
  color: #9ca3af;
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

/* 进度条 */
.resource-progress { margin-bottom: 8px; }
.resource-progress-track {
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.resource-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6c5ce7 0%, #a29bfe 60%, #6c5ce7 100%);
  background-size: 200% 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
  position: relative;
  overflow: hidden;
  animation: resource-gradient 2s linear infinite;
}

@keyframes resource-gradient {
  from { background-position: 200% 0; }
  to { background-position: 0 0; }
}

.resource-progress-shimmer {
  position: absolute;
  top: 0; left: -100%;
  width: 100%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
  animation: resource-shimmer 1.6s ease-in-out infinite;
}

@keyframes resource-shimmer {
  from { left: -100%; }
  to { left: 200%; }
}

.resource-progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--text-secondary);
}

.resource-percent {
  font-weight: 700;
  font-size: 14px;
  color: var(--accent);
}

.resource-mb {
  color: #9ca3af;
}

.resource-elapsed {
  color: #9ca3af;
  font-variant-numeric: tabular-nums;
}

/* 按钮区 */
.resource-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 24px;
}

.btn-lg {
  padding: 10px 24px;
  font-size: 14px;
  border-radius: 8px;
}

.btn-outline {
  background: #fff;
  color: var(--text-secondary);
  border: 1px solid var(--border);
}
.btn-outline:hover:not(:disabled) {
  background: #f9fafb;
  color: var(--text);
  border-color: #d1d5db;
}

/* 手动安装入口 */
.resource-manual {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.resource-manual a {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--accent);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.15s;
}

.resource-manual a:hover { color: #5a4bd1; text-decoration: underline; }
.progress-bar { flex: 1; height: 6px; background: #f3f4f6; border-radius: 3px; overflow: hidden; }
.progress-fill {
  height: 100%;
  width: 0%;
  background: linear-gradient(90deg, var(--accent), var(--accent-light));
  border-radius: 3px;
  transition: width 0.3s ease;
}

/* Upload zone */
.upload-zone {
  border: 2px dashed #d1d5db;
  border-radius: 10px;
  padding: 28px;
  text-align: center;
  transition: all 0.2s;
  cursor: pointer;
  margin-bottom: 14px;
}
.upload-zone.drag-over { border-color: var(--accent); background: rgba(108,92,231,0.05); }
.upload-placeholder { display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--text-secondary); }
.upload-icon { font-size: 36px; line-height: 1; }
.upload-hint { font-size: 12px; color: #9ca3af; }
.upload-preview { display: flex; align-items: center; gap: 12px; justify-content: center; }
.file-name { font-weight: 600; color: var(--text); max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-size { color: var(--text-secondary); font-size: 13px; }

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 24px;
  padding: 4px 0;
}
.page-btn {
  min-width: 34px;
  height: 34px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--card-bg);
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.12s;
  padding: 0 10px;
}
.page-btn:hover:not(:disabled):not(.active) {
  border-color: var(--accent);
  color: var(--accent);
}
.page-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.page-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.page-info { margin-left: 14px; font-size: 13px; color: var(--text-secondary); }

/* Preview */
.preview-body { border-radius: 10px; overflow: hidden; }
.video-player { width: 100%; max-height: 70vh; display: block; }

/* Material section (MashupManager) */
.material-section { border: 1px solid var(--border); border-radius: 10px; padding: 14px; background: #fafbfc; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.section-header strong { font-size: 13px; color: var(--text); }
.empty-hint { text-align: center; padding: 24px 16px; color: var(--text-secondary); font-size: 13px; }
.material-item { display: flex; align-items: center; gap: 10px; padding: 8px 4px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.material-item:last-child { border-bottom: none; }
.mat-order {
  width: 26px; height: 26px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--accent-light));
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600;
  flex-shrink: 0;
}
.mat-content { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
.mat-time { color: var(--text-secondary); font-size: 12px; white-space: nowrap; }
.mat-actions { display: flex; gap: 3px; }
.btn-icon {
  background: none;
  border: 1px solid var(--border);
  border-radius: 5px;
  cursor: pointer;
  width: 28px; height: 28px;
  font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-secondary);
  transition: all 0.12s;
}
.btn-icon:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.btn-icon:disabled { opacity: 0.3; cursor: not-allowed; }
.btn-icon-danger { color: #ef4444; border-color: #fecaca; }
.btn-icon-danger:hover:not(:disabled) { background: #fef2f2; border-color: #ef4444; color: #dc2626; }
.mat-picker-list { max-height: 320px; overflow-y: auto; }
.mat-picker-item {
  display: flex; gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
  font-size: 13px;
  border-radius: 6px;
  transition: background 0.1s;
}
.mat-picker-item:hover { background: #f0f4ff; }
.mat-picker-item:last-child { border-bottom: none; }
.mat-picker-item .mat-content { flex: 1; }
.mat-picker-item span:first-child { color: var(--text-secondary); font-weight: 600; font-size: 12px; }

/* Upload options */
.upload-options { display: flex; gap: 14px; margin-bottom: 14px; }
.upload-options label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-secondary); }
.upload-options select { padding: 5px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; background: var(--card-bg); color: var(--text); outline: none; }

/* Data table variant override for scoped */
table.data-table { background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow); }
.data-table-wrapper { overflow-x: auto; -webkit-overflow-scrolling: touch; }

/* ── Move-to-Folder Dialog ── */
.folder-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 320px;
  overflow-y: auto;
  margin: 0 -4px;
}
.folder-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text);
  transition: all 0.12s ease;
  user-select: none;
}
.folder-item:hover {
  background: #f0f4ff;
  color: var(--accent);
}
.folder-item:active {
  background: #e8ecf8;
  transform: scale(0.98);
}
.folder-item .folder-icon {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  color: #f59e0b;
  opacity: 0.7;
}
.folder-item:hover .folder-icon {
  opacity: 1;
}
.folder-item .folder-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}
.folder-item .folder-arrow {
  flex-shrink: 0;
  width: 14px;
  height: 14px;
  color: var(--text-secondary);
  opacity: 0;
  transition: all 0.12s;
}
.folder-item:hover .folder-arrow {
  opacity: 0.6;
  transform: translateX(3px);
}
.folder-item.uncategorized .folder-icon {
  color: var(--text-secondary);
}
.folder-list::-webkit-scrollbar { width: 4px; }
.folder-list::-webkit-scrollbar-track { background: transparent; }
.folder-list::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
.folder-list::-webkit-scrollbar-thumb:hover { background: #9ca3af; }

/* ── Responsive ── */
@media (max-width: 1024px) {
  .main-content { padding: 1px 3px; }
  .view-header { flex-direction: column; align-items: stretch; gap: 12px; }
  .header-actions { justify-content: space-between; }
  .search-input { width: 100%; }
  .modal-wide { width: calc(100vw - 40px); }
  .modal { width: calc(100vw - 40px); }
}

@media (max-width: 768px) {
  .view-container { max-width: 100%; }
  .data-table { font-size: 13px; }
  .data-table th, .data-table td { padding: 8px 10px; }
  .content-cell { max-width: 120px; }
  .actions { flex-direction: column; align-items: stretch; }
  .actions .btn-sm { width: 100%; justify-content: center; }
  .header-actions { flex-wrap: wrap; }
  .header-actions .btn { flex: 1; justify-content: center; }
  .mat-picker-item { flex-wrap: wrap; }
  .upload-options { flex-direction: column; }
}

@media (max-width: 480px) {
  .main-content { padding: 12px 8px; }
  .data-table-wrapper { overflow-x: auto; }
  .pagination { flex-wrap: wrap; gap: 2px; }
  .page-btn { min-width: 28px; height: 28px; font-size: 12px; padding: 0 6px; }
  .page-info { margin-left: 6px; font-size: 12px; }
  .modal { padding: 20px 16px; }
  .upload-zone { padding: 20px 12px; }
}
</style>
