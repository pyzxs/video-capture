<template>
  <div class="auto-wrapper">
    <!-- ===== HEADER ===== -->
    <header class="auto-header">
      <div class="header-left">
        <button class="header-back-btn" @click="goBack" title="返回">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        </button>
        <span class="header-brand">智能混剪</span>
      </div>
      <div class="header-right">
        <button class="btn-search" @click="searchMaterials" :disabled="!autoForm.description || searching">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          {{ searching ? '检索中...' : '检索素材' }}
        </button>
        <button class="btn-generate" @click="startAuto" :disabled="!autoForm.description || autoProcessing">
          <svg v-if="!autoProcessing" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          <template v-if="autoProcessing">生成中...</template>
          <template v-else>开始生成</template>
        </button>
      </div>
    </header>

    <!-- ===== BODY ===== -->
    <div class="auto-body">
      <!-- Left: Toolbar -->
      <aside class="auto-toolbar">
        <div class="toolbar-group">
          <label class="toolbar-label">扩写</label>
          <label class="expand-toggle" :class="{ on: !autoForm.skipExpand }" title="开启后由大模型自动扩写脚本">
            <span class="expand-toggle-track">
              <span class="expand-toggle-thumb"></span>
            </span>
            <input type="checkbox" :checked="!autoForm.skipExpand" @change="autoForm.skipExpand = !$event.target.checked" class="expand-toggle-input" />
          </label>
        </div>

        <div class="toolbar-group">
          <label class="toolbar-label">生成批次</label>
          <input type="number" v-model.number="autoForm.batchCount" class="toolbar-input" min="1" @change="autoForm.batchCount = Math.max(1, Math.min(50, autoForm.batchCount || 1))" />
        </div>

        <div class="toolbar-group">
          <label class="toolbar-label">画面比率</label>
          <select v-model="autoForm.ratioIdx" class="toolbar-select">
            <option value="">默认</option>
            <option value="0">1920×1080 (16:9)</option>
            <option value="1">1280×720 (16:9)</option>
            <option value="2">1080×1920 (9:16) 抖音</option>
            <option value="3">720×1280 (9:16)</option>
            <option value="4">540×960 (9:16)</option>
            <option value="5">1080×2340 全面屏</option>
            <option value="6">1080×1350 (4:5)</option>
            <option value="7">1080×1440 (3:4)</option>
            <option value="8">1080×1080 (1:1)</option>
            <option value="9">640×640 (1:1)</option>
            <option value="10">1920×960 (2:1)</option>
            <option value="11">1440×1080 (4:3)</option>
          </select>
        </div>

        <div class="toolbar-group">
          <label class="toolbar-label">默认音色</label>
          <select v-model="autoForm.voice" class="toolbar-select">
            <option value="">系统默认</option>
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
        </div>

        <div class="toolbar-group">
          <label class="toolbar-label">背景音频</label>
          <div class="toolbar-audio-row">
            <select v-model="autoForm.audioMaterialId" class="toolbar-select toolbar-audio-select" @focus="loadAudioMaterials">
              <option value="">无</option>
              <option v-for="m in audioMaterials" :key="m.id" :value="m.id">{{ m.filename || '音频 ' + m.id }}</option>
            </select>
            <button
              class="toolbar-audio-play-btn"
              :class="{ playing: playingAudioId === autoForm.audioMaterialId }"
              :disabled="!autoForm.audioMaterialId"
              @click="toggleAudioPreview(autoForm.audioMaterialId)"
              :title="playingAudioId === autoForm.audioMaterialId ? '停止' : '试听'"
            >
              <svg v-if="playingAudioId !== autoForm.audioMaterialId" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
            </button>
          </div>
        </div>

        <audio ref="audioPlayer" @ended="onAudioEnded" style="display:none"></audio>

        <div class="toolbar-divider"></div>

        <button class="toolbar-ai-btn" :class="{ active: showChat }" @click="toggleChat" :title="showChat ? '关闭 AI 助手' : 'AI 辅助生成脚本'">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            <circle cx="12" cy="16" r="1"/>
          </svg>
          <span>AI 助手</span>
        </button>
      </aside>

      <!-- Center: Main Form -->
      <div class="auto-main-panel">
        <p class="auto-desc">输入描述，智能体自动扩写脚本、检索素材、拼接并配音生成混剪视频。</p>

        <!-- Description Section -->
        <div class="auto-card">
          <div class="auto-card-header">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            <span>描述</span>
          </div>
          <div class="auto-card-body">
            <div class="md-editor">
              <div class="md-toolbar">
                <button type="button" class="md-btn" @click="mdInsert('**', '**')" title="粗体"><strong>B</strong></button>
                <button type="button" class="md-btn" @click="mdInsert('*', '*')" title="斜体"><em>I</em></button>
                <button type="button" class="md-btn" @click="mdInsert('## ', '')" title="标题">H</button>
                <button type="button" class="md-btn" @click="mdInsert('- ', '')" title="列表">•</button>
                <button type="button" class="md-btn" @click="mdLink" title="链接">🔗</button>
                <span class="md-sep"></span>
                <button type="button" class="md-btn" :class="{ active: showDescPreview }" @click="showDescPreview = !showDescPreview">
                  {{ showDescPreview ? '编辑' : '预览' }}
                </button>
              </div>
              <textarea v-if="!showDescPreview" ref="mdTextarea" v-model="autoForm.description" rows="8" class="md-textarea" placeholder="描述你想生成的视频内容，如：春日公园里孩子们在放风筝..."></textarea>
              <div v-else class="md-preview" v-html="renderMarkdown(autoForm.description)"></div>
            </div>
          </div>
        </div>

        <!-- Search Results Section -->
        <div v-if="searchResults" class="auto-card">
          <div class="auto-card-header">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <span>检索结果（{{ searchResults.materials?.length || 0 }} 个素材）</span>
          </div>
          <div class="auto-card-body no-padding">
            <div v-if="searchResults.materials?.length" class="search-table-wrap">
              <table class="search-table">
                <thead>
                  <tr>
                    <th class="scol-idx">#</th>
                    <th class="scol-content">内容</th>
                    <th class="scol-time">时间段</th>
                    <th class="scol-actions">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(m, idx) in searchResults.materials" :key="m.material_id || idx">
                    <td class="scol-idx"><span class="search-mat-idx">{{ idx + 1 }}</span></td>
                    <td class="scol-content" :title="m.content">{{ truncate(m.content, 60) }}</td>
                    <td class="scol-time">{{ m.start_time?.toFixed(1) }}s - {{ m.end_time?.toFixed(1) }}s</td>
                    <td class="scol-actions">
                      <button class="mat-action-btn" @click="moveSearchMaterial(idx, -1)" :disabled="idx === 0" title="上移">↑</button>
                      <button class="mat-action-btn" @click="moveSearchMaterial(idx, 1)" :disabled="idx === searchResults.materials.length - 1" title="下移">↓</button>
                      <button class="mat-action-btn mat-action-del" @click="removeSearchMaterial(idx)" title="删除">✕</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="search-empty">未匹配到素材，请尝试修改描述内容</div>
          </div>
        </div>

        <!-- Processing Progress -->
        <div v-if="autoProcessing" class="auto-card auto-progress-card">
          <div class="auto-card-body">
            <div class="progress-header">
              <div class="progress-spinner"></div>
              <span v-if="autoProgress.total === 0">LLM 扩写 → 检索素材 → 拼接 → 配音，请稍候...</span>
              <span v-else>生成中 {{ autoProgress.current }} / {{ autoProgress.total }}</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: autoProgress.total ? (autoProgress.current / autoProgress.total * 100) + '%' : '30%', animation: autoProgress.total ? 'none' : 'progress-indeterminate 1.5s ease infinite' }"></div>
            </div>
            <!-- Generated video list -->
            <div v-if="autoGeneratedVideos.length > 0" class="auto-gen-list">
              <div class="auto-gen-list-header">已生成混剪 ({{ autoGeneratedVideos.length }})</div>
              <div class="auto-gen-list-body">
                <div v-for="(v, idx) in autoGeneratedVideos" :key="v.id" class="auto-gen-item">
                  <div class="auto-gen-player">
                    <video
                      v-if="playingGenId === v.id"
                      :ref="el => setGenVideoRef(v.id, el)"
                      :src="apiUrl(`/api/generated/${v.id}/download`)"
                      class="auto-gen-video"
                      autoplay
                      controls
                      @ended="onGenVideoEnded(v.id)"
                    ></video>
                    <div v-else class="auto-gen-thumb-wrap" @click="playGeneratedVideo(v)">
                      <img v-if="v.thumbnail" :src="v.thumbnail" class="auto-gen-thumb" />
                      <div v-else class="auto-gen-thumb auto-gen-thumb-empty"></div>
                      <div class="auto-gen-play-icon">
                        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                      </div>
                    </div>
                  </div>
                  <div class="auto-gen-info">
                    <div class="auto-gen-title">{{ v.title || '未命名' }}</div>
                    <div class="auto-gen-meta">{{ v.duration ? v.duration.toFixed(1) + 's' : '' }}{{ v.frame_width ? ' · ' + v.frame_width + '×' + v.frame_height : '' }}</div>
                  </div>
                  <div class="auto-gen-actions">
                    <button class="auto-gen-btn auto-gen-btn-play" @click="playGeneratedVideo(v)" :title="playingGenId === v.id ? '停止' : '播放'">
                      <svg v-if="playingGenId !== v.id" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                      <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                    </button>
                    <button class="auto-gen-btn auto-gen-btn-del" @click="deleteGeneratedVideo(v, idx)" title="删除">
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: AI Chat Panel -->
      <div v-if="showChat" class="auto-chat-panel">
        <div class="chat-panel-header">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            <circle cx="12" cy="16" r="1"/>
          </svg>
          <span>智能体助手</span>
          <button class="chat-close-btn" @click="showChat = false" title="关闭">✕</button>
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
              <button class="chat-apply-btn" @click="applyChatResult(msg.content)" title="应用到脚本">应用到脚本</button>
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
            <button class="chat-send-btn" @click="sendChat" :disabled="!chatInput.trim() || chatLoading || !selectedAgentId">发送</button>
            <button class="chat-clear-btn" @click="clearChat">清空</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script src="./AutoMashup.js"></script>

<style src="./AutoMashup.css" scoped></style>
