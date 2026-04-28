<template>
<div class="view-container">
    <div class="panel">
      <div class="view-header">
        <h2>原始视频管理</h2>
        <div class="header-actions">
          <label class="select-all-label" v-if="videos.length > 0" title="全选">
            <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" />
          </label>
          <button v-if="selectedIds.size > 0" class="btn btn-sm btn-default" @click="showBatchMoveFolder">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            移动到文件夹 ({{ selectedIds.size }})
          </button>
          <button v-if="selectedIds.size > 0" class="btn btn-sm btn-danger" @click="batchDeleteVideos">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            批量删除 ({{ selectedIds.size }})
          </button>
          <div class="view-mode-toggle">
            <button class="vm-btn" :class="{ active: viewMode === 'card' }" @click="viewMode = 'card'" title="卡片视图">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
            </button>
            <button class="vm-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" title="列表视图">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
          </div>
          <input v-model="searchQuery" placeholder="搜索文件名..." class="search-input" @input="page=1; loadVideos()" />
          <button class="btn btn-primary" @click="openUpload" title="上传视频">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          </button>
          <button class="btn btn-info" @click="openDownload" title="网络下载">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else>
      <div v-if="videos.length === 0" class="empty">暂无数据</div>
      <template v-else>
        <div v-if="viewMode === 'card'" class="video-grid">
          <div v-for="v in videos" :key="v.id" class="video-card" :class="{ 'card-selected': selectedIds.has(v.id) }">
          <div class="card-top">
            <label class="card-checkbox" @click.stop>
              <input type="checkbox" :checked="selectedIds.has(v.id)" @change="toggleSelect(v.id)" />
            </label>
            <span class="card-id">#{{ v.id }}</span>
            <span class="status-badge" :class="v.status">{{ v.status === 'completed' ? '已完成' : v.status === 'processing' ? '处理中' : '失败' }}</span>
          </div>
          <div class="card-video">
            <template v-if="activeVideos.has(v.id)">
              <video
                :ref="el => setVideoRef(v.id, el)"
                :src="`/api/videos/${v.id}/file`"
                controls
                preload="auto"
                class="video-player-card"
                @mouseenter="hoverPlay($event)"
                @mouseleave="hoverPause($event)"
                @loadeddata="onVideoLoaded($event)"
              ></video>
            </template>
            <div v-else class="thumbnail-wrap" @click="activateVideo(v.id)">
              <img
                v-if="v.thumbnail"
                :src="v.thumbnail"
                class="video-thumbnail"
                loading="lazy"
                alt="thumbnail"
              />
              <div v-else class="thumbnail-placeholder">
                <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              </div>
              <div class="play-overlay">
                <svg viewBox="0 0 24 24" width="36" height="36" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              </div>
            </div>
          </div>
          <div class="card-name" :title="v.filename">{{ truncateFilename(v.filename) }}</div>
          <div class="card-meta">
            <span class="meta-item">{{ v.frame_width }}x{{ v.frame_height }}</span>
            <span class="meta-item">{{ v.frame_rate }}fps</span>
            <span class="meta-item">{{ formatDuration(v.duration) }}</span>
          </div>
          <div class="card-actions">
            <button class="btn btn-sm btn-primary" @click="openEdit(v)" title="编辑">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            </button>
            <button class="btn btn-sm btn-primary" @click="openSplit(v)" title="分割">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="12" x2="20" y2="12"/><path d="M18 8l4 4-4 4"/><path d="M6 8l-4 4 4 4"/></svg>
            </button>
            <button class="btn btn-sm btn-default" @click="showMoveFolder(v, 'video')" title="移动到文件夹">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            </button>
            <button class="btn btn-sm btn-success" @click="copyContent(v)" title="复制文案">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            </button>
            <button class="btn btn-sm btn-danger" @click="deleteVideo(v)" title="删除">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      </div>
      <div v-else-if="viewMode === 'list'" class="list-table-wrap">
        <table class="list-table">
          <thead>
            <tr>
              <th class="list-col-chk"></th>
              <th class="list-col-id">#</th>
              <th class="list-col-name">文件名</th>
              <th class="list-col-meta">分辨率</th>
              <th class="list-col-meta">帧率</th>
              <th class="list-col-meta">时长</th>
              <th class="list-col-meta">文件夹</th>
              <th class="list-col-status">状态</th>
              <th class="list-col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in videos" :key="v.id" :class="{ 'row-selected': selectedIds.has(v.id) }">
              <td class="list-col-chk"><label class="card-checkbox"><input type="checkbox" :checked="selectedIds.has(v.id)" @change="toggleSelect(v.id)" /></label></td>
              <td class="list-col-id">#{{ v.id }}</td>
              <td class="list-col-name" :title="v.filename">{{ truncateFilename(v.filename) }}</td>
              <td class="list-col-meta">{{ v.frame_width }}x{{ v.frame_height }}</td>
              <td class="list-col-meta">{{ v.frame_rate }}fps</td>
              <td class="list-col-meta">{{ formatDuration(v.duration) }}</td>
              <td class="list-col-meta">{{ folderMap[v.folder_id] || '-' }}</td>
              <td class="list-col-status"><span class="status-badge" :class="v.status">{{ v.status === 'completed' ? '已完成' : v.status === 'processing' ? '处理中' : '失败' }}</span></td>
              <td class="list-col-actions">
                <button class="btn btn-xs btn-primary" @click="openEdit(v)" title="编辑">编辑</button>
                <button class="btn btn-xs btn-primary" @click="openSplit(v)" title="分割">分割</button>
                <button class="btn btn-xs btn-default" @click="showMoveFolder(v, 'video')" title="移动">移动</button>
                <button class="btn btn-xs btn-success" @click="copyContent(v)" title="复制文案">复制</button>
                <button class="btn btn-xs btn-danger" @click="deleteVideo(v)" title="删除">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    </template>

    <Pagination :page="page" :total="total" :page-size="pageSize" @change="onPageChange" />

    <!-- 上传弹窗 -->
    <div v-if="showDialog" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <h3>上传视频</h3>
          <div class="modal-actions">
            <button class="btn btn-primary" @click="startUpload" :disabled="!selectedFile || uploading" title="上传">
              <svg v-if="!uploading" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
              <span v-else>{{ '处理中...' }}</span>
            </button>
            <button class="btn btn-default" @click="closeDialog" :disabled="uploading" title="取消">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        <p class="modal-desc">上传后将自动提取元数据（分辨率、帧率）。</p>
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
          <button class="btn btn-sm btn-default" @click="clearFile" title="重新选择">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          </button>
          </div>
        </div>

        <div class="upload-options">
          <label class="dl-extract">
            <input type="checkbox" v-model="uploadExtract" />
            上传后提取文案（语音转文字）
          </label>
        </div>

        <div v-if="uploading || processing" class="upload-progress">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
          </div>
          <span>{{ processing ? '正在提取文案，请稍候...' : '上传中 ' + uploadProgress + '%' }}</span>
        </div>

      </div>
    </div>

    <!-- 网络下载弹窗 -->
    <div v-if="showDownload" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <h3>网络视频下载</h3>
          <div class="modal-actions">
            <button class="btn btn-primary" @click="startDownload" :disabled="!downloadUrls || downloading" title="下载">
              <svg v-if="!downloading" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              <span v-else>{{ '下载中...' }}</span>
            </button>
            <button class="btn btn-default" @click="closeDownload" :disabled="downloading" title="取消">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        <p class="modal-desc">输入视频地址或分享内容。</p>

        <div class="dl-channels">
          <button v-for="ch in channels" :key="ch.key" class="dl-channel-btn"
            :class="{ active: downloadChannel === ch.key }"
            @click="downloadChannel = ch.key">
            {{ ch.label }}
          </button>
        </div>

        <div class="form">
          <label>视频详情地址或分享内容
            <textarea v-model="downloadUrls" rows="4" class="dl-textarea" placeholder="视频详情分享链接或分享内容"></textarea>
          </label>

          <label class="dl-extract">
            <input type="checkbox" v-model="downloadExtract" />
            下载后提取文案（语音转文字）
          </label>
        </div>

        <div v-if="downloadResults.length > 0" class="dl-results">
          <div v-for="r in downloadResults" :key="r.url" class="dl-result-item" :class="r.status">
            <span class="dl-result-icon">{{ r.status === 'completed' ? '✓' : '✗' }}</span>
            <span class="dl-result-url">{{ r.url }}</span>
            <span class="dl-result-msg">{{ r.status === 'completed' ? '下载成功' : (r.error || '失败') }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <div v-if="showEdit" class="modal-overlay">
      <div class="modal modal-wide modal-xwide">
        <div class="modal-header">
          <h3>编辑视频</h3>
          <div class="modal-actions">
            <button class="btn btn-primary" @click="saveEdit" :disabled="saving" title="保存">
              <svg v-if="!saving" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              <span v-else>{{ '保存中...' }}</span>
            </button>
            <button class="btn btn-default" @click="closeEdit" title="取消">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        <div class="edit-layout">
          <div class="edit-form">
            <div class="form">
              <label>文件名
                <input v-model="editForm.filename" class="readonly-input" />
              </label>
              <div class="video-meta-row">
                <span class="meta-item"><span class="meta-lbl">画面比率</span> {{ calcAspectRatio(editingVideo?.frame_width, editingVideo?.frame_height) }}</span>
                <span class="meta-item"><span class="meta-lbl">帧率</span> {{ editingVideo?.frame_rate ?? '-' }}fps</span>
                <span class="meta-item"><span class="meta-lbl">时长</span> {{ formatDuration(editingVideo?.duration) }}</span>
              </div>
              <label>
                <div class="label-row">
                  <span>文案</span>
                  <div class="label-row-actions">
                    <button class="agent-btn" @click="saveToNote" title="保存到笔记">
                      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                        <line x1="8" y1="7" x2="16" y2="7"/>
                        <line x1="8" y1="11" x2="14" y2="11"/>
                      </svg>
                    </button>
                    <button class="agent-btn" @click="toggleChat" :title="showChat ? '关闭 AI 助手' : 'AI 改写文案'">
                      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                        <circle cx="12" cy="16" r="1"/>
                      </svg>
                    </button>
                  </div>
                </div>
                <div class="md-editor">
                  <div class="md-toolbar">
                    <button type="button" class="md-btn" @click="mdInsert('**', '**')" title="粗体"><strong>B</strong></button>
                    <button type="button" class="md-btn" @click="mdInsert('*', '*')" title="斜体"><em>I</em></button>
                    <button type="button" class="md-btn" @click="mdInsert('## ', '')" title="标题">H</button>
                    <button type="button" class="md-btn" @click="mdInsert('- ', '')" title="列表">•</button>
                    <button type="button" class="md-btn" @click="mdLink" title="链接">🔗</button>
                    <span class="md-sep"></span>
                    <button type="button" class="md-btn" @click="showEditPreview = !showEditPreview">
                      {{ showEditPreview ? '编辑' : '预览' }}
                    </button>
                  </div>
                  <textarea v-if="!showEditPreview" ref="mdTextarea" v-model="editForm.content" rows="12" class="md-textarea" placeholder="输入 Markdown 文案..."></textarea>
                  <div v-else class="md-preview" v-html="renderMarkdown(editForm.content)"></div>
                </div>
              </label>
            </div>
          </div>

          <!-- AI 改写聊天面板 -->
          <div v-if="showChat" class="edit-chat-panel">
            <div class="chat-panel-header">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                <circle cx="12" cy="16" r="1"/>
              </svg>
              <span>智能体</span>
              <button class="btn btn-sm btn-default" @click="showChat = false" title="关闭">✕</button>
            </div>
            <div class="chat-agent-select">
              <select v-model="selectedAgentId" class="agent-select" @change="onAgentChange">
                <option value="">选择智能体...</option>
                <option v-for="a in agents" :key="a.id" :value="a.id">{{ a.name }}</option>
              </select>
            </div>
            <div class="chat-messages" ref="chatMessagesRef">
              <div v-if="chatMessages.length === 0" class="chat-empty-hint">
                选择智能体后，发送消息即可与智能体对话改写文案
              </div>
              <div v-for="msg in chatMessages" :key="msg.id" :class="['chat-msg', msg.role]">
                <div class="chat-avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
                <div class="chat-bubble">{{ msg.content }}</div>
                <div v-if="msg.role === 'assistant'" class="chat-msg-actions">
                  <button class="btn btn-sm btn-default" @click="applyRewrite(msg.content)" title="应用到文案">应用到文案</button>
                </div>
              </div>
              <div v-if="chatLoading" class="chat-msg assistant">
                <div class="chat-avatar">AI</div>
                <div class="chat-bubble thinking">思考中...</div>
              </div>
            </div>
            <div class="chat-footer">
              <textarea
                v-model="chatInput"
                @keydown.enter.exact.prevent="sendChat"
                placeholder="输入消息..."
                rows="2"
                class="chat-input-area"
                :disabled="!selectedAgentId"
              ></textarea>
              <div class="chat-actions">
                <button class="btn btn-primary btn-sm" @click="sendChat" :disabled="!chatInput.trim() || chatLoading || !selectedAgentId">发送</button>
                <button class="btn btn-default btn-sm" @click="clearChat">清空</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 移动到文件夹弹窗 -->
    <div v-if="showMoveDialog" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ moveBatchMode ? `移动到文件夹 (${selectedIds.size} 项)` : '移动到文件夹' }}</h3>
          <div class="modal-actions">
            <button class="btn btn-default" @click="closeMoveDialog" title="关闭">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        <div class="form">
          <div class="folder-list">
            <div class="folder-item" @click="moveToFolder(null)">
              <svg class="folder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              <span class="folder-name" style="color:#9ca3af">(无文件夹)</span>
              <svg class="folder-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
            </div>
            <div v-for="f in folders" :key="f.id" class="folder-item" @click="moveToFolder(f.id)">
              <svg class="folder-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              <span class="folder-name">{{ f.name }}</span>
              <svg class="folder-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 分割弹窗 -->
    <div v-if="showSplit" class="modal-overlay">
      <div class="modal modal-wide" :class="{ 'modal-xwide': splitMaterials.length > 0 || splitMode === 'manual' }" style="overflow:hidden">
        <div class="modal-header">
          <h3>分割视频 — {{ splitVideoRef?.filename || '' }}</h3>
          <div class="modal-actions">
            <button class="btn btn-default" @click="closeSplit" :disabled="splitDoing" title="关闭">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>

        <!-- 模式选择 -->
        <div class="split-mode-tabs" v-if="!splitStarted && splitState !== 'done'">
          <button class="split-mode-tab" :class="{ active: splitMode === 'auto' }" @click="splitMode = 'auto'">智能分割</button>
          <button class="split-mode-tab" :class="{ active: splitMode === 'manual' }" @click="splitMode = 'manual'">手动分割</button>
        </div>

        <!-- ────────── 智能分割 ────────── -->
        <template v-if="splitMode === 'auto'">
          <!-- 步骤进度 -->
          <div class="split-steps">
            <div v-for="(step, idx) in splitSteps" :key="idx" class="split-step"
              :class="step.status" :title="step.desc">
              <span class="split-step-icon">
                <svg v-if="step.status === 'done'" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                <svg v-else-if="step.status === 'doing'" class="spin" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/></svg>
                <svg v-else-if="step.status === 'error'" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
                <span v-else class="step-num">{{ idx + 1 }}</span>
              </span>
              <div class="split-step-text">
                <span class="split-step-label">{{ step.label }}</span>
                <span class="split-step-desc">{{ step.desc }}</span>
              </div>
            </div>
          </div>

          <!-- 等待开始 -->
          <template v-if="!splitStarted">
            <div class="smart-desc">
              <div class="smart-desc-title">
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                智能分割流程说明
              </div>
              <p class="smart-desc-intro">智能分割通过以下 7 个步骤，将原始视频自动拆分为可直接使用的素材片段：</p>
              <ol class="smart-desc-steps">
                <li><strong>分析视频软字幕</strong> — 检测视频是否内嵌 SRT/ASS 字幕流，优先使用字幕作为文本来源</li>
                <li><strong>提取视频音频</strong> — 通过 ffmpeg 将视频音轨提取为 16kHz 单声道 WAV 文件</li>
                <li><strong>提取音频到文字</strong> — 使用 Whisper 本地语音识别模型将音频转录为带时间戳的文字</li>
                <li><strong>分析语义到自然段落</strong> — 通过 LLM 大模型分析语义完整性，过滤无关内容，合并为自然段落</li>
                <li><strong>按自然段落分割</strong> — 根据段落时间戳使用 ffmpeg 精确切割视频画面</li>
                <li><strong>去除视频音频</strong> — 移除分割后片段的原始音频轨道，生成纯画面素材</li>
                <li><strong>生成素材列表</strong> — 创建素材数据库记录，建立向量索引供后续检索和混剪</li>
              </ol>
            </div>
            <div class="split-start-action">
              <button class="btn btn-primary" @click="startSplitAnalysis">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
                开始智能分割
              </button>
            </div>
          </template>

          <!-- 进行中 -->
          <template v-if="splitDoing">
            <p class="modal-desc" style="margin-top:0">{{ splitDoingText }}</p>
            <div class="upload-progress">
              <div class="progress-bar">
                <div class="progress-fill processing-anim"></div>
              </div>
            </div>
            <p class="split-current-desc">
              <template v-for="(step, idx) in splitSteps" :key="idx">
                <span v-if="step.status === 'doing'">{{ step.label }}：{{ step.desc }}</span>
              </template>
            </p>
          </template>

          <!-- 错误信息 -->
          <div v-if="splitError" class="split-error">
            <span>{{ splitError }}</span>
            <div class="split-error-actions">
              <button class="btn btn-sm btn-primary" @click="startSplitAnalysis" title="重试">重试</button>
              <button class="btn btn-sm btn-default" @click="splitError = ''">关闭</button>
            </div>
          </div>

          <!-- 结果列表 -->
          <template v-if="splitState === 'done' && !splitDoing">
            <p class="modal-desc" style="margin-top:0">已生成 {{ splitMaterials.length }} 个素材片段 ✓</p>
            <div v-if="splitMaterials.length === 0" class="empty-hint">无素材片段</div>
            <div v-else class="split-list">
              <div v-for="(m, idx) in splitMaterials" :key="m.id" class="split-item">
                <span class="split-order">{{ idx + 1 }}</span>
                <div class="split-preview">
                  <video :src="`/api/materials/${m.id}/file`" controls preload="metadata"
                    class="split-video-preview"
                    @mouseenter="hoverPlay($event)" @mouseleave="hoverPause($event)"></video>
                </div>
                <div class="split-info">
                  <span v-if="m.filename && m.filename.startsWith('seg_') === false" class="split-title">{{ m.filename }}</span>
                  <span class="split-time">{{ m.start_time?.toFixed(1) || '0' }}s - {{ m.end_time?.toFixed(1) || '0' }}s</span>
                  <span class="split-content">{{ truncate(m.content, 80) }}</span>
                </div>
                <button class="btn btn-sm btn-danger" @click="deleteSplitMaterial(m)" title="删除">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </div>
            </div>
          </template>
        </template>

        <!-- ────────── 手动分割 ────────── -->
        <template v-if="splitMode === 'manual' && !splitStarted">
          <div class="manual-split-body">
            <div class="manual-split-top">
              <!-- 视频播放器 -->
              <div class="manual-player-wrap">
                <video ref="manualVideoEl" :src="`/api/videos/${splitVideoRef?.id}/file`"
                  @timeupdate="onManualTimeUpdate" @loadedmetadata="onManualLoaded"
                  controls class="manual-player"></video>
              </div>

              <!-- 小工具窗口 -->
              <div class="manual-toolbox">
                <div class="toolbox-title">分割工具</div>

                <button class="toolbox-btn toolbox-btn-primary" @click="addSplitPoint"
                  :disabled="splitCurrentTime <= 0 || splitCurrentTime >= videoDuration">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  在当前点分割
                </button>

                <button class="toolbox-btn toolbox-btn-default" @click="clearSplitPoints"
                  :disabled="splitPoints.length === 0">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#374151" stroke-width="2.5"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  清除所有
                </button>

                <button class="toolbox-btn toolbox-btn-save" @click="startManualCut"
                  :disabled="splitDoing || splitSegments.length === 0">
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                  保存分割（{{ splitSegments.length }} 段）
                </button>
                <label class="toolbox-checkbox">
                  <input type="checkbox" v-model="splitExtractText" />
                  提取文案
                </label>
                <label class="toolbox-checkbox">
                  <input type="checkbox" v-model="splitRemoveAudio" />
                  去除音频
                </label>
              </div>
            </div>

            <!-- 时间轴 -->
            <div class="manual-timeline-wrap">
              <div class="manual-timeline" ref="manualTimelineEl" @click="onTimelineClick">
                <div class="manual-timeline-bg"></div>
                <!-- 分割点标记 -->
                <div v-for="(pt, idx) in splitPoints" :key="idx" class="manual-marker"
                  :style="{ left: (pt / videoDuration * 100) + '%' }"
                  @click.stop="removeSplitPoint(idx)">
                  <span class="manual-marker-line"></span>
                  <span class="manual-marker-label">{{ formatSplitTime(pt) }}</span>
                </div>
                <!-- 播放头 -->
                <div class="manual-playhead" :style="{ left: (splitCurrentTime / videoDuration * 100) + '%' }">
                  <span class="manual-playhead-head"></span>
                </div>
              </div>
              <div class="manual-timeline-time">
                <span>{{ formatSplitTime(0) }}</span>
                <span>{{ formatSplitTime(videoDuration) }}</span>
              </div>
            </div>

            <!-- 分段列表 -->
            <div v-if="splitSegments.length > 0" class="manual-segments">
              <div class="manual-segments-header">
                <span class="seg-h-order">#</span>
                <span class="seg-h-title">标题</span>
                <span class="seg-h-range">时间范围</span>
                <span class="seg-h-dur">时长</span>
                <span class="seg-h-text">文本（留空则自动识别）</span>
              </div>
              <div v-for="(seg, idx) in splitSegments" :key="idx" class="manual-segment-row">
                <span class="seg-order">{{ idx + 1 }}</span>
                <input class="seg-title-input" v-model="seg.title" placeholder="片段标题" />
                <span class="seg-range">{{ formatSplitTime(seg.start) }} - {{ formatSplitTime(seg.end) }}</span>
                <span class="seg-dur">{{ (seg.end - seg.start).toFixed(1) }}s</span>
                <input class="seg-text-input" v-model="seg.text" placeholder="留空自动识别文本" />
                <button class="btn btn-sm btn-icon" @click="removeSegmentSplit(idx)" title="移除">
                  <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>
            </div>
          </div>
        </template>

        <!-- 手动分割进行中 -->
        <template v-if="splitMode === 'manual' && splitDoing">
          <p class="modal-desc" style="margin-top:0">{{ splitDoingText }}</p>
          <div class="upload-progress">
            <div class="progress-bar">
              <div class="progress-fill processing-anim"></div>
            </div>
          </div>
        </template>

        <!-- 手动分割错误 -->
        <div v-if="splitError" class="split-error">
          <span>{{ splitError }}</span>
          <div class="split-error-actions">
            <button class="btn btn-sm btn-primary" @click="splitError = ''">关闭</button>
          </div>
        </div>

        <!-- 手动分割结果 -->
        <template v-if="splitMode === 'manual' && splitState === 'done' && !splitDoing">
          <p class="modal-desc" style="margin-top:0">已生成 {{ splitMaterials.length }} 个素材片段 ✓</p>
          <div v-if="splitMaterials.length === 0" class="empty-hint">无素材片段</div>
          <div v-else class="split-list">
            <div v-for="(m, idx) in splitMaterials" :key="m.id" class="split-item">
              <span class="split-order">{{ idx + 1 }}</span>
              <div class="split-preview">
                <video :src="`/api/materials/${m.id}/file`" controls preload="metadata"
                  class="split-video-preview"
                  @mouseenter="hoverPlay($event)" @mouseleave="hoverPause($event)"></video>
              </div>
              <div class="split-info">
                  <span v-if="m.filename && m.filename.startsWith('seg_') === false" class="split-title">{{ m.filename }}</span>
                <span class="split-time">{{ m.start_time?.toFixed(1) || '0' }}s - {{ m.end_time?.toFixed(1) || '0' }}s</span>
                <span class="split-content">{{ truncate(m.content, 80) }}</span>
              </div>
              <button class="btn btn-sm btn-danger" @click="deleteSplitMaterial(m)" title="删除">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script src="./VideoManager.js"></script>

<style src="./VideoManager.css" scoped></style>
