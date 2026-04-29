<template>
  <div v-if="visible" class="profile-overlay" @click.self="$emit('close')">
    <div class="profile-panel">
      <div class="profile-header">
        <h3>用户信息</h3>
        <button class="btn-icon" @click="$emit('close')" title="关闭">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>

      <div v-if="loading" class="profile-loading">加载中...</div>
      <template v-else-if="profile">
        <div class="profile-section">
          <div class="profile-field">
            <label>User ID</label>
            <span class="profile-value mono">{{ profile.user_id }}</span>
          </div>
          <div class="profile-field">
            <label>API Key</label>
            <span class="profile-value mono">{{ profile.api_key }}</span>
          </div>
          <div class="profile-field">
            <label>剩余额度</label>
            <span class="profile-value highlight">${{ profile.remaining_quota?.toFixed(4) }}</span>
          </div>
          <div class="profile-field">
            <label>免费额度</label>
            <span class="profile-value">${{ profile.free_quota?.toFixed(2) }}</span>
          </div>
          <div class="profile-field">
            <label>注册时间</label>
            <span class="profile-value">{{ formatDate(profile.created_at) }}</span>
          </div>
        </div>

        <div class="profile-section">
          <h4>消耗记录</h4>
          <div v-if="recordsLoading" class="profile-loading">加载中...</div>
          <div v-else-if="records.length === 0" class="profile-empty">暂无记录</div>
          <table v-else class="record-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>类型</th>
                <th>模型</th>
                <th>输入</th>
                <th>输出</th>
                <th>费用</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in records" :key="r.id">
                <td>{{ formatDate(r.created_at) }}</td>
                <td><span class="tag">{{ r.request_type }}</span></td>
                <td class="content-cell">{{ r.model }}</td>
                <td>{{ r.tokens_input }}</td>
                <td>{{ r.tokens_output }}</td>
                <td>${{ r.cost?.toFixed(6) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="totalPages > 1" class="pagination">
            <button class="page-btn" :disabled="page <= 1" @click="page--; loadRecords()">上一页</button>
            <span class="page-info">{{ page }} / {{ totalPages }}</span>
            <button class="page-btn" :disabled="page >= totalPages" @click="page++; loadRecords()">下一页</button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import { profileApi } from '../../api/index.js'

export default {
  name: 'ProfilePanel',
  props: { visible: Boolean },
  emits: ['close'],
  data() {
    return {
      profile: null,
      loading: false,
      records: [],
      recordsLoading: false,
      page: 1,
      pageSize: 20,
      total: 0,
    }
  },
  computed: {
    totalPages() {
      return Math.max(1, Math.ceil(this.total / this.pageSize))
    },
  },
  watch: {
    visible(val) {
      if (val) {
        this.loadProfile()
        this.page = 1
        this.loadRecords()
      }
    },
  },
  methods: {
    async loadProfile() {
      this.loading = true
      try {
        const { data } = await profileApi.get()
        this.profile = data?.data || data
      } catch (e) {
        console.error('加载用户信息失败', e)
        this.profile = null
      } finally {
        this.loading = false
      }
    },
    async loadRecords() {
      this.recordsLoading = true
      try {
        const { data } = await profileApi.records(this.page, this.pageSize)
        this.records = data?.data || []
        this.total = data?.total || 0
      } catch (e) {
        console.error('加载消耗记录失败', e)
        this.records = []
      } finally {
        this.recordsLoading = false
      }
    },
    formatDate(s) {
      if (!s) return '-'
      return new Date(s).toLocaleString('zh-CN')
    },
  },
}
</script>

<style scoped>
.profile-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.3);
  z-index: 200;
  display: flex;
  justify-content: flex-end;
}
.profile-panel {
  width: 440px;
  max-width: 90vw;
  height: 100%;
  background: #fff;
  box-shadow: -4px 0 24px rgba(0,0,0,0.12);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  animation: slide-in 0.2s ease;
}
@keyframes slide-in { from { transform: translateX(100%); } to { transform: translateX(0); } }

.profile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}
.profile-header h3 { font-size: 17px; font-weight: 600; margin: 0; }

.profile-section {
  padding: 16px 24px;
  border-bottom: 1px solid #f3f4f6;
}
.profile-section h4 {
  font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 10px;
}

.profile-field {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 8px 0;
  gap: 12px;
}
.profile-field label {
  font-size: 13px; color: #6b7280; flex-shrink: 0;
}
.profile-value {
  font-size: 13px; color: #1a1a2e; text-align: right; word-break: break-all;
}
.profile-value.mono { font-family: 'SF Mono', 'Fira Code', monospace; font-size: 12px; }
.profile-value.highlight { color: #059669; font-weight: 600; font-size: 15px; }

.profile-loading, .profile-empty {
  text-align: center; padding: 24px; color: #9ca3af; font-size: 13px;
}

.record-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.record-table th {
  padding: 8px 6px; text-align: left; font-weight: 600;
  color: #6b7280; border-bottom: 1px solid #e5e7eb; font-size: 11px;
}
.record-table td {
  padding: 8px 6px; border-bottom: 1px solid #f3f4f6; color: #374151;
}
.content-cell { max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag {
  display: inline-block; padding: 1px 8px; border-radius: 10px;
  font-size: 10px; font-weight: 500;
  background: #eef2ff; color: #4f46e5;
}

.pagination {
  display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 12px;
}
.page-btn {
  padding: 4px 12px; border: 1px solid #d1d5db; border-radius: 6px;
  background: #fff; cursor: pointer; font-size: 12px; color: #374151;
}
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 12px; color: #6b7280; }

.btn-icon {
  background: none; border: 1px solid #e5e7eb; border-radius: 6px;
  cursor: pointer; width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  color: #6b7280; transition: all 0.12s;
}
.btn-icon:hover { border-color: #d1d5db; color: #1a1a2e; background: #f3f4f6; }
</style>
