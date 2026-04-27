import { noteApi, agentApi, materialApi, folderApi } from '../../api'
import { useToast } from '../../composables/useToast.js'

export default {
  name: 'NotesView',
  data() {
    return {
      loading: false,
      saving: false,
      folders: [],
      notes: [],
      selectedFolderId: null,
      editingNote: null,
      _savedSelStart: 0,
      _savedSelEnd: 0,
      showFolderDialog: false,
      editingFolder: null,
      folderForm: { title: '' },
      noteForm: { title: '', content: '' },
      showPreview: false,
      // Agent chat
      showAgentChat: false,
      agents: [],
      selectedAgentId: '',
      agentMessages: [],
      agentInput: '',
      agentLoading: false,
      searchQuery: '',
      searchTimer: null,
      // TTS
      ttsVoice: '',
      ttsBusy: false,
      showTtsDialog: false,
      ttsNote: null,
      ttsFolderId: null,
      materialFolders: [],
      voiceOptions: [
        { label: 'Alex（亚力克斯）', value: 'FunAudioLLM/CosyVoice2-0.5B:alex' },
        { label: 'Anna（安娜）', value: 'FunAudioLLM/CosyVoice2-0.5B:anna' },
        { label: 'Bella（贝拉）', value: 'FunAudioLLM/CosyVoice2-0.5B:bella' },
        { label: 'Benjamin（本杰明）', value: 'FunAudioLLM/CosyVoice2-0.5B:benjamin' },
        { label: 'Charles（查尔斯）', value: 'FunAudioLLM/CosyVoice2-0.5B:charles' },
        { label: 'Claire（克莱尔）', value: 'FunAudioLLM/CosyVoice2-0.5B:claire' },
        { label: 'David（大卫）', value: 'FunAudioLLM/CosyVoice2-0.5B:david' },
        { label: 'Diana（黛安娜）', value: 'FunAudioLLM/CosyVoice2-0.5B:diana' },
      ],
      // Move note
      showMoveDialog: false,
      moveTargetNote: null,
      moveTargetParentId: null,
      moveSaving: false,
    }
  },
  computed: {
    currentTitle() {
      if (this.selectedFolderId === null) return '全部笔记'
      const f = this.folders.find(f => f.id === this.selectedFolderId)
      return f ? f.title : '笔记'
    },
  },
  created() {
    this.toast = useToast()
  },
  mounted() {
    this.loadFolders()
    this.loadNotes()
  },
  methods: {
    async loadFolders() {
      try {
        const res = await noteApi.list({ tp: 'folder' })
        this.folders = res.data.items || res.data
      } catch (e) {
        console.error('加载文件夹失败', e)
      }
    },
    async loadNotes() {
      this.loading = true
      try {
        const params = {}
        if (this.searchQuery) {
          params.q = this.searchQuery
        } else if (this.selectedFolderId !== null) {
          params.parent_id = this.selectedFolderId
        } else {
          params.tp = 'note'
        }
        const res = await noteApi.list(params)
        this.notes = res.data.items || res.data
      } catch (e) {
        console.error('加载笔记失败', e)
      } finally {
        this.loading = false
      }
    },
    selectFolder(id) {
      this.selectedFolderId = id
      this.searchQuery = ''
      this.editingNote = null
      this.loadNotes()
    },
    onSearch() {
      if (this.searchTimer) clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => this.loadNotes(), 300)
    },
    formatDate(d) {
      if (!d) return ''
      return new Date(d).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    },
    // ── Folder ──
    openFolderDialog(folder) {
      this.editingFolder = folder || null
      this.folderForm = { title: folder ? folder.title : '' }
      this.showFolderDialog = true
    },
    async saveFolder() {
      if (!this.folderForm.title.trim()) {
        this.toast.warning('请输入文件夹名称')
        return
      }
      this.saving = true
      try {
        if (this.editingFolder) {
          await noteApi.update(this.editingFolder.id, { title: this.folderForm.title })
          this.toast.success('文件夹已更新')
        } else {
          await noteApi.create({ title: this.folderForm.title, tp: 'folder' })
          this.toast.success('文件夹已创建')
        }
        this.showFolderDialog = false
        await this.loadFolders()
      } catch (e) {
        this.toast.error('操作失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        this.saving = false
      }
    },
    async deleteFolder(f) {
      if (!await this.toast.confirm(`确定删除文件夹「${f.title}」？文件夹内的笔记也会被删除。`)) return
      try {
        await noteApi.remove(f.id)
        if (this.selectedFolderId === f.id) {
          this.selectedFolderId = null
        }
        await this.loadFolders()
        await this.loadNotes()
        this.toast.success('文件夹已删除')
      } catch (e) {
        this.toast.error('删除失败')
      }
    },
    // ── Note ──
    openNoteDialog() {
      this.noteForm = { title: '', content: '' }
      this.editingNote = true
      this.agentMessages = []
    },
    editNote(n) {
      this.noteForm = { title: n.title, content: n.content }
      this.editingNote = n.id
      this.agentMessages = []
    },
    async saveNote() {
      this.saving = true
      try {
        const data = {
          title: this.noteForm.title,
          content: this.noteForm.content,
          tp: 'note',
          parent_id: this.selectedFolderId,
        }
        if (typeof this.editingNote === 'number') {
          await noteApi.update(this.editingNote, data)
          this.toast.success('笔记已更新')
        } else {
          await noteApi.create(data)
          this.toast.success('笔记已创建')
        }
        this.editingNote = null
        await this.loadNotes()
      } catch (e) {
        this.toast.error('保存失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        this.saving = false
      }
    },
    async deleteNote(n) {
      if (!await this.toast.confirm(`确定删除笔记「${n.title || '无标题'}」？`)) return
      try {
        await noteApi.remove(n.id)
        if (this.editingNote === n.id) {
          this.editingNote = null
        }
        await this.loadNotes()
      } catch (e) {
        this.toast.error('删除失败')
      }
    },
    exportNote(n) {
      const title = n.title || '无标题'
      const content = n.content || ''
      const md = `# ${title}\n\n${content}`
      const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${title.replace(/[\\/:*?"<>|]/g, '_')}.md`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    },
    // ── Move Note ──
    openMoveDialog(n) {
      this.moveTargetNote = n
      this.moveTargetParentId = n.parent_id
      this.showMoveDialog = true
    },
    async moveNote() {
      if (!this.moveTargetNote) return
      this.moveSaving = true
      try {
        await noteApi.update(this.moveTargetNote.id, { parent_id: this.moveTargetParentId })
        this.showMoveDialog = false
        this.toast.success('笔记已移动')
        await this.loadNotes()
      } catch (e) {
        this.toast.error('移动失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        this.moveSaving = false
      }
    },
    // ── Image paste ──
    async handlePaste(e) {
      const items = e.clipboardData?.items
      if (!items) return
      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault()
          const file = item.getAsFile()
          if (!file) continue
          const ta = this.$refs.mdTextarea
          if (!ta) return
          const cursor = ta.selectionStart
          try {
            const res = await noteApi.uploadImage(file)
            const url = res.data.url || res.data.data?.url
            if (!url) continue
            const imgTag = `![](${url})`
            const text = this.noteForm.content
            this.noteForm.content = text.substring(0, cursor) + imgTag + text.substring(cursor)
            this.$nextTick(() => {
              ta.focus()
              const pos = cursor + imgTag.length
              ta.setSelectionRange(pos, pos)
            })
          } catch (e) {
            console.error('图片上传失败', e)
          }
          break
        }
      }
    },

    // ── Markdown editor helpers ──
    onMdCursor() {
      const ta = this.$refs.mdTextarea
      if (!ta) return
      this._savedSelStart = ta.selectionStart
      this._savedSelEnd = ta.selectionEnd
    },
    _getSel() {
      const ta = this.$refs.mdTextarea
      if (!ta) return { start: 0, end: 0 }
      const start = ta.selectionStart
      if (start >= 0) return { start, end: ta.selectionEnd }
      return { start: this._savedSelStart, end: this._savedSelEnd }
    },
    mdInsert(before, after) {
      const ta = this.$refs.mdTextarea
      if (!ta) return
      const { start, end } = this._getSel()
      const text = this.noteForm.content
      const selected = text.substring(start, end)
      this.noteForm.content = text.substring(0, start) + before + selected + after + text.substring(end)
      const newCursor = start + before.length + selected.length + after.length
      this.$nextTick(() => {
        ta.focus()
        ta.setSelectionRange(newCursor, newCursor)
      })
    },
    mdLink() {
      const ta = this.$refs.mdTextarea
      if (!ta) return
      const { start, end } = this._getSel()
      const text = this.noteForm.content
      const selected = text.substring(start, end) || '链接文本'
      const replacement = `[${selected}](url)`
      this.noteForm.content = text.substring(0, start) + replacement + text.substring(end)
      this.$nextTick(() => {
        ta.focus()
        ta.setSelectionRange(start + replacement.length - 1, start + replacement.length - 1)
      })
    },
    mdImage() {
      const ta = this.$refs.mdTextarea
      if (!ta) return
      const { start, end } = this._getSel()
      const text = this.noteForm.content
      const selected = text.substring(start, end) || '图片描述'
      const replacement = `![${selected}](url)`
      this.noteForm.content = text.substring(0, start) + replacement + text.substring(end)
      this.$nextTick(() => {
        ta.focus()
        ta.setSelectionRange(start + replacement.length - 1, start + replacement.length - 1)
      })
    },
    mdOrderedList() {
      const ta = this.$refs.mdTextarea
      if (!ta) return
      const { start } = this._getSel()
      const text = this.noteForm.content
      // 在当前行前面插入 "1. "
      const lineStart = text.lastIndexOf('\n', start - 1) + 1
      const replacement = '1. '
      this.noteForm.content = text.substring(0, lineStart) + replacement + text.substring(lineStart)
      this.$nextTick(() => {
        ta.focus()
        ta.setSelectionRange(start + replacement.length, start + replacement.length)
      })
    },
    mdCodeBlock() {
      const ta = this.$refs.mdTextarea
      if (!ta) return
      const { start, end } = this._getSel()
      const text = this.noteForm.content
      const selected = text.substring(start, end)
      const replacement = selected ? `\`\`\`\n${selected}\n\`\`\`` : '\`\`\`\n\n\`\`\`'
      this.noteForm.content = text.substring(0, start) + replacement + text.substring(end)
      const cursor = start + replacement.length
      this.$nextTick(() => {
        ta.focus()
        ta.setSelectionRange(cursor, cursor)
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
      html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>')
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')
      html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
      html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
      html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')
      html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
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
    // ── Agent Chat ──
    async toggleAgentChat() {
      this.showAgentChat = !this.showAgentChat
      if (this.showAgentChat && this.agents.length === 0) {
        try {
          const res = await agentApi.list()
          this.agents = res.data || []
          if (this.agents.length > 0 && !this.selectedAgentId) {
            this.selectedAgentId = this.agents[0].id
          }
        } catch (e) {
          console.error('加载智能体失败', e)
        }
      }
      this.$nextTick(() => this.scrollAgentChat())
    },
    loadAgentInfo() {
      this.agentMessages = []
    },
    scrollAgentChat() {
      this.$nextTick(() => {
        const box = this.$refs.agentChatBox
        if (box) box.scrollTop = box.scrollHeight
      })
    },
    async sendAgentMessage() {
      if (!this.agentInput.trim() || this.agentLoading || !this.selectedAgentId) return
      const msg = this.agentInput.trim()
      this.agentMessages.push({ role: 'user', content: msg })
      this.agentInput = ''
      this.agentLoading = true
      this.scrollAgentChat()
      try {
        const msgs = this.agentMessages.filter(m => m.role !== 'system').map(m => ({ role: m.role, content: m.content }))
        const ctx = '当前笔记标题：' + this.noteForm.title + '\n当前笔记内容：\n' + (this.noteForm.content || '(空)')
        const res = await agentApi.chat(this.selectedAgentId, msgs, '你是一个笔记助手，帮助用户完善笔记内容。当前笔记内容如下，请参考。\n' + ctx)
        this.agentMessages.push({ role: 'assistant', content: res.data.content || res.data.data?.content || '' })
      } catch (e) {
        this.agentMessages.push({ role: 'assistant', content: '调用失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message) })
      } finally {
        this.agentLoading = false
        this.scrollAgentChat()
      }
    },
    applyAgentResponse(index) {
      const msg = this.agentMessages[index]
      if (msg && msg.role === 'assistant') {
        this.noteForm.content = msg.content
        this.toast.success('已应用智能体回复到笔记内容')
      }
    },
    // ── TTS Synthesize ──
    async synthesizeNote() {
      const text = this.noteForm.content.trim()
      if (!text) {
        this.toast.warning('请先输入笔记内容')
        return
      }
      this.ttsBusy = true
      try {
        await materialApi.tts({ text, voice: this.ttsVoice || undefined })
        this.toast.success('语音合成成功，已生成音频素材')
      } catch (e) {
        this.toast.error('语音合成失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        this.ttsBusy = false
      }
    },
    // ── TTS Dialog (from note card list) ──
    async loadMaterialFolders() {
      try {
        const res = await folderApi.list({ folder_type: 'material' })
        this.materialFolders = res.data.items || []
      } catch (e) {
        console.error('加载素材文件夹失败', e)
        this.materialFolders = []
      }
    },
    openTtsDialog(n) {
      this.ttsNote = n
      this.ttsVoice = ''
      this.ttsFolderId = null
      this.showTtsDialog = true
      this.loadMaterialFolders()
    },
    closeTtsDialog() {
      this.showTtsDialog = false
      this.ttsNote = null
    },
    async synthesizeNoteTts() {
      const n = this.ttsNote
      if (!n) return
      const text = n.content?.trim()
      if (!text) {
        this.toast.warning('笔记内容为空')
        return
      }
      this.ttsBusy = true
      try {
        await materialApi.tts({ text, voice: this.ttsVoice || undefined, folder_id: this.ttsFolderId || undefined })
        this.closeTtsDialog()
        this.toast.success('语音合成成功，已生成音频素材')
      } catch (e) {
        this.toast.error('语音合成失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        this.ttsBusy = false
      }
    },
  },
}
