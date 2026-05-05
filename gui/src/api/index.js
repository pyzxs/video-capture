import axios from 'axios'

const BACKEND_URL = 'http://127.0.0.1:8090'

const api = axios.create({
  baseURL: BACKEND_URL + '/api',
  timeout: 600000,
})

export default api

// SSE streaming helper
async function _sseStream(url, body, onProgress, onComplete, onError) {
  const controller = new AbortController()
  try {
    const resp = await fetch(BACKEND_URL + url, {
      method: 'POST',
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
    if (!resp.ok) {
      const errText = await resp.text().catch(() => '')
      onError(new Error(errText || `HTTP ${resp.status}`))
      return { abort: () => {} }
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'progress') {
              onProgress(event)
            } else if (event.type === 'complete') {
              onComplete(event)
              return { abort: () => {} }
            } else if (event.type === 'error') {
              onError(new Error(event.message || '未知错误'))
              return { abort: () => {} }
            }
          } catch (e) {
            // skip parse errors
          }
        }
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      onError(e)
    }
  }
  return { abort: () => controller.abort() }
}

// ── Videos ──
export const videoApi = {
  list: (params) => api.get('/videos', { params }),
  get: (id) => api.get(`/videos/${id}`),
  upload: (file, language, onProgress, folderId, extractText) => {
    const fd = new FormData()
    fd.append('file', file)
    if (language) fd.append('language', language)
    if (folderId !== null && folderId !== undefined) fd.append('folder_id', folderId)
    fd.append('extract_text', extractText !== false)
    return api.post('/videos/upload', fd, {
      onUploadProgress: onProgress,
      timeout: 600000,
    })
  },
  status: (id) => api.get(`/videos/${id}/status`),
  update: (id, data) => api.patch(`/videos/${id}`, data),
  remove: (id) => api.delete(`/videos/${id}`),
  split: (id, language) => api.post(`/videos/${id}/split`, null, { params: { language } }),
  splitAnalyze: (id, language) => api.post(`/videos/${id}/split/analyze`, null, { params: { language } }),
  splitCut: (id, data) => api.post(`/videos/${id}/split/cut`, data, { timeout: 600000 }),
  smartSubtitles: (id) => api.post(`/videos/${id}/split/smart/subtitles`),
  smartExtractAudio: (id) => api.post(`/videos/${id}/split/smart/extract-audio`),
  smartAnalyze: (id, data) => api.post(`/videos/${id}/split/smart/analyze`, data, { timeout: 600000 }),
  saveToNote: (id) => api.post(`/videos/${id}/save-to-notes`),
  rewriteChat: (id, data) => api.post(`/videos/${id}/rewrite-chat`, data, { timeout: 120000 }),
  dub: (id, data) => api.post(`/videos/${id}/dub`, data, { timeout: 600000 }),
}

// ── Materials ──
export const materialApi = {
  list: (params) => api.get('/materials', { params }),
  get: (id) => api.get(`/materials/${id}`),
  create: (data, file) => {
    if (file) {
      const fd = new FormData()
      fd.append('file', file)
      for (const [k, v] of Object.entries(data)) {
        fd.append(k, v ?? '')
      }
      return api.post('/materials/upload', fd)
    }
    return api.post('/materials', data)
  },
  update: (id, data) => api.put(`/materials/${id}`, data),
  remove: (id) => api.delete(`/materials/${id}`),
  tts: (data) => api.post('/materials/tts', data, { timeout: 120000 }),
  createFromSegment: (sourceId, startFrame, endFrame) => {
    const fd = new FormData()
    fd.append('source_id', sourceId)
    fd.append('start_frame', startFrame)
    fd.append('end_frame', endFrame)
    return api.post('/materials/from-segment', fd)
  },
}

// ── Settings ──
export const settingApi = {
  list: (params) => api.get('/settings', { params }),
  update: (id, value) => api.put(`/settings/${id}`, { value }),
}

