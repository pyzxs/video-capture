import { ref, computed, onMounted, watch } from 'vue'
import { materialApi, folderApi, exportApi } from '../../api/index.js'
import { useToast } from '../../composables/useToast.js'
import { useFolders } from '../../composables/useFolders.js'
import Pagination from '../../components/Pagination.vue'

export default {
  name: 'MaterialManager',
  components: { Pagination },
  setup() {
    const toast = useToast()
    const { folders, selectedFolderId, loadFolders } = useFolders()
    const folderMap = computed(() => {
      const m = {}
      for (const f of folders.value) m[f.id] = f.name
      return m
    })
    const materials = ref([])
    const loading = ref(true)
    const searchQuery = ref('')
    const typeFilter = ref('')
    const showDialog = ref(false)
    const editing = ref(null)
    const form = ref(emptyForm())
    const page = ref(1)
    const pageSize = 20
    const total = ref(0)
    const showMoveDialog = ref(false)
    const moveTarget = ref(null)
    const moveTargetType = ref('')
    // Selection
    const selectedIds = ref(new Set())
    const moveBatchMode = ref(false)
    const isAllSelected = computed(() => materials.value.length > 0 && materials.value.every(m => selectedIds.value.has(m.id)))
    const toggleSelect = (id) => {
      const s = new Set(selectedIds.value)
      if (s.has(id)) s.delete(id); else s.add(id)
      selectedIds.value = s
    }
    const toggleSelectAll = () => {
      if (isAllSelected.value) selectedIds.value = new Set()
      else selectedIds.value = new Set(materials.value.map(m => m.id))
    }
    const clearSelection = () => { selectedIds.value = new Set() }
    const viewMode = ref('card')
    const truncateFilename = (name) => name && name.length > 28 ? name.substring(0, 26) + '...' : name
    const selectedFile = ref(null)
    const dragging = ref(false)
    const saving = ref(false)
    const fileInput = ref(null)
    const mdTextarea = ref(null)
    const showPreview = ref(false)
    const showEditPreview = ref(false)

    // ── Audio / TTS state ──
    const audioMode = ref('upload')
    const ttsText = ref('')
    const ttsVoice = ref('')
    const ttsBusy = ref(false)
    const showTtsPreview = ref(false)
    const ttsMdTextarea = ref(null)
    // TTS AI Chat
    const showTtsChat = ref(false)
    const ttsChatMessages = ref([])
    const ttsChatInput = ref('')
    const ttsChatLoading = ref(false)
    const ttsChatMessagesRef = ref(null)
    const ttsAgents = ref([])
    const ttsSelectedAgentId = ref('')
    let ttsChatIdCounter = 0

    // ── Text create state ──
    const showTextPreview = ref(false)
    const textMdTextarea = ref(null)

    function emptyForm() {
      return { type: 'video', content: '', filename: '', filepath: '' }
    }

    const loadMaterials = async () => {
      loading.value = true
      try {
        const params = { q: searchQuery.value || undefined, type: typeFilter.value || undefined, status: 1, folder_id: selectedFolderId.value !== null && selectedFolderId.value !== 0 ? selectedFolderId.value : undefined, skip: (page.value - 1) * pageSize, limit: pageSize }
        if (selectedFolderId.value === 0) params.folder_id = 0
        const res = await materialApi.list(params)
        const data = res.data
        materials.value = data.items || data || []
        total.value = data.total ?? (Array.isArray(data) ? data.length : 0)
      } catch (e) {
        console.error(e)
        materials.value = []
      } finally {
        loading.value = false
      }
    }

    const openCreate = () => {
      editing.value = null
      form.value = emptyForm()
      selectedFile.value = null
      showPreview.value = false
      showEditPreview.value = false
      audioMode.value = 'upload'
      ttsText.value = ''
      ttsVoice.value = ''
      showTtsPreview.value = false
      showTtsChat.value = false
      ttsChatMessages.value = []
      ttsChatInput.value = ''
      showTextPreview.value = false
      showDialog.value = true
    }

    const openEdit = (m) => {
      editing.value = m
      form.value = { ...m }
      selectedFile.value = null
      showPreview.value = false
      showEditPreview.value = false
      showDialog.value = true
    }

    const closeDialog = () => {
      showDialog.value = false
      editing.value = null
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

    const clearFile = () => {
      selectedFile.value = null
    }

    // ── TTS Generate ──
    const ttsGenerate = async () => {
      if (!ttsText.value.trim()) { toast.warning('请输入需要合成的文本'); return }
      ttsBusy.value = true
      try {
        const text = ttsText.value
        await materialApi.tts({ text, voice: ttsVoice.value || undefined })
        toast.success('语音合成成功')
        closeDialog()
        loadMaterials()
      } catch (e) {
        toast.error('合成失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally { ttsBusy.value = false }
    }

    // ── TTS Markdown helpers ──
    const ttsMdInsert = (before, after) => {
      const ta = ttsMdTextarea.value
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = ttsText.value
      const selected = text.substring(start, end)
      ttsText.value = text.substring(0, start) + before + selected + after + text.substring(end)
      const newCursor = start + before.length + selected.length + after.length
      setTimeout(() => { ta.focus(); ta.setSelectionRange(newCursor, newCursor) }, 0)
    }
    const ttsMdLink = () => {
      const ta = ttsMdTextarea.value
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = ttsText.value
      const selected = text.substring(start, end) || '链接文本'
      const rep = '[' + selected + '](url)'
      ttsText.value = text.substring(0, start) + rep + text.substring(end)
      setTimeout(() => { ta.focus(); ta.setSelectionRange(start + rep.length - 1, start + rep.length - 1) }, 0)
    }

    // ── TTS AI Chat ──
    const toggleTtsChat = async () => {
      showTtsChat.value = !showTtsChat.value
      if (showTtsChat.value) {
        if (ttsAgents.value.length === 0) {
          try {
            const { agentApi } = await import('../../api/index.js')
            const res = await agentApi.list()
            ttsAgents.value = res.data || []
            if (ttsAgents.value.length > 0 && !ttsSelectedAgentId.value) {
              ttsSelectedAgentId.value = ttsAgents.value[0].id
            }
          } catch (e) { console.error('加载智能体失败', e) }
        }
        if (ttsChatMessages.value.length === 0) {
          ttsChatMessages.value.push({
            id: ++ttsChatIdCounter,
            role: 'assistant',
            content: '选择一个智能体，然后告诉我你想要什么样的文案，例如：写一段关于春天公园的文案、润色当前文案等。'
          })
        }
      }
      setTimeout(scrollTtsChatToBottom, 100)
    }
    const scrollTtsChatToBottom = () => {
      const el = ttsChatMessagesRef.value
      if (el) el.scrollTop = el.scrollHeight
    }
    const sendTtsChat = async () => {
      const text = ttsChatInput.value.trim()
      if (!text || ttsChatLoading.value) return
      if (!ttsSelectedAgentId.value) { toast.warning('请先选择一个智能体'); return }
      ttsChatMessages.value.push({ id: ++ttsChatIdCounter, role: 'user', content: text })
      ttsChatInput.value = ''
      ttsChatLoading.value = true
      setTimeout(scrollTtsChatToBottom, 50)
      try {
        const { agentApi } = await import('../../api/index.js')
        const msgs = ttsChatMessages.value.map(m => ({ role: m.role, content: m.content }))
        const ctx = '当前合成文案：\n' + (ttsText.value || '(空)')
        const res = await agentApi.chat(ttsSelectedAgentId.value, msgs, '你是一个文案写作助手。根据用户的需求创作或改写文案，直接输出文案内容不要添加额外解释。\n\n' + ctx)
        const reply = res.data?.content || ''
        ttsChatMessages.value.push({ id: ++ttsChatIdCounter, role: 'assistant', content: reply })
      } catch (e) {
        toast.error('AI 响应失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        ttsChatLoading.value = false
        setTimeout(scrollTtsChatToBottom, 50)
      }
    }
    const applyTtsRewrite = (msgContent) => {
      if (msgContent) {
        ttsText.value = msgContent
        toast.success('已应用 AI 生成的文案')
      }
    }
    const onTtsAgentChange = () => {
      ttsChatMessages.value = []
      ttsChatInput.value = ''
    }
    const clearTtsChat = () => {
      ttsChatMessages.value = []
      ttsChatInput.value = ''
    }
const mdInsertText = (before, after) => {
      const ta = textMdTextarea.value
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = form.value.content
      const selected = text.substring(start, end)
      form.value.content = text.substring(0, start) + before + selected + after + text.substring(end)
      setTimeout(() => {
        ta.focus()
        ta.setSelectionRange(start + before.length + selected.length + after.length, start + before.length + selected.length + after.length)
      }, 0)
    }
    const mdLinkText = () => {
      const ta = textMdTextarea.value
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = form.value.content
      const selected = text.substring(start, end) || '链接文本'
      const replacement = `[${selected}](url)`
      form.value.content = text.substring(0, start) + replacement + text.substring(end)
      setTimeout(() => {
        ta.focus()
        ta.setSelectionRange(start + replacement.length - 1, start + replacement.length - 1)
      }, 0)
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
      moveTargetType.value = 'material'
      showMoveDialog.value = true
    }
    const closeMoveDialog = () => { showMoveDialog.value = false; moveTarget.value = null; moveBatchMode.value = false }
    const moveToFolder = async (folderId) => {
      const ids = [...selectedIds.value]
      if (ids.length === 0) return
      try {
        for (const id of ids) {
          if (folderId === null) {
            await folderApi.removeMaterialFromFolder(0, id)
          } else {
            await folderApi.moveMaterial(folderId, id)
          }
        }
        closeMoveDialog()
        clearSelection()
        loadMaterials()
        loadFolders('material')
        toast.success(folderId === null ? '已移出文件夹' : '已移动到文件夹')
      } catch (e) { toast.error('移动失败') }
    }

    // ── Markdown editor helpers ──
    const mdInsert = (before, after) => {
      const ta = mdTextarea.value
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = form.value.content
      const selected = text.substring(start, end)
      form.value.content = text.substring(0, start) + before + selected + after + text.substring(end)
      // restore cursor position
      const newCursor = start + before.length + selected.length + after.length
      // Vue will update the DOM async, so we need to wait a tick
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
      const text = form.value.content
      const selected = text.substring(start, end) || '链接文本'
      const replacement = `[${selected}](url)`
      form.value.content = text.substring(0, start) + replacement + text.substring(end)
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
      // code block
      html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
      // inline code
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
      // images
      html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%">')
      // links
      html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      // bold
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      // italic
      html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
      // headings
      html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
      html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
      html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')
      // unordered list
      html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
      html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
      // ordered list
      html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
      // paragraphs (double newlines)
      const parts = html.split(/\n\n+/)
      html = parts.map(p => {
        const t = p.trim()
        if (!t) return ''
        if (t.startsWith('<ul>') || t.startsWith('<pre>') || t.startsWith('<h')) return t
        return `<p>${t}</p>`
      }).join('\n')
      // single line breaks within paragraphs
      html = html.replace(/<\/p>\n<p>/g, '</p>\n<p>')
      html = html.replace(/\n(?!<\/?(?:ul|pre|h))/g, '<br>')
      return html
    }

    // ── Save ──
    const saveMaterial = async () => {
      saving.value = true
      try {
        if (editing.value) {
          await materialApi.update(editing.value.id, form.value)
        } else {
          await materialApi.create({ ...form.value, folder_id: selectedFolderId.value || undefined }, selectedFile.value)
        }
        closeDialog()
        loadMaterials()
        toast.success('保存成功')
      } catch (e) {
        toast.error('保存失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        saving.value = false
      }
    }

    const onPageChange = (p) => {
      page.value = p
      loadMaterials()
    }

    const deleteMaterial = async (m) => {
      if (!await toast.confirm(`确定删除素材 #${m.id}？将从数据库和向量库同步删除。`)) return
      try {
        await materialApi.remove(m.id)
        loadMaterials()
      } catch (e) {
        toast.error('删除失败')
      }
    }

    const batchDelete = async () => {
      const ids = [...selectedIds.value]
      if (ids.length === 0) return
      if (!confirm(`确定删除选中的 ${ids.length} 项？`)) return
      try {
        for (const id of ids) {
          await materialApi.remove(id)
        }
        clearSelection()
        loadMaterials()
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
        const res = await exportApi.exportFiles({ material_ids: ids, dest_dir: destDir })
        const d = res.data
        if (d.errors && d.errors.length > 0) {
          toast.warning(`导出完成：成功 ${d.copied} 个，失败 ${d.errors.length} 个`)
        } else {
          toast.success(`已导出 ${d.copied} 个素材到 ${destDir}`)
        }
      } catch (e) {
        toast.error('导出失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        exporting.value = false
      }
    }
    const exportSelected = () => doExport([...selectedIds.value])
    const exportItem = (id) => doExport([id])

    // Lazy video loading
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

    const truncate = (s, n) => s && s.length > n ? s.slice(0, n) + '...' : s

    const formatSize = (bytes) => {
      if (!bytes) return ''
      if (bytes < 1024) return bytes + 'B'
      if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
      return (bytes / (1024 * 1024)).toFixed(1) + 'MB'
    }

    watch(selectedFolderId, () => {
      page.value = 1
      loadMaterials()
    })

    onMounted(() => { loadMaterials() })

    return {
      materials, loading, searchQuery, typeFilter, loadMaterials,
      page, pageSize, total, onPageChange,
      folders, selectedFolderId, folderMap,
      showMoveDialog, showMoveFolder, closeMoveDialog, moveToFolder,
      selectedIds, isAllSelected, viewMode, toggleSelect, toggleSelectAll, clearSelection, truncateFilename,
      showBatchMoveFolder, moveBatchMode, batchDelete,
      exporting, exportSelected, exportItem,
      openCreate, openEdit, closeDialog, saveMaterial, deleteMaterial,
      showDialog, editing, form, selectedFile, dragging, saving, fileInput,
      onFileSelect, onDrop, clearFile, formatSize, truncate,
      activeVideos, activateVideo, setVideoRef, onVideoLoaded,
      hoverPlay, hoverPause, mdTextarea, showPreview, showEditPreview,
      mdInsert, mdLink, renderMarkdown,
      audioMode, ttsText, ttsVoice, ttsBusy, ttsGenerate,
      showTtsPreview, ttsMdTextarea, ttsMdInsert, ttsMdLink,
      showTtsChat, ttsChatMessages, ttsChatInput, ttsChatLoading, ttsChatMessagesRef,
      ttsAgents, ttsSelectedAgentId,
      toggleTtsChat, sendTtsChat, applyTtsRewrite, onTtsAgentChange, clearTtsChat,
      showTextPreview, textMdTextarea, mdInsertText, mdLinkText,
    }
  },
}
