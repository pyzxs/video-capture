import { ref, computed, onMounted, watch } from 'vue'
import { videoApi, materialApi, folderApi, downloadApi, agentApi, exportApi } from '../../api/index.js'
import { useToast } from '../../composables/useToast.js'
import { useFolders } from '../../composables/useFolders.js'
import Pagination from '../../components/Pagination.vue'

export default {
  name: 'VideoManager',
  components: { Pagination },
  setup() {
    const toast = useToast()
    const { folders, selectedFolderId, loadFolders } = useFolders()
    const folderMap = computed(() => {
      const m = {}
      for (const f of folders.value) m[f.id] = f.name
      return m
    })
    const videos = ref([])
    const loading = ref(true)
    const searchQuery = ref('')
    const page = ref(1)
    const pageSize = 20
    const total = ref(0)

    // Selection
    const selectedIds = ref(new Set())
    const moveBatchMode = ref(false)
    const isAllSelected = computed(() => videos.value.length > 0 && videos.value.every(v => selectedIds.value.has(v.id)))
    const toggleSelect = (id) => {
      const s = new Set(selectedIds.value)
      if (s.has(id)) s.delete(id); else s.add(id)
      selectedIds.value = s
    }
    const toggleSelectAll = () => {
      if (isAllSelected.value) {
        selectedIds.value = new Set()
      } else {
        selectedIds.value = new Set(videos.value.map(v => v.id))
      }
    }
    const clearSelection = () => { selectedIds.value = new Set() }
    const viewMode = ref('card')
    const truncateFilename = (name) => name && name.length > 28 ? name.substring(0, 26) + '...' : name

    const batchDeleteVideos = async () => {
      const ids = [...selectedIds.value]
      if (ids.length === 0) return
      if (!confirm(`确定删除选中的 ${ids.length} 个视频？`)) return
      try {
        for (const id of ids) {
          await videoApi.remove(id)
        }
        clearSelection()
        loadVideos()
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
        const res = await exportApi.exportFiles({ video_ids: ids, dest_dir: destDir })
        const d = res.data
        if (d.errors && d.errors.length > 0) {
          toast.warning(`导出完成：成功 ${d.copied} 个，失败 ${d.errors.length} 个`)
        } else {
          toast.success(`已导出 ${d.copied} 个视频到 ${destDir}`)
        }
      } catch (e) {
        toast.error('导出失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        exporting.value = false
      }
    }
    const exportSelected = () => doExport([...selectedIds.value])
    const exportItem = (id) => doExport([id])

    // Move to folder dialog
    const showMoveDialog = ref(false)
    const moveTarget = ref(null)
    const moveTargetType = ref('')

    // Split dialog
    const showSplit = ref(false)
    const splitStarted = ref(false)
    const splitDoing = ref(false)
    const splitDoingText = ref('')
    const splitState = ref('') // '' | 'done'
    const splitSteps = ref([
      { label: '分析视频软字幕', desc: '检测并提取视频内嵌的 SRT/ASS 字幕流', status: 'pending' },
      { label: '提取视频音频', desc: '通过 ffmpeg 提取 16kHz 单声道 WAV 音频', status: 'pending' },
      { label: '提取音频到文字', desc: '使用 Whisper 本地模型进行语音识别', status: 'pending' },
      { label: '分析语义到自然段落', desc: '通过 LLM 分析语义完整性，合并为自然段落', status: 'pending' },
      { label: '按自然段落分割', desc: '根据段落时间戳切割视频画面片段', status: 'pending' },
      { label: '去除视频音频', desc: '移除分割后片段的原始音频轨道', status: 'pending' },
      { label: '生成素材列表', desc: '创建素材数据库记录并建立向量索引', status: 'pending' },
    ])
    const splitMaterials = ref([])
    const splitVideoRef = ref(null)
    const splitError = ref('')
    let splitSubtitles = null       // Step 1: soft subtitles
    let splitAudioPath = null       // Step 2: extracted audio path
    let splitParagraphs = null      // Steps 3+4: merged paragraphs

    // Manual split
    const splitMode = ref('auto')
    const splitExtractText = ref(true)
    const splitRemoveAudio = ref(true)
    const manualVideoEl = ref(null)
    const splitCurrentTime = ref(0)
    const videoDuration = ref(0)
    const splitPoints = ref([])
    const manualTimelineEl = ref(null)
    const splitSegments = computed(() => {
      const pts = [0, ...splitPoints.value.sort((a, b) => a - b), videoDuration.value]
      const segs = []
      for (let i = 0; i < pts.length - 1; i++) {
        if (pts[i + 1] - pts[i] > 0.3) {
          segs.push({ start: pts[i], end: pts[i + 1], text: '', title: '' })
        }
      }
      return segs
    })

    const formatSplitTime = (s) => {
      if (!s || s <= 0) return '0:00'
      const m = Math.floor(s / 60)
      const sec = Math.floor(s % 60)
      return `${m}:${sec.toString().padStart(2, '0')}`
    }

    const onManualLoaded = () => {
      const el = manualVideoEl.value
      if (el) videoDuration.value = el.duration || 0
    }

    const onManualTimeUpdate = () => {
      const el = manualVideoEl.value
      if (el) splitCurrentTime.value = el.currentTime
    }

    const onTimelineClick = (e) => {
      const el = manualTimelineEl.value
      if (!el || !videoDuration.value) return
      const rect = el.getBoundingClientRect()
      const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
      const time = ratio * videoDuration.value
      splitCurrentTime.value = time
      if (manualVideoEl.value) manualVideoEl.value.currentTime = time
    }

    const addSplitPoint = () => {
      const t = splitCurrentTime.value
      if (t <= 0 || t >= videoDuration.value) return
      if (splitPoints.value.some(p => Math.abs(p - t) < 0.5)) return
      splitPoints.value.push(t)
      splitPoints.value.sort((a, b) => a - b)
    }

    const removeSplitPoint = (idx) => {
      splitPoints.value.splice(idx, 1)
    }

    const removeSegmentSplit = (idx) => {
      const segs = splitSegments.value
      if (idx >= segs.length) return
      const seg = segs[idx]
      // Remove the split point at seg.end (or seg.start)
      const pt = seg.end < videoDuration.value ? seg.end : seg.start
      const pi = splitPoints.value.findIndex(p => Math.abs(p - pt) < 0.1)
      if (pi >= 0) splitPoints.value.splice(pi, 1)
    }

    const clearSplitPoints = () => {
      splitPoints.value = []
      if (manualVideoEl.value) manualVideoEl.value.currentTime = 0
      splitCurrentTime.value = 0
    }

    const startManualCut = async () => {
      const v = splitVideoRef.value
      if (!v || splitSegments.value.length === 0) return
      splitStarted.value = true
      splitDoing.value = true
      splitState.value = ''
      splitMaterials.value = []
      splitError.value = ''

      const paragraphs = splitSegments.value.map((seg, idx) => ({
        seq_index: idx,
        start: seg.start,
        end: seg.end,
        text: seg.text || '',
        title: seg.title || '',
      }))

      splitDoingText.value = `正在切割 ${paragraphs.length} 个视频片段...`
      try {
        const res = await videoApi.splitCut(v.id, {
          paragraphs,
          extract_text: splitExtractText.value,
          remove_audio: splitRemoveAudio.value,
        })
        const d = res.data.data || res.data
        const items = d.materials || []
        if (items.length === 0) {
          // fallback: use material IDs
          const materialIds = d.material_ids || []
          const fetched = await Promise.all(
            materialIds.map(id => materialApi.get(id).then(r => r.data).catch(() => null))
          )
          splitMaterials.value = fetched.filter(Boolean)
        } else {
          splitMaterials.value = items
        }
        splitState.value = 'done'
        loadVideos()
      } catch (e) {
        splitError.value = '分割失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message)
      } finally {
        splitDoing.value = false
      }
    }

    // Edit dialog
    const showEdit = ref(false)
    const showEditPreview = ref(false)
    const editForm = ref({ filename: '', content: '' })
    const editingVideo = ref(null)
    const saving = ref(false)
    const savingToNote = ref(false)
    const mdTextarea = ref(null)

    // AI rewrite chat
    const showChat = ref(false)
    const chatMessages = ref([])
    const chatInput = ref('')
    const chatLoading = ref(false)
    const chatMessagesRef = ref(null)
    const agents = ref([])
    const selectedAgentId = ref('')
    let chatIdCounter = 0

    // Dub (TTS)
    const dubbing = ref(false)

    // Upload dialog
    const showDialog = ref(false)
    const selectedFile = ref(null)
    const dragging = ref(false)
    const uploading = ref(false)
    const processing = ref(false)
    const uploadProgress = ref(0)
    const uploadLang = ref('zh')
    const uploadExtract = ref(true)
    const fileInput = ref(null)

    // Download dialog
    const showDownload = ref(false)
    const downloadChannel = ref('douyin')
    const downloadUrls = ref('')
    const downloadProxy = ref('')
    const downloadExtract = ref(true)
    const downloading = ref(false)
    const downloadResults = ref([])
    const channels = [
      { key: 'douyin', label: '抖音' },
      { key: 'bilibili', label: 'B站' },
      { key: 'kuaishou', label: '快手' },
    ]

    const loadVideos = async () => {
      loading.value = true
      try {
        const params = { q: searchQuery.value || undefined, folder_id: selectedFolderId.value !== null && selectedFolderId.value !== 0 ? selectedFolderId.value : undefined, skip: (page.value - 1) * pageSize, limit: pageSize }
        if (selectedFolderId.value === 0) params.folder_id = 0
        const res = await videoApi.list(params)
        const body = res.data?.data || res.data  // 解包 response_success
        videos.value = body.items || body || []
        total.value = body.total ?? (Array.isArray(body) ? body.length : 0)
      } catch (e) {
        console.error(e)
        videos.value = []
      } finally {
        loading.value = false
      }
    }

    // ── Move to folder ──
    const showMoveFolder = (item, type) => {
      moveBatchMode.value = false
      selectedIds.value = new Set([item.id])
      moveTargetType.value = type
      showMoveDialog.value = true
    }

    const showBatchMoveFolder = () => {
      if (selectedIds.value.size === 0) return
      moveBatchMode.value = true
      moveTargetType.value = 'video'
      showMoveDialog.value = true
    }

    const closeMoveDialog = () => {
      showMoveDialog.value = false
    }

    const moveToFolder = async (folderId) => {
      const ids = [...selectedIds.value]
      if (ids.length === 0) return
      const type = moveTargetType.value || 'video'
      try {
        for (const id of ids) {
          if (folderId === null) {
            if (type === 'video') await folderApi.removeVideoFromFolder(0, id)
            else if (type === 'material') await folderApi.removeMaterialFromFolder(0, id)
            else await folderApi.removeGeneratedFromFolder(0, id)
          } else {
            if (type === 'video') await folderApi.moveVideo(folderId, id)
            else if (type === 'material') await folderApi.moveMaterial(folderId, id)
            else await folderApi.moveGenerated(folderId, id)
          }
        }
        closeMoveDialog()
        clearSelection()
        loadVideos()
        loadFolders('video')
        toast.success(folderId === null ? '已移出文件夹' : '已移动到文件夹')
      } catch (e) {
        toast.error('移动失败')
      }
    }

    // ── Upload ──
    const openUpload = () => {
      selectedFile.value = null
      uploading.value = false
      uploadExtract.value = true
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
      uploadProgress.value = 0
      try {
        const res = await videoApi.upload(selectedFile.value, uploadLang.value, (pe) => {
          if (pe.total) uploadProgress.value = Math.round((pe.loaded / pe.total) * 100)
        }, selectedFolderId.value, uploadExtract.value)
        // 上传完成，等待 ASR 后台处理
        uploading.value = false
        processing.value = true
        const videoId = res.data.data.id
        await pollStatus(videoId)
        processing.value = false
        closeDialog()
        loadVideos()
        toast.success('上传完成')
      } catch (e) {
        toast.error('上传失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        uploading.value = false
        processing.value = false
      }
    }

    const pollStatus = async (id) => {
      const maxAttempts = 120
      for (let i = 0; i < maxAttempts; i++) {
        try {
          const res = await videoApi.status(id)
          const s = res.data.data?.status
          if (s === 'completed') return
          if (s === 'failed') throw new Error(res.data.data?.content || 'ASR 处理失败')
        } catch (e) {
          if (e.response?.status === 404) return
          throw e
        }
        await new Promise((r) => setTimeout(r, 2000))
      }
    }

    // ── Download ──
    const openDownload = () => {
      downloadChannel.value = 'douyin'
      downloadUrls.value = ''
      downloadProxy.value = ''
      downloadExtract.value = true
      downloading.value = false
      downloadResults.value = []
      showDownload.value = true
    }

    const closeDownload = () => {
      if (downloading.value) return
      showDownload.value = false
    }

    const startDownload = async () => {
      if (!downloadUrls.value.trim()) return
      downloading.value = true
      downloadResults.value = []
      try {
        const res = await downloadApi.fromUrl({
          channel: downloadChannel.value,
          urls: downloadUrls.value,
          proxy: downloadProxy.value,
          extract_text: downloadExtract.value,
          folder_id: selectedFolderId.value || undefined,
        })
        const data = res.data
        const raw = data?.data
        const items = Array.isArray(raw) ? raw : (raw ? [{ ...raw, status: 'completed' }] : [])
        downloadResults.value = items
        loadVideos()

        const completed = items.filter(r => r.status === 'completed').length
        const failed = items.filter(r => r.status === 'failed').length
        if (completed > 0 && failed === 0) {
          showDownload.value = false
          toast.success(data?.message || `全部下载成功，共 ${completed} 个`)
        } else if (failed > 0 && completed === 0) {
          toast.error(data?.message || `全部失败，共 ${failed} 个`)
        } else {
          toast.warning(`${completed} 个成功，${failed} 个失败`)
        }
      } catch (e) {
        const msg = e.response?.data?.message || e.response?.data?.detail || e.message
        downloadResults.value = [{ url: '', status: 'failed', error: msg }]
        toast.error(msg)
      } finally {
        downloading.value = false
      }
    }

    // ── Actions ──
    const setStep = (idx, status) => {
      splitSteps.value[idx].status = status
    }

    const openSplit = (v) => {
      splitVideoRef.value = v
      splitStarted.value = false
      splitDoing.value = false
      splitDoingText.value = ''
      splitState.value = ''
      splitMaterials.value = []
      splitError.value = ''
      splitParagraphs = null
      splitSubtitles = null
      splitAudioPath = null
      splitSteps.value.forEach(s => (s.status = 'pending'))
      splitMode.value = 'auto'
      splitCurrentTime.value = 0
      videoDuration.value = 0
      splitPoints.value = []
      showSplit.value = true
    }

    const startSplitAnalysis = async () => {
      const v = splitVideoRef.value
      if (!v) return
      splitStarted.value = true
      splitState.value = ''
      splitMaterials.value = []
      splitError.value = ''
      splitSubtitles = null
      splitAudioPath = null
      splitParagraphs = null
      splitSteps.value.forEach(s => (s.status = 'pending'))

      // ── Step 1: 分析视频软字幕 ──
      setStep(0, 'doing')
      splitDoing.value = true
      splitDoingText.value = '正在提取视频内嵌软字幕...'
      try {
        const res = await videoApi.smartSubtitles(v.id)
        const d = res.data.data || res.data
        splitSubtitles = d.subtitles || null
        setStep(0, 'done')
      } catch (e) {
        setStep(0, 'error')
        splitError.value = '提取软字幕失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message)
        splitDoing.value = false
        return
      }

      // ── Step 2: 提取视频音频 ──
      setStep(1, 'doing')
      splitDoingText.value = '正在从视频中提取音频轨道...'
      try {
        const res = await videoApi.smartExtractAudio(v.id)
        const d = res.data.data || res.data
        splitAudioPath = d.audio_path
        setStep(1, 'done')
      } catch (e) {
        setStep(1, 'error')
        splitError.value = '提取音频失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message)
        splitDoing.value = false
        return
      }

      // ── Steps 3+4: 语音识别 + 语义段落分析 ──
      setStep(2, 'doing')
      setStep(3, 'doing')
      splitDoingText.value = '正在进行语音识别并分析语义段落...'
      try {
        const res = await videoApi.smartAnalyze(v.id, {
          subtitles: splitSubtitles,
          audio_path: splitAudioPath,
          language: 'zh',
        })
        const d = res.data.data || res.data
        splitParagraphs = d.paragraphs || []
        setStep(2, 'done')
        setStep(3, 'done')
      } catch (e) {
        setStep(2, 'error')
        setStep(3, 'error')
        splitError.value = '语音识别或段落分析失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message)
        splitDoing.value = false
        return
      }

      if (!splitParagraphs || splitParagraphs.length === 0) {
        splitError.value = '未能识别出任何有效段落'
        splitDoing.value = false
        return
      }

      // ── Steps 5+6+7: 切割 + 去音频 + 生成素材 ──
      setStep(4, 'doing')
      setStep(5, 'doing')
      setStep(6, 'doing')
      splitDoingText.value = `正在切割 ${splitParagraphs.length} 个视频片段并生成素材...`
      let materialIds = []
      try {
        const res = await videoApi.splitCut(v.id, {
          paragraphs: splitParagraphs,
          extract_text: splitExtractText.value,
          remove_audio: splitRemoveAudio.value,
        })
        const d = res.data.data || res.data
        materialIds = d.material_ids || []
        setStep(4, 'done')
        setStep(5, 'done')
        setStep(6, 'done')
        splitState.value = 'done'
      } catch (e) {
        setStep(4, 'error')
        setStep(5, 'error')
        setStep(6, 'error')
        splitError.value = '切割失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message)
        splitDoing.value = false
        return
      }

      // ── Fetch material details for display ──
      splitDoingText.value = '正在获取素材详情...'
      try {
        const items = await Promise.all(
          materialIds.map(id => materialApi.get(id).then(r => r.data).catch(() => null))
        )
        splitMaterials.value = items.filter(Boolean)
        loadVideos()
      } catch (e) {
        splitError.value = '获取素材详情失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message)
      } finally {
        splitDoing.value = false
      }
    }

    const closeSplit = () => {
      if (splitDoing.value) return
      showSplit.value = false
      splitStarted.value = false
      splitMaterials.value = []
      splitVideoRef.value = null
      splitError.value = ''
    }

    const deleteSplitMaterial = async (m) => {
      try {
        await materialApi.remove(m.id)
        splitMaterials.value = splitMaterials.value.filter(x => x.id !== m.id)
        toast.success('素材已删除')
        loadVideos()
      } catch (e) {
        toast.error('删除失败')
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

    // ── Edit ──
    const openEdit = (v) => {
      editingVideo.value = v
      editForm.value = { filename: v.filename || '', content: v.content || '' }
      showEditPreview.value = false
      showChat.value = false
      chatMessages.value = []
      chatInput.value = ''
      showEdit.value = true
    }

    const closeEdit = () => {
      showEdit.value = false
      editingVideo.value = null
      showChat.value = false
      chatMessages.value = []
      chatInput.value = ''
    }


    const saveEdit = async () => {
      saving.value = true
      try {
        await videoApi.update(editingVideo.value.id, editForm.value)
        closeEdit()
        loadVideos()
        toast.success('保存成功')
      } catch (e) {
        toast.error('保存失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        saving.value = false
      }
    }


    const saveToNote = async () => {
      if (savingToNote.value) return
      const v = editingVideo.value
      if (!v) return
      if (!v.content) {
        toast.warning('视频暂无文案，请先保存文案')
        return
      }
      if (!await toast.confirm('确定将文案保存到笔记？将经由笔记智能体排版后存入默认笔记文件夹。')) return
      savingToNote.value = true
      try {
        await videoApi.saveToNote(v.id)
        toast.success('已保存到笔记')
      } catch (e) {
        toast.error('保存失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        savingToNote.value = false
      }
    }

    const startDub = async () => {
      if (!editingVideo.value || !editForm.value.content) { toast.warning('请先输入文案'); return }
      dubbing.value = true
      try {
        const res = await videoApi.dub(editingVideo.value.id, { content: editForm.value.content })
        if (res.data?.output_filepath) editingVideo.value.filepath = res.data.output_filepath
        toast.success('配音完成')
      } catch (e) {
        toast.error('配音失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        dubbing.value = false
      }
    }

    // ── AI Rewrite Chat ──
    const lastAssistantMsg = () => {
      const msgs = chatMessages.value.filter(m => m.role === 'assistant')
      return msgs.length > 0 ? msgs[msgs.length - 1].content : null
    }

    const toggleChat = async () => {
      showChat.value = !showChat.value
      if (showChat.value) {
        if (agents.value.length === 0) {
          try {
            const res = await agentApi.list()
            agents.value = res.data || []
            if (agents.value.length > 0 && !selectedAgentId.value) {
              selectedAgentId.value = agents.value[0].id
            }
          } catch (e) {
            console.error('加载智能体失败', e)
          }
        }
        if (chatMessages.value.length === 0) {
          chatMessages.value.push({
            id: ++chatIdCounter,
            role: 'assistant',
            content: '选择一个智能体，然后告诉我你想如何修改这段文案，例如：润色、缩短、扩写、改变语气等。'
          })
        }
      }
      setTimeout(scrollChatToBottom, 100)
    }

    const scrollChatToBottom = () => {
      const el = chatMessagesRef.value
      if (el) el.scrollTop = el.scrollHeight
    }

    const sendChat = async () => {
      const text = chatInput.value.trim()
      if (!text || chatLoading.value || !editingVideo.value) return
      if (!selectedAgentId.value) {
        toast.warning('请先选择一个智能体')
        return
      }

      chatMessages.value.push({ id: ++chatIdCounter, role: 'user', content: text })
      chatInput.value = ''
      chatLoading.value = true
      setTimeout(scrollChatToBottom, 50)

      try {
        const msgs = chatMessages.value.map(m => ({ role: m.role, content: m.content }))
        const ctx = '当前视频文案：\n' + (editForm.value.content || '(空)')
        const res = await agentApi.chat(selectedAgentId.value, msgs, '你是一个视频文案改写助手。根据用户的需求改写视频文案，直接输出改写后的文案，不要添加额外解释。\n\n' + ctx)
        const reply = res.data?.content || ''
        chatMessages.value.push({ id: ++chatIdCounter, role: 'assistant', content: reply })
      } catch (e) {
        toast.error('AI 响应失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        chatLoading.value = false
        setTimeout(scrollChatToBottom, 50)
      }
    }

    const applyRewrite = (msgContent) => {
      const text = msgContent || lastAssistantMsg()
      if (text) {
        editForm.value.content = text
        toast.success('已应用 AI 改写结果')
      }
    }

    const onAgentChange = () => {
      chatMessages.value = []
      chatInput.value = ''
    }

    const clearChat = () => {
      chatMessages.value = []
      chatInput.value = ''
    }

    // ── Markdown editor helpers ──
    const mdInsert = (before, after) => {
      const ta = mdTextarea.value
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = editForm.value.content
      const selected = text.substring(start, end)
      editForm.value.content = text.substring(0, start) + before + selected + after + text.substring(end)
      const newCursor = start + before.length + selected.length + after.length
      setTimeout(() => {
        ta.focus()
        ta.setSelectionRange(newCursor, newCursor)
      }, 0)
    }

    const mdLink = () => {
      const ta = mdTextarea.value
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = editForm.value.content
      const selected = text.substring(start, end) || '链接文本'
      const replacement = `[${selected}](url)`
      editForm.value.content = text.substring(0, start) + replacement + text.substring(end)
      setTimeout(() => {
        ta.focus()
        ta.setSelectionRange(start + replacement.length - 1, start + replacement.length - 1)
      }, 0)
    }

    const renderMarkdown = (text) => {
      if (!text) return ''
      let html = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
      html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
      html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%">')
      html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
      html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
      html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
      html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')
      html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
      html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
      html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
      const parts = html.split(/\n\n+/)
      html = parts.map(p => {
        const t = p.trim()
        if (!t) return ''
        if (t.startsWith('<ul>') || t.startsWith('<pre>') || t.startsWith('<h')) return t
        return `<p>${t}</p>`
      }).join('\n')
      html = html.replace(/\n(?!<\/?(?:ul|pre|h))/g, '<br>')
      return html
    }

    // Lazy video loading — only load the <video> element after user clicks thumbnail
    const activeVideos = ref(new Set())
    const videoEls = {}
    const activateVideo = (id) => {
      const s = new Set(activeVideos.value)
      s.add(id)
      activeVideos.value = s
      setTimeout(() => {
        const el = videoEls[id]
        if (el) el.play()
      }, 100)
    }
    const setVideoRef = (id, el) => { if (el) videoEls[id] = el }
    const onVideoLoaded = (e) => { e.target.play() }

    const hoverPlay = (e) => {
      const v = e.target
      if (v.readyState >= 2) v.play()
    }

    const hoverPause = (e) => {
      const v = e.target
      v.pause()
      v.currentTime = 0
    }

    const deleteVideo = async (v) => {
      if (!await toast.confirm(`确定删除视频「${v.filename}」？`)) return
      try {
        await videoApi.remove(v.id)
        loadVideos()
      } catch (e) {
        toast.error('删除失败')
      }
    }

    const onPageChange = (p) => {
      page.value = p
      loadVideos()
    }

    const calcAspectRatio = (w, h) => {
      if (!w || !h) return '-'
      const gcd = (a, b) => b ? gcd(b, a % b) : a
      const d = gcd(w, h)
      return `${w / d}:${h / d}`
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

    watch(selectedFolderId, () => {
      page.value = 1
      loadVideos()
    })

    onMounted(() => { loadVideos() })

    return {
      videos, loading, searchQuery, loadVideos,
      page, pageSize, total, onPageChange,
      folders, selectedFolderId, folderMap,
      showMoveDialog, showMoveFolder, closeMoveDialog, moveToFolder, showBatchMoveFolder, batchDeleteVideos,
      showDialog, selectedFile, dragging, uploading, processing, uploadProgress, uploadLang, uploadExtract, fileInput,
      openUpload, closeDialog, clearFile, onFileSelect, onDrop, startUpload,
      showDownload, downloadChannel, downloadUrls, downloadProxy, downloadExtract, downloading, downloadResults, channels,
      openDownload, closeDownload, startDownload,
      showEdit, showEditPreview, editForm, editingVideo, saving, mdTextarea,
      openEdit, closeEdit, saveEdit, saveToNote, savingToNote, startDub, dubbing, mdInsert, mdLink, renderMarkdown,
      copyContent, deleteVideo,
      activeVideos, activateVideo, setVideoRef, onVideoLoaded,
      hoverPlay, hoverPause,
      showSplit, splitStarted, splitState, splitSteps, splitDoing, splitDoingText, splitError,
      splitMaterials, splitVideoRef, openSplit, startSplitAnalysis, closeSplit, deleteSplitMaterial,
      selectedIds, isAllSelected, viewMode, toggleSelect, toggleSelectAll, clearSelection, truncateFilename, batchDeleteVideos,
      exporting, exportSelected, exportItem,
      splitMode, splitExtractText, splitRemoveAudio, manualVideoEl, splitCurrentTime, videoDuration, splitPoints, splitSegments,
      manualTimelineEl, formatSplitTime, onManualLoaded, onManualTimeUpdate, onTimelineClick,
      addSplitPoint, removeSplitPoint, removeSegmentSplit, clearSplitPoints, startManualCut,
      calcAspectRatio, formatDuration, formatTime, truncate, formatSize,
      // AI chat
      showChat, chatMessages, chatInput, chatLoading, chatMessagesRef,
      agents, selectedAgentId,
      toggleChat, sendChat, applyRewrite, clearChat, onAgentChange, lastAssistantMsg,
    }
  },
}
