<template>
  <div class="view-container">
    <div class="view-header">
      <h2>素材管理</h2>
      <div class="header-actions">
        <select v-model="typeFilter" class="filter-select" @change="page=1; loadMaterials()">
          <option value="">全部类型</option>
          <option value="video">视频</option>
          <option value="text">文本</option>
          <option value="image">图片</option>
          <option value="scene">场景</option>
        </select>
        <input v-model="searchQuery" placeholder="搜索素材内容..." class="search-input" @input="page=1; loadMaterials()" />
        <button class="btn btn-primary" @click="openCreate">+ 新增素材</button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else>
      <div v-if="materials.length === 0" class="empty">暂无数据</div>
      <div v-else class="material-grid">
        <div v-for="m in materials" :key="m.id" class="material-card">
          <div class="card-top">
            <span class="card-id">#{{ m.id }}</span>
            <span class="tag">{{ m.type }}</span>
          </div>

          <div class="card-content">
            <p class="card-text">{{ m.content || '-' }}</p>
          </div>

          <div v-if="m.type === 'video' && m.filepath" class="card-video">
            <video
              :src="`/api/materials/${m.id}/file`"
              controls
              preload="metadata"
              class="material-player"
              @mouseenter="hoverPlay($event)"
              @mouseleave="hoverPause($event)"
            ></video>
          </div>

          <div class="card-meta">
            <span v-if="m.frame_width" class="meta-item">{{ m.frame_width }}x{{ m.frame_height }}</span>
            <span v-if="m.filename" class="meta-item meta-file" :title="m.filename">{{ m.filename }}</span>
          </div>

          <div class="card-actions">
            <button class="btn btn-sm btn-primary" @click="openEdit(m)">编辑</button>
            <button class="btn btn-sm btn-danger" @click="deleteMaterial(m)">删除</button>
          </div>
        </div>
      </div>
    </template>

    <Pagination :page="page" :total="total" :page-size="pageSize" @change="onPageChange" />

    <!-- 新增/编辑弹窗 -->
    <div v-if="showDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal">
        <h3>{{ editing ? '编辑素材' : '新增素材' }}</h3>
        <div class="form">
          <label>类型
            <select v-model="form.type">
              <option>video</option><option>text</option><option>image</option><option>scene</option>
            </select>
          </label>
          <label>内容文本
            <textarea v-model="form.content" rows="3"></textarea>
          </label>
          <label>开始时间（秒）
            <input v-model.number="form.start_time" type="number" step="0.1" />
          </label>
          <label>结束时间（秒）
            <input v-model.number="form.end_time" type="number" step="0.1" />
          </label>
          <label>宽度
            <input v-model.number="form.frame_width" type="number" />
          </label>
          <label>高度
            <input v-model.number="form.frame_height" type="number" />
          </label>
          <label>帧率
            <input v-model.number="form.frame_rate" type="number" step="0.1" />
          </label>
          <label>文件路径
            <input v-model="form.filepath" placeholder="可选" />
          </label>
        </div>
        <div class="modal-actions">
          <button class="btn btn-default" @click="closeDialog">取消</button>
          <button class="btn btn-primary" @click="saveMaterial">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { materialApi } from '../api/index.js'
import { useToast } from '../composables/useToast.js'
import Pagination from '../components/Pagination.vue'

export default {
  name: 'MaterialManager',
  components: { Pagination },
  setup() {
    const toast = useToast()
    const materials = ref([])
    const loading = ref(true)
    const searchQuery = ref('')
    const typeFilter = ref('')
    const showDialog = ref(false)
    const editing = ref(null)
    const form = ref(emptyForm())
    const page = ref(1)
    const pageSize = 20
    const total = ref(0)

    function emptyForm() {
      return { type: 'video', content: '', start_time: 0, end_time: 0, frame_width: 0, frame_height: 0, frame_rate: 0, filename: '', filepath: '' }
    }

    const loadMaterials = async () => {
      loading.value = true
      try {
        const params = { q: searchQuery.value || undefined, type: typeFilter.value || undefined, skip: (page.value - 1) * pageSize, limit: pageSize }
        const res = await materialApi.list(params)
        const data = res.data
        materials.value = data.items || data || []
        total.value = data.total ?? (Array.isArray(data) ? data.length : 0)
      } catch (e) {
        console.error(e)
        materials.value = []
      } finally {
        loading.value = false
      }
    }

    const openCreate = () => {
      editing.value = null
      form.value = emptyForm()
      showDialog.value = true
    }

    const openEdit = (m) => {
      editing.value = m
      form.value = { ...m }
      showDialog.value = true
    }

    const closeDialog = () => {
      showDialog.value = false
      editing.value = null
    }

    const saveMaterial = async () => {
      try {
        if (editing.value) {
          await materialApi.update(editing.value.id, form.value)
        } else {
          await materialApi.create(form.value)
        }
        closeDialog()
        loadMaterials()
      } catch (e) {
        toast.error('保存失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const onPageChange = (p) => {
      page.value = p
      loadMaterials()
    }

    const deleteMaterial = async (m) => {
      if (!confirm(`确定删除素材 #${m.id}？将从数据库和向量库同步删除。`)) return
      try {
        await materialApi.remove(m.id)
        loadMaterials()
      } catch (e) {
        toast.error('删除失败')
      }
    }

    const hoverPlay = (e) => {
      const v = e.target
      if (v.readyState >= 2) v.play()
    }

    const hoverPause = (e) => {
      const v = e.target
      v.pause()
      v.currentTime = 0
    }

    const truncate = (s, n) => s && s.length > n ? s.slice(0, n) + '...' : s

    onMounted(loadMaterials)

    return { materials, loading, searchQuery, typeFilter, loadMaterials, page, pageSize, total, onPageChange, openCreate, openEdit, closeDialog, saveMaterial, deleteMaterial, showDialog, editing, form, truncate, hoverPlay, hoverPause }
  },
}
</script>

<style scoped>
.material-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.material-card {
  background: var(--card-bg);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
  transition: box-shadow 0.2s, transform 0.15s;
  display: flex;
  flex-direction: column;
}
.material-card:hover {
  box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 0;
}
.card-id {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}
.card-content {
  padding: 10px 16px;
  flex: 1;
}
.card-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.card-video {
  margin: 0 16px 10px;
  border-radius: 8px;
  overflow: hidden;
  background: #000;
}
.material-player {
  width: 100%;
  display: block;
  max-height: 180px;
  cursor: pointer;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 16px 12px;
}
.meta-item {
  font-size: 12px;
  color: var(--text-secondary);
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 4px;
}
.meta-file {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-actions {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid #f3f4f6;
}

.empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 48px 16px;
  font-size: 14px;
}

@media (max-width: 640px) {
  .material-grid {
    grid-template-columns: 1fr;
  }
}
</style>
