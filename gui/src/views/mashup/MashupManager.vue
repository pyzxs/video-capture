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
            移动 ({{ selectedIds.size }})
          </button>
          <button v-if="selectedIds.size > 0" class="btn btn-sm btn-danger" @click="batchDeleteGens">
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
          <input v-model="searchQuery" placeholder="搜索标题..." class="search-input" @input="page=1; loadList()" />
          <select v-model="statusFilter" class="filter-select" @change="page=1; loadList()">
            <option value="">全部状态</option>
            <option value="created">已创建</option>
            <option value="completed">已完成</option>
          </select>
          <button class="btn btn-primary" @click="openManual" title="手动剪辑">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><line x1="8.5" y1="6.5" x2="17.5" y2="17"/><line x1="8.5" y1="17.5" x2="17.5" y2="7"/></svg>
          </button>
          <button class="btn btn-info" @click="goAuto" title="智能混剪">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l1.5 5.5L19 9l-5.5 1.5L12 16l-1.5-5.5L5 9l5.5-1.5z"/><path d="M18.5 15l.75 2.75L22 18.5l-2.75.75L18.5 22l-.75-2.75L15 18.5l2.75-.75z"/></svg>
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
              <template v-if="g.output_filepath">
                <template v-if="activeVideos.has(g.id)">
                  <video
                    :ref="el => setVideoRef(g.id, el)"
                    :src="$apiUrl(`/api/generated/${g.id}/download`)"
                    controls
                    preload="auto"
                    class="video-player-card"
                    @mouseenter="hoverPlay($event)"
                    @mouseleave="hoverPause($event)"
                    @loadeddata="onVideoLoaded($event)"
                  ></video>
                </template>
                <div v-else class="thumbnail-wrap" @click="activateVideo(g.id)">
                  <img
                    v-if="g.thumbnail"
                    :src="g.thumbnail"
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
              </template>
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
              <button v-if="g.status !== 'completed'" class="btn btn-sm btn-primary" @click="openEdit(g)" title="编辑">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
              </button>
              <button class="btn btn-sm btn-info" @click="exportItem(g.id)" :disabled="exporting" title="导出">
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
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
                  <button v-if="g.status !== 'completed'" class="btn btn-xs btn-primary" @click="openEdit(g)" title="编辑">编辑</button>
                  <button class="btn btn-xs btn-success" @click="genVideo(g)" :disabled="g.status==='processing'" title="生成">生成</button>
                  <button class="btn btn-xs btn-info" @click="exportItem(g.id)" :disabled="exporting" title="导出">导出</button>
                  <button class="btn btn-xs btn-danger" @click="deleteGen(g)" title="删除">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>

    <Pagination :page="page" :total="total" :page-size="pageSize" @change="onPageChange" />

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
