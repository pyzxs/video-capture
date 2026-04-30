<template>
  <div class="view-container">
    <section class="panel">
      <div class="view-header">
        <h2>用户信息</h2>
        <button class="btn btn-default" @click="refresh">刷新</button>
      </div>
      <div v-if="loading" class="loading"></div>
      <template v-else-if="profile">
        <div class="info-grid">
          <div class="info-item">
            <label>用户ID</label>
            <span class="mono">{{ profile.user_id }}</span>
          </div>
          <div class="info-item">
            <label>授权密钥</label>
            <span class="mono">{{ profile.api_key }}</span>
          </div>
          <div class="info-item">
            <label>免费额度</label>
            <span>¥{{ profile.free_quota?.toFixed(2) }}</span>
          </div>
          <div class="info-item highlight">
            <label>剩余额度</label>
            <span>¥{{ profile.remaining_quota?.toFixed(4) }}</span>
          </div>
          <div class="info-item">
            <label>注册时间</label>
            <span>{{ formatDate(profile.created_at) }}</span>
          </div>
        </div>
      </template>
    </section>

    <section class="panel">
      <h3 style="margin-bottom:12px;">充值</h3>
      <div class="recharge-row">
        <input
          v-model="rechargeCode"
          class="search-input"
          placeholder="请输入充值码"
          style="width:260px;"
          @keyup.enter="doRecharge"
        />
        <button class="btn btn-success" :disabled="recharging || !rechargeCode" @click="doRecharge">
          {{ recharging ? '充值中...' : '充值' }}
        </button>
      </div>
      <p v-if="rechargeMsg" class="recharge-msg" :class="{ error: rechargeError }">{{ rechargeMsg }}</p>
    </section>

    <section class="panel">
      <div class="view-header" style="margin-bottom:12px;">
        <h2>消耗记录</h2>
      </div>
      <div v-if="recordsLoading" class="loading"></div>
      <div v-else-if="records.length === 0" class="empty">暂无记录</div>
      <table v-else class="data-table">
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
            <td>¥{{ r.cost?.toFixed(6) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="totalPages > 1" class="pagination">
        <button class="page-btn" :disabled="page <= 1" @click="page--; loadRecords()">上一页</button>
        <span class="page-info">{{ page }} / {{ totalPages }}</span>
        <button class="page-btn" :disabled="page >= totalPages" @click="page++; loadRecords()">下一页</button>
      </div>
    </section>
  </div>
</template>

<script>
import { profileApi } from '../../api/index.js'

export default {
  name: 'ProfilePage',
  data() {
    return {
      profile: null,
      loading: false,
      records: [],
      recordsLoading: false,
      page: 1,
      pageSize: 20,
      total: 0,
      rechargeCode: '',
      recharging: false,
      rechargeMsg: '',
      rechargeError: false,
    }
  },
  computed: {
    totalPages() {
      return Math.max(1, Math.ceil(this.total / this.pageSize))
    },
  },
  mounted() {
    this.loadProfile()
    this.loadRecords()
  },
  methods: {
    async refresh() {
      this.loadProfile()
      this.page = 1
      this.loadRecords()
    },
    async loadProfile() {
      this.loading = true
      try {
        const { data } = await profileApi.get()
        this.profile = data?.data || data
      } catch (e) {
        console.error('加载用户信息失败', e)
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
      } finally {
        this.recordsLoading = false
      }
    },
    async doRecharge() {
      if (!this.rechargeCode) return
      this.recharging = true
      this.rechargeMsg = ''
      this.rechargeError = false
      try {
        const { data } = await profileApi.recharge(this.rechargeCode)
        const msg = data?.message || '充值成功'
        this.rechargeMsg = msg
        this.rechargeCode = ''
        await this.loadProfile()
      } catch (e) {
        const msg = e?.response?.data?.message || e?.response?.data?.detail || '充值失败'
        this.rechargeMsg = typeof msg === 'string' ? msg : '充值失败'
        this.rechargeError = true
      } finally {
        this.recharging = false
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
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 24px;
}
.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #f3f4f6;
  gap: 16px;
}
.info-item label {
  font-size: 13px;
  color: #6b7280;
  flex-shrink: 0;
}
.info-item span {
  font-size: 13px;
  color: #1a1a2e;
  text-align: right;
  word-break: break-all;
}
.info-item .mono {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
}
.info-item.highlight span {
  color: #059669;
  font-weight: 700;
  font-size: 16px;
}
.recharge-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.recharge-msg {
  margin-top: 8px;
  font-size: 13px;
  color: #059669;
}
.recharge-msg.error {
  color: #dc2626;
}
</style>
