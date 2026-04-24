<template>
  <div class="view-container">
    <div class="view-header">
      <h2>原始视频管理</h2>
      <div class="header-actions">
        <input v-model="searchQuery" placeholder="搜索文件名..." class="search-input" @input="page=1; loadVideos()" />
        <button class="btn btn-primary" @click="openUpload">+ 上传视频</button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else class="data-table-wrapper"><table class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>预览</th>
          <th>文件名</th>
          <th>分辨率</th>
          <th>帧率</th>
          <th>文案（前100字）</th>
          <th>导入时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="v in videos" :key="v.id">
          <td>{{ v.id }}</td>
          <td class="video-cell">
            <video
              :src="`/api/videos/${v.id}/file`"
              @mouseenter="hoverPlay($event)"
              @mouseleave="hoverPause($event)"
              muted
              preload="metadata"
              class="inline-player"
            ></video>
          </td>
          <td>{{ v.filename }}</td>
          <td>{{ v.frame_width }}x{{ v.frame_height }}</td>
          <td>{{ v.frame_rate }}fps</td>
          <td class="content-cell" :title="v.content">{{ truncate(v.content, 100) || '-' }}</td>
          <td>{{ formatTime(v.created_at) }}</td>
          <td class="actions">
            <button class="btn btn-sm btn-info" @click="previewVideoAction(v)">预览</button>
            <button class="btn btn-sm btn-primary" @click="splitVideo(v)">分割</button>
            <button class="btn btn-sm btn-success" @click="copyContent(v)">复制文案</button>
            <button class="btn btn-sm btn-danger" @click="deleteVideo(v)">删除</button>
          </td>
        </tr>
        <tr v-if="videos.length === 0">
          <td colspan="8" class="empty">暂无数据</td>
        </tr>
      </tbody>
    </table></div>

    <Pagination :page="page" :total="total" :page-size="pageSize" @change="onPageChange" />

    <!-- 视频预览弹窗 -->
    <div v-if="showPreview" class="modal-overlay" @click.self="closePreview">
      <div class="modal modal-wide">
        <div class="preview-header">
          <h3>{{ previewVideo?.filename }}</h3>
          <button class="btn btn-default btn-sm" @click="closePreview">✕</button>
        </div>
        <div class="preview-body">
          <video v-if="previewSrc" :src="previewSrc" controls autoplay class="video-player"></video>
          <div v-else class="loading">加载中...</div>
        </div>
      </div>
    </div>

    <!-- 上传弹窗 -->
    <div v-if="showDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal">
        <h3>上传视频</h3>
        <p class="modal-desc">上传后将自动提取元数据（分辨率、帧率）和文案（ASR 语音转文字）。</p>
        <div class="upload-zone" @drop.prevent="onDrop" @dragover.prevent
             :class="{ 'drag-over': dragging }" @dragenter="dragging = true" @dragleave="dragging = false">
          <input ref="fileInput" type="file" accept=".mp4,.avi,.mkv,.mov,.webm,.flv" hidden @change="onFileSelect" />
          <div v-if="!selectedFile" class="upload-placeholder" @click="$refs.fileInput.click()">
            <span class="upload-icon">📁</span>
            <span>点击选择视频文件，或拖拽到此处</span>
            <span class="upload-hint">支持 mp4, avi, mkv, mov, webm, flv</span>
          </div>
          <div v-else class="upload-preview">
            <span class="file-name">{{ selectedFile.name }}</span>
            <span class="file-size">{{ formatSize(selectedFile.size) }}</span>
            <button class="btn btn-sm btn-default" @click="clearFile">重新选择</button>
          </div>
        </div>

        <div class="upload-options">
          <label>ASR 语言
            <select v-model="uploadLang">
              <option value="zh">中文</option>
              <option value="en">英文</option>
              <option value="ja">日文</option>
            </select>
          </label>
        </div>

        <div v-if="uploading" class="upload-progress">
          <div class="progress-bar">
            <div class="progress-fill"></div>
          </div>
          <span>正在上传并处理，请稍候...</span>
        </div>

        <div class="modal-actions">
          <button class="btn btn-default" @click="closeDialog" :disabled="uploading">取消</button>
          <button class="btn btn-primary" @click="startUpload" :disabled="!selectedFile || uploading">
            {{ uploading ? '处理中...' : '上传并处理' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { videoApi } from '../api/index.js'
import { useToast } from '../composables/useToast.js'
import Pagination from '../components/Pagination.vue'

export default {
  name: 'VideoManager',
  components: { Pagination },
  setup() {
    const toast = useToast()
    const videos = ref([])
    const loading = ref(true)
    const searchQuery = ref('')
    const page = ref(1)
    const pageSize = 20
    const total = ref(0)

    // Preview
    const showPreview = ref(false)
    const previewVideo = ref(null)
    const previewSrc = ref('')

    const previewVideoAction = (v) => {
      previewVideo.value = v
      previewSrc.value = `/api/videos/${v.id}/file`
      showPreview.value = true
    }

    const closePreview = () => {
      showPreview.value = false
      previewSrc.value = ''
      previewVideo.value = null
    }

    // Upload dialog
    const showDialog = ref(false)
    const selectedFile = ref(null)
    const dragging = ref(false)
    const uploading = ref(false)
    const uploadLang = ref('zh')
    const fileInput = ref(null)

    const loadVideos = async () => {
      loading.value = true
      try {
        const params = { q: searchQuery.value || undefined, skip: (page.value - 1) * pageSize, limit: pageSize }
        const res = await videoApi.list(params)
        const data = res.data
        videos.value = data.items || data || []
        total.value = data.total ?? (Array.isArray(data) ? data.length : 0)
      } catch (e) {
        console.error(e)
        videos.value = []
      } finally {
        loading.value = false
      }
    }

    // ── Upload ──
    const openUpload = () => {
      selectedFile.value = null
      uploading.value = false
      showDialog.value = true
    }

    const closeDialog = () => {
      if (uploading.value) return
      showDialog.value = false
      selectedFile.value = null
    }

    const clearFile = () => {
      selectedFile.value = null
    }

    const onFileSelect = (e) => {
      const file = e.target.files?.[0]
      if (file) selectedFile.value = file
    }

    const onDrop = (e) => {
      dragging.value = false
      const file = e.dataTransfer?.files?.[0]
      if (file) selectedFile.value = file
    }

    const startUpload = async () => {
      if (!selectedFile.value) return
      uploading.value = true
      try {
        await videoApi.upload(selectedFile.value, uploadLang.value)
        closeDialog()
        loadVideos()
      } catch (e) {
        toast.error('上传失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        uploading.value = false
      }
    }

    // ── Actions ──
    const splitVideo = async (v) => {
      if (!confirm(`确定分割视频「${v.filename}」为素材？`)) return
      try {
        const res = await videoApi.split(v.id, 'zh')
        toast.success(`分割完成，生成 ${res.data.material_count} 个素材`)
        loadVideos()
      } catch (e) {
        toast.error('分割失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const copyContent = async (v) => {
      const text = v.content || ''
      if (!text) {
        toast.warning('该视频暂无文案')
        return
      }
      try {
        await navigator.clipboard.writeText(text)
        toast.success('文案已复制到剪贴板')
      } catch {
        const ta = document.createElement('textarea')
        ta.value = text
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
        toast.success('文案已复制到剪贴板')
      }
    }

    const deleteVideo = async (v) => {
      if (!confirm(`确定删除视频「${v.filename}」？`)) return
      try {
        await videoApi.remove(v.id)
        loadVideos()
      } catch (e) {
        toast.error('删除失败')
      }
    }

    const hoverPlay = (e) => {
      const v = e.target
      if (v.readyState >= 2) v.play()
    }

    const hoverPause = (e) => {
      const v = e.target
      v.pause()
      v.currentTime = 0
    }

    const onPageChange = (p) => {
      page.value = p
      loadVideos()
    }

    const formatDuration = (s) => {
      if (!s) return '-'
      const m = Math.floor(s / 60)
      const sec = Math.floor(s % 60)
      return `${m}:${String(sec).padStart(2, '0')}`
    }

    const formatTime = (t) => t ? new Date(t).toLocaleString() : '-'
    const truncate = (s, n) => s && s.length > n ? s.slice(0, n) + '...' : (s || '')

    const formatSize = (bytes) => {
      if (!bytes) return ''
      if (bytes < 1024) return bytes + 'B'
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
      return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
    }

    onMounted(loadVideos)

    return {
      videos, loading, searchQuery, loadVideos,
      page, pageSize, total, onPageChange,
      showDialog, selectedFile, dragging, uploading, uploadLang, fileInput,
      openUpload, closeDialog, clearFile, onFileSelect, onDrop, startUpload,
      showPreview, previewVideo, previewSrc, previewVideoAction, closePreview,
      splitVideo, copyContent, deleteVideo,
      hoverPlay, hoverPause,
      formatDuration, formatTime, truncate, formatSize,
    }
  },
}
</script>

<style scoped>
/* VideoManager only needs a few specific overrides */
.preview-body { background: #000; border-radius: 10px; overflow: hidden; }
.video-player { width: 100%; max-height: 70vh; display: block; }

.video-cell { width: 100px; padding: 4px 8px !important; }
.inline-player {
  width: 90px;
  height: 56px;
  border-radius: 6px;
  background: #000;
  object-fit: cover;
  display: block;
  cursor: pointer;
  transition: transform 0.15s;
}
.inline-player:hover { transform: scale(1.08); }
</style>
