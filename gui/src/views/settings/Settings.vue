<template>
<div class="view-container">
    <div class="panel">
      <div class="view-header">
        <h2>系统配置</h2>
        <div class="header-actions">
          <button class="btn btn-sm btn-primary" @click="loadSettings" :disabled="loading">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            刷新
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else>
      <div v-for="(items, group) in groups" :key="group" class="panel settings-group">
        <div class="group-header">
          <h3 class="group-title">{{ group }}</h3>
        </div>
        <div class="settings-list">
          <div v-for="s in items" :key="s.id" class="setting-item">
            <div class="setting-info">
              <span class="setting-label">{{ s.description }}</span>
              <span class="setting-key">{{ s.key }}</span>
            </div>
            <div class="setting-control">
              <!-- 只读配置：仅显示值，不可编辑 -->
              <template v-if="s.is_active === 0">
                <input
                  v-model="editMap[s.id]"
                  type="text"
                  class="setting-field"
                  disabled
                />
              </template>
              <template v-else>
              <!-- 目录选择 -->
              <div v-if="s.key === 'source_dir' || s.key === 'material_dir' || s.key === 'mixed_dir' || s.key === 'vector_db_path' || s.key === 'log_dir'" class="dir-input-wrap">
                <input
                  v-model="editMap[s.id]"
                  type="text"
                  class="setting-field dir-field"
                  placeholder="输入目录路径"
                />
                <button class="btn btn-sm btn-default" @click="selectDir(s)" title="选择目录">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                  选择
                </button>
              </div>
              <!-- 数字 -->
              <input
                v-else-if="s.key === 'paragraph_gap_threshold' || s.key === 'subtitle_crop_bottom'"
                v-model="editMap[s.id]"
                type="number"
                step="0.1"
                class="setting-field"
                @input="editMap[s.id] = $event.target.value"
              />
              <!-- 密码（API 密钥），带显隐切换 -->
              <div v-else-if="s.key.includes('api_key') || s.key === 'tts_api_key'" class="pwd-input-wrap">
                <input
                  v-model="editMap[s.id]"
                  :type="pwdVisible[s.id] ? 'text' : 'password'"
                  class="setting-field"
                />
                <button class="btn btn-sm btn-default" @click="togglePwd(s)" :title="pwdVisible[s.id] ? '隐藏' : '显示'">
                  <svg v-if="!pwdVisible[s.id]" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                </button>
              </div>
              <!-- 文本 -->
              <input
                v-else
                v-model="editMap[s.id]"
                type="text"
                class="setting-field"
              />
              <button
                class="btn btn-sm btn-primary save-btn"
                @click="saveSetting(s)"
              >
                <svg v-if="savingId !== s.id" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                <span v-else class="saving-spinner"></span>
                {{ savingId === s.id ? '保存中...' : '保存' }}
              </button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script src="./Settings.js"></script>

<style src="./Settings.css" scoped></style>
