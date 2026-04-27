import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { generatedApi, folderApi, agentApi } from '../../api/index.js'
import { useToast } from '../../composables/useToast.js'
import { useFolders } from '../../composables/useFolders.js'
import Pagination from '../../components/Pagination.vue'

export default {
  name: 'MashupManager',
  components: { Pagination },
  setup() {
    const router = useRouter()
    const toast = useToast()
    const { folders, loadFolders } = useFolders()
    const folderMap = computed(() => {
      const m = {}
      for (const f of folders.value) m[f.id] = f.name
      return m
    })
    const list = ref([])
    const loading = ref(true)
    const searchQuery = ref('')
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

    // AI chat (auto dialog)
    const showChat = ref(false)
    const chatMessages = ref([])
    const chatInput = ref('')
    const chatLoading = ref(false)
    const chatMessagesRef = ref(null)
    const agents = ref([])
    const selectedAgentId = ref('')
    let chatIdCounter = 0

    // Auto mashup
    const showAutoDialog = ref(false)
    const autoProcessing = ref(false)
    const searching = ref(false)
    const searchResults = ref(null)
    const autoForm = ref({ title: '', description: '', ratioIdx: '', voice: '', batchCount: 1 })
    const ratioOptions = [
      { width: 1920, height: 1080 },
      { width: 1280, height: 720 },
      { width: 1080, height: 1920 },
      { width: 720, height: 1280 },
      { width: 540, height: 960 },
      { width: 1080, height: 2340 },
      { width: 1080, height: 1350 },
      { width: 1080, height: 1440 },
      { width: 1080, height: 1080 },
      { width: 640, height: 640 },
      { width: 1920, height: 960 },
      { width: 1440, height: 1080 },
    ]

    const loadList = async () => {
      loading.value = true
      try {
        const params = {
          q: searchQuery.value || undefined,
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
    const openAuto = () => {
      autoForm.value = { title: '', description: '', ratioIdx: '', voice: '', batchCount: 1 }
      autoProcessing.value = false
      searching.value = false
      searchResults.value = null
      showChat.value = false
      showDescPreview.value = false
      chatMessages.value = []
      chatInput.value = ''
      showAutoDialog.value = true
    }

    const closeAuto = () => {
      if (autoProcessing.value) return
      showAutoDialog.value = false
    }

    const searchMaterials = async () => {
      if (!autoForm.value.description) return
      searching.value = true
      searchResults.value = null
      try {
        const ratio = autoForm.value.ratioIdx !== '' ? (ratioOptions[autoForm.value.ratioIdx] || {}) : {}
        const res = await generatedApi.autoSearch({
          description: autoForm.value.description,
          frame_width: ratio.width,
          frame_height: ratio.height,
        })
        searchResults.value = res.data
      } catch (e) {
        toast.error('检索失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        searching.value = false
      }
    }

    const startAuto = async () => {
      if (!autoForm.value.description) return
      autoProcessing.value = true
      try {
        const ratio = autoForm.value.ratioIdx !== '' ? (ratioOptions[autoForm.value.ratioIdx] || {}) : {}
        const count = autoForm.value.batchCount || 1
        const payload = {
          ...autoForm.value,
          count,
          frame_width: ratio.width,
          frame_height: ratio.height,
          tts_voice: autoForm.value.voice || undefined,
          voice: undefined,
          ratioIdx: undefined,
          material_ids: searchResults.value?.materials?.length
            ? searchResults.value.materials.map(m => m.material_id) : undefined,
        }
        if (count > 1) {
          const res = await generatedApi.autoBatchGenerate(payload)
          const d = res.data
          const ok = d.count || 0
          const errs = d.errors?.length || 0
          closeAuto()
          loadList()
          if (errs > 0) {
            toast.warning(`批次生成完成：成功 ${ok} 个，失败 ${errs} 个`)
          } else {
            toast.success(`批次生成完成：共 ${ok} 个混剪视频`)
          }
        } else {
          await generatedApi.autoGenerate(payload)
          closeAuto()
          loadList()
          toast.success('自动混剪完成')
        }
      } catch (e) {
        toast.error('自动混剪失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        autoProcessing.value = false
      }
    }

    // ── Search results reorder / delete ──
    const removeSearchMaterial = (idx) => {
      searchResults.value.materials.splice(idx, 1)
      searchResults.value = { ...searchResults.value }
    }
    const moveSearchMaterial = (idx, dir) => {
      const mats = searchResults.value.materials
      const target = idx + dir
      if (target < 0 || target >= mats.length) return
      const tmp = mats[idx]
      mats[idx] = mats[target]
      mats[target] = tmp
      searchResults.value = { ...searchResults.value }
    }

    // ── AI Chat ──
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
            content: '选择一个智能体，然后告诉我你想生成什么样的混剪脚本，例如：帮我写一个春日公园的混剪脚本。'
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
      if (!text || chatLoading.value) return
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
        const ctx = '当前混剪描述：\n' + (autoForm.value.description || '(空)')
        const res = await agentApi.chat(selectedAgentId.value, msgs, '你是一个视频混剪脚本生成助手。根据用户的需求生成或改写混剪描述/脚本，直接输出结果，不要添加额外解释。\n\n' + ctx)
        const reply = res.data?.content || ''
        chatMessages.value.push({ id: ++chatIdCounter, role: 'assistant', content: reply })
      } catch (e) {
        toast.error('AI 响应失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        chatLoading.value = false
        setTimeout(scrollChatToBottom, 50)
      }
    }

    const applyChatResult = (msgContent) => {
      const text = msgContent
      if (text) {
        autoForm.value.description = text
        toast.success('已应用到脚本')
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

    const onPageChange = (p) => {
      page.value = p
      loadList()
    }

    // ── Markdown editor ──
    const showDescPreview = ref(false)
    const mdTextarea = ref(null)

    const mdInsert = (before, after) => {
      const ta = mdTextarea.value
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = autoForm.value.description
      const selected = text.substring(start, end)
      autoForm.value.description = text.substring(0, start) + before + selected + after + text.substring(end)
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
      const text = autoForm.value.description
      const selected = text.substring(start, end) || '链接文本'
      const replacement = `[${selected}](url)`
      autoForm.value.description = text.substring(0, start) + replacement + text.substring(end)
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

    const hoverPlay = (e) => {
      const v = e.target
      if (v.readyState >= 2) v.play()
    }

    const hoverPause = (e) => {
      const v = e.target
      v.pause()
      v.currentTime = 0
    }

    onMounted(() => {
      loadList()
      loadFolders('generated')
    })

    return {
      list, loading, searchQuery,
      page, pageSize, total, onPageChange,
      viewMode,
      folders, folderMap,
      selectedIds, isAllSelected, toggleSelect, toggleSelectAll, clearSelection,
      showMoveDialog, moveBatchMode,
      showBatchMoveFolder, closeMoveDialog, moveToFolder,
      batchDeleteGens,
      openManual, openEdit,
      genVideo, dubVideo, deleteGen,
      showAutoDialog, autoForm, autoProcessing, searching, searchResults, openAuto, closeAuto, searchMaterials, startAuto,
      removeSearchMaterial, moveSearchMaterial,
      ratioOptions,
      showChat, chatMessages, chatInput, chatLoading, chatMessagesRef,
      agents, selectedAgentId,
      toggleChat, sendChat, applyChatResult, clearChat, onAgentChange,
      showDescPreview, mdTextarea, mdInsert, mdLink, renderMarkdown,
      statusText, formatTime, truncate, formatDuration,
      hoverPlay, hoverPause,
    }
  },
}