// ── Generated ──
export const generatedApi = {
  list: (params) => api.get('/generated', { params }),
  get: (id) => api.get(`/generated/${id}`),
  create: (data) => api.post('/generated', data),
  update: (id, data) => api.put(`/generated/${id}`, data),
  remove: (id) => api.delete(`/generated/${id}`),
  generate: (id, voice) => api.post(`/generated/${id}/generate`, null, { params: { voice: voice || '' }, timeout: 600000 }),
  dub: (id, voice) => api.post(`/generated/${id}/dub`, { voice }, { timeout: 600000 }),
  autoGenerate: (data) => api.post('/generated/auto-generate', data, { timeout: 600000 }),
  autoBatchGenerate: (data) => api.post('/generated/auto-batch-generate', data, { timeout: 600000 }),
  autoSearch: (data) => api.post('/generated/auto-search', data, { timeout: 60000 }),
  batchGenerateGroups: (id) => api.post(`/generated/${id}/batch-generate-groups`, null, { timeout: 600000 }),
  // SSE streaming versions — returns { abort } for cancellation
  autoBatchGenerateStream: (data, onProgress, onComplete, onError) =>
    _sseStream('/api/generated/auto-batch-generate-stream', data, onProgress, onComplete, onError),
  batchGenerateGroupsStream: (id, onProgress, onComplete, onError) =>
    _sseStream(`/api/generated/${id}/batch-generate-groups-stream`, null, onProgress, onComplete, onError),
}

// ── Folders ──
export const folderApi = {
  list: (params) => api.get('/folders', { params }),
  create: (name, folderType) => api.post('/folders', null, { params: { name, folder_type: folderType } }),
  update: (id, name) => api.put(`/folders/${id}`, null, { params: { name } }),
  remove: (id) => api.delete(`/folders/${id}`),
  moveVideo: (folderId, videoId) => api.put(`/folders/${folderId}/videos/${videoId}`),
  moveMaterial: (folderId, materialId) => api.put(`/folders/${folderId}/materials/${materialId}`),
  moveGenerated: (folderId, genId) => api.put(`/folders/${folderId}/generated/${genId}`),
  removeVideoFromFolder: (folderId, videoId) => api.delete(`/folders/${folderId}/videos/${videoId}`),
  removeMaterialFromFolder: (folderId, materialId) => api.delete(`/folders/${folderId}/materials/${materialId}`),
  removeGeneratedFromFolder: (folderId, genId) => api.delete(`/folders/${folderId}/generated/${genId}`),
}

// ── Network Download ──
export const downloadApi = {
  fromUrl: (data) => api.post('/videos/download', data, { timeout: 600000 }),
}

// ── Agents ──
export const agentApi = {
  list: () => api.get('/agents'),
  create: (data) => api.post('/agents', data),
  update: (id, data) => api.put(`/agents/${id}`, data),
  remove: (id) => api.delete(`/agents/${id}`),
  chat: (id, messages, prompt) => api.post(`/agents/${id}/chat`, { messages, prompt }),
  chatByName: (name, prompt, messages, maxTokens) =>
    api.post(`/agents/by-name/${name}/chat`, { prompt, messages: messages || [], max_tokens: maxTokens || 2000 }),
  chatByKey: (key, prompt, messages, maxTokens) =>
    api.post(`/agents/by-key/${key}/chat`, { prompt, messages: messages || [], max_tokens: maxTokens || 2000 }),
}

// ── Notes ──
export const noteApi = {
  list: (params) => api.get('/notes', { params }),
  tree: () => api.get('/notes/tree'),
  get: (id) => api.get(`/notes/${id}`),
  create: (data) => api.post('/notes', data),
  update: (id, data) => api.put(`/notes/${id}`, data),
  remove: (id) => api.delete(`/notes/${id}`),
  uploadImage: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post('/notes/upload-image', fd)
  },
}

// ── Profile ──
export const profileApi = {
  get: () => api.get('/profile'),
  records: (page = 1, pageSize = 20) => api.get('/profile/records', { params: { page, page_size: pageSize } }),
  recharge: (code) => api.post('/profile/recharge', { code }),
}

// ── Editor ──
export const editorApi = {
  extractSubtitles: (clips) => api.post('/editor/extract-subtitles', { clips }, { timeout: 300000 }),
}

// ── Resources ──
export const resourceApi = {
  status: () => api.get('/resources/status'),
  download: () => api.post('/resources/download'),
}

// ── Export ──
export const exportApi = {
  exportFiles: (data) => api.post('/export', data, { timeout: 300000 }),
}
