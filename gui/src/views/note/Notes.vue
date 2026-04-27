<template>
<div class="view-container notes-layout">
    <!-- 左侧文件夹树 -->
    <div class="notes-sidebar">
      <div class="notes-sidebar-header">
        <strong>笔记目录</strong>
        <button class="btn btn-sm btn-default" @click="openFolderDialog()" title="新建文件夹">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
      </div>
      <div class="notes-tree">
        <div class="tree-item" :class="{ active: selectedFolderId === null }" @click="selectFolder(null)">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <span>全部笔记</span>
        </div>
        <div v-for="f in folders" :key="f.id" class="tree-item"
             :class="{ active: selectedFolderId === f.id }"
             @click="selectFolder(f.id)">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <span class="tree-item-name">{{ f.title || '未命名' }}</span>
          <div class="tree-item-actions">
            <button v-if="!f.is_system" class="btn-icon" @click.stop="openFolderDialog(f)" title="编辑">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            </button>
            <button v-if="!f.is_system" class="btn-icon btn-icon-danger" @click.stop="deleteFolder(f)" title="删除">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧笔记列表 + 编辑器 -->
    <div class="notes-main">
      <div v-if="!editingNote" class="notes-toolbar">
        <h3>{{ currentTitle }}</h3>
        <div class="toolbar-right">
          <input v-model="searchQuery" class="search-input" placeholder="搜索笔记标题..." @input="onSearch" />
          <button class="btn btn-primary btn-sm" @click="openNoteDialog()">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          <span>新增笔记</span>
        </button>
        </div>
      </div>

      <!-- 笔记列表 -->
      <div v-if="!editingNote" class="notes-list">
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="notes.length === 0" class="empty">暂无笔记</div>
        <div v-else v-for="n in notes" :key="n.id" class="note-card" @click="editNote(n)">
          <div class="note-card-body">
            <div class="note-card-title">{{ n.title || '无标题' }}</div>
            <div class="note-card-preview">{{ n.content ? n.content.substring(0, 120) : '无内容' }}</div>
            <div class="note-card-time">{{ formatDate(n.updated_at) }}</div>
          </div>
          <div class="note-card-actions">
            <button @click.stop="openMoveDialog(n)" title="移动到文件夹">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v1"/><path d="M17 22v-6"/><path d="M20 19l-3-3-3 3"/></svg>
            </button>
            <button @click.stop="exportNote(n)" title="导出 Markdown">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </button>
            <button @click.stop="openTtsDialog(n)" title="合成为语音素材">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
            </button>
            <button @click.stop="deleteNote(n)" title="删除">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      </div>

      <!-- 笔记编辑器 -->
      <div v-if="editingNote" class="editor-with-agent">
        <div class="note-editor">
          <div class="editor-toolbar">
            <button class="btn btn-sm btn-default" @click="editingNote = null" title="返回">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            </button>
            <button class="btn btn-sm btn-primary" @click="saveNote" :disabled="saving" title="保存">
              <svg v-if="!saving" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              <span v-else class="btn-loading"></span>
            </button>
            <button class="btn btn-sm btn-agent" @click="toggleAgentChat" :class="{ active: showAgentChat }" title="智能体">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>
            </button>
          </div>
          <input v-model="noteForm.title" class="editor-title" placeholder="笔记标题" />
          <div class="md-editor">
            <div class="md-toolbar">
              <button type="button" class="md-btn" @mousedown.prevent="mdInsert('**', '**')" title="粗体"><strong>B</strong></button>
              <button type="button" class="md-btn" @mousedown.prevent="mdInsert('*', '*')" title="斜体"><em>I</em></button>
              <button type="button" class="md-btn" @mousedown.prevent="mdInsert('~~', '~~')" title="删除线"><del>S</del></button>
              <span class="md-sep"></span>
              <button type="button" class="md-btn" @mousedown.prevent="mdInsert('# ', '')" title="标题1">H1</button>
              <button type="button" class="md-btn" @mousedown.prevent="mdInsert('## ', '')" title="标题2">H2</button>
              <button type="button" class="md-btn" @mousedown.prevent="mdInsert('### ', '')" title="标题3">H3</button>
              <span class="md-sep"></span>
              <button type="button" class="md-btn" @mousedown.prevent="mdInsert('- ', '')" title="无序列表">•</button>
              <button type="button" class="md-btn" @mousedown.prevent="mdOrderedList" title="有序列表">1.</button>
              <button type="button" class="md-btn" @mousedown.prevent="mdInsert('> ', '')" title="引用">❝</button>
              <span class="md-sep"></span>
              <button type="button" class="md-btn" @mousedown.prevent="mdCodeBlock" title="代码块">&lt;/&gt;</button>
              <button type="button" class="md-btn" @mousedown.prevent="mdInsert('`', '`')" title="行内代码">`</button>
              <button type="button" class="md-btn" @mousedown.prevent="mdLink" title="链接">🔗</button>
              <button type="button" class="md-btn" @mousedown.prevent="mdImage" title="图片">🖼</button>
              <button type="button" class="md-btn" @mousedown.prevent="mdInsert('\n---\n', '')" title="分割线">—</button>
              <span class="md-sep"></span>
              <button type="button" class="md-btn" @click="showPreview = !showPreview">
                {{ showPreview ? '编辑' : '预览' }}
              </button>
            </div>
            <textarea v-if="!showPreview" ref="mdTextarea" v-model="noteForm.content" rows="16" class="md-textarea" placeholder="开始写笔记..." @keyup="onMdCursor" @mouseup="onMdCursor" @paste="handlePaste"></textarea>
            <div v-else class="md-preview" v-html="renderMarkdown(noteForm.content)"></div>
          </div>
        </div>

        <!-- 智能体聊天侧栏 -->
        <div v-if="showAgentChat" class="agent-sidebar">
          <div class="agent-sidebar-header">
            <span>智能体</span>
            <div class="agent-sidebar-actions">
              <select v-model="selectedAgentId" class="agent-select" @change="loadAgentInfo">
                <option value="">选择智能体...</option>
                <option v-for="a in agents" :key="a.id" :value="a.id">{{ a.name }}</option>
              </select>
              <button class="btn-icon" @click="showAgentChat = false" title="关闭">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>
          <div class="agent-chat-messages" ref="agentChatBox">
            <div v-if="agentMessages.length === 0" class="agent-chat-empty">
              与智能体对话，帮助修改和完善笔记内容
            </div>
            <div v-for="(msg, i) in agentMessages" :key="i" :class="['agent-msg', msg.role]">
              <div class="agent-msg-label">{{ msg.role === 'user' ? '我' : '智能体' }}</div>
              <div class="agent-msg-content">{{ msg.content }}</div>
              <div v-if="msg.role === 'assistant'" class="agent-msg-actions">
                <button class="btn btn-sm btn-default" @click="applyAgentResponse(i)">应用到笔记</button>
              </div>
            </div>
            <div v-if="agentLoading" class="agent-msg assistant">
              <div class="agent-msg-label">智能体</div>
              <div class="agent-msg-content thinking">思考中...</div>
            </div>
          </div>
          <div class="agent-chat-input-row">
            <textarea v-model="agentInput" class="agent-chat-input" placeholder="输入消息..." rows="2" @keydown.enter.prevent="sendAgentMessage" :disabled="agentLoading || !selectedAgentId"></textarea>
            <button class="btn btn-primary btn-sm" @click="sendAgentMessage" :disabled="agentLoading || !agentInput.trim() || !selectedAgentId">发送</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 文件夹编辑弹窗 -->
    <div v-if="showFolderDialog" class="modal-overlay" @click.self="showFolderDialog = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h3>{{ editingFolder ? '编辑文件夹' : '新建文件夹' }}</h3>
        </div>
        <div class="form">
          <label>名称 <input v-model="folderForm.title" placeholder="文件夹名称" @keydown.enter="saveFolder" /></label>
        </div>
        <div class="modal-actions">
          <button class="btn btn-default" @click="showFolderDialog = false">取消</button>
          <button class="btn btn-primary" @click="saveFolder" :disabled="saving">{{ saving ? '保存中...' : '确定' }}</button>
        </div>
      </div>
    </div>

    <!-- 移动到文件夹弹窗 -->
    <div v-if="showMoveDialog" class="modal-overlay" @click.self="showMoveDialog = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h3>移动到文件夹</h3>
        </div>
        <div class="folder-list">
          <div class="folder-item" :class="{ active: moveTargetParentId === null }" @click="moveTargetParentId = null">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            <span class="folder-name">根目录（无文件夹）</span>
          </div>
          <div v-for="f in folders" :key="f.id" class="folder-item"
               :class="{ active: moveTargetParentId === f.id }"
               @click="moveTargetParentId = f.id">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            <span class="folder-name">{{ f.title }}</span>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-default" @click="showMoveDialog = false">取消</button>
          <button class="btn btn-primary" @click="moveNote" :disabled="moveSaving">{{ moveSaving ? '移动中...' : '移动' }}</button>
        </div>
      </div>
    </div>

    <!-- 语音合成弹窗 -->
    <div v-if="showTtsDialog" class="modal-overlay" @click.self="closeTtsDialog">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h3>合成为语音素材</h3>
          <div class="modal-actions">
            <button class="btn btn-default" @click="closeTtsDialog" title="关闭">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        <div class="form">
          <label>配音音色
            <select v-model="ttsVoice" class="form-select">
              <option value="">默认音色</option>
              <option v-for="opt in voiceOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
          <label>素材文件夹
            <select v-model="ttsFolderId" class="form-select">
              <option :value="null">无文件夹</option>
              <option v-for="f in materialFolders" :key="f.id" :value="f.id">{{ f.name }}</option>
            </select>
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn btn-default" @click="closeTtsDialog">取消</button>
          <button class="btn btn-primary" @click="synthesizeNoteTts" :disabled="ttsBusy">{{ ttsBusy ? '合成中...' : '合成' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script src="./Notes.js"></script>

<style src="./Notes.css" scoped></style>
