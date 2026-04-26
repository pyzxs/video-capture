import { ref, reactive, onMounted } from 'vue'
import { settingApi } from '../../api/index.js'
import { useToast } from '../../composables/useToast.js'

export default {
  name: 'SettingsView',
  setup() {
    const toast = useToast()
    const loading = ref(true)
    const savingId = ref(null)
    const groups = ref({})
    const editMap = reactive({})
    const pwdVisible = reactive({})

    const togglePwd = (s) => {
      pwdVisible[s.id] = !pwdVisible[s.id]
    }

    const loadSettings = async () => {
      loading.value = true
      try {
        const res = await settingApi.list()
        groups.value = res.data.groups || {}
        for (const items of Object.values(groups.value)) {
          for (const s of items) {
            editMap[s.id] = s.value
          }
        }
      } catch (e) {
        console.error(e)
        groups.value = {}
        toast.error('加载配置失败')
      } finally {
        loading.value = false
      }
    }

    const saveSetting = async (s) => {
      if (savingId.value) return
      const val = editMap[s.id]
      savingId.value = s.id
      try {
        await settingApi.update(s.id, val)
        s.value = val
        toast.success(`${s.description || s.key} 已保存`)
      } catch (e) {
        toast.error('保存失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally {
        savingId.value = null
      }
    }

    const selectDir = async (s) => {
      let dir = null
      if (window.electronAPI) {
        dir = await window.electronAPI.selectDirectory()
      } else {
        dir = prompt('请输入目录路径：', editMap[s.id] || '')
      }
      if (dir) {
        editMap[s.id] = dir
      }
    }

    onMounted(loadSettings)

    return { loading, savingId, groups, editMap, saveSetting, pwdVisible, selectDir, togglePwd }
  },
}
