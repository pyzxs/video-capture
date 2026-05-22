<template>
<div class="view-container">
    <div class="panel">
      <div class="view-header">
        <h2>素材管理</h2>
        <div class="header-actions">
          <label class="select-all-label" v-if="materials.length > 0" title="全选">
            <input type="checkbox" :checked="isAllSelected" @change="toggleSelectAll" />
          </label>
          <button v-if="selectedIds.size > 0" class="btn btn-sm btn-default" @click="showBatchMoveFolder">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            移动 ({{ selectedIds.size }})
          </button>
          <button v-if="selectedIds.size > 0" class="btn btn-sm btn-danger" @click="batchDelete">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            批量删除 ({{ selectedIds.size }})
          </button>
          <button v-if="selectedIds.size > 0" class="btn btn-sm btn-success" @click="exportSelected" :disabled="exporting">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            {{ exporting ? '导出中...' : `导出 (${selectedIds.size})` }}
          </button>
          <div class="view-mode-toggle">
            <button class="vm-btn" :class="{ active: viewMode === 'card' }" @click="viewMode = 'card'" title="卡片视图">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
            </button>
            <button class="vm-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" title="列表视图">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
          </div>
          <select v-model="typeFilter" class="filter-select" @change="page=1; loadMaterials()">
            <option value="">全部类型</option>
            <option value="video">视频</option>
            <option value="image">图片</option>
            <option value="audio">音频</option>
          </select>
          <input v-model="searchQuery" placeholder="搜索素材内容..." class="search-input" @input="page=1; loadMaterials()" />
          <button class="btn btn-primary" @click="openCreate" title="新增素材">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else>
      <div v-if="materials.length === 0" class="empty">暂无数据</div>
      <div v-else-if="viewMode === 'card'" class="material-grid">
        <div v-for="m in materials" :key="m.id" class="material-card" :class="{ 'card-selected': selectedIds.has(m.id) }">
          <div class="card-top">
            <label class="card-checkbox" @click.stop>
              <input type="checkbox" :checked="selectedIds.has(m.id)" @change="toggleSelect(m.id)" />
            </label>
            <span class="card-id">#{{ m.id }}</span>
            <span class="tag">{{ m.type }}</span>
          </div>

          <div class="card-content">
            <p class="card-text">{{ m.content || '-' }}</p>
          </div>

          <div v-if="(m.type === 'video' || m.type === 'scene') && m.filepath" class="card-video">
            <template v-if="activeVideos.has(m.id)">
              <video
                :ref="el => setVideoRef(m.id, el)"
                :src="$apiUrl(`/api/materials/${m.id}/file`)"
                controls
                preload="auto"
                class="material-player"
                @mouseenter="hoverPlay($event)"
                @mouseleave="hoverPause($event)"
                @loadeddata="onVideoLoaded($event)"
              ></video>
            </template>
            <div v-else class="thumbnail-wrap" @click="activateVideo(m.id)">
              <img
                v-if="m.thumbnail"
                :src="m.thumbnail"
                class="material-thumbnail"
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
          <div v-else-if="m.type === 'image' && m.filepath" class="card-image">
            <img :src="$apiUrl(`/api/materials/${m.id}/file`)" class="material-img" />
          </div>
          <div v-else-if="m.type === 'audio' && m.filepath" class="card-audio">
            <audio :src="$apiUrl(`/api/materials/${m.id}/file`)" controls preload="none" class="material-audio" @play="onAudioPlay($event)"></audio>
          </div>
          <div v-else-if="m.type === 'text'" class="card-text-preview">
            <div class="md-preview-sm" v-html="renderMarkdown(m.content)"></div>
          </div>

          <div class="card-meta">
            <span v-if="m.frame_width" class="meta-item">{{ m.frame_width }}x{{ m.frame_height }}</span>
          </div>

          <div class="card-actions">
            <button class="btn btn-sm btn-primary" @click="openEdit(m)" title="编辑">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
            </button>
            <button class="btn btn-sm btn-default" @click="showMoveFolder(m, 'material')" title="移动">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            </button>
            <button class="btn btn-sm btn-info" @click="exportItem(m.id)" :disabled="exporting" title="导出">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </button>
            <button class="btn btn-sm btn-danger" @click="deleteMaterial(m)" title="删除">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
            <button v-if="m.type === 'video'" class="btn btn-sm btn-warning" @click="eraseSubtitle(m)" :disabled="erasingMaterialId === m.id" title="擦除字幕">
              <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><line x1="7" y1="10" x2="17" y2="10"/><line x1="7" y1="14" x2="13" y2="14"/><line x1="2" y1="2" x2="22" y2="22"/></svg>
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
              <th>类型</th>
              <th class="list-col-name">内容</th>
              <th class="list-col-meta">分辨率</th>
              <th class="list-col-meta">文件夹</th>
              <th class="list-col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in materials" :key="m.id" :class="{ 'row-selected': selectedIds.has(m.id) }">
              <td class="list-col-chk"><label class="card-checkbox"><input type="checkbox" :checked="selectedIds.has(m.id)" @change="toggleSelect(m.id)" /></label></td>
              <td class="list-col-id">#{{ m.id }}</td>
              <td><span class="tag">{{ m.type }}</span></td>
              <td class="list-col-name" :title="m.content">{{ truncateFilename(m.content) }}</td>
              <td class="list-col-meta">{{ m.frame_width && m.frame_height ? `${m.frame_width}x${m.frame_height}` : '-' }}</td>
              <td class="list-col-meta">{{ folderMap[m.folder_id] || '-' }}</td>
              <td class="list-col-actions">
                <button class="btn btn-xs btn-primary" @click="openEdit(m)" title="编辑">编辑</button>
                <button class="btn btn-xs btn-default" @click="showMoveFolder(m, 'material')" title="移动">移动</button>
                <button class="btn btn-xs btn-info" @click="exportItem(m.id)" :disabled="exporting" title="导出">导出</button>
                <button v-if="m.type === 'video'" class="btn btn-xs btn-warning" @click="eraseSubtitle(m)" :disabled="erasingMaterialId === m.id" title="擦除字幕">擦除</button>
                <button class="btn btn-xs btn-danger" @click="deleteMaterial(m)" title="删除">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <Pagination :page="page" :total="total" :page-size="pageSize" @change="onPageChange" />

    <!-- 新增/编辑弹窗 -->
    <div v-if="showDialog" class="modal-overlay">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editing ? '编辑素材' : '新增素材' }}</h3>
          <div class="modal-actions">
            <button class="btn btn-primary" @click="saveMaterial" :disabled="saving" title="保存">
              <svg v-if="!saving" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              <span v-else>{{ '保存中...' }}</span>
            </button>
            <button class="btn btn-default" @click="closeDialog" title="取消">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </div>
        </div>
        <div class="form">

          <template v-if="editing">
            <!-- 编辑模式：类型只读，内容使用 markdown 编辑器 -->
            <label>类型 <span class="tag">{{ form.type }}</span></label>
            <label>内容文本
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
                <textarea v-if="!showEditPreview" ref="mdTextarea" v-model="form.content" rows="10" class="md-textarea" placeholder="输入 Markdown 内容..."></textarea>
                <div v-else class="md-preview" v-html="renderMarkdown(form.content)"></div>
              </div>
            </label>
          </template>

          <template v-else>
            <!-- 新增模式 -->
            <label class="type-label">类型 <select v-model="form.type"><option>video</option><option>image</option><option>audio</option></select></label>
            <div v-if="form.type === 'audio'" class="audio-mode-toggle-inline">
              <span class="audio-mode-label">语音素材</span>
              <label class="radio-inline"><input type="radio" v-model="audioMode" value="upload" /> 上传</label>
              <label class="radio-inline"><input type="radio" v-model="audioMode" value="synthesize" /> 合成</label>
            </div>

            <!-- Video: upload zone + content textarea -->
            <template v-if="form.type === 'video'">
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
              <label>内容文本 <textarea v-model="form.content" rows="3"></textarea></label>
            </template>

            <!-- Image: upload zone + content textarea -->
            <template v-if="form.type === 'image'">
              <div class="upload-zone" @drop.prevent="onDrop" @dragover.prevent
                   :class="{ 'drag-over': dragging }" @dragenter="dragging = true" @dragleave="dragging = false">
                <input ref="fileInput" type="file" accept=".png,.jpg,.jpeg,.gif,.webp,.bmp,.svg" hidden @change="onFileSelect" />
                <div v-if="!selectedFile" class="upload-placeholder" @click="$refs.fileInput.click()">
                  <span class="upload-icon">🖼️</span>
                  <span>点击选择图片文件，或拖拽到此处</span>
                  <span class="upload-hint">支持 png, jpg, gif, webp, bmp, svg</span>
                </div>
                <div v-else class="upload-preview">
                  <span class="file-name">{{ selectedFile.name }}</span>
                  <span class="file-size">{{ formatSize(selectedFile.size) }}</span>
                  <button class="btn btn-sm btn-default" @click="clearFile" title="重新选择">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                  </button>
                </div>
              </div>
              <label>描述文本 <textarea v-model="form.content" rows="3" placeholder="图片描述/文案..."></textarea></label>
            </template>

            <!-- Audio: upload OR synthesize -->
            <template v-if="form.type === 'audio'">
              <!-- Upload mode -->
              <template v-if="audioMode === 'upload'">
                <div class="upload-zone" @drop.prevent="onDrop" @dragover.prevent
                     :class="{ 'drag-over': dragging }" @dragenter="dragging = true" @dragleave="dragging = false">
                  <input ref="fileInput" type="file" accept=".mp3,.wav,.flac,.aac,.ogg,.m4a" hidden @change="onFileSelect" />
                  <div v-if="!selectedFile" class="upload-placeholder" @click="$refs.fileInput.click()">
                    <span class="upload-icon">🎵</span>
                    <span>点击选择音频文件，或拖拽到此处</span>
                    <span class="upload-hint">支持 mp3, wav, flac, aac, ogg, m4a</span>
                  </div>
                  <div v-else class="upload-preview">
                    <span class="file-name">{{ selectedFile.name }}</span>
                    <span class="file-size">{{ formatSize(selectedFile.size) }}</span>
                    <button class="btn btn-sm btn-default" @click="clearFile" title="重新选择">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
                    </button>
                  </div>
                </div>
                <label>内容文本 <textarea v-model="form.content" rows="2" placeholder="音频描述..."></textarea></label>
              </template>

              <!-- Synthesize mode -->
              <template v-if="audioMode === 'synthesize'">
                <div class="edit-layout">
                  <div class="edit-form">
                    <div class="form">
                      <label>
                        <div class="label-row">
                          <span>合成文案（Markdown）</span>
                          <div class="label-row-actions">
                            <button class="agent-btn" @click="toggleTtsChat" :title="showTtsChat ? '关闭 AI 助手' : 'AI 助手写文案'">
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
                            <button type="button" class="md-btn" @click="ttsMdInsert('**', '**')" title="粗体"><strong>B</strong></button>
                            <button type="button" class="md-btn" @click="ttsMdInsert('*', '*')" title="斜体"><em>I</em></button>
                            <button type="button" class="md-btn" @click="ttsMdInsert('## ', '')" title="标题">H</button>
                            <button type="button" class="md-btn" @click="ttsMdInsert('- ', '')" title="列表">•</button>
                            <button type="button" class="md-btn" @click="ttsMdLink" title="链接">🔗</button>
                            <span class="md-sep"></span>
                            <button type="button" class="md-btn" @click="showTtsPreview = !showTtsPreview">
                              {{ showTtsPreview ? '编辑' : '预览' }}
                            </button>
                          </div>
                          <textarea v-if="!showTtsPreview" ref="ttsMdTextarea" v-model="ttsText" rows="8" class="md-textarea" placeholder="输入或通过 AI 助手生成合成文案..."></textarea>
                          <div v-else class="md-preview" v-html="renderMarkdown(ttsText)"></div>
                        </div>
                      </label>
                      <div class="tts-voice-row" style="margin-top:8px">
                        <select v-model="ttsVoice" class="filter-select" style="flex:1">
                          <option value="">默认音色</option>
                          <option value="FunAudioLLM/CosyVoice2-0.5B:alex">Alex（亚力克斯）</option>
                          <option value="FunAudioLLM/CosyVoice2-0.5B:anna">Anna（安娜）</option>
                          <option value="FunAudioLLM/CosyVoice2-0.5B:bella">Bella（贝拉）</option>
                          <option value="FunAudioLLM/CosyVoice2-0.5B:benjamin">Benjamin（本杰明）</option>
                          <option value="FunAudioLLM/CosyVoice2-0.5B:charles">Charles（查尔斯）</option>
                          <option value="FunAudioLLM/CosyVoice2-0.5B:claire">Claire（克莱尔）</option>
                          <option value="FunAudioLLM/CosyVoice2-0.5B:david">David（大卫）</option>
                          <option value="FunAudioLLM/CosyVoice2-0.5B:diana">Diana（黛安娜）</option>
                          <option value="FunAudioLLM/CosyVoice2-0.5B:longfei">Longfei（龙飞）</option>
                        </select>
                        <button class="btn btn-primary" @click="ttsGenerate" :disabled="ttsBusy || !ttsText.trim()" style="white-space:nowrap">
                          {{ ttsBusy ? '合成中...' : '合成语音' }}
                        </button>
                      </div>
                      <label style="margin-top:8px">描述文本 <textarea v-model="form.content" rows="2" placeholder="素材描述（可选）..."></textarea></label>
                    </div>
                  </div>

                  <!-- AI Chat sidebar -->
                  <div v-if="showTtsChat" class="edit-chat-panel">
                    <div class="chat-panel-header">
                      <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                        <circle cx="12" cy="16" r="1"/>
                      </svg>
                      <span>智能体</span>
                      <button class="btn btn-sm btn-default" @click="showTtsChat = false" title="关闭">✕</button>
                    </div>
                    <div class="chat-agent-select">
                      <select v-model="ttsSelectedAgentId" class="agent-select" @change="onTtsAgentChange">
                        <option value="">选择智能体...</option>
                        <option v-for="a in ttsAgents" :key="a.id" :value="a.id">{{ a.name }}</option>
                      </select>
                    </div>
                    <div class="chat-messages" ref="ttsChatMessagesRef">
                      <div v-if="ttsChatMessages.length === 0" class="chat-empty-hint">
                        选择智能体后，发送消息即可让 AI 帮你写合成文案
                      </div>
                      <div v-for="msg in ttsChatMessages" :key="msg.id" :class="['chat-msg', msg.role]">
                        <div class="chat-avatar">{{ msg.role === 'user' ? '我' : 'AI' }}</div>
                        <div class="chat-bubble">{{ msg.content }}</div>
                        <div v-if="msg.role === 'assistant'" class="chat-msg-actions">
                          <button class="btn btn-sm btn-default" @click="applyTtsRewrite(msg.content)" title="应用到文案">应用到文案</button>
                        </div>
                      </div>
                      <div v-if="ttsChatLoading" class="chat-msg assistant">
                        <div class="chat-avatar">AI</div>
                        <div class="chat-bubble thinking">思考中...</div>
                      </div>
                    </div>
                    <div class="chat-footer">
                      <textarea
                        v-model="ttsChatInput"
                        @keydown.enter.exact.prevent="sendTtsChat"
                        placeholder="输入消息..."
                        rows="2"
                        class="chat-input-area"
                        :disabled="!ttsSelectedAgentId"
                      ></textarea>
                      <div class="chat-actions">
                        <button class="btn btn-primary btn-sm" @click="sendTtsChat" :disabled="!ttsChatInput.trim() || ttsChatLoading || !ttsSelectedAgentId">发送</button>
                        <button class="btn btn-default btn-sm" @click="clearTtsChat">清空</button>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </template>
          </template>

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

<script src="./MaterialManager.js"></script>

<style src="./MaterialManager.css" scoped></style>
