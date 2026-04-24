<template>
  <div class="app-container">
    <aside class="sidebar">
      <div class="logo">
        <svg class="logo-icon" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="23 7 16 12 23 17 23 7" />
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
        </svg>
        <span>Video Capture</span>
      </div>
      <nav>
        <router-link to="/videos" class="nav-item" active-class="active">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="23 7 16 12 23 17 23 7" /><rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
          </svg>
          <span>原始视频管理</span>
        </router-link>
        <router-link to="/materials" class="nav-item" active-class="active">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="22 3 22 15 16 15 16 21 2 21 2 3 22 3" /><line x1="6" y1="7" x2="18" y2="7" /><line x1="6" y1="11" x2="18" y2="11" /><line x1="6" y1="15" x2="10" y2="15" />
          </svg>
          <span>素材管理</span>
        </router-link>
        <router-link to="/mashups" class="nav-item" active-class="active">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M15 8a5 5 0 0 1 0 8" /><path d="M18.3 4.7a9 9 0 0 1 0 14.6" /><rect x="2" y="6" width="10" height="12" rx="1" />
          </svg>
          <span>混剪视频管理</span>
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <span class="status-dot" :class="apiStatus"></span>
        <span class="status-text">{{ apiStatus === 'online' ? 'API 已连接' : 'API 断开' }}</span>
      </div>
    </aside>
    <main class="main-content">
      <router-view />
    </main>
    <ToastMessage />
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted } from 'vue'
import api from './api/index.js'
import ToastMessage from './components/ToastMessage.vue'

export default {
  name: 'App',
  components: { ToastMessage },
  setup() {
    const apiStatus = ref('checking')
    let timer

    const checkHealth = async () => {
      try {
        await api.get('/health')
        apiStatus.value = 'online'
      } catch {
        apiStatus.value = 'offline'
      }
    }

    onMounted(() => {
      checkHealth()
      timer = setInterval(checkHealth, 5000)
    })

    onUnmounted(() => {
      clearInterval(timer)
    })

    return { apiStatus }
  },
}
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --sidebar-w: 236px;
  --accent: #6c5ce7;
  --accent-light: #a29bfe;
  --accent-bg: rgba(108,92,231,0.08);
  --bg: #f0f2f5;
  --card-bg: #ffffff;
  --text: #1a1a2e;
  --text-secondary: #6b7280;
  --border: #e5e7eb;
  --radius: 10px;
  --radius-sm: 6px;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.08);
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

.app-container { display: flex; height: 100vh; }

