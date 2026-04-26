<template>
<div class="view-container">
    <div class="panel">
      <div class="view-header">
        <h2>混剪视频管理</h2>
        <div class="header-actions">
          <label class="select-all-label" v-if="list.length > 0" title="全选">
            <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" />
          </label>
          <button v-if="selectedIds.size > 0" class="btn btn-sm btn-default" @click="showBatchMoveFolder">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            移动到文件夹 ({{ selectedIds.size }})
          </button>
          <button v-if="selectedIds.size > 0" class="btn btn-sm btn-danger" @click="batchDeleteGens">
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
          <input v-model="searchQuery" placeholder="搜索标题..." class="search-input" @input="page=1; loadList()" />
          <button class="btn btn-primary" @click="openManual" title="手动混剪">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            手动混剪
          </button>
          <button class="btn btn-info" @click="openAuto" title="自动混剪">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>
            自动混剪
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else>
      <div v-if="list.length === 0" class="empty">暂无数据</div>
      <template v-else>
        <div v-if="viewMode === 'card'" class="video-grid">
          <div v-for="g in list" :key="g.id" class="video-card" :class="{ 'card-selected': selectedIds.has(g.id) }">
            <div class="card-top">
              <label class="card-checkbox" @click.stop>
                <input type="checkbox" :checked="selectedIds.has(g.id)" @change="toggleSelect(g.id)" />
              </label>
              <span class="card-id">#{{ g.id }}</span>
              <span class="status-badge" :class="g.status">{{ statusText(g.status) }}</span>
            </div>
            <div class="card-video">
              <video
                v-if="g.output_filepath"
                :src="`/api/generated/${g.id}/download`"
                controls
                preload="metadata"
                class="video-player-card"
                @mouseenter="hoverPlay($event)"
                @mouseleave="hoverPause($event)"
              ></video>
              <div v-else class="card-video-placeholder">
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                <span>尚未生成</span>
              </div>
            </div>
            <div class="card-title">{{ g.title || `混剪 #${g.id}` }}</div>
            <div class="card-meta">
              <span v-if="g.duration" class="meta-item">{{ formatDuration(g.duration) }}</span>
              <span v-if="g.frame_width" class="meta-item">{{ g.frame_width }}x{{ g.frame_height }}</span>
              <span class="meta-item">{{ g.material_count }} 素材</span>
            </div>
            <div class="card-script" :title="g.script">{{ truncate(g.script, 60) || '-' }}</div>
            <div class="card-actions">
              <button class="btn btn-sm btn-primary" @click="openEdit(g)" title="编辑">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
              </button>
              <button class="btn btn-sm btn-danger" @click="deleteGen(g)" title="删除">
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
                <th class="list-col-name">标题</th>
                <th class="list-col-meta">素材数</th>
                <th class="list-col-meta">分辨率</th>
                <th class="list-col-meta">时长</th>
                <th class="list-col-meta">文件夹</th>
                <th class="list-col-status">状态</th>
                <th class="list-col-script">脚本</th>
                <th class="list-col-time">创建时间</th>
                <th class="list-col-actions">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="g in list" :key="g.id" :class="{ 'row-selected': selectedIds.has(g.id) }">
                <td class="list-col-chk"><label class="card-checkbox"><input type="checkbox" :checked="selectedIds.has(g.id)" @change="toggleSelect(g.id)" /></label></td>
                <td class="list-col-id">#{{ g.id }}</td>
                <td class="list-col-name" :title="g.title">{{ g.title || `混剪 #${g.id}` }}</td>
                <td class="list-col-meta">{{ g.material_count }}</td>
                <td class="list-col-meta">{{ g.frame_width ? g.frame_width+'x'+g.frame_height : '-' }}</td>
                <td class="list-col-meta">{{ formatDuration(g.duration) }}</td>
                <td class="list-col-meta">{{ folderMap[g.folder_id] || '-' }}</td>
                <td class="list-col-status"><span class="status-badge" :class="g.status">{{ statusText(g.status) }}</span></td>
                <td class="list-col-script" :title="g.script">{{ truncate(g.script, 60) || '-' }}</td>
                <td class="list-col-time">{{ formatTime(g.created_at) }}</td>
                <td class="list-col-actions">
                  <button class="btn btn-xs btn-primary" @click="openEdit(g)" title="编辑">编辑</button>
                  <button class="btn btn-xs btn-success" @click="genVideo(g)" :disabled="g.status==='processing'" title="生成">生成</button>
                  <button class="btn btn-xs btn-danger" @click="deleteGen(g)" title="删除">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>

    <Pagination :page="page" :total="total" :page-size="pageSize" @change="onPageChange" />

    <!-- 自动混剪弹窗 -->
    <div v-if="showAutoDialog" class="modal-overlay" @click.self="closeAuto">
      <div class="modal modal-wide modal-xwide modal-autogen">
        <div class="modal-header">
          <h3>自动混剪</h3>
          <div class="modal-actions">
            <button class="btn btn-sm btn-info" @click="searchMaterials" :disabled="!autoForm.description || searching" title="检索素材">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            </button>
            <button class="btn btn-sm btn-primary" @click="startAuto" :disabled="!autoForm.description || autoProcessing" title="开始合成">
              <svg v-if="!autoProcessing" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              <span v-else>合成中</span>
            </button>
            <button class="btn btn-default" @click="closeAuto" :disabled="autoProcessing" title="取消">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        <div class="auto-layout">
          <div class="auto-form">
            <p class="modal-desc">标题和描述，智能体自动扩写脚本、检索素材、拼接并配音生成混剪视频。</p>
            <div class="form">
              <label>标题
                <input v-model="autoForm.title" placeholder="混剪标题" />
              </label>
              <label>
                <div class="label-row">
                  <span>描述 / 脚本</span>
                  <div class="label-row-actions">
                    <select v-model="autoForm.ratioIdx" class="filter-select ratio-select">
                      <option value="">请选择画面比率</option>
                      <option value="0">1920×1080 (16:9)</option>
                      <option value="1">1280×720 (16:9)</option>
                      <option value="2">1080×1920 (9:16) 抖音</option>
                      <option value="3">720×1280 (9:16) 竖屏</option>
                      <option value="4">540×960 (9:16) 竖屏标清</option>
                      <option value="5">1080×2340 (19.5:9) 全面屏</option>
                      <option value="6">1080×1350 (4:5) Instagram</option>
                      <option value="7">1080×1440 (3:4) 小红书</option>
                      <option value="8">1080×1080 (1:1) 方屏</option>
                      <option value="9">640×640 (1:1) 方屏标清</option>
                      <option value="10">1920×960 (2:1) 宽屏</option>
                      <option value="11">1440×1080 (4:3)</option>
                    </select>
                    <select v-model="autoForm.voice" class="filter-select voice-select">
                      <option value="">默认音色</option>
                      <option value="FunAudioLLM/CosyVoice2-0.5B:alex">亚力克斯</option>
                      <option value="FunAudioLLM/CosyVoice2-0.5B:anna">安娜</option>
                      <option value="FunAudioLLM/CosyVoice2-0.5B:bella">贝拉</option>
                      <option value="FunAudioLLM/CosyVoice2-0.5B:benjamin">本杰明</option>
                      <option value="FunAudioLLM/CosyVoice2-0.5B:charles">查尔斯</option>
                      <option value="FunAudioLLM/CosyVoice2-0.5B:claire">克莱尔</option>
                      <option value="FunAudioLLM/CosyVoice2-0.5B:david">大卫</option>
                      <option value="FunAudioLLM/CosyVoice2-0.5B:diana">黛安娜</option>
                      <option value="FunAudioLLM/CosyVoice2-0.5B:longfei">龙飞</option>
                    </select>
                    <button class="agent-btn" @click="toggleChat" :title="showChat ? '关闭 AI 助手' : 'AI 辅助生成脚本'">
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
                    <button type="button" class="md-btn" @click="showDescPreview = !showDescPreview">
                      {{ showDescPreview ? '编辑' : '预览' }}
                    </button>
                  </div>
                  <textarea v-if="!showDescPreview" ref="mdTextarea" v-model="autoForm.description" rows="12" class="md-textarea" placeholder="描述你想生成的视频内容，如：春日公园里孩子们在放风筝..."></textarea>
                  <div v-else class="md-preview" v-html="renderMarkdown(autoForm.description)"></div>
                </div>
              </label>

            </div>

            <!-- 检索结果 -->
            <div v-if="searchResults" class="search-results">
              <div class="search-results-header">
                <strong>检索结果（{{ searchResults.materials?.length || 0 }} 个素材）</strong>
                <span class="search-script-preview" :title="searchResults.script">{{ truncate(searchResults.script, 100) }}</span>
              </div>
              <div v-if="searchResults.materials?.length" class="search-mat-list">
                <div v-for="(m, idx) in searchResults.materials" :key="m.material_id || idx" class="search-mat-item">
                  <span class="search-mat-idx">{{ idx + 1 }}</span>
                  <span class="search-mat-content" :title="m.content">{{ truncate(m.content, 60) }}</span>
                  <span class="search-mat-time">{{ m.start_time?.toFixed(1) }}s-{{ m.end_time?.toFixed(1) }}s</span>
                  <span class="search-mat-actions">
                    <button class="mat-move-btn" @click="moveSearchMaterial(idx, -1)" :disabled="idx === 0" title="上移">↑</button>
                    <button class="mat-move-btn" @click="moveSearchMaterial(idx, 1)" :disabled="idx === searchResults.materials.length - 1" title="下移">↓</button>
                    <button class="mat-del-btn" @click="removeSearchMaterial(idx)" title="删除">✕</button>
                  </span>
                </div>
              </div>
              <div v-else class="search-empty">未匹配到素材</div>
            </div>

            <div v-if="autoProcessing" class="upload-progress">
              <div class="progress-bar">
                <div class="progress-fill processing-anim"></div>
              </div>
              <span>LLM 扩写 → 检索素材 → 拼接 → 配音，请稍候...</span>
            </div>
          </div>

          <!-- AI 聊天面板 -->
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
                选择智能体后，发送消息即可与智能体对话生成或改写脚本
              </div>
              <div v-for="msg in chatMessages" :key="msg.id" :class="['chat-msg', msg.role]">
                <div class="chat-avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
                <div class="chat-bubble">{{ msg.content }}</div>
                <div v-if="msg.role === 'assistant'" class="chat-msg-actions">
                  <button class="btn btn-sm btn-default" @click="applyChatResult(msg.content)" title="应用到脚本">应用到脚本</button>
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
  </div>
</template>

<script src="./MashupManager.js"></script>

<style src="./MashupManager.css" scoped></style>
