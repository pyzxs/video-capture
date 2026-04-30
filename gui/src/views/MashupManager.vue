<template>
  <div class="view-container">
    <div class="view-header">
      <h2>混剪视频管理</h2>
      <div class="header-actions">
        <button class="btn btn-primary" @click="openCreate">手动剪辑</button>
        <button class="btn btn-info" @click="openAuto">智能混剪</button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else class="data-table-wrapper"><table class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>标题</th>
          <th>素材数</th>
          <th>状态</th>
          <th>脚本</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="g in list" :key="g.id">
          <td>{{ g.id }}</td>
          <td>{{ g.title || `混剪 #${g.id}` }}</td>
          <td>{{ g.material_count }}</td>
          <td><span class="status-badge" :class="g.status">{{ statusText(g.status) }}</span></td>
          <td class="content-cell" :title="g.script">{{ truncate(g.script, 80) || '-' }}</td>
          <td>{{ formatTime(g.created_at) }}</td>
          <td class="actions">
            <button class="btn btn-sm btn-primary" @click="openEdit(g)">编辑</button>
            <button class="btn btn-sm btn-success" @click="genVideo(g)" :disabled="g.status==='processing'">生成</button>
            <button class="btn btn-sm btn-info" @click="dubVideo(g)" :disabled="g.status==='processing'">配音</button>
            <button class="btn btn-sm btn-danger" @click="deleteGen(g)">删除</button>
          </td>
        </tr>
        <tr v-if="list.length === 0">
          <td colspan="8" class="empty">暂无混剪视频</td>
        </tr>
      </tbody>
    </table></div>

    <Pagination :page="page" :total="total" :page-size="pageSize" @change="onPageChange" />

    <!-- 编辑弹窗 -->
    <div v-if="showDialog" class="modal-overlay" @click.self="closeDialog">
      <div class="modal modal-wide">
        <h3>{{ editingId ? '编辑混剪' : '新建混剪' }}</h3>
        <div class="form">
          <label>标题
            <input v-model="form.title" placeholder="混剪标题" />
          </label>
          <label>配音脚本
            <textarea v-model="form.script" rows="4" placeholder="TTS 配音文本，留空则不配音"></textarea>
          </label>

          <!-- 素材列表 -->
          <div class="material-section">
            <div class="section-header">
              <strong>素材列表（共 {{ form.materials.length }} 个）</strong>
              <button class="btn btn-sm btn-primary" @click="showMaterialPicker = true">+ 添加素材</button>
            </div>
            <div v-if="form.materials.length === 0" class="empty-hint">请添加素材</div>
            <div v-for="(item, idx) in form.materials" :key="item.material_id" class="material-item">
              <span class="mat-order">{{ idx + 1 }}</span>
              <span class="mat-content">{{ truncate(item.content, 50) }}</span>
              <span class="mat-time">{{ item.segment_start_time.toFixed(1) }}s-{{ item.segment_end_time.toFixed(1) }}s</span>
              <div class="mat-actions">
                <button class="btn-icon" @click="moveMaterial(idx, -1)" :disabled="idx === 0">↑</button>
                <button class="btn-icon" @click="moveMaterial(idx, 1)" :disabled="idx === form.materials.length - 1">↓</button>
                <button class="btn-icon btn-icon-danger" @click="removeMaterial(idx)">✕</button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-default" @click="closeDialog">取消</button>
          <button class="btn btn-primary" @click="saveGen">保存</button>
        </div>
      </div>
    </div>

    <!-- 素材选择弹窗 -->
    <div v-if="showMaterialPicker" class="modal-overlay" @click.self="showMaterialPicker = false">
      <div class="modal">
        <h3>选择素材</h3>
        <input v-model="matSearch" placeholder="搜索素材..." class="search-input" style="width:100%;margin-bottom:12px;" />
        <div class="mat-picker-list">
          <div v-for="m in filteredMaterials" :key="m.id" class="mat-picker-item" @click="pickMaterial(m)">
            <span>#{{ m.id }}</span>
            <span class="mat-content">{{ truncate(m.content, 50) }}</span>
            <span class="mat-time">{{ m.start_time.toFixed(1) }}s-{{ m.end_time.toFixed(1) }}s</span>
          </div>
          <div v-if="filteredMaterials.length === 0" class="empty-hint">无可用素材</div>
        </div>
        <div class="modal-actions">
          <button class="btn btn-default" @click="showMaterialPicker = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- 智能混剪弹窗 -->
    <div v-if="showAutoDialog" class="modal-overlay" @click.self="closeAuto">
      <div class="modal">
        <h3>智能混剪</h3>
        <p class="modal-desc">输入标题和描述，LLM 将自动扩写脚本、检索素材、拼接并配音生成混剪视频。</p>
        <div class="form">
          <label>标题
            <input v-model="autoForm.title" placeholder="混剪标题" />
          </label>
          <label>描述
            <textarea v-model="autoForm.description" rows="4" placeholder="描述你想生成的视频内容，如：春日公园里孩子们在放风筝"></textarea>
          </label>
        </div>
        <div v-if="autoProcessing" class="upload-progress">
          <div class="progress-bar">
            <div class="progress-fill"></div>
          </div>
          <span>LLM 扩写 → 检索素材 → 拼接 → 配音，请稍候...</span>
        </div>
        <div class="modal-actions">
          <button class="btn btn-default" @click="closeAuto" :disabled="autoProcessing">取消</button>
          <button class="btn btn-primary" @click="startAuto" :disabled="!autoForm.description || autoProcessing">
            {{ autoProcessing ? '处理中...' : '开始生成' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
import { generatedApi, materialApi } from '../api/index.js'
import { useToast } from '../composables/useToast.js'
import Pagination from '../components/Pagination.vue'

export default {
  name: 'MashupManager',
  components: { Pagination },
  setup() {
    const toast = useToast()
    const list = ref([])
    const loading = ref(true)
    const page = ref(1)
    const pageSize = 20
    const total = ref(0)
    const showDialog = ref(false)
    const editingId = ref(null)
    const form = ref(emptyForm())
    const showMaterialPicker = ref(false)
    const matSearch = ref('')
    const allMaterials = ref([])

    // Auto mashup
    const showAutoDialog = ref(false)
    const autoProcessing = ref(false)
    const autoForm = ref({ title: '', description: '' })

    function emptyForm() {
      return { title: '', script: '', materials: [] }
    }

    const loadList = async () => {
      loading.value = true
      try {
        const res = await generatedApi.list({ skip: (page.value - 1) * pageSize, limit: pageSize })
        const data = res.data
        list.value = data.items || data || []
        total.value = data.total ?? (Array.isArray(data) ? data.length : 0)
      } catch (e) {
        console.error(e)
        list.value = []
      } finally {
        loading.value = false
      }
    }

    const loadMaterials = async () => {
      try {
        const res = await materialApi.list({ limit: 500 })
        const data = res.data
        allMaterials.value = data.items || data || []
      } catch (e) {
        console.error(e)
        allMaterials.value = []
      }
    }

    const filteredMaterials = computed(() => {
      const existing = new Set(form.value.materials.map(m => m.material_id))
      let list = allMaterials.value.filter(m => !existing.has(m.id))
      if (matSearch.value) {
        const q = matSearch.value.toLowerCase()
        list = list.filter(m => (m.content || '').toLowerCase().includes(q))
      }
      return list
    })

    const openCreate = () => {
      editingId.value = null
      form.value = emptyForm()
      showDialog.value = true
      loadMaterials()
    }

    const openEdit = async (g) => {
      editingId.value = g.id
      const res = await generatedApi.get(g.id)
      const detail = res.data
      form.value = {
        title: detail.title,
        script: detail.script,
        materials: (detail.materials || []).map(m => ({
          material_id: m.material_id,
          sequence_order: m.sequence_order,
          segment_start_time: m.segment_start_time,
          segment_end_time: m.segment_end_time,
          content: m.content,
          filepath: m.filepath,
        })),
      }
      showDialog.value = true
      loadMaterials()
    }

    const closeDialog = () => {
      showDialog.value = false
      editingId.value = null
    }

    const saveGen = async () => {
      try {
        const payload = {
          title: form.value.title,
          script: form.value.script,
          material_ids: form.value.materials.map(m => m.material_id),
        }
        if (editingId.value) {
          await generatedApi.update(editingId.value, payload)
          // Reorder
          await generatedApi.reorder(editingId.value, payload.material_ids)
        } else {
          await generatedApi.create(payload)
        }
        closeDialog()
        loadList()
      } catch (e) {
        toast.error('保存失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const deleteGen = async (g) => {
      if (!confirm(`确定删除混剪 #${g.id}？`)) return
      try {
        await generatedApi.remove(g.id)
        loadList()
      } catch (e) {
        toast.error('删除失败')
      }
    }

    const genVideo = async (g) => {
      try {
        await generatedApi.generate(g.id)
        toast.success('生成完成')
        loadList()
      } catch (e) {
        toast.error('生成失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const dubVideo = async (g) => {
      const voice = prompt('输入 TTS 音色（留空使用默认）:')
      try {
        await generatedApi.dub(g.id, voice || undefined)
        toast.success('配音完成')
        loadList()
      } catch (e) {
        toast.error('配音失败: ' + (e.response?.data?.detail || e.message))
      }
    }

    const moveMaterial = (idx, dir) => {
      const items = form.value.materials
      const target = idx + dir
      if (target < 0 || target >= items.length) return
      ;[items[idx], items[target]] = [items[target], items[idx]]
      // Force reactivity
      form.value.materials = [...items]
    }

    const removeMaterial = (idx) => {
      form.value.materials.splice(idx, 1)
      form.value.materials = [...form.value.materials]
    }

    const pickMaterial = (m) => {
      form.value.materials.push({
        material_id: m.id,
        sequence_order: form.value.materials.length,
        segment_start_time: m.start_time,
        segment_end_time: m.end_time,
        content: m.content,
        filepath: m.filepath,
      })
      showMaterialPicker.value = false
      matSearch.value = ''
    }

    const onPageChange = (p) => {
      page.value = p
      loadList()
    }

    // ── Auto mashup ──
    const openAuto = () => {
      autoForm.value = { title: '', description: '' }
      autoProcessing.value = false
      showAutoDialog.value = true
    }

    const closeAuto = () => {
      if (autoProcessing.value) return
      showAutoDialog.value = false
    }

    const startAuto = async () => {
      if (!autoForm.value.description) return
      autoProcessing.value = true
      try {
        await generatedApi.autoGenerate(autoForm.value)
        closeAuto()
        loadList()
      } catch (e) {
        toast.error('智能混剪失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        autoProcessing.value = false
      }
    }

    const statusText = (s) => ({ created: '已创建', processing: '处理中', completed: '已完成', failed: '失败' }[s] || s)

    const formatTime = (t) => t ? new Date(t).toLocaleString() : '-'
    const truncate = (s, n) => s && s.length > n ? s.slice(0, n) + '...' : (s || '')

    onMounted(loadList)

    return {
      list, loading, showDialog, editingId, form,
      page, pageSize, total, onPageChange,
      showMaterialPicker, matSearch, filteredMaterials,
      openCreate, openEdit, closeDialog, saveGen,
      deleteGen, genVideo, dubVideo,
      moveMaterial, removeMaterial, pickMaterial,
      showAutoDialog, autoForm, autoProcessing, openAuto, closeAuto, startAuto,
      statusText, formatTime, truncate,
    }
  },
}
</script>

<style scoped>
/* MashupManager - minimal scoped styles */
</style>