/* ── Sidebar ── */
.sidebar {
  width: var(--sidebar-w);
  background: linear-gradient(180deg, #1a1b2f 0%, #12132a 100%);
  color: #c8c9dc;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  user-select: none;
}
.logo {
  padding: 22px 20px 20px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 700;
  color: #e8e9f0;
  letter-spacing: 0.3px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.logo-icon { color: var(--accent-light); flex-shrink: 0; }

nav { flex: 1; padding: 14px 10px; display: flex; flex-direction: column; gap: 2px; }
.nav-item {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 14px;
  color: #8e8fa8;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  border-radius: 8px;
  transition: all 0.15s ease;
}
.nav-item:hover { background: rgba(255,255,255,0.06); color: #d0d1e2; }
.nav-item.active {
  background: var(--accent-bg);
  color: var(--accent-light);
}
.nav-item svg { flex-shrink: 0; opacity: 0.7; }
.nav-item.active svg { opacity: 1; }

.sidebar-footer {
  padding: 14px 20px;
  font-size: 12px;
  border-top: 1px solid rgba(255,255,255,0.06);
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b6c84;
}
.status-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.status-dot.online { background: #4ade80; box-shadow: 0 0 6px rgba(74,222,128,0.4); }
.status-dot.offline { background: #f87171; box-shadow: 0 0 6px rgba(248,113,113,0.4); }
.status-dot.checking { background: #fbbf24; box-shadow: 0 0 6px rgba(251,191,36,0.4); }
.status-text { line-height: 1; }

/* ── Main Content ── */
.main-content { flex: 1; overflow-y: auto; background: var(--bg); padding: 28px 32px; }

/* ── Scrollbar ── */
.main-content::-webkit-scrollbar { width: 6px; }
.main-content::-webkit-scrollbar-track { background: transparent; }
.main-content::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 3px; }
.main-content::-webkit-scrollbar-thumb:hover { background: #9ca3af; }

/* ── Global Shared Styles ── */
.view-container { width: 100%; max-width: 1400px; margin: 0 auto; }
.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}
.view-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.3px;
}
.header-actions { display: flex; gap: 10px; align-items: center; }

/* Cards */
.card {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
}

/* Tables */
.data-table { width: 100%; border-collapse: collapse; }
.data-table thead { background: #f9fafb; }
.data-table th {
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid var(--border);
}
.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid #f3f4f6;
  font-size: 14px;
  color: var(--text);
}
.data-table tbody tr { transition: background 0.12s; }
.data-table tbody tr:hover td { background: #f8f9ff; }
.data-table tbody tr:last-child td { border-bottom: none; }
.content-cell {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  color: var(--text-secondary);
}
.empty { text-align: center; color: var(--text-secondary); padding: 48px 16px !important; font-size: 14px; }
.actions { display: flex; gap: 6px; flex-wrap: wrap; }

/* Loading */
.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 60px 0;
  color: var(--text-secondary);
  font-size: 14px;
  gap: 10px;
}
.loading::before {
  content: '';
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  padding: 7px 14px;
  transition: all 0.15s ease;
  white-space: nowrap;
  line-height: 1.4;
}
.btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.btn:active:not(:disabled) { transform: translateY(0); }
.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.btn-sm { padding: 5px 10px; font-size: 12px; border-radius: 5px; }
.btn-primary { background: var(--accent); color: #fff; }
.btn-primary:hover:not(:disabled) { background: #5a4bd1; }
.btn-success { background: #10b981; color: #fff; }
.btn-success:hover:not(:disabled) { background: #059669; }
.btn-danger { background: #ef4444; color: #fff; }
.btn-danger:hover:not(:disabled) { background: #dc2626; }
.btn-info { background: #3b82f6; color: #fff; }
.btn-info:hover:not(:disabled) { background: #2563eb; }
.btn-default { background: #f3f4f6; color: #374151; border: 1px solid var(--border); }
.btn-default:hover:not(:disabled) { background: #e5e7eb; }

/* Inputs */
.search-input {
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  width: 240px;
  font-size: 13px;
  background: var(--card-bg);
  color: var(--text);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.search-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(108,92,231,0.12);
}
.search-input::placeholder { color: #9ca3af; }

.filter-select {
  padding: 8px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  background: var(--card-bg);
  color: var(--text);
  outline: none;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.filter-select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(108,92,231,0.12);
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.45);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  animation: overlay-in 0.15s ease;
}
@keyframes overlay-in { from { opacity: 0; } to { opacity: 1; } }
.modal {
  background: var(--card-bg);
  border-radius: 14px;
  padding: 28px;
  width: 520px;
  max-height: 82vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15);
  animation: modal-in 0.2s ease;
}
@keyframes modal-in { from { opacity: 0; transform: scale(0.96) translateY(8px); } to { opacity: 1; transform: scale(1) translateY(0); } }
.modal-wide { width: 780px; }
.modal h3 { font-size: 17px; font-weight: 700; margin-bottom: 6px; color: var(--text); }
.modal-desc { font-size: 13px; color: var(--text-secondary); margin-bottom: 20px; line-height: 1.5; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; }

/* Form */
.form { display: flex; flex-direction: column; gap: 14px; }
.form label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}
.form input, .form select, .form textarea {
  padding: 9px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 14px;
  background: #f9fafb;
  color: var(--text);
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  font-family: inherit;
}
.form input:focus, .form select:focus, .form textarea:focus {
  border-color: var(--accent);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(108,92,231,0.1);
}

/* Tag / Badge */
.tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
  background: #eef2ff;
  color: var(--accent);
}
.status-badge {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}
.status-badge.created { background: #eef2ff; color: #4f46e5; }
.status-badge.processing { background: #fff7ed; color: #ea580c; }
.status-badge.completed { background: #ecfdf5; color: #059669; }
.status-badge.failed { background: #fef2f2; color: #dc2626; }

/* Upload progress */
.upload-progress {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 4px 0 8px;
  font-size: 13px;
  color: var(--text-secondary);
}
.progress-bar { flex: 1; height: 6px; background: #f3f4f6; border-radius: 3px; overflow: hidden; }
.progress-fill {
  height: 100%;
  width: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent-light));
  border-radius: 3px;
  animation: progress 1.6s ease-in-out infinite;
}
@keyframes progress { 0% { width: 8%; } 50% { width: 55%; } 100% { width: 8%; } }

/* Upload zone */
.upload-zone {
  border: 2px dashed #d1d5db;
  border-radius: 10px;
  padding: 28px;
  text-align: center;
  transition: all 0.2s;
  cursor: pointer;
  margin-bottom: 14px;
}
.upload-zone.drag-over { border-color: var(--accent); background: rgba(108,92,231,0.05); }
.upload-placeholder { display: flex; flex-direction: column; align-items: center; gap: 8px; color: var(--text-secondary); }
.upload-icon { font-size: 36px; line-height: 1; }
.upload-hint { font-size: 12px; color: #9ca3af; }
.upload-preview { display: flex; align-items: center; gap: 12px; justify-content: center; }
.file-name { font-weight: 600; color: var(--text); }
.file-size { color: var(--text-secondary); font-size: 13px; }

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin-top: 24px;
  padding: 4px 0;
}
.page-btn {
  min-width: 34px;
  height: 34px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--card-bg);
  color: var(--text);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.12s;
  padding: 0 10px;
}
.page-btn:hover:not(:disabled):not(.active) {
  border-color: var(--accent);
  color: var(--accent);
}
.page-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.page-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.page-info { margin-left: 14px; font-size: 13px; color: var(--text-secondary); }

/* Preview */
.preview-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.preview-header h3 { margin: 0; font-size: 16px; font-weight: 600; }
.preview-body { background: #000; border-radius: 10px; overflow: hidden; }
.video-player { width: 100%; max-height: 70vh; display: block; }

/* Material section (MashupManager) */
.material-section { border: 1px solid var(--border); border-radius: 10px; padding: 14px; background: #fafbfc; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.section-header strong { font-size: 13px; color: var(--text); }
.empty-hint { text-align: center; padding: 24px 16px; color: var(--text-secondary); font-size: 13px; }
.material-item { display: flex; align-items: center; gap: 10px; padding: 8px 4px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.material-item:last-child { border-bottom: none; }
.mat-order {
  width: 26px; height: 26px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--accent-light));
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 600;
  flex-shrink: 0;
}
.mat-content { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
.mat-time { color: var(--text-secondary); font-size: 12px; white-space: nowrap; }
.mat-actions { display: flex; gap: 3px; }
.btn-icon {
  background: none;
  border: 1px solid var(--border);
  border-radius: 5px;
  cursor: pointer;
  width: 28px; height: 28px;
  font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-secondary);
  transition: all 0.12s;
}
.btn-icon:hover:not(:disabled) { border-color: var(--accent); color: var(--accent); }
.btn-icon:disabled { opacity: 0.3; cursor: not-allowed; }
.btn-icon-danger { color: #ef4444; border-color: #fecaca; }
.btn-icon-danger:hover:not(:disabled) { background: #fef2f2; border-color: #ef4444; color: #dc2626; }
.mat-picker-list { max-height: 320px; overflow-y: auto; }
.mat-picker-item {
  display: flex; gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
  font-size: 13px;
  border-radius: 6px;
  transition: background 0.1s;
}
.mat-picker-item:hover { background: #f0f4ff; }
.mat-picker-item:last-child { border-bottom: none; }
.mat-picker-item .mat-content { flex: 1; }
.mat-picker-item span:first-child { color: var(--text-secondary); font-weight: 600; font-size: 12px; }

/* Upload options */
.upload-options { display: flex; gap: 14px; margin-bottom: 14px; }
.upload-options label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-secondary); }
.upload-options select { padding: 5px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; background: var(--card-bg); color: var(--text); outline: none; }

/* Data table variant override for scoped */
table.data-table { background: var(--card-bg); border-radius: var(--radius); box-shadow: var(--shadow); }
.data-table-wrapper { overflow-x: auto; -webkit-overflow-scrolling: touch; }

/* ── Responsive ── */
@media (max-width: 1024px) {
  .main-content { padding: 20px 16px; }
  .view-header { flex-direction: column; align-items: stretch; gap: 12px; }
  .header-actions { justify-content: space-between; }
  .search-input { width: 100%; }
  .modal-wide { width: calc(100vw - 40px); }
  .modal { width: calc(100vw - 40px); }
}

@media (max-width: 768px) {
  :root { --sidebar-w: 56px; }
  .logo span { display: none; }
  .logo { justify-content: center; padding: 18px 0; }
  .nav-item { justify-content: center; padding: 10px 0; }
  .nav-item span { display: none; }
  .sidebar-footer .status-text { display: none; }
  .sidebar-footer { justify-content: center; }
  .view-container { max-width: 100%; }
  .data-table { font-size: 13px; }
  .data-table th, .data-table td { padding: 8px 10px; }
  .content-cell { max-width: 120px; }
  .actions { flex-direction: column; align-items: stretch; }
  .actions .btn-sm { width: 100%; justify-content: center; }
  .header-actions { flex-wrap: wrap; }
  .header-actions .btn { flex: 1; justify-content: center; }
  .mat-picker-item { flex-wrap: wrap; }
  .preview-header { flex-direction: column; gap: 8px; }
  .upload-options { flex-direction: column; }
}

@media (max-width: 480px) {
  .main-content { padding: 12px 8px; }
  .data-table-wrapper { overflow-x: auto; }
  .pagination { flex-wrap: wrap; gap: 2px; }
  .page-btn { min-width: 28px; height: 28px; font-size: 12px; padding: 0 6px; }
  .page-info { margin-left: 6px; font-size: 12px; }
  .modal { padding: 20px 16px; }
  .upload-zone { padding: 20px 12px; }
}
</style>
