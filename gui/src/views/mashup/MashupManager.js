import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { generatedApi, folderApi, exportApi } from '../../api/index.js'
import { useToast } from '../../composables/useToast.js'
import { useFolders } from '../../composables/useFolders.js'
import { usePlaybackGuard } from '../../composables/usePlaybackGuard.js'
import Pagination from '../../components/Pagination.vue'

export default {
  name: 'MashupManager',
  components: { Pagination },
  setup() {
    const router = useRouter()
    const toast = useToast()
    const { folders, loadFolders } = useFolders()
    const { play: playOne, pause: pauseOne } = usePlaybackGuard()
    const folderMap = computed(() => {
      const m = {}
      for (const f of folders.value) m[f.id] = f.name
      return m
    })
    const list = ref([])
    const loading = ref(true)
    const searchQuery = ref('')
    const statusFilter = ref('')
    const page = ref(1)
    const pageSize = 20
    const total = ref(0)
    const viewMode = ref('card')

    // Selection
    const selectedIds = ref(new Set())
    const moveBatchMode = ref(false)
    const isAllSelected = computed(() => list.value.length > 0 && list.value.every(g => selectedIds.value.has(g.id)))
    const toggleSelect = (id) => {
      const s = new Set(selectedIds.value)
      if (s.has(id)) s.delete(id); else s.add(id)
      selectedIds.value = s
    }
    const toggleSelectAll = () => {
      if (isAllSelected.value) {
        selectedIds.value = new Set()
      } else {
        selectedIds.value = new Set(list.value.map(g => g.id))
      }
    }
    const clearSelection = () => { selectedIds.value = new Set() }

    // Move to folder dialog
    const showMoveDialog = ref(false)

    const loadList = async () => {
      loading.value = true
      try {
        const params = {
          q: searchQuery.value || undefined,
          status: statusFilter.value || undefined,
          skip: (page.value - 1) * pageSize,
          limit: pageSize,
        }
        const res = await generatedApi.list(params)
        const data = res.data
        list.value = data.items || data || []
        total.value = data.total ?? (Array.isArray(data) ? data.length : 0)
      } catch (e) {
        console.error(e)
        list.value = []
      } finally {
        loading.value = false
      }
    }

    // ── Navigation ──
    const openManual = () => {
      router.push('/mashups/editor')
    }

    const openEdit = (g) => {
      router.push(`/mashups/editor/${g.id}`)
    }

    // ── Actions ──
    const genVideo = async (g) => {
      try {
        await generatedApi.generate(g.id)
        toast.success('生成完成')
        loadList()
      } catch (e) {
        toast.error('生成失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const dubVideo = async (g) => {
      const voice = prompt('输入 TTS 音色（留空使用默认）:')
      if (voice === null) return
      try {
        await generatedApi.dub(g.id, voice || undefined)
        toast.success('配音完成')
        loadList()
      } catch (e) {
        toast.error('配音失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const deleteGen = async (g) => {
      if (!await toast.confirm(`确定删除混剪「${g.title || '#' + g.id}」？`)) return
      try {
        await generatedApi.remove(g.id)
        loadList()
        toast.success('已删除')
      } catch (e) {
        toast.error('删除失败')
      }
    }

    // ── Batch operations ──
    const batchDeleteGens = async () => {
      const ids = [...selectedIds.value]
      if (ids.length === 0) return
      if (!await toast.confirm(`确定删除选中的 ${ids.length} 个混剪视频？`)) return
      try {
        for (const id of ids) {
          await generatedApi.remove(id)
        }
        clearSelection()
        loadList()
        toast.success('批量删除成功')
      } catch (e) {
        toast.error('批量删除失败')
      }
    }

    const exporting = ref(false)
    const doExport = async (ids) => {
      if (ids.length === 0) return
      let destDir = ''
      if (window.electronAPI && window.electronAPI.selectDirectory) {
        destDir = await window.electronAPI.selectDirectory()
        if (!destDir) return
      } else {
        toast.warning('当前环境不支持选择目录')
        return
      }
      exporting.value = true
      try {
        const res = await exportApi.exportFiles({ generated_ids: ids, dest_dir: destDir })
        const d = res.data
        if (d.errors && d.errors.length > 0) {
          toast.warning(`导出完成：成功 ${d.copied} 个，失败 ${d.errors.length} 个`)
        } else {
          toast.success(`已导出 ${d.copied} 个混剪视频到 ${destDir}`)
        }
      } catch (e) {
        toast.error('导出失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        exporting.value = false
      }
    }
    const exportSelected = () => doExport([...selectedIds.value])
    const exportItem = (id) => doExport([id])

    const showBatchMoveFolder = () => {
      if (selectedIds.value.size === 0) return
      moveBatchMode.value = true
      showMoveDialog.value = true
    }

    const closeMoveDialog = () => {
      showMoveDialog.value = false
    }

    const moveToFolder = async (folderId) => {
      const ids = [...selectedIds.value]
      if (ids.length === 0) return
      try {
        for (const id of ids) {
          if (folderId === null) {
            await folderApi.removeGeneratedFromFolder(0, id)
          } else {
            await folderApi.moveGenerated(folderId, id)
          }
        }
        closeMoveDialog()
        clearSelection()
        loadList()
        loadFolders('generated')
        toast.success(folderId === null ? '已移出文件夹' : '已移动到文件夹')
      } catch (e) {
        toast.error('移动失败')
      }
    }

    // ── Auto mashup ──
    const goAuto = () => {
      router.push('/mashups/auto')
    }

    const onPageChange = (p) => {
      page.value = p
      loadList()
    }

    // ── Helpers ──
    const statusText = (s) => ({ created: '已创建', processing: '处理中', completed: '已完成', failed: '失败' }[s] || s)

    const formatTime = (t) => t ? new Date(t).toLocaleString() : '-'
    const truncate = (s, n) => s && s.length > n ? s.slice(0, n) + '...' : (s || '')

    const formatDuration = (s) => {
      if (!s) return '-'
      const m = Math.floor(s / 60)
      const sec = Math.floor(s % 60)
      return `${m}:${String(sec).padStart(2, '0')}`
    }

    // Lazy video loading
    const activeVideos = ref(new Set())
    const videoEls = {}
    const activateVideo = (id) => {
      const s = new Set(activeVideos.value)
      s.add(id)
      activeVideos.value = s
      setTimeout(() => {
        const el = videoEls[id]
        if (el) playOne(el)
      }, 100)
    }
    const setVideoRef = (id, el) => { if (el) videoEls[id] = el }
    const onVideoLoaded = (e) => { playOne(e.target) }

    const hoverPlay = (e) => {
      const v = e.target
      if (v.readyState >= 2) playOne(v)
    }

    const hoverPause = (e) => {
      const v = e.target
      pauseOne(v)
      v.currentTime = 0
    }

    const copyScript = async (g) => {
      const text = g.script || ''
      if (!text) { toast.warning('该视频无文案内容'); return }
      try {
        await navigator.clipboard.writeText(text)
        toast.success('文案已复制')
      } catch (e) {
        toast.error('复制失败')
      }
    }

    onMounted(() => {
      loadList()
      loadFolders('generated')
    })

    return {
      list, loading, searchQuery, statusFilter, loadList,
      page, pageSize, total, onPageChange,
      viewMode,
      folders, folderMap,
      selectedIds, isAllSelected, toggleSelect, toggleSelectAll, clearSelection,
      showMoveDialog, moveBatchMode,
      showBatchMoveFolder, closeMoveDialog, moveToFolder,
      batchDeleteGens,
      exporting, exportSelected, exportItem,
      openManual, openEdit,
      genVideo, dubVideo, deleteGen,
      copyScript,
      goAuto,
      statusText, formatTime, truncate, formatDuration,
      activeVideos, activateVideo, setVideoRef, onVideoLoaded,
      hoverPlay, hoverPause,
    }
  },
}
