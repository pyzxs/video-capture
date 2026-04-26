import { ref } from 'vue'
import { folderApi } from '../api/index.js'

const folders = ref([])
const selectedFolderId = ref(null)

export function useFolders() {
  const loadFolders = async (folderType) => {
    try {
      const res = await folderApi.list({ folder_type: folderType })
      folders.value = res.data.items || []
    } catch (e) {
      folders.value = []
    }
  }

  const selectFolder = (id) => {
    selectedFolderId.value = id
  }

  return {
    folders,
    selectedFolderId,
    loadFolders,
    selectFolder,
  }
}
