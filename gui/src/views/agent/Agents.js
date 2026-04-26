import { agentApi } from '../../api'
import { useToast } from '../../composables/useToast.js'

export default {
  name: 'AgentsView',
  data() {
    return {
      loading: false,
      agents: [],
      // Agent dialog
      showAgentDialog: false,
      editingAgent: null,
      agentForm: { key: '', name: '', prompt: '' },
      showPromptPreview: false,
      saving: false,
      // Test chat
      showTestDialog: false,
      testAgent: null,
      testMessages: [],
      testInput: '',
      testLoading: false,
    }
  },
  created() {
    this.toast = useToast()
  },
  mounted() {
    this.loadData()
  },
  methods: {
    async loadData() {
      this.loading = true
      try {
        const agentsRes = await agentApi.list()
        this.agents = agentsRes.data
      } catch (e) {
        console.error('加载失败', e)
      } finally {
        this.loading = false
      }
    },
    formatDate(d) {
      if (!d) return '-'
      return new Date(d).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    },
    // ── Agent ──
    openAgentDialog(agent) {
      this.editingAgent = agent || null
      this.agentForm = agent
        ? { key: agent.key, name: agent.name, prompt: agent.prompt }
        : { key: '', name: '', prompt: '' }
      this.showAgentDialog = true
    },
    async saveAgent() {
      this.saving = true
      try {
        if (this.editingAgent) {
          await agentApi.update(this.editingAgent.id, this.agentForm)
        } else {
          await agentApi.create(this.agentForm)
        }
        this.showAgentDialog = false
        this.loadData()
        this.toast.success(this.editingAgent ? '智能体已更新' : '智能体已创建')
      } catch (e) {
        this.toast.error('保存失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        this.saving = false
      }
    },
    async deleteAgent(a) {
      if (!await this.toast.confirm(`确定删除智能体「${a.name}」？`)) return
      try {
        await agentApi.remove(a.id)
        this.loadData()
      } catch (e) {
        console.error('删除失败', e)
      }
    },
    // ── Markdown editor helpers ──
    mdInsert(before, after) {
      const ta = this.$refs.mdTextarea
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = this.agentForm.prompt
      const selected = text.substring(start, end)
      this.agentForm.prompt = text.substring(0, start) + before + selected + after + text.substring(end)
      const newCursor = start + before.length + selected.length + after.length
      this.$nextTick(() => {
        ta.focus()
        ta.setSelectionRange(newCursor, newCursor)
      })
    },
    mdLink() {
      const ta = this.$refs.mdTextarea
      if (!ta) return
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const text = this.agentForm.prompt
      const selected = text.substring(start, end) || '链接文本'
      const replacement = `[${selected}](url)`
      this.agentForm.prompt = text.substring(0, start) + replacement + text.substring(end)
      this.$nextTick(() => {
        ta.focus()
        ta.setSelectionRange(start + replacement.length - 1, start + replacement.length - 1)
      })
    },
    renderMarkdown(text) {
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
    },
    // ── Test Chat ──
    openTestChat(a) {
      this.testAgent = a
      this.testMessages = []
      this.testInput = ''
      this.showTestDialog = true
      this.$nextTick(() => this.scrollChat())
    },
    async sendTest() {
      if (!this.testInput.trim() || this.testLoading) return
      const msg = this.testInput.trim()
      this.testMessages.push({ role: 'user', content: msg })
      this.testInput = ''
      this.testLoading = true
      this.scrollChat()
      try {
        const res = await agentApi.chat(this.testAgent.id, [{ role: 'user', content: msg }], '')
        this.testMessages.push({ role: 'assistant', content: res.data.content })
      } catch (e) {
        this.testMessages.push({ role: 'assistant', content: '调用失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message) })
      } finally {
        this.testLoading = false
        this.scrollChat()
      }
    },
    scrollChat() {
      this.$nextTick(() => {
        const box = this.$refs.chatBox
        if (box) box.scrollTop = box.scrollHeight
      })
    },
  },
}
