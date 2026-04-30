<template>
<div class="editor-wrapper">
    <!-- ===== HEADER ===== -->
    <header class="editor-header">
      <div class="header-left">
        <button class="header-back-btn" @click="goBack" title="返回">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        </button>
        <span class="header-brand">手动剪辑</span>
        <input v-model="form.title" class="header-title" placeholder="剪辑标题" />
        <span v-if="isEditMode" class="header-id">#{{ editId }}</span>
      </div>
      <div class="header-right">
        <button class="btn-save" @click="save" :disabled="saving">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
          {{ saving ? '保存中' : '保存' }}
        </button>
        <button v-if="isEditMode" class="btn-generate" @click="generate" :disabled="generating" title="合成">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          <template v-if="generating">生成中...</template>
        </button>
      </div>
    </header>

    <!-- ===== BODY ===== -->
    <div class="editor-body">
      <!-- ===== RESOURCES PANEL ===== -->
      <div class="resources-panel">
        <div class="menu-list">
          <div v-for="item in menuItems" :key="item.key" class="menu-item"
            :class="{ active: activeMenu === item.key }" @click="activeMenu = item.key; panelVisible = true">
            <span class="menu-icon" v-html="item.icon"></span>
            <span class="menu-label">{{ item.label }}</span>
          </div>
        </div>
        <div class="item-list" :class="{ collapsed: !panelVisible }">
          <div class="item-list-header">
            <span>{{ activeMenuLabel }}</span>
            <div class="view-toggle">
              <button class="view-btn" @click="togglePanel" :title="panelVisible ? '隐藏素材列表' : '显示素材列表'">
                <svg v-if="panelVisible" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
              </button>
              <button class="view-btn" :class="{ active: viewMode === 'grid' }" @click="viewMode = 'grid'" title="图标展示">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
              </button>
              <button class="view-btn" :class="{ active: viewMode === 'list' }" @click="viewMode = 'list'" title="列表展示">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
              </button>
            </div>
          </div>
          <div class="item-list-content" ref="matListRef" @scroll="onMatScroll">
            <!-- Local / Upload -->
            <template v-if="activeMenu === 'local'">
              <div class="upload-zone" @click="showUploadDialog = true">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                <span>上传素材</span>
              </div>
              <div class="mat-search-row">
                <input v-model="matSearch" class="resource-search" placeholder="搜索素材..." />
              </div>
              <div class="mat-folder-row">
                <select v-model="matFolderId" class="mat-folder-select" title="按文件夹筛选">
                  <option value="">全部文件夹</option>
                  <option v-for="f in matFolders" :key="f.id" :value="f.id">{{ f.name }}</option>
                </select>
              </div>
              <div class="resource-grid" :class="viewMode">
                <div v-for="m in localFilteredMaterials" :key="m.id" class="resource-item" :class="'r-' + viewMode"
                  draggable="true"
                  @dragstart="onResourceDragStart(m, $event)"
                  @click="addToTimeline(m)">
                  <div class="resource-thumb">
                    <img v-if="m.type === 'image'" :src="`/api/materials/${m.id}/file`" class="resource-img" />
                    <template v-else-if="m.type === 'video'">
                      <div class="video-thumb-wrap">
                        <video :src="`/api/materials/${m.id}/file`" preload="metadata" muted playsinline
                          class="video-mat-thumb" :class="{ playing: playingVideoId === m.id }"
                          :ref="el => { if (el) videoRefs[m.id] = el }"
                          @loadedmetadata="el => { el.currentTime = 0.01 }"
                          @ended="onVideoEnded(m.id)"
                          @click.stop></video>
                        <button class="play-overlay" @click.stop="toggleVideo(m)" :title="playingVideoId === m.id ? '停止' : '预览'">
                          <span class="play-icon-sm">
                            <svg v-if="playingVideoId !== m.id" viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><polygon points="8 5 19 12 8 19 8 5"/></svg>
                            <svg v-else viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                          </span>
                        </button>
                      </div>
                    </template>
                    <svg v-else-if="m.type === 'audio'" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
                    <svg v-else-if="m.type === 'text'" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>
                    <svg v-else viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                  </div>
                  <span class="resource-name" :title="truncate(m.content, 20)">{{ viewMode === 'grid' ? m.content : truncate(m.content, 10) }}</span>
                </div>
                <div v-if="localFilteredMaterials.length === 0" class="resource-empty">无匹配素材</div>
                <div v-if="localLoading" class="mat-loading">加载中...</div>
                <div v-else-if="!localHasMore && localMaterials.length > 0" class="mat-loading mat-loading-done">已加载全部</div>
              </div>
            </template>
            <!-- Video panel -->
            <template v-else-if="activeMenu === 'video'">
              <div class="upload-zone" @click="showUploadDialog = true">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                <span>上传视频</span>
              </div>
              <div class="resource-grid" :class="viewMode">
                <div v-for="m in videoMatItems" :key="m.id" class="resource-item" :class="'r-' + viewMode"
                  draggable="true"
                  @dragstart="onResourceDragStart(m, $event)"
                  @click="addToTimeline(m)">
                  <div class="resource-thumb">
                    <div class="video-thumb-wrap">
                      <video :src="`/api/materials/${m.id}/file`" preload="metadata" muted playsinline
                        class="video-mat-thumb" :class="{ playing: playingVideoId === m.id }"
                        :ref="el => { if (el) videoRefs[m.id] = el }"
                        @loadedmetadata="el => { el.currentTime = 0.01 }"
                        @ended="onVideoEnded(m.id)"
                        @click.stop></video>
                      <button class="play-overlay" @click.stop="toggleVideo(m)" :title="playingVideoId === m.id ? '停止' : '预览'">
                        <span class="play-icon-sm">
                          <svg v-if="playingVideoId !== m.id" viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><polygon points="8 5 19 12 8 19 8 5"/></svg>
                          <svg v-else viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                        </span>
                      </button>
                    </div>
                  </div>
                  <span class="resource-name" :title="truncate(m.content, 20)">{{ viewMode === 'grid' ? m.content : truncate(m.content, 10) }}</span>
                </div>
                <div v-if="videoMatItems.length === 0" class="resource-empty">无视频素材</div>
              </div>
            </template>
            <!-- Image panel -->
            <template v-else-if="activeMenu === 'image'">
              <div class="upload-zone" @click="showUploadDialog = true">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                <span>上传图片</span>
              </div>
              <div class="resource-grid" :class="viewMode">
                <div v-for="m in imageMatItems" :key="m.id" class="resource-item" :class="'r-' + viewMode"
                  draggable="true"
                  @dragstart="onResourceDragStart(m, $event)"
                  @click="addToTimeline(m)">
                  <div class="resource-thumb">
                    <img :src="`/api/materials/${m.id}/file`" class="resource-img" />
                  </div>
                  <span class="resource-name" :title="truncate(m.content, 20)">{{ viewMode === 'grid' ? m.content : truncate(m.content, 10) }}</span>
                </div>
                <div v-if="imageMatItems.length === 0" class="resource-empty">无图片素材</div>
              </div>
            </template>
            <!-- Audio panel -->
            <template v-else-if="activeMenu === 'audio'">
              <div class="upload-zone" @click="showUploadDialog = true">
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                <span>上传音频</span>
              </div>
              <div class="resource-grid" :class="viewMode">
                <div v-for="m in audioMatItems" :key="m.id" class="resource-item" :class="'r-' + viewMode"
                  draggable="true"
                  @dragstart="onResourceDragStart(m, $event)"
                  @click="addToTimeline(m)">
                  <div class="resource-thumb">
                    <button class="audio-play-btn" :class="{ playing: playingAudioId === m.id }" @click.stop="toggleAudio(m)" :title="playingAudioId === m.id ? '停止' : '试听'">
                      <svg v-if="playingAudioId !== m.id" viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><polygon points="8 5 19 12 8 19 8 5"/></svg>
                      <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                    </button>
                  </div>
                  <span class="resource-name" :title="truncate(m.content, 20)">{{ viewMode === 'grid' ? m.content : truncate(m.content, 10) }}</span>
                </div>
                <div v-if="audioMatItems.length === 0" class="resource-empty">无音频素材</div>
              </div>
            </template>
            <!-- Text panel: 花字 creation -->
            <template v-else-if="activeMenu === 'text'">
              <div class="text-create-form">
                <textarea v-model="textForm.content" class="text-input" placeholder="输入文字内容..." rows="3"></textarea>
                <div class="preset-section">
                  <div class="preset-label">花字模板</div>
                  <div class="preset-grid">
                    <div v-for="(ps, pi) in textStylePresets" :key="pi" class="preset-card"
                      :class="{ active: textForm.styleIndex === pi }"
                      @click="textForm.styleIndex = pi">
                      <span class="preset-preview" :style="{ fontWeight: ps.bold ? 'bold' : 'normal', fontStyle: ps.italic ? 'italic' : 'normal', color: ps.fontColor, WebkitTextStroke: ps.outline ? '1px ' + (ps.outlineColor||'#000') : 'transparent' }">Aa</span>
                      <span class="preset-name">{{ ps.name }}</span>
                    </div>
                  </div>
                </div>
                <button class="btn btn-primary btn-sm btn-block" @click="addTextToTimeline" :disabled="!textForm.content.trim()">添加到轨道</button>
              </div>
              <div v-if="textMatItems.length > 0" class="text-materials-section">
                <div class="preset-label">已有文字素材</div>
                <div class="resource-grid list">
                  <div v-for="m in textMatItems" :key="m.id" class="resource-item r-list"
                    draggable="true"
                    @dragstart="onResourceDragStart(m, $event)"
                    @click="addToTimeline(m)">
                    <div class="resource-thumb">
                      <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>
                    </div>
                    <span class="resource-name" :title="truncate(m.content, 20)">{{ truncate(m.content, 20) }}</span>
                  </div>
                </div>
              </div>
            </template>
            <!-- Effect presets panel -->
            <template v-else-if="activeMenu === 'effect'">
              <div class="preset-section">
                <div class="preset-label">视频特效</div>
                <div class="preset-grid">
                  <div v-for="ep in effectPresets" :key="ep.key" class="preset-card"
                    :class="{ active: selectedClip && selectedClip.effect === ep.key }"
                    @click="applyEffect(ep.key)">
                    <span class="preset-preview" style="background:#1f2937;display:flex;align-items:center;justify-content:center">
                      <span v-html="effectSvg(ep.icon)" style="color:#fff;width:18px;height:18px;display:flex;align-items:center;justify-content:center"></span>
                    </span>
                    <span class="preset-name">{{ ep.name }}</span>
                  </div>
                </div>
                <p v-if="!selectedClip" class="preset-hint">请在轨道中选择片段后应用特效</p>
              </div>
            </template>
            <!-- Transition presets panel -->
            <template v-else-if="activeMenu === 'transition'">
              <div class="preset-section">
                <div class="preset-label">转场效果</div>
                <div class="preset-grid">
                  <div v-for="tp in transitionPresets" :key="tp.key" class="preset-card"
                    @click="applyTransitionAtPlayhead(tp)">
                    <span class="preset-preview" style="background:#1f2937;display:flex;align-items:center;justify-content:center">
                      <span v-html="transitionSvg(tp.icon)" style="color:#fff;width:18px;height:18px;display:flex;align-items:center;justify-content:center"></span>
                    </span>
                    <span class="preset-name">{{ tp.name }}</span>
                  </div>
                </div>
                <p class="preset-hint">将播放头置于两个片段之间，点击转场应用</p>
              </div>
            </template>
          </div>
        </div>
      </div>
      <button v-if="!panelVisible" class="panel-show-btn" @click="panelVisible = true" title="显示素材列表">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
      </button>

      <!-- ===== MAIN + ATTRIBUTE ===== -->
      <div class="main-vertical">
        <div class="main-horizontal">
          <!-- Canvas Player -->
          <div class="canvas-player">
            <div class="player-header">
              <span>播放器</span>
              <div class="player-header-right">
                <select v-model="playerRatioIndex" class="ph-select">
                  <option v-for="(opt, i) in ratioOptions" :key="i" :value="i">{{ opt.label }}</option>
                </select>
                <select v-model="playerZoom" class="ph-select">
                  <option v-for="opt in zoomOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
                </select>
              </div>
            </div>
            <div class="player-content" ref="playerContentRef">
              <div class="player-canvas-wrap">
                <canvas ref="previewCanvas" class="preview-canvas" @mousedown="onCanvasMouseDown"></canvas>
              </div>
              <div v-if="!previewItem" class="player-empty">
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
                <p>点击轨道片段预览</p>
              </div>
              <video ref="hiddenVideoRef" style="display:none" preload="auto"></video>
              <audio ref="hiddenAudioRef" style="display:none" preload="auto"></audio>
            </div>
            <div class="player-control">
              <span class="ctrl-time">{{ formatFrame(playStartFrame) }}</span>
              <span class="ctrl-sep">/</span>
              <span class="ctrl-total">{{ formatFrame(totalFrames) }}</span>
              <div class="ctrl-btns">
                <button class="ctrl-btn" @click="togglePlay" :title="isPlaying ? '暂停' : '播放'">
                  <svg v-if="isPlaying" viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
                  <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
                </button>
              </div>
            </div>
          </div>
          <!-- Attribute Panel -->
          <div class="attribute-panel" :style="{ width: attrWidth + 'px' }">
            <div class="attr-split-handle" @mousedown="startAttrResize"></div>
            <div v-if="selectedClip" class="attr-content">
              <div class="attr-header">属性</div>
              <div class="attr-form">
                <div class="attr-group">
                  <div class="attr-group-title">基础</div>
                  <label class="attr-row">
                    <span>名称</span>
                    <input :value="selectedClip.content" disabled class="attr-input" />
                  </label>
                  <label class="attr-row">
                    <span>类型</span>
                    <span class="attr-value">{{ typeLabel(selectedClip.type) }}</span>
                  </label>
                  <label class="attr-row">
                    <span>时长</span>
                    <span class="attr-value">{{ ((selectedClip.end - selectedClip.start) / 30).toFixed(1) }}s</span>
                  </label>
                </div>
                <div class="attr-group">
                  <div class="attr-group-title">位置</div>
                  <label class="attr-row">
                    <span>X</span>
                    <input v-model.number="selectedClip.centerX" class="attr-input" type="number" />
                  </label>
                  <label class="attr-row">
                    <span>Y</span>
                    <input v-model.number="selectedClip.centerY" class="attr-input" type="number" />
                  </label>
                  <label class="attr-row">
                    <span>缩放</span>
                    <input v-model.number="selectedClip.scale" class="attr-input" type="range" min="10" max="200" />
                    <span class="attr-range-val">{{ selectedClip.scale }}%</span>
                  </label>
                </div>
                <div v-if="selectedClip.type === 'text'" class="attr-group">
                  <div class="attr-group-title">文字样式</div>
                  <label class="attr-row">
                    <span>内容</span>
                    <textarea v-model="selectedClip.content" class="attr-textarea" rows="2"></textarea>
                  </label>
                  <label class="attr-row">
                    <span>字体</span>
                    <select v-model="selectedClip.fontFamily" class="attr-select">
                      <option v-for="f in fontFamilies" :key="f.value" :value="f.value">{{ f.label }}</option>
                    </select>
                  </label>
                  <label class="attr-row">
                    <span>字号</span>
                    <input v-model.number="selectedClip.fontSize" class="attr-input" type="range" min="20" max="200" />
                    <span class="attr-range-val">{{ selectedClip.fontSize }}px</span>
                  </label>
                  <label class="attr-row">
                    <span>颜色</span>
                    <input v-model="selectedClip.fontColor" class="attr-color" type="color" />
                    <span class="attr-color-badge" :style="{ background: selectedClip.fontColor }"></span>
                  </label>
                  <label class="attr-row">
                    <span></span>
                    <button class="attr-toggle" :class="{ active: selectedClip.bold }" @click="selectedClip.bold = !selectedClip.bold" title="加粗"><b>B</b></button>
                    <button class="attr-toggle" :class="{ active: selectedClip.italic }" @click="selectedClip.italic = !selectedClip.italic" title="斜体"><i>I</i></button>
                    <button class="attr-toggle" :class="{ active: selectedClip.shadow }" @click="selectedClip.shadow = !selectedClip.shadow" title="阴影">影</button>
                    <button class="attr-toggle" :class="{ active: selectedClip.outline }" @click="selectedClip.outline = !selectedClip.outline" title="描边">边</button>
                  </label>
                  <label v-if="selectedClip.outline" class="attr-row">
                    <span>描边</span>
                    <input v-model="selectedClip.outlineColor" class="attr-color" type="color" />
                    <span class="attr-color-badge" :style="{ background: selectedClip.outlineColor }"></span>
                  </label>
                  <label class="attr-row">
                    <span>背景</span>
                    <input v-model="selectedClip.bgColor" class="attr-color" type="color" value="#000000" />
                    <label class="attr-checkbox-label">
                      <input type="checkbox" v-model="selectedClip.bgEnabled" class="attr-checkbox" />
                      启用
                    </label>
                  </label>
                  <label class="attr-row">
                    <span>对齐</span>
                    <select v-model="selectedClip.textAlign" class="attr-select">
                      <option value="left">左对齐</option>
                      <option value="center">居中</option>
                      <option value="right">右对齐</option>
                    </select>
                  </label>
                </div>
                <!-- Effect selector -->
                <div class="attr-group">
                  <div class="attr-group-title">特效</div>
                  <div class="effect-grid">
                    <div v-for="ep in effectPresets" :key="ep.key" class="effect-card"
                      :class="{ active: selectedClip && selectedClip.effect === ep.key }"
                      @click="applyEffect(ep.key)">
                      <span class="effect-preview">
                        <span v-html="effectSvg(ep.icon)" style="width:20px;height:20px;display:flex;align-items:center;justify-content:center"></span>
                      </span>
                      <span class="effect-name">{{ ep.name }}</span>
                    </div>
                  </div>
                </div>
                <!-- Transition selector -->
                <div v-if="selectIndex > 0" class="attr-group">
                  <div class="attr-group-title">转场 (入)</div>
                  <div class="effect-grid">
                    <div v-for="tp in transitionPresets" :key="tp.key" class="effect-card"
                      :class="{ active: selectedClip && selectedClip.transitionIn && selectedClip.transitionIn.key === tp.key }"
                      @click="setTransition(selectLine, selectIndex, tp)">
                      <span class="effect-preview">
                        <span v-html="transitionSvg(tp.icon)" style="width:20px;height:20px;display:flex;align-items:center;justify-content:center"></span>
                      </span>
                      <span class="effect-name">{{ tp.name }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="attr-empty">
              <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1" opacity="0.4"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
              <p>点击轨道进行编辑</p>
            </div>
          </div>
        </div>

        <!-- ===== TIMELINE ===== -->
        <div class="track-container" :style="{ height: trackHeight + 'px' }">
          <div class="track-resize-handle" @mousedown="startTrackResize">
            <div class="track-resize-bar"></div>
          </div>
          <!-- Track toolbar -->
          <div class="track-toolbar">
            <div class="toolbar-left">
              <button class="tb-btn" @click="splitClip" :disabled="!canSplit" title="分割">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="3" x2="12" y2="21"/></svg>
              </button>
              <button class="tb-btn" @click="extractSubtitles" :disabled="!hasAudioTracks || extractingSubtitles" title="提取音频为字幕">
                <svg v-if="!extractingSubtitles" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M7 9.5h10M7 13h7M7 16.5h9"/></svg>
                <span v-else class="tb-btn-loading"></span>
              </button>
              <button class="tb-btn" @click="deleteSelected" :disabled="!selectedClip" title="删除">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
              <button class="tb-btn" @click="deleteTrack" :disabled="!canDeleteTrack" title="删除轨道">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
              </button>
              <button class="tb-btn" @click="addTrack" title="添加轨道">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
              </button>
              <div class="tb-sep"></div>
            </div>
            <div class="toolbar-right">
              <button class="tb-btn" @click="addGroupToTrack" title="添加素材组（视频+配音）到新轨道">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><line x1="12" y1="11" x2="12" y2="13"/></svg>
              </button>
              <div class="tb-sep"></div>
              <label class="subtitle-toggle" :class="{ disabled: !hasGroupTracks }" :title="hasGroupTracks ? '字幕显示开关' : '需要组轨道'" @click.stop>
                <span class="subtitle-toggle-label">字幕</span>
                <input type="checkbox" :checked="showSubtitles" :disabled="!hasGroupTracks" @change="toggleSubtitles" />
                <span class="subtitle-toggle-track"></span>
              </label>
              <div class="tb-sep"></div>
              <button class="tb-btn" @click="changeScale(-10)" title="缩小">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
              </button>
              <input type="range" class="tb-slider" v-model.number="trackScale" min="0" max="100" step="10" />
              <button class="tb-btn" @click="changeScale(10)" title="放大">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
              </button>
            </div>
          </div>
          <!-- Track list -->
          <div class="track-list" ref="trackListRef" @scroll="onTrackScroll">
            <div class="track-list-inner">
              <!-- Time ruler -->
              <div class="track-ruler-wrap">
                <div class="track-icons-spacer"></div>
                <div class="ruler-canvas-wrap" ref="rulerWrapRef" @mousedown="onTimelineSeek($event)">
                  <canvas ref="rulerCanvas" class="ruler-canvas"></canvas>
                </div>
              </div>
              <!-- Track rows -->
              <div class="track-rows" ref="trackRowsRef"
                @dragover.prevent="onTrackDragOver($event)"
                @drop.prevent="onTrackDrop($event)">
                <div class="track-icons-column" ref="trackIconsRef">
                  <div v-for="(line, li) in trackLines" :key="li" class="track-icon-item"
                    :class="[trackHeightClass(line.type), line.main ? 'is-main' : '',
                             { 'is-active': selectLine === li && selectIndex < 0, 'is-locked': line.locked }]"
                    @click="if (!line.locked) { selectLine = li; selectIndex = -1 }">
                    <span class="ti-type-icon" :title="line.main ? '主轨道' : trackTypeName(line.type)">
                      <component :is="trackIconComp(line.type)" />
                    </span>
                    <button class="ti-btn" :class="{ active: line.visible }" @click.stop="line.visible = !line.visible" :title="line.visible ? '隐藏轨道' : '显示轨道'">
                      <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/><line v-if="!line.visible" x1="1" y1="1" x2="23" y2="23"/></svg>
                    </button>
                    <button class="ti-btn" :class="{ active: line.locked }" @click.stop="line.locked = !line.locked" :title="line.locked ? '解锁轨道' : '锁定轨道'">
                      <svg v-if="line.locked" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                      <svg v-else viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/><line x1="7" y1="11" x2="7" y2="7"/></svg>
                    </button>
                    <button class="ti-btn" :class="{ active: line.muted }" @click.stop="line.muted = !line.muted" :title="line.muted ? '取消静音' : '静音'">
                      <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line v-if="line.muted" x1="23" y1="9" x2="17" y2="15"/><line v-if="line.muted" x1="17" y1="9" x2="23" y2="15"/></svg>
                    </button>
                  </div>
                </div>
                <div class="track-scroll-area" @mousedown="onTimelineSeek($event)">
                  <div v-for="(line, li) in trackLines" :key="li" class="track-row"
                    :class="[trackHeightClass(line.type), line.main ? 'is-main' : '', { 'is-active': selectLine === li }]"
                    @click="selectLine = li; selectIndex = -1">
                    <div v-for="(clip, ci) in line.list" :key="clip.id" class="track-clip"
                      :class="{ 'is-selected': selectLine === li && selectIndex === ci, 'is-dragging': dragClipId === clip.id }"
                      :style="getClipStyle(clip)"
                      @click.stop="selectClip(li, ci)"
                      @mousedown.stop="onClipMouseDown($event, li, ci)">
                      <!-- Clip content -->
                      <div class="tc-header" :class="'tc-' + clip.type">
                        <component :is="trackIconComp(clip.type)" />
                        <span class="tc-name">{{ truncate(clip.content, 10) }}</span>
                      </div>
                      <div class="tc-body" :class="'tc-body-' + clip.type">
                        <img v-if="clip.type === 'image'" :src="`/api/materials/${clip.material_id}/file`" class="tc-thumb" />
                      </div>
                      <!-- Trim handles -->
                      <div v-if="selectLine === li && selectIndex === ci" class="tc-handle left" @mousedown.stop="startTrim($event, li, ci, 'left')">
                        <span>∣</span>
                      </div>
                      <div v-if="selectLine === li && selectIndex === ci" class="tc-handle right" @mousedown.stop="startTrim($event, li, ci, 'right')">
                        <span>∣</span>
                      </div>
                      <!-- Transition indicator -->
                      <div v-if="ci > 0 && clip.transitionIn && clip.transitionIn.key" class="tc-transition-indicator"
                        :title="getTransitionName(clip.transitionIn.key)">
                        <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12h18M3 12l4-4M3 12l4 4"/></svg>
                      </div>
                    </div>
                  </div>
                  <!-- Playhead -->
                  <div class="track-playhead" :style="{ left: playheadLeft + 'px' }">
                    <span class="playhead-time">{{ formatFrame(playStartFrame) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Upload Dialog -->
    <div v-if="showUploadDialog" class="modal-overlay" @click.self="showUploadDialog = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h3>上传素材</h3>
          <button class="btn btn-default btn-sm" @click="showUploadDialog = false">✕</button>
        </div>
        <div class="upload-form">
          <label>类型
            <select v-model="uploadForm.type">
              <option value="video">视频</option>
              <option value="image">图片</option>
              <option value="scene">场景</option>
            </select>
          </label>
          <label>文件
            <input type="file" ref="uploadFileInput" @change="onFileChange" accept="video/*,image/*" />
          </label>
          <label>内容描述
            <textarea v-model="uploadForm.content" placeholder="描述素材内容..." rows="3"></textarea>
          </label>
          <div class="upload-actions">
            <button class="btn btn-primary" @click="uploadMaterial" :disabled="uploading">
              {{ uploading ? '上传中...' : '上传' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Saving overlay -->
    <teleport to="body">
      <transition name="fade">
        <div v-if="saving || generating" class="global-toast">
          <div class="toast-spinner"></div>
          <span>{{ saving ? '保存中...' : '合成中...' }}</span>
        </div>
      </transition>
    </teleport>
  </div>
</template>

<script src="./MashupManyEditor.js"></script>

<style src="./MashupManyEditor.css" scoped></style>
