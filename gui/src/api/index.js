import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

export default api

// ── Videos ──
export const videoApi = {
  list: (params) => api.get('/videos', { params }),
  get: (id) => api.get(`/videos/${id}`),
  upload: (file, language) => {
    const fd = new FormData()
    fd.append('file', file)
    if (language) fd.append('language', language)
    return api.post('/videos/upload', fd)
  },
  remove: (id) => api.delete(`/videos/${id}`),
  split: (id, language) => api.post(`/videos/${id}/split`, null, { params: { language } }),
}

// ── Materials ──
export const materialApi = {
  list: (params) => api.get('/materials', { params }),
  get: (id) => api.get(`/materials/${id}`),
  create: (data) => api.post('/materials', data),
  update: (id, data) => api.put(`/materials/${id}`, data),
  remove: (id) => api.delete(`/materials/${id}`),
}

// ── Generated ──
export const generatedApi = {
  list: (params) => api.get('/generated', { params }),
  get: (id) => api.get(`/generated/${id}`),
  create: (data) => api.post('/generated', data),
  update: (id, data) => api.put(`/generated/${id}`, data),
  remove: (id) => api.delete(`/generated/${id}`),
  addMaterial: (id, materialId) => api.post(`/generated/${id}/materials`, { material_id: materialId }),
  removeMaterial: (id, materialId) => api.delete(`/generated/${id}/materials/${materialId}`),
  reorder: (id, materialIds) => api.put(`/generated/${id}/reorder`, { material_ids: materialIds }),
  generate: (id) => api.post(`/generated/${id}/generate`),
  dub: (id, voice) => api.post(`/generated/${id}/dub`, { voice }),
  autoGenerate: (data) => api.post('/generated/auto-generate', data),
}
