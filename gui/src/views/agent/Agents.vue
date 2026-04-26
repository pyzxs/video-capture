<template>
<div class="view-container">
    <div class="panel">
      <div class="view-header">
        <h2>智能体管理</h2>
        <div class="header-actions">
          <button class="btn btn-primary" @click="openAgentDialog()">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            <span>新增智能体</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="agents.length === 0" class="empty">暂无智能体，点击上方按钮创建</div>
    <table v-else class="data-table">
      <thead>
        <tr><th>标识键</th><th>名称</th><th>提示词</th><th>创建时间</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="a in agents" :key="a.id">
          <td><code class="key-cell">{{ a.key || '-' }}</code></td>
          <td class="agent-name-cell">{{ a.name || '未命名' }}</td>
          <td class="prompt-cell">{{ a.prompt || '-' }}</td>
          <td class="date-cell">{{ formatDate(a.created_at) }}</td>
          <td>
            <button class="btn btn-sm btn-default" @click="openAgentDialog(a)" title="编辑">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Agent 弹窗 -->
    <div v-if="showAgentDialog" class="modal-overlay">
      <div class="modal modal-wide">
        <div class="modal-header">
          <h3>{{ editingAgent ? '编辑智能体' : '新增智能体' }}</h3>
          <div class="modal-actions">
            <button class="btn btn-primary" @click="saveAgent" :disabled="saving" title="保存">
              <svg v-if="!saving" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              <span v-else>{{ '保存中...' }}</span>
            </button>
            <button class="btn btn-default" @click="showAgentDialog = false">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        <div class="form">
          <label>
            标识键
            <input v-model="agentForm.key" placeholder="唯一标识，如 content_expand" :readonly="!!editingAgent" :class="{ readonly: !!editingAgent }" />
          </label>
          <label>名称 <input v-model="agentForm.name" placeholder="智能体名称" /></label>
          <label>提示词
            <div class="md-editor">
              <div class="md-toolbar">
                <button type="button" class="md-btn" @click="mdInsert('**', '**')" title="粗体"><strong>B</strong></button>
                <button type="button" class="md-btn" @click="mdInsert('*', '*')" title="斜体"><em>I</em></button>
                <button type="button" class="md-btn" @click="mdInsert('## ', '')" title="标题">H</button>
                <button type="button" class="md-btn" @click="mdInsert('- ', '')" title="列表">•</button>
                <button type="button" class="md-btn" @click="mdLink" title="链接">🔗</button>
                <span class="md-sep"></span>
                <button type="button" class="md-btn" @click="showPromptPreview = !showPromptPreview">
                  {{ showPromptPreview ? '编辑' : '预览' }}
                </button>
              </div>
              <textarea v-if="!showPromptPreview" ref="mdTextarea" v-model="agentForm.prompt" rows="8" class="md-textarea" placeholder="智能体的系统提示词..."></textarea>
              <div v-else class="md-preview" v-html="renderMarkdown(agentForm.prompt)"></div>
            </div>
          </label>
        </div>
      </div>
    </div>

    <!-- 测试对话弹窗 -->
    <div v-if="showTestDialog" class="modal-overlay">
      <div class="modal modal-wide">
        <div class="modal-header">
          <h3>测试: {{ testAgent?.name }}</h3>
          <div class="modal-actions">
            <button class="btn btn-default" @click="showTestDialog = false">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        <div class="chat-box">
          <div class="chat-messages" ref="chatBox">
            <div v-for="(msg, i) in testMessages" :key="i" :class="['msg', msg.role]">
              <div class="msg-bubble">{{ msg.content }}</div>
            </div>
            <div v-if="testLoading" class="msg assistant">
              <div class="msg-bubble thinking">思考中...</div>
            </div>
          </div>
          <div class="chat-input-row">
            <input v-model="testInput" class="chat-input" placeholder="输入消息..." @keydown.enter="sendTest" :disabled="testLoading" />
            <button class="btn btn-primary" @click="sendTest" :disabled="testLoading || !testInput.trim()">发送</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script src="./Agents.js"></script>

<style src="./Agents.css" scoped></style>
