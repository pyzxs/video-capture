import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { generatedApi, agentApi } from '../../api/index.js'
import { useToast } from '../../composables/useToast.js'

export default {
  name: 'AutoMashup',
  setup() {
    const router = useRouter()
    const toast = useToast()

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

    const goBack = () => {
      router.push('/mashups')
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
        if (res.data.script) {
          autoForm.value.description = res.data.script
        }
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
          router.push('/mashups')
          if (errs > 0) {
            toast.warning(`批次生成完成：成功 ${ok} 个，失败 ${errs} 个`)
          } else {
            toast.success(`批次生成完成：共 ${ok} 个混剪视频`)
          }
        } else {
          await generatedApi.autoGenerate(payload)
          router.push('/mashups')
          toast.success('自动混剪完成')
        }
      } catch (e) {
        toast.error('自动混剪失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        autoProcessing.value = false
      }
    }

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
    const showChat = ref(false)
    const chatMessages = ref([])
    const chatInput = ref('')
    const chatLoading = ref(false)
    const chatMessagesRef = ref(null)
    const agents = ref([])
    const selectedAgentId = ref('')
    let chatIdCounter = 0

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
      if (msgContent) {
        autoForm.value.description = msgContent
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

    const truncate = (s, n) => s && s.length > n ? s.slice(0, n) + '...' : (s || '')

    return {
      autoForm, autoProcessing, searching, searchResults,
      goBack, searchMaterials, startAuto,
      removeSearchMaterial, moveSearchMaterial,
      ratioOptions,
      showChat, chatMessages, chatInput, chatLoading, chatMessagesRef,
      agents, selectedAgentId,
      toggleChat, sendChat, applyChatResult, clearChat, onAgentChange,
      showDescPreview, mdTextarea, mdInsert, mdLink, renderMarkdown,
      truncate,
    }
  },
}
