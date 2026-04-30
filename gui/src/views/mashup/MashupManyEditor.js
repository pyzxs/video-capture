import { ref, computed, onMounted, watch, nextTick, onUnmounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { generatedApi, materialApi, folderApi, editorApi } from '../../api/index.js'
import { useToast } from '../../composables/useToast.js'
import { useFolders } from '../../composables/useFolders.js'

// ── Utility functions ──
// roundRect polyfill for older browsers/Electron
if (!CanvasRenderingContext2D.prototype.roundRect) {
  CanvasRenderingContext2D.prototype.roundRect = function(x, y, w, h, r) {
    if (typeof r === 'number') r = [r]
    const tl = r[0] || 0
    this.moveTo(x + tl, y)
    this.lineTo(x + w - tl, y)
    this.quadraticCurveTo(x + w, y, x + w, y + tl)
    this.lineTo(x + w, y + h - tl)
    this.quadraticCurveTo(x + w, y + h, x + w - tl, y + h)
    this.lineTo(x + tl, y + h)
    this.quadraticCurveTo(x, y + h, x, y + h - tl)
    this.lineTo(x, y + tl)
    this.quadraticCurveTo(x, y, x + tl, y)
    this.closePath()
    return this
  }
}
function getGridSize(scale) {
  const map = { 100: 100, 90: 50, 80: 20, 70: 10, 60: 80, 50: 40, 40: 20, 30: 10, 20: 40, 10: 25, 0: 10 }
  return map[Math.round(scale / 10) * 10] ?? 80
}
function getGridPixel(scale, frames) {
  let px = getGridSize(scale) * frames
  if (scale < 70) px /= 30
  if (scale < 30) px /= 6
  return px
}
function getSelectFrame(offsetX, scale) {
  const size = getGridSize(scale)
  if (scale < 70) offsetX *= 30
  if (scale < 30) offsetX *= 6
  return Math.max(0, Math.floor(offsetX / size))
}
function genId() { return 'c-' + Math.random().toString(36).slice(2, 9) }
function formatFrame(f) { const s = Math.floor(f / 30); return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}:${String(f % 30).padStart(2, '0')}` }

// ── Icon components (inline) ──
const icons = {
  video: { render() { return h('svg', { viewBox: '0 0 24 24', width: '16', height: '16', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('polygon', { points: '23 7 16 12 23 17 23 7' }), h('rect', { x: '1', y: '5', width: '15', height: '14', rx: '2', ry: '2' })]) } },
  image: { render() { return h('svg', { viewBox: '0 0 24 24', width: '16', height: '16', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('rect', { x: '3', y: '3', width: '18', height: '18', rx: '2', ry: '2' }), h('circle', { cx: '8.5', cy: '8.5', r: '1.5' }), h('polyline', { points: '21 15 16 10 5 21' })]) } },
  audio: { render() { return h('svg', { viewBox: '0 0 24 24', width: '16', height: '16', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('path', { d: 'M9 18V5l12-2v13' }), h('circle', { cx: '6', cy: '18', r: '3' }), h('circle', { cx: '18', cy: '16', r: '3' })]) } },
  text: { render() { return h('svg', { viewBox: '0 0 24 24', width: '16', height: '16', fill: 'none', stroke: 'currentColor', 'stroke-width': '2' }, [h('polyline', { points: '4 7 4 4 20 4 20 7' }), h('line', { x1: '9', y1: '20', x2: '15', y2: '20' }), h('line', { x1: '12', y1: '4', x2: '12', y2: '20' })]) } },
}

export default {
  name: 'MashupManyEditor',
  setup() {
    const route = useRoute()
    const router = useRouter()
    const toast = useToast()

    const isEditMode = computed(() => !!route.params.id)
    const editId = computed(() => route.params.id ? Number(route.params.id) : null)

    // ── Form state ──
    const form = ref({ title: '', script: '', materials: [] })
    const saving = ref(false)
    const generating = ref(false)
    const editVoice = ref('')

    // ── Resources ──
    const localMaterials = ref([])
    const localLoading = ref(false)
    const localHasMore = ref(true)
    const localPage = ref(1)
    const localPageSize = 50
    const videoMatItems = ref([])
    const imageMatItems = ref([])
    const audioMatItems = ref([])
    const textMatItems = ref([])
    const matSearch = ref('')
    const matListRef = ref(null)
    const activeMenu = ref('local')
    const matFolders = ref([])
    const matFolderId = ref('')
    const loadMatFolders = async () => {
      try {
        const res = await folderApi.list({ folder_type: 'material' })
        matFolders.value = res.data.items || []
      } catch (e) { matFolders.value = [] }
    }
    const menuItems = [
      { key: 'local', label: '本地', icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>' },
      { key: 'video', label: '视频', icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>' },
      { key: 'image', label: '图片', icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>' },
      { key: 'audio', label: '音频', icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>' },
      { key: 'text', label: '文字', icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>' },
      { key: 'effect', label: '特效', icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/></svg>' },
      { key: 'transition', label: '转场', icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12h18M3 12l4-4M3 12l4 4"/></svg>' },
    ]
    const activeMenuLabel = computed(() => menuItems.find(m => m.key === activeMenu.value)?.label || '')
    const viewMode = ref('grid')
    const panelVisible = ref(true)
    const togglePanel = () => { panelVisible.value = !panelVisible.value }

    const localFilteredMaterials = computed(() => {
      let list = localMaterials.value
      if (matSearch.value.trim()) {
        const q = matSearch.value.trim().toLowerCase()
        list = list.filter(m => (m.content || '').toLowerCase().includes(q))
      }
      return list
    })
    const textForm = ref({ content: '', styleIndex: 0 })

    // ── Track data ──
    const trackScale = ref(60)
    const trackLines = ref([])
    const selectLine = ref(-1)
    const selectIndex = ref(-1)
    const totalFrames = ref(300)
    const playStartFrame = ref(0)
    const isPlaying = ref(false)
    const selectedClip = computed(() => {
      if (selectLine.value >= 0 && selectIndex.value >= 0 && trackLines.value[selectLine.value]) {
        return trackLines.value[selectLine.value].list[selectIndex.value] || null
      }
      return null
    })

    const canSplit = computed(() => {
      if (!selectedClip.value || selectedClip.value.type !== 'video') return false
      const f = playStartFrame.value
      return f > selectedClip.value.start && f < selectedClip.value.end
    })

    const canExtractSubtitles = computed(() => {
      return selectedClip.value && selectedClip.value.type === 'audio'
    })

    const extractingSubtitles = ref(false)
    const showSubtitles = ref(true)

    const hasGroupTracks = computed(() => false)

    const toggleSubtitles = () => {
      if (!hasGroupTracks.value) return
      showSubtitles.value = !showSubtitles.value
      for (const line of trackLines.value) {
        if (line.type === 'text') {
          line.visible = showSubtitles.value
        }
      }
    }

    const canDeleteTrack = computed(() => {
      if (selectLine.value < 0 || selectIndex.value >= 0) return false
      const line = trackLines.value[selectLine.value]
      return line && !line.main
    })

    // Clip at playhead position (for playback preview)
    const playheadClip = computed(() => {
      const f = playStartFrame.value
      for (const line of trackLines.value) {
        for (const clip of line.list) {
          if (f >= clip.start && f < clip.end) return clip
        }
      }
      return null
    })

    // ── Player ──
    const playerContentRef = ref(null)
    const previewCanvas = ref(null)
    const hiddenVideoRef = ref(null)
    const hiddenAudioRef = ref(null)
    const previewLoaded = ref(false)
    let loadedVideoId = null
    let audioFromVideo = false  // true when hiddenVideoRef is the active audio source
    const imageCache = {}
    let resizeObserver = null

    // ── Text box interaction state ──
    let lastTextBoxBounds = { current: null }  // updated every drawToCanvas
    const textDragState = ref({ active: false, type: '', startX: 0, startY: 0, startCX: 50, startCY: 50, startFS: 48, startScale: 100 })

    const previewItem = computed(() => playheadClip.value || selectedClip.value)

    // Player zoom & aspect ratio controls
    const playerZoom = ref('fit')
    const playerRatioIndex = ref(0)
    const ratioOptions = [
      // ---- 横屏 ----
      { label: '3840×2160 (16:9) 4K', width: 3840, height: 2160 },
      { label: '2560×1440 (16:9) 2K', width: 2560, height: 1440 },
      { label: '1920×1080 (16:9) 全高清', width: 1920, height: 1080 },
      { label: '1280×720 (16:9) 高清', width: 1280, height: 720 },
      { label: '640×360 (16:9) 标清', width: 640, height: 360 },
      // ---- 竖屏 ----
      { label: '1080×1920 (9:16) 抖音/Shorts', width: 1080, height: 1920 },
      { label: '720×1280 (9:16) 竖屏高清', width: 720, height: 1280 },
      { label: '540×960 (9:16) 竖屏标清', width: 540, height: 960 },
      { label: '1080×2340 (19.5:9) 全面屏', width: 1080, height: 2340 },
      // ---- 方形 ----
      { label: '1080×1080 (1:1) 方屏', width: 1080, height: 1080 },
      { label: '640×640 (1:1) 方屏标清', width: 640, height: 640 },
      // ---- 其他常用 ----
      { label: '1080×1440 (3:4) 小红书', width: 1080, height: 1440 },
      { label: '1080×1350 (4:5) Instagram', width: 1080, height: 1350 },
      { label: '1920×960 (2:1) 电影宽屏', width: 1920, height: 960 },
      { label: '2560×1080 (21:9) 超宽影院', width: 2560, height: 1080 },
      { label: '1440×1080 (4:3) 经典电视', width: 1440, height: 1080 },
    ]
    const zoomOptions = [
      { label: '自适应', value: 'fit' },
      { label: '200%', value: 2 },
      { label: '100%', value: 1 },
      { label: '50%', value: 0.5 },
      { label: '20%', value: 0.2 },
    ]
    const currentRatio = computed(() => ratioOptions[playerRatioIndex.value])

    // Resize canvas to fill container (frame computed in drawToCanvas)
    function resizeCanvas() {
      const container = playerContentRef.value
      const canvas = previewCanvas.value
      if (!container || !canvas) return
      const rect = container.getBoundingClientRect()
      const w = Math.floor(Math.max(100, rect.width - 8))
      const h = Math.floor(Math.max(60, rect.height - 8))
      const ratio = window.devicePixelRatio || 1
      canvas.width = w * ratio
      canvas.height = h * ratio
      canvas.style.width = w + 'px'
      canvas.style.height = h + 'px'
      const ctx = canvas.getContext('2d')
      ctx.scale(ratio, ratio)
      drawToCanvas(false)
    }

    // Video loader for hidden video element
    let loadVideoPending = false
    function loadVideo(clip) {
      if (!clip || clip.type === 'image') { previewLoaded.value = false; loadedVideoId = null; return false }
      if (clip.material_id === loadedVideoId && previewLoaded.value) return true
      const video = hiddenVideoRef.value
      if (!video) return false
      // During playback when video element IS the audio source: skip loading
      // to avoid interrupting audio. Canvas will use whatever frame available.
      if (isPlaying.value && audioFromVideo) return previewLoaded.value
      // During playback with separate audio source: playLoop manages video
      // loading and playback at volume 0 for natural frame advancement.
      if (isPlaying.value && !audioFromVideo) {
        return clip.material_id === loadedVideoId && previewLoaded.value
      }
      loadedVideoId = clip.material_id
      // Non-playback (seeking/editing): normal async load
      previewLoaded.value = false
      video.pause()
      video.onloadeddata = () => {
        previewLoaded.value = true
        video.currentTime = Math.max(0, (playStartFrame.value - clip.start) / 30)
      }
      video.onseeked = () => { requestAnimationFrame(() => { if (previewLoaded.value) drawToCanvas(false) }) }
      video.onerror = () => { previewLoaded.value = false }
      video.src = `/api/materials/${clip.material_id}/file`
      video.load()
      return false
    }

    // Image cache loader
    function getImage(clip) {
      if (!clip || clip.type !== 'image') return null
      const id = clip.material_id
      if (imageCache[id]?.complete && imageCache[id]?.naturalWidth > 0) return imageCache[id]
      if (!imageCache[id]) {
        const img = new Image()
        imageCache[id] = img
        img.onload = () => { drawToCanvas(false) }
        img.src = `/api/materials/${id}/file`
      }
      return null
    }

    // Draw current frame to canvas (composite all clips at playhead)
    function drawToCanvas(seekVideo = true) {
      const canvas = previewCanvas.value
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const w = canvas.width / (window.devicePixelRatio || 1)
      const h = canvas.height / (window.devicePixelRatio || 1)

      // Transparent background (CSS handles the theme color)
      ctx.clearRect(0, 0, w, h)

      // Compute video frame bounds (centered, with aspect ratio & zoom)
      const baseW = currentRatio.value.width
      const baseH = currentRatio.value.height
      const aspectRatio = baseW / baseH

      let frameW, frameH
      if (playerZoom.value === 'fit') {
        frameW = w; frameH = Math.floor(frameW / aspectRatio)
        if (frameH > h) { frameH = h; frameW = Math.floor(frameH * aspectRatio) }
      } else {
        const zoom = playerZoom.value
        frameW = Math.floor(baseW * zoom)
        frameH = Math.floor(baseH * zoom)
      }
      const frameX = Math.floor((w - frameW) / 2)
      const frameY = Math.floor((h - frameH) / 2)

      const f = playStartFrame.value

      // Collect all visible clips at playhead (reverse track order: first track = top layer)
      const clips = []
      const textClips = []
      for (let t = trackLines.value.length - 1; t >= 0; t--) {
        if (!trackLines.value[t].visible) continue
        for (const clip of trackLines.value[t].list) {
          if (f >= clip.start && f < clip.end) {
            if (clip.type === 'text') {
              textClips.push(clip)
            } else {
              clips.push(clip)
            }
          }
        }
      }
      // 文字始终在最上层
      clips.push(...textClips)

      if (clips.length === 0) { previewLoaded.value = false; return }

      // ── Transition detection ──
      const transitionInfo = new Map()
      for (let t = trackLines.value.length - 1; t >= 0; t--) {
        if (!trackLines.value[t].visible) continue
        const track = trackLines.value[t]
        for (let ci = 1; ci < track.list.length; ci++) {
          const clip = track.list[ci]
          if (clip.transitionIn && clip.transitionIn.key) {
            const dur = clip.transitionIn.duration || 15
            if (f >= clip.start && f < clip.start + dur) {
              const prevClip = track.list[ci - 1]
              const progress = Math.min(1, (f - clip.start) / dur)
              transitionInfo.set(clip.id, { role: 'in', progress, type: clip.transitionIn.type })
              // Extend prev clip visibility (add to clips if not already there)
              if (prevClip && !clips.find(c => c.id === prevClip.id)) {
                clips.push(prevClip)
              }
              if (prevClip) {
                const freeze = f >= prevClip.end
                transitionInfo.set(prevClip.id, { role: 'out', progress, type: clip.transitionIn.type, freezeFrame: freeze })
              }
            }
          }
        }
      }

      // Render from bottom (index 0) to top (last index)
      for (const clip of clips) {
        const tInfo = transitionInfo.get(clip.id)
        const localFrame = (tInfo?.freezeFrame ? (clip.end - clip.start - 1) : (f - clip.start))
        if (localFrame < 0 || localFrame > clip.end - clip.start) continue

        if (clip.type === 'image') {
          const img = getImage(clip)
          if (img) {
            ctx.save()
            if (clip.effect) {
              const preset = effectPresets.find(ep => ep.key === clip.effect)
              if (preset && preset.filter) ctx.filter = preset.filter
            }
            if (tInfo) ctx.globalAlpha = tInfo.role === 'in' ? tInfo.progress : (1 - tInfo.progress)
            ctx.beginPath()
            ctx.rect(frameX, frameY, frameW, frameH)
            ctx.clip()
            ctx.translate(frameX, frameY)
            drawMediaToCanvas(ctx, img, frameW, frameH, clip)
            ctx.restore()
            // ── Selection box for selected image clip ──
            const isImgSelected = !isPlaying.value && selectIndex.value >= 0 && selectedClip.value && clip.id === selectedClip.value.id
            if (isImgSelected) {
              const mw = img.naturalWidth || clip.width || 1920
              const mh = img.naturalHeight || clip.height || 1080
              const clipScale = (clip.scale ?? 100) / 100
              const baseScale = Math.min(frameW / mw, frameH / mh)
              const finalScale = baseScale * clipScale
              const dw = mw * finalScale
              const dh = mh * finalScale
              const scx = (clip.centerX ?? 50) / 100
              const scy = (clip.centerY ?? 50) / 100
              const imgX = frameX + (frameW - dw) * scx
              const imgY = frameY + (frameH - dh) * scy
              lastTextBoxBounds.current = { x: imgX, y: imgY, w: dw, h: dh, clipId: clip.id }
              ctx.save()
              ctx.setLineDash([4, 4])
              ctx.strokeStyle = '#6c5ce7'
              ctx.lineWidth = 1.5
              ctx.strokeRect(imgX, imgY, dw, dh)
              ctx.setLineDash([])
              const hs = 8
              const half = hs / 2
              const corners = [
                [imgX - half, imgY - half],
                [imgX + dw - half, imgY - half],
                [imgX - half, imgY + dh - half],
                [imgX + dw - half, imgY + dh - half],
              ]
              ctx.fillStyle = '#ffffff'
              ctx.strokeStyle = '#6c5ce7'
              ctx.lineWidth = 1.5
              for (const [hx, hy] of corners) {
                ctx.fillRect(hx, hy, hs, hs)
                ctx.strokeRect(hx, hy, hs, hs)
              }
              ctx.restore()
            }
          }
        } else if (clip.type === 'text') {
          const txt = clip.content || ''
          if (!txt) continue
          // Text style — declare before save so selection box can use them
          const fs = clip.fontSize || 48
          const ff = clip.fontFamily || 'sans-serif'
          const fw = clip.bold ? 'bold' : 'normal'
          const fst = clip.italic ? 'italic' : 'normal'
          ctx.font = `${fst} ${fw} ${fs}px ${ff}`
          ctx.textAlign = clip.textAlign || 'center'
          ctx.textBaseline = 'middle'
          const s = (clip.scale ?? 100) / 100
          const cx = (clip.centerX ?? 50) / 100
          const cy = (clip.centerY ?? 50) / 100
          const padX = 20
          const textMaxW = frameW - padX * 2
          let tx = frameX + frameW * cx
          let ty = frameY + frameH * cy
          if (ctx.textAlign === 'left') tx = frameX + frameW * cx + padX
          else if (ctx.textAlign === 'right') tx = frameX + frameW * cx - padX
          let displayTxt = txt
          if (ctx.measureText(displayTxt).width * s > textMaxW) {
            while (ctx.measureText(displayTxt + '…').width * s > textMaxW && displayTxt.length > 1) {
              displayTxt = displayTxt.slice(0, -1)
            }
            displayTxt += '…'
          }
          // Draw clipped text
          ctx.save()
          if (clip.effect) {
            const preset = effectPresets.find(ep => ep.key === clip.effect)
            if (preset && preset.filter) ctx.filter = preset.filter
          }
          if (tInfo) ctx.globalAlpha = tInfo.role === 'in' ? tInfo.progress : (1 - tInfo.progress)
          ctx.beginPath()
          ctx.rect(frameX, frameY, frameW, frameH)
          ctx.clip()
          // Background
          if (clip.bgEnabled && clip.bgColor) {
            const metrics = ctx.measureText(txt)
            const tw = (Math.min(metrics.width, textMaxW) + 24) * s
            const th = fs * 1.5 * s
            let bgx = tx
            if (ctx.textAlign === 'center') bgx = tx - tw / 2
            else if (ctx.textAlign === 'right') bgx = tx - tw
            ctx.fillStyle = clip.bgColor
            ctx.roundRect(bgx, ty - th / 2, tw, th, 8 * s)
            ctx.fill()
          }
          // Shadow
          if (clip.shadow) {
            ctx.shadowColor = 'rgba(0,0,0,0.7)'
            ctx.shadowBlur = 8
            ctx.shadowOffsetX = 3
            ctx.shadowOffsetY = 3
          }
          // Outline
          if (clip.outline) {
            ctx.strokeStyle = clip.outlineColor || '#000000'
            ctx.lineWidth = Math.max(2 * s, (fs / 12) * s)
            ctx.lineJoin = 'round'
            ctx.strokeText(displayTxt, tx, ty)
          }
          // Fill text
          ctx.fillStyle = clip.fontColor || '#ffffff'
          ctx.fillText(displayTxt, tx, ty)
          ctx.restore()
          // ── Selection box for selected text clip ──
          const isTextSelected = !isPlaying.value && selectIndex.value >= 0 && selectedClip.value && clip.id === selectedClip.value.id
          if (isTextSelected) {
            const metrics = ctx.measureText(displayTxt)
            const textW = metrics.width * s
            const textH = fs * 1.2 * s
            const boxPad = 12 * s
            const boxW = textW + boxPad * 2
            const boxH = textH + boxPad * 2
            let boxX = tx
            if (ctx.textAlign === 'center') boxX = tx - boxW / 2
            else if (ctx.textAlign === 'right') boxX = tx - boxW
            const boxY = ty - boxH / 2
            // Store bounds for mouse hit-testing
            lastTextBoxBounds.current = { x: boxX, y: boxY, w: boxW, h: boxH, tx, ty, clipId: clip.id }
            ctx.save()
            ctx.setLineDash([4, 4])
            ctx.strokeStyle = '#6c5ce7'
            ctx.lineWidth = 1.5
            ctx.strokeRect(boxX, boxY, boxW, boxH)
            ctx.setLineDash([])
            // Corner handles
            const hs = 8
            const half = hs / 2
            const corners = [
              [boxX - half, boxY - half],
              [boxX + boxW - half, boxY - half],
              [boxX - half, boxY + boxH - half],
              [boxX + boxW - half, boxY + boxH - half],
            ]
            ctx.fillStyle = '#ffffff'
            ctx.strokeStyle = '#6c5ce7'
            ctx.lineWidth = 1.5
            for (const [hx, hy] of corners) {
              ctx.fillRect(hx, hy, hs, hs)
              ctx.strokeRect(hx, hy, hs, hs)
            }
            ctx.restore()
          }
        } else if (clip.type === 'audio') {
        } else if (clip.type === 'audio') {
            // Audio clips contribute sound only, no video frame to render
          } else {
          if (!loadVideo(clip)) continue
          const video = hiddenVideoRef.value
          if (!video) continue
          // During playback with separate audio source, the video plays at
          // volume 0 (managed by syncVideoForPlayback) so frames advance
          // naturally. No seeking needed.
          if (seekVideo && !isPlaying.value) {
            const targetTime = Math.max(0, localFrame / 30)
            if (Math.abs(video.currentTime - targetTime) > 0.15) {
              video.currentTime = targetTime
            }
          }
          // Clip video to frame area (overlays can extend beyond via translation)
          ctx.save()
          if (clip.effect) {
            const preset = effectPresets.find(ep => ep.key === clip.effect)
            if (preset && preset.filter) ctx.filter = preset.filter
          }
          if (tInfo) ctx.globalAlpha = tInfo.role === 'in' ? tInfo.progress : (1 - tInfo.progress)
          ctx.beginPath()
          ctx.rect(frameX, frameY, frameW, frameH)
          ctx.clip()
          ctx.translate(frameX, frameY)
          drawMediaToCanvas(ctx, video, frameW, frameH, clip)
          ctx.restore()
        }
      }

      // Fade overlays for fadeblack/fadewhite transitions
      for (const [, info] of transitionInfo) {
        if (info.role === 'in' && (info.type === 'fadeblack' || info.type === 'fadewhite')) {
          ctx.save()
          const overlayAlpha = info.progress <= 0.5 ? info.progress * 2 : (1 - info.progress) * 2
          ctx.fillStyle = info.type === 'fadeblack' ? '#000' : '#fff'
          ctx.globalAlpha = overlayAlpha
          ctx.fillRect(frameX, frameY, frameW, frameH)
          ctx.restore()
        }
      }
    }

    function drawMediaToCanvas(ctx, media, w, h, clip) {
      const mw = media.videoWidth || media.naturalWidth || 1920
      const mh = media.videoHeight || media.naturalHeight || 1080
      if (!mw || !mh) return
      const clipScale = (clip?.scale ?? 100) / 100
      const baseScale = Math.min(w / mw, h / mh)
      const finalScale = baseScale * clipScale
      const dw = mw * finalScale
      const dh = mh * finalScale
      const cx = (clip?.centerX ?? 50) / 100
      const cy = (clip?.centerY ?? 50) / 100
      const x = (w - dw) * cx
      const y = (h - dh) * cy
      ctx.drawImage(media, x, y, dw, dh)
    }

    // Check if a clip is on a track that can play audio
    function isClipAudible(clip) {
      if (!clip) return false
      if (clip.type !== 'video' && clip.type !== 'audio') return false
      for (const line of trackLines.value) {
        if (line.muted) continue
        if (line.list.includes(clip)) return true
      }
      return false
    }

    // Find the best clip that carries audio at the given frame position
    function findAudioClip(frame) {
      for (const line of trackLines.value) {
        if (line.muted) continue
        for (const clip of line.list) {
          if (frame >= clip.start && frame < clip.end && (clip.type === 'video' || clip.type === 'audio')) return clip
        }
      }
      return null
    }

    // ── Playback (requestAnimationFrame) ──
    let playRaf = null
    const togglePlay = () => {
      if (isPlaying.value) {
        isPlaying.value = false
        if (playRaf) cancelAnimationFrame(playRaf)
        const video = hiddenVideoRef.value
        if (video) { video.pause(); video.volume = 1 }
        const audio = hiddenAudioRef.value
        if (audio) audio.pause()
      } else {
        if (playStartFrame.value >= totalFrames.value) playStartFrame.value = 0
        isPlaying.value = true
        // Use audioClip (from findAudioClip) for audio playback — it finds
        // audio/video clips on non-muted tracks regardless of playheadClip
        const audioClip = findAudioClip(playStartFrame.value)
        if (audioClip && audioClip.type === 'audio' && hiddenAudioRef.value) {
          audioFromVideo = false
          const audioEl = hiddenAudioRef.value
          const lf = Math.max(0, playStartFrame.value - audioClip.start)
          const seekTo = lf / 30
          audioEl.src = `/api/materials/${audioClip.material_id}/file`
          // Wait for metadata before seeking and playing, otherwise
          // currentTime and play() may fail silently
          const startAudio = () => {
            audioEl.currentTime = seekTo
            audioEl.play().catch(e => console.warn('Audio play error:', e))
          }
          if (audioEl.readyState >= HTMLMediaElement.HAVE_METADATA) {
            startAudio()
          } else {
            audioEl.addEventListener('loadedmetadata', startAudio, { once: true })
          }
        } else if (audioClip && audioClip.type === 'video' && hiddenVideoRef.value) {
          audioFromVideo = true
          const video = hiddenVideoRef.value
          const lf = Math.max(0, playStartFrame.value - audioClip.start)
          const seekToVideo = lf / 30
          if (audioClip.material_id !== loadedVideoId) {
            loadedVideoId = audioClip.material_id
            previewLoaded.value = true
            video.src = `/api/materials/${audioClip.material_id}/file`
            const startVideo = () => {
              video.currentTime = seekToVideo
              video.play().catch(e => console.warn('Video play error:', e))
            }
            if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
              startVideo()
            } else {
              video.addEventListener('loadedmetadata', startVideo, { once: true })
            }
          } else {
            video.currentTime = seekToVideo
            video.play().catch(e => console.warn('Video play error:', e))
          }
        }
        // When audio comes from separate element, also play visible video
        // at volume 0 so frames advance naturally for visual rendering.
        if (!audioFromVideo) {
          const vClip = findVideoClip(playStartFrame.value)
          if (vClip && hiddenVideoRef.value) {
            const v = hiddenVideoRef.value
            const lfv = Math.max(0, playStartFrame.value - vClip.start)
            if (vClip.material_id !== loadedVideoId) {
              loadedVideoId = vClip.material_id
              previewLoaded.value = true
              v.src = `/api/materials/${vClip.material_id}/file`
            }
            v.volume = 0
            v.currentTime = lfv / 30
            v.play().catch(() => {})
          }
        }
        playRaf = requestAnimationFrame(playLoop)
      }
    }
    function playLoop() {
      if (!isPlaying.value) return
      const audioClip = findAudioClip(playStartFrame.value)
      // Sync playback off audio-bearing clip from findAudioClip (handles
      // overlapping tracks: image on track 1 + video on track 2, etc.)
      if (audioClip && audioClip.type === 'audio' && hiddenAudioRef.value) {
        const audioEl = hiddenAudioRef.value
        // Only stop if media has loaded data AND is paused (not still loading)
        if (audioEl.paused && !audioEl.ended && audioEl.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) { isPlaying.value = false; return }
        const clipFrame = Math.floor((audioEl.currentTime || 0) * 30)
        playStartFrame.value = audioClip.start + clipFrame
      } else if (audioClip && audioClip.type === 'video' && hiddenVideoRef.value) {
        const video = hiddenVideoRef.value
        if (video.paused && !video.ended && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) { isPlaying.value = false; return }
        const clipFrame = Math.floor((video.currentTime || 0) * 30)
        playStartFrame.value = audioClip.start + clipFrame
      } else {
        // Pause any media when on a muted/non-audio region
        if (hiddenAudioRef.value) hiddenAudioRef.value.pause()
        if (audioFromVideo && hiddenVideoRef.value) hiddenVideoRef.value.pause()
        playStartFrame.value++
      }
      // Sync video for visual rendering when video is not the audio source
      if (!audioFromVideo) {
        syncVideoForPlayback()
      }
      if (playStartFrame.value >= totalFrames.value) {
        playStartFrame.value = 0
        isPlaying.value = false
        const video = hiddenVideoRef.value
        if (video) { video.pause(); video.volume = 1 }
        const audio = hiddenAudioRef.value
        if (audio) audio.pause()
        return
      }
      drawToCanvas(false)
      playRaf = requestAnimationFrame(playLoop)
    }

    // Find the best video clip for visual rendering at the given frame
    // (only considers visible tracks, can be muted since visual ≠ audio)
    function findVideoClip(frame) {
      for (const line of trackLines.value) {
        if (!line.visible) continue
        for (const clip of line.list) {
          if (frame >= clip.start && frame < clip.end && clip.type === 'video') return clip
        }
      }
      return null
    }

    // During playback when audio comes from a separate element,
    // keep video playing at volume 0 so frames advance naturally.
    // Handles clip transitions by loading new video src when needed.
    let syncVideoLoading = false
    function syncVideoForPlayback() {
      const vClip = findVideoClip(playStartFrame.value)
      const video = hiddenVideoRef.value
      if (!video || !vClip) {
        if (video) video.pause()
        return
      }
      const lf = Math.max(0, playStartFrame.value - vClip.start)
      if (vClip.material_id !== loadedVideoId) {
        if (syncVideoLoading) return
        syncVideoLoading = true
        loadedVideoId = vClip.material_id
        previewLoaded.value = false
        video.pause()
        video.onloadeddata = () => {
          previewLoaded.value = true
          syncVideoLoading = false
          video.volume = 0
          video.currentTime = lf / 30
          video.play().catch(() => {})
          video.onloadeddata = null
        }
        video.onerror = () => { syncVideoLoading = false; previewLoaded.value = false }
        video.src = `/api/materials/${vClip.material_id}/file`
        video.load()
      } else if (video.paused && previewLoaded.value) {
        video.volume = 0
        video.currentTime = lf / 30
        video.play().catch(() => {})
      }
    }

    // ── Playhead seek on timeline ──
    function onTimelineSeek(ev) {
      const area = ev.currentTarget
      if (!area) return
      const rect = area.getBoundingClientRect()
      const x = ev.clientX - rect.left + scrollLeft
      playStartFrame.value = Math.max(0, Math.min(totalFrames.value, getSelectFrame(x, trackScale.value)))
      const onMove = (e) => {
        const rx = e.clientX - rect.left + scrollLeft
        playStartFrame.value = Math.max(0, Math.min(totalFrames.value, getSelectFrame(rx, trackScale.value)))
      }
      const onUp = () => {
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', onUp)
      }
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
    }

    // ── Panel sizes ──
    const attrWidth = ref(280)
    const trackHeight = ref(320)

    // ── Drag state ──
    const dragClipId = ref('')
    let dragData = null

    // ── Refs ──
    const trackListRef = ref(null)
    const trackRowsRef = ref(null)
    const trackIconsRef = ref(null)
    const rulerCanvas = ref(null)
    const rulerWrapRef = ref(null)

    // ── Computed clip positions ──
    const getClipStyle = (clip) => ({
      width: getGridPixel(trackScale.value, clip.end - clip.start) + 'px',
      left: getGridPixel(trackScale.value, clip.start) + 'px',
    })
    const playheadLeft = computed(() => getGridPixel(trackScale.value, playStartFrame.value))

    // ── Playback ──

    watch(selectLine, () => { selectIndex.value = -1 })

    // ── Timeline scroll sync ──
    let scrollLeft = 0
    let scrollTop = 0
    const onTrackScroll = () => {
      const el = trackListRef.value
      if (!el) return
      scrollLeft = el.scrollLeft
      scrollTop = el.scrollTop
      if (trackIconsRef.value) trackIconsRef.value.style.transform = `translateY(${-scrollTop}px)`
      drawRuler()
    }

    // ── Ruler canvas ──
    const drawRuler = () => {
      const canvas = rulerCanvas.value
      if (!canvas) return
      const wrap = rulerWrapRef.value
      if (!wrap) return
      const ratio = window.devicePixelRatio || 1
      const w = wrap.clientWidth
      const h = 26
      canvas.width = w * ratio
      canvas.height = h * ratio
      canvas.style.width = w + 'px'
      canvas.style.height = h + 'px'
      const ctx = canvas.getContext('2d')
      ctx.scale(ratio, ratio)
      ctx.fillStyle = '#f3f4f6'
      ctx.fillRect(0, 0, w, h)

      const size = getGridSize(trackScale.value)
      const step = trackScale.value > 60 ? 30 : 10
      const gridB = size * step
      const startOff = scrollLeft
      const endVal = startOff + w + gridB

      // Long ticks
      ctx.strokeStyle = '#6b7280'
      ctx.fillStyle = '#374151'
      ctx.font = '10px sans-serif'
      ctx.lineWidth = 1
      ctx.beginPath()
      for (let v = Math.floor(startOff / gridB) * gridB; v < endVal; v += gridB) {
        const x = v - startOff
        ctx.moveTo(x, 0)
        ctx.lineTo(x, h * 0.5)
        let seconds = trackScale.value >= 70 ? v / size : trackScale.value >= 30 ? v / size * 30 / 30 : v / size * 30 * 6 / 30
        seconds = Math.round(seconds)
        const label = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
        ctx.fillText(label, x + 3, 14)
      }
      ctx.stroke()

      // Short ticks
      const gridS = getGridPixel(trackScale.value, 1)
      ctx.strokeStyle = '#9ca3af'
      ctx.beginPath()
      for (let v = Math.floor(startOff / gridS) * gridS; v < endVal; v += gridS) {
        if (v % gridB === 0) continue
        const x = v - startOff
        ctx.moveTo(x, 0)
        ctx.lineTo(x, h * 0.35)
      }
      ctx.stroke()

      // Playhead thumb + triangle on the ruler
      const phLeft = getGridPixel(trackScale.value, playStartFrame.value) - startOff
      if (phLeft > -60 && phLeft < w + 60) {
        ctx.fillStyle = '#1f2937'
        // Rounded rectangle thumb
        const tw = 10, th = 8, rx = 2
        const tx = phLeft - tw / 2, ty = 1
        ctx.beginPath()
        ctx.moveTo(tx + rx, ty)
        ctx.lineTo(tx + tw - rx, ty)
        ctx.quadraticCurveTo(tx + tw, ty, tx + tw, ty + rx)
        ctx.lineTo(tx + tw, ty + th - rx)
        ctx.quadraticCurveTo(tx + tw, ty + th, tx + tw - rx, ty + th)
        ctx.lineTo(tx + rx, ty + th)
        ctx.quadraticCurveTo(tx, ty + th, tx, ty + th - rx)
        ctx.lineTo(tx, ty + rx)
        ctx.quadraticCurveTo(tx, ty, tx + rx, ty)
        ctx.closePath()
        ctx.fill()
        // Triangle below thumb, tip at ruler bottom
        ctx.beginPath()
        ctx.moveTo(phLeft, h - 1)
        ctx.lineTo(phLeft - 4, ty + th)
        ctx.lineTo(phLeft + 4, ty + th)
        ctx.closePath()
        ctx.fill()
      }
    }

    // ── Track height utilities ──
    const trackHeightMap = { video: 64, audio: 48, image: 48, text: 32 }
    const trackHeightClass = (t) => `th-${t}`
    const trackTypeName = (t) => ({ video: '视频轨道', audio: '音频轨道', image: '图片轨道', text: '文字轨道' }[t] || t)
    const trackIconComp = (t) => icons[t] || icons.video
    const typeLabel = (t) => ({ video: '视频', image: '图片', scene: '场景', audio: '音频', text: '文字' }[t] || t || '素材')

    // ── Effect/Transition helpers ──
    const applyEffect = (key) => {
      if (selectedClip.value) {
        selectedClip.value.effect = key
        drawToCanvas(false)
      }
    }
    const setTransition = (li, ci, preset) => {
      const clip = trackLines.value[li]?.list[ci]
      if (!clip) return
      if (preset.key) {
        clip.transitionIn = { key: preset.key, type: preset.type, duration: preset.duration || 15, direction: preset.key.replace(/wipe/, '') || 'left' }
      } else {
        clip.transitionIn = null
      }
      drawToCanvas(false)
    }
    const getTransitionName = (key) => {
      const tp = transitionPresets.find(p => p.key === key)
      return tp ? tp.name : key
    }
    const applyTransitionAtPlayhead = (preset) => {
      const f = playStartFrame.value
      for (const line of trackLines.value) {
        for (let ci = 1; ci < line.list.length; ci++) {
          const clip = line.list[ci]
          const boundary = clip.start
          if (Math.abs(f - boundary) <= 15) {
            if (preset.key) {
              clip.transitionIn = { key: preset.key, type: preset.type, duration: preset.duration || 15, direction: preset.key.replace(/wipe/, '') || 'left' }
            } else {
              clip.transitionIn = null
            }
            toast.success(`已应用转场: ${preset.name}`)
            drawToCanvas(false)
            return
          }
        }
      }
      toast.warning('请将播放头置于两个片段交界处附近')
    }

    // ── Text style presets (花字) ──
    const textStylePresets = [
      { name: '默认白', fontSize: 48, fontColor: '#ffffff', bold: false, italic: false, shadow: false, outline: false, outlineColor: '#000000', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '黄金标题', fontSize: 64, fontColor: '#ffdd00', bold: true, italic: false, shadow: true, outline: false, outlineColor: '#000000', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '描边白', fontSize: 48, fontColor: '#ffffff', bold: true, italic: false, shadow: false, outline: true, outlineColor: '#000000', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '阴影字', fontSize: 48, fontColor: '#ffffff', bold: false, italic: false, shadow: true, outline: false, outlineColor: '#000000', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '黑底白', fontSize: 48, fontColor: '#ffffff', bold: false, italic: false, shadow: false, outline: false, outlineColor: '#000000', bgColor: 'rgba(0,0,0,0.6)', bgEnabled: true, textAlign: 'center' },
      { name: '红粉粗斜', fontSize: 48, fontColor: '#ff6b6b', bold: true, italic: true, shadow: false, outline: false, outlineColor: '#000000', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '青色文艺', fontSize: 40, fontColor: '#64d8cb', bold: false, italic: true, shadow: false, outline: false, outlineColor: '#000000', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '橙色醒目', fontSize: 56, fontColor: '#ff9f43', bold: true, italic: false, shadow: true, outline: false, outlineColor: '#000000', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '蓝白描边', fontSize: 52, fontColor: '#54a0ff', bold: true, italic: false, shadow: false, outline: true, outlineColor: '#ffffff', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '荧光绿', fontSize: 44, fontColor: '#00d2d3', bold: true, italic: false, shadow: true, outline: true, outlineColor: '#1e272e', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '暗夜金', fontSize: 50, fontColor: '#f7d794', bold: true, italic: false, shadow: false, outline: false, outlineColor: '#000000', bgColor: 'rgba(30,39,46,0.8)', bgEnabled: true, textAlign: 'center' },
      { name: '渐变紫', fontSize: 46, fontColor: '#c084fc', bold: false, italic: false, shadow: true, outline: false, outlineColor: '#000000', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '大标题', fontSize: 72, fontColor: '#ffffff', bold: true, italic: false, shadow: true, outline: true, outlineColor: '#1e293b', bgColor: '#000000', bgEnabled: false, textAlign: 'center' },
      { name: '粉嫩少女', fontSize: 42, fontColor: '#f472b6', bold: false, italic: true, shadow: false, outline: false, outlineColor: '#000000', bgColor: 'rgba(251,207,232,0.2)', bgEnabled: true, textAlign: 'center' },
      { name: '科技蓝', fontSize: 50, fontColor: '#38bdf8', bold: true, italic: false, shadow: false, outline: true, outlineColor: '#0f172a', bgColor: 'rgba(15,23,42,0.7)', bgEnabled: true, textAlign: 'center' },
    ]
    // ── Effect presets (特效) ──
    const effectPresets = [
      { key: '', name: '无', filter: '', icon: 'circle' },
      { key: 'gray', name: '黑白', filter: 'grayscale(1)', icon: 'gray' },
      { key: 'sepia', name: '怀旧', filter: 'sepia(0.8) contrast(1.1)', icon: 'sepia' },
      { key: 'bright', name: '提亮', filter: 'brightness(1.3)', icon: 'bright' },
      { key: 'dark', name: '暗调', filter: 'brightness(0.6)', icon: 'dark' },
      { key: 'hcontrast', name: '高对比', filter: 'contrast(1.6) saturate(1.1)', icon: 'hcontrast' },
      { key: 'saturate', name: '高饱和', filter: 'saturate(2.0)', icon: 'saturate' },
      { key: 'desat', name: '低饱和', filter: 'saturate(0.3)', icon: 'desat' },
      { key: 'vintage', name: '复古', filter: 'sepia(0.5) contrast(1.1) saturate(0.8)', icon: 'vintage' },
      { key: 'cool', name: '冷色调', filter: 'sepia(0.2) hue-rotate(180deg) saturate(1.2)', icon: 'cool' },
      { key: 'warm', name: '暖色调', filter: 'sepia(0.3) hue-rotate(-30deg) saturate(1.4)', icon: 'warm' },
      { key: 'blur', name: '模糊', filter: 'blur(4px)', icon: 'blur' },
      { key: 'noir', name: '胶片', filter: 'grayscale(0.9) contrast(1.4) brightness(0.85)', icon: 'noir' },
      { key: 'dramatic', name: '戏剧', filter: 'contrast(1.6) brightness(0.9) saturate(1.3)', icon: 'dramatic' },
      { key: 'soft', name: '柔光', filter: 'brightness(1.1) contrast(0.9) saturate(0.9) blur(0.5px)', icon: 'soft' },
      { key: 'invert', name: '反相', filter: 'invert(1)', icon: 'invert' },
      { key: 'pastel', name: '粉彩', filter: 'saturate(0.7) brightness(1.15) contrast(0.9)', icon: 'pastel' },
      { key: 'neon', name: '霓虹', filter: 'brightness(1.2) contrast(1.5) saturate(2.5)', icon: 'neon' },
      { key: 'edgeglow', name: '边缘发光', filter: 'brightness(1.08) contrast(1.05) drop-shadow(0 0 6px rgba(255,255,255,0.4))', icon: 'edgeglow' },
    ]

    // ── Transition presets (转场) ──
    const transitionPresets = [
      { key: '', name: '无', duration: 0, type: 'none', icon: 'trans-none' },
      { key: 'crossfade', name: '淡入淡出', duration: 15, type: 'crossfade', icon: 'crossfade' },
      { key: 'fadeblack', name: '黑场过渡', duration: 15, type: 'fadeblack', icon: 'fadeblack' },
      { key: 'fadewhite', name: '白场过渡', duration: 15, type: 'fadewhite', icon: 'fadewhite' },
      { key: 'wipeleft', name: '向左擦除', duration: 15, type: 'wipeleft', icon: 'wipeleft' },
      { key: 'wiperight', name: '向右擦除', duration: 15, type: 'wiperight', icon: 'wiperight' },
      { key: 'wipeup', name: '向上擦除', duration: 15, type: 'wipeup', icon: 'wipeup' },
      { key: 'wipedown', name: '向下擦除', duration: 15, type: 'wipedown', icon: 'wipedown' },
      { key: 'zoomblur', name: '缩放模糊', duration: 15, type: 'zoomblur', icon: 'zoomblur' },
      { key: 'pagecurl', name: '翻页', duration: 15, type: 'pagecurl', icon: 'pagecurl' },
      { key: 'shutter', name: '百叶窗', duration: 15, type: 'shutter', icon: 'shutter' },
      { key: 'radial', name: '圆形展开', duration: 15, type: 'radial', icon: 'radial' },
    ]

    const fontFamilies = [
      { value: 'sans-serif', label: '无衬线' },
      { value: 'serif', label: '衬线' },
      { value: 'monospace', label: '等宽' },
      { value: 'SimHei, sans-serif', label: '黑体' },
      { value: 'Microsoft YaHei, sans-serif', label: '微软雅黑' },
      { value: 'SimSun, serif', label: '宋体' },
      { value: 'KaiTi, serif', label: '楷体' },
      { value: 'FangSong, serif', label: '仿宋' },
      { value: '"Noto Sans SC", sans-serif', label: 'Noto Sans' },
    ]

    // ── Track operations ──
    const addToTimeline = (m) => {
      const frames = m.type === 'image' ? 150 : 300
      const clip = {
        id: genId(),
        type: m.type,
        material_id: m.id,
        content: m.content,
        filepath: m.filepath,
        start: 0,
        end: frames,
        frameCount: frames,
        offsetL: 0,
        offsetR: 0,
        centerX: 50,
        centerY: 50,
        scale: 100,
        width: m.frame_width || 1920,
        height: m.frame_height || 1080,
        // Text style defaults (for text materials)
        fontSize: 48,
        fontFamily: 'sans-serif',
        fontColor: '#ffffff',
        bold: false,
        italic: false,
        shadow: false,
        outline: false,
        outlineColor: '#000000',
        bgColor: '#000000',
        bgEnabled: false,
        textAlign: 'center',
        effect: '',
        transitionIn: null,
      }
      // Find best track and position
      let inserted = false
      for (const line of trackLines.value) {
        if (line.type === m.type && !line.locked) {
          const lastClip = line.list[line.list.length - 1]
          const newStart = lastClip ? lastClip.end + 1 : 0
          clip.start = newStart
          clip.end = newStart + frames
          line.list.push({ ...clip })
          selectLine.value = trackLines.value.indexOf(line)
          selectIndex.value = line.list.length - 1
          inserted = true
          break
        }
      }
      if (!inserted) {
        // Auto-create track
        const mainVideo = trackLines.value.find(l => l.main)
        if (!mainVideo) {
          trackLines.value.push(makeTrack('video', true))
        }
        const line = makeTrack(m.type)
        line.list = [{ ...clip }]
        // Insert text at top, video/audio after main, others before last
        if (m.type === 'text') {
          trackLines.value.unshift(line)
        } else if (m.type === 'video' || m.type === 'audio') {
          trackLines.value.push(line)
        } else {
          trackLines.value.splice(trackLines.value.length - 1, 0, line)
        }
        selectLine.value = trackLines.value.indexOf(line)
        selectIndex.value = 0
      }
      updateTotalFrames()
    }

    // Create a text clip from the text form (花字) and add to timeline
    const addTextToTimeline = () => {
      const txt = textForm.value.content.trim()
      if (!txt) return
      const preset = textStylePresets[textForm.value.styleIndex] || textStylePresets[0]
      const frames = 300
      const clip = {
        id: genId(),
        type: 'text',
        material_id: null,
        content: txt,
        filepath: '',
        start: 0,
        end: frames,
        frameCount: frames,
        offsetL: 0,
        offsetR: 0,
        centerX: 50,
        centerY: 50,
        scale: 100,
        width: 1920,
        height: 1080,
        // Text style properties
        fontSize: preset.fontSize,
        fontFamily: 'sans-serif',
        fontColor: preset.fontColor,
        bold: preset.bold,
        italic: preset.italic,
        shadow: preset.shadow,
        outline: preset.outline,
        outlineColor: preset.outlineColor,
        bgColor: preset.bgColor,
        bgEnabled: preset.bgEnabled,
        textAlign: preset.textAlign,
        effect: '',
        transitionIn: null,
      }
      // Find or create text track
      let targetLine = trackLines.value.find(l => l.type === 'text' && !l.locked)
      if (!targetLine) {
        targetLine = makeTrack('text')
        trackLines.value.unshift(targetLine)
      }
      const lastClip = targetLine.list[targetLine.list.length - 1]
      const newStart = lastClip ? lastClip.end + 1 : 0
      clip.start = newStart
      clip.end = newStart + frames
      targetLine.list.push({ ...clip })
      selectLine.value = trackLines.value.indexOf(targetLine)
      selectIndex.value = targetLine.list.length - 1
      updateTotalFrames()
      toast.success('已添加文字素材')
      // Reset form
      textForm.value.content = ''
      textForm.value.styleIndex = 0
    }

    const selectClip = (li, ci) => {
      const track = trackLines.value[li]
      if (track && track.locked) return
      selectLine.value = li
      selectIndex.value = ci
      const clip = track?.list[ci]
      if (clip) playStartFrame.value = clip.start
    }

    // Helper to create track objects with default state
    const makeTrack = (type, main = false) => ({ type, main, list: [], visible: true, locked: false, muted: false })

    const deleteSelected = () => {
      if (selectLine.value < 0 || selectIndex.value < 0) return
      const line = trackLines.value[selectLine.value]
      if (!line || line.locked) return
      line.list.splice(selectIndex.value, 1)
      if (line.list.length === 0 && !line.main) {
        trackLines.value.splice(selectLine.value, 1)
      }
      selectIndex.value = -1
      updateTotalFrames()
    }

    const addTrack = () => {
      const type = 'video'
      trackLines.value.push(makeTrack(type))
      toast.success(`已添加${trackTypeName(type)}`)
    }

    const deleteTrack = () => {
      if (selectLine.value < 0 || selectIndex.value >= 0) return
      const line = trackLines.value[selectLine.value]
      if (!line || line.main) { toast.warning('不能删除主轨道'); return }
      if (line.locked) { toast.warning('请先解锁轨道'); return }
      trackLines.value.splice(selectLine.value, 1)
      selectLine.value = -1
      selectIndex.value = -1
      updateTotalFrames()
      toast.success('轨道已删除')
    }

    const splitClip = () => {
      if (!canSplit.value) return
      const line = trackLines.value[selectLine.value]
      if (line && line.locked) { toast.warning('请先解锁轨道'); return }
      const clip = selectedClip.value
      const li = selectLine.value
      const ci = selectIndex.value
      const cutFrame = playStartFrame.value
      const copy = JSON.parse(JSON.stringify(clip))
      clip.end = cutFrame
      copy.id = genId()
      copy.start = cutFrame
      copy.offsetL = cutFrame - clip.start
      trackLines.value[li].list.splice(ci + 1, 0, copy)
      updateTotalFrames()
    }

    const extractSubtitles = async () => {
      if (!canExtractSubtitles.value || extractingSubtitles.value) return

      const clip = selectedClip.value
      extractingSubtitles.value = true
      try {
        const res = await editorApi.extractSubtitles([{
          material_id: clip.material_id,
          src_start: clip.offsetL ? (clip.start + clip.offsetL) / 30 : clip.start / 30,
          src_end: clip.offsetR ? (clip.end - clip.offsetR) / 30 : clip.end / 30,
          timeline_start: clip.start / 30,
        }])

        const segments = res.data?.segments || []
        if (segments.length === 0) {
          toast.warning('未识别到语音内容')
          return
        }

        // Convert seconds to frames and create text clips at timeline positions
        const subtitleClips = segments.map(seg => ({
          id: genId(),
          type: 'text',
          material_id: null,
          content: seg.text,
          filepath: '',
          start: Math.floor(seg.start * 30),
          end: Math.floor(seg.end * 30),
          frameCount: Math.floor((seg.end - seg.start) * 30),
          offsetL: 0,
          offsetR: 0,
          centerX: 50,
          centerY: 85,
          scale: 100,
          width: 1920,
          height: 1080,
          fontSize: 36,
          fontFamily: 'sans-serif',
          fontColor: '#ffffff',
          bold: false,
          italic: false,
          shadow: true,
          outline: true,
          outlineColor: '#000000',
          bgColor: 'rgba(0,0,0,0.5)',
          bgEnabled: true,
          textAlign: 'center',
          effect: '',
          transitionIn: null,
        }))

        // Find or create text track for subtitles
        let targetLine = trackLines.value.find(l => l.type === 'text' && !l.locked)
        if (!targetLine) {
          targetLine = makeTrack('text')
          targetLine.visible = showSubtitles.value
          trackLines.value.unshift(targetLine)
        }

        for (const sc of subtitleClips) {
          targetLine.list.push(sc)
        }

        updateTotalFrames()
        toast.success(`已提取 ${segments.length} 条字幕`)
      } catch (e) {
        toast.error('字幕提取失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        extractingSubtitles.value = false
      }
    }

    // ── Trim handlers ──
    let trimState = null
    const startTrim = (ev, li, ci, side) => {
      ev.stopPropagation()
      if (trackLines.value[li]?.locked) return
      const clip = trackLines.value[li].list[ci]
      if (!clip) return
      trimState = { li, ci, side, startX: ev.clientX, origStart: clip.start, origEnd: clip.end }
      document.addEventListener('mousemove', onTrimMove)
      document.addEventListener('mouseup', endTrim)
    }
    const onTrimMove = (ev) => {
      if (!trimState) return
      const clip = trackLines.value[trimState.li].list[trimState.ci]
      if (!clip) return
      const dx = ev.clientX - trimState.startX
      const frameDelta = Math.round(dx / Math.max(getGridPixel(trackScale.value, 1), 1))
      if (trimState.side === 'left') {
        const newStart = Math.max(0, Math.min(trimState.origStart + frameDelta, clip.end - 5))
        clip.start = newStart
      } else {
        const newEnd = Math.min(totalFrames.value, Math.max(trimState.origEnd + frameDelta, clip.start + 5))
        clip.end = newEnd
      }
      updateTotalFrames()
    }
    const endTrim = () => {
      trimState = null
      document.removeEventListener('mousemove', onTrimMove)
      document.removeEventListener('mouseup', endTrim)
    }

    // ── Resource drag to timeline ──
    const onResourceDragStart = (m, ev) => {
      dragData = m
      ev.dataTransfer.effectAllowed = 'copy'
      ev.dataTransfer.setData('text/plain', m.id + '')
    }

    const onTrackDragOver = (ev) => {
      ev.dataTransfer.dropEffect = 'copy'
    }

    const onTrackDrop = (ev) => {
      if (!dragData) return
      const rect = trackRowsRef.value.getBoundingClientRect()
      const x = ev.clientX - rect.left + scrollLeft
      const startFrame = getSelectFrame(x, trackScale.value)
      const m = dragData
      const frames = m.type === 'image' ? 150 : 300
      const clip = {
        id: genId(),
        type: m.type,
        material_id: m.id,
        content: m.content,
        filepath: m.filepath,
        start: startFrame,
        end: startFrame + frames,
        frameCount: frames,
        offsetL: 0,
        offsetR: 0,
        centerX: 50,
        centerY: 50,
        scale: 100,
        width: m.frame_width || 1920,
        height: m.frame_height || 1080,
        // Text style defaults
        fontSize: 48,
        fontFamily: 'sans-serif',
        fontColor: '#ffffff',
        bold: false,
        italic: false,
        shadow: false,
        outline: false,
        outlineColor: '#000000',
        bgColor: '#000000',
        bgEnabled: false,
        textAlign: 'center',
        effect: '',
        transitionIn: null,
      }
      // Find or create matching track
      let targetLine = trackLines.value.find(l => l.type === m.type && !l.locked)
      if (!targetLine) {
        targetLine = makeTrack(m.type)
        if (m.type === 'video' || m.type === 'audio') {
          trackLines.value.push(targetLine)
        } else {
          trackLines.value.unshift(targetLine)
        }
      }
      targetLine.list.push(clip)
      selectLine.value = trackLines.value.indexOf(targetLine)
      selectIndex.value = targetLine.list.length - 1
      dragData = null
      updateTotalFrames()
    }

    // ── Clip mouse drag (move) ──
    let moveState = null
    const onClipMouseDown = (ev, li, ci) => {
      if (ev.button !== 0) return
      const track = trackLines.value[li]
      if (!track || track.locked) return
      const clip = track.list[ci]
      if (!clip) return
      moveState = { li, ci, startX: ev.clientX, origStart: clip.start, origEnd: clip.end, startFrame: playStartFrame.value }
      document.addEventListener('mousemove', onMoveMove)
      document.addEventListener('mouseup', endMove)
    }
    const onMoveMove = (ev) => {
      if (!moveState) return
      const clip = trackLines.value[moveState.li]?.list[moveState.ci]
      if (!clip) return
      const dx = ev.clientX - moveState.startX
      const frameDelta = Math.round(dx / Math.max(getGridPixel(trackScale.value, 1), 1))
      const origDuration = moveState.origEnd - moveState.origStart
      clip.start = Math.max(0, moveState.origStart + frameDelta)
      clip.end = clip.start + origDuration
      updateTotalFrames()

      // Vertical: detect track switch while dragging
      if (trackRowsRef.value) {
        const rows = trackRowsRef.value.querySelectorAll('.track-row')
        for (let i = 0; i < rows.length; i++) {
          const rect = rows[i].getBoundingClientRect()
          if (ev.clientY >= rect.top && ev.clientY < rect.bottom && i !== moveState.li) {
            const cd = trackLines.value[moveState.li]?.list[moveState.ci]
            if (cd) {
              const curStart = cd.start
              trackLines.value[moveState.li].list.splice(moveState.ci, 1)
              trackLines.value[i].list.push(cd)
              moveState.startX = ev.clientX
              moveState.origStart = curStart
              moveState.origEnd = cd.end
              moveState.ci = trackLines.value[i].list.length - 1
              moveState.li = i
              selectLine.value = i
              selectIndex.value = moveState.ci
            }
            break
          }
        }
      }
    }
    const endMove = () => {
      moveState = null
      document.removeEventListener('mousemove', onMoveMove)
      document.removeEventListener('mouseup', endMove)
    }

    // ── Total frames ──
    const updateTotalFrames = () => {
      let maxFrame = 300
      for (const line of trackLines.value) {
        for (const clip of line.list) {
          if (clip.end > maxFrame) maxFrame = clip.end
        }
      }
      totalFrames.value = maxFrame + 60
    }

    // ── Scale ──
    const changeScale = (delta) => {
      trackScale.value = Math.max(0, Math.min(100, trackScale.value + delta))
    }

    // ── Panel resize ──
    const startAttrResize = (ev) => {
      const startX = ev.clientX
      const startW = attrWidth.value
      const onMove = (e) => { attrWidth.value = Math.max(200, Math.min(500, startW + (startX - e.clientX))) }
      const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp) }
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
    }
    const startTrackResize = (ev) => {
      const startY = ev.clientY
      const startH = trackHeight.value
      const onMove = (e) => { trackHeight.value = Math.max(150, Math.min(800, startH + (e.clientY - startY))) }
      const onUp = () => { document.removeEventListener('mousemove', onMove); document.removeEventListener('mouseup', onUp) }
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
    }

    // ── Upload ──
    const showUploadDialog = ref(false)
    const uploadForm = ref({ type: 'video', content: '' })
    const uploadFile = ref(null)
    const uploadFileInput = ref(null)
    const uploading = ref(false)

    const onFileChange = (e) => { uploadFile.value = e.target.files[0] || null }
    const uploadMaterial = async () => {
      if (!uploadFile.value) { toast.warning('请选择文件'); return }
      if (!uploadForm.value.content.trim()) { toast.warning('请输入内容描述'); return }
      uploading.value = true
      try {
        await materialApi.create({ type: uploadForm.value.type, content: uploadForm.value.content }, uploadFile.value)
        toast.success('上传成功')
        showUploadDialog.value = false
        uploadForm.value = { type: 'video', content: '' }
        uploadFile.value = null
        await loadMaterials()
      } catch (e) {
        toast.error('上传失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally { uploading.value = false }
    }

    // ── Save ──
    const save = async () => {
      if (!form.value.title.trim()) { toast.warning('请输入标题'); return }
      saving.value = true
      try {
        // Serialize full track data as JSON
        const trackData = trackLines.value.map(line => ({
          name: line.name,
          type: line.type,
          visible: line.visible,
          muted: line.muted,
          list: line.list.map(c => ({
            id: c.id, type: c.type, material_id: c.material_id,
            content: c.content, filepath: c.filepath,
            start: c.start, end: c.end, frameCount: c.frameCount,
            offsetL: c.offsetL, offsetR: c.offsetR,
            centerX: c.centerX, centerY: c.centerY,
            scale: c.scale, width: c.width, height: c.height,
            fontSize: c.fontSize, fontFamily: c.fontFamily, fontColor: c.fontColor,
            bold: c.bold, italic: c.italic, shadow: c.shadow,
            outline: c.outline, outlineColor: c.outlineColor,
            bgColor: c.bgColor, bgEnabled: c.bgEnabled, textAlign: c.textAlign,
            effect: c.effect, transitionIn: c.transitionIn,
          }))
        }))
        const payload = {
          title: form.value.title.trim(),
          script: form.value.script || '',
          data: JSON.stringify({ tracks: trackData }),
          frame_width: currentRatio.value.width,
          frame_height: currentRatio.value.height,
        }
        if (isEditMode.value) {
          await generatedApi.update(editId.value, payload)
          toast.success('已保存')
        } else {
          const res = await generatedApi.create(payload)
          toast.success('创建成功')
          router.replace({ name: 'MashupManyEditor', params: { id: res.data.id } })
        }
      } catch (e) {
        toast.error('保存失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally { saving.value = false }
    }

    // ── Generate ──
    const generate = async () => {
      if (!isEditMode.value) return
      generating.value = true
      try {
        await generatedApi.generate(editId.value, editVoice.value || undefined)
        toast.success('合成完成')
      } catch (e) {
        toast.error('合成失败: ' + (e.response?.data?.message || e.response?.data?.detail || e.message))
      } finally { generating.value = false }
    }

    // ── Navigation ──
    const goBack = () => router.push({ name: 'Mashups' })

    // ── Canvas mouse handlers for text drag/resize ──
    function onCanvasMouseDown(ev) {
      const clip = selectedClip.value
      if (!clip || (clip.type !== 'text' && clip.type !== 'image') || isPlaying.value) return
      const canvas = previewCanvas.value
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const mx = ev.clientX - rect.left
      const my = ev.clientY - rect.top
      const box = lastTextBoxBounds.current
      if (!box || box.clipId !== clip.id) return
      const hs = 8
      // Check corner handles first (priority over drag)
      const corners = [
        { x: box.x - hs/2, y: box.y - hs/2, type: 'se' },
        { x: box.x + box.w - hs/2, y: box.y - hs/2, type: 'ne' },
        { x: box.x - hs/2, y: box.y + box.h - hs/2, type: 'sw' },
        { x: box.x + box.w - hs/2, y: box.y + box.h - hs/2, type: 'nw' },
      ]
      for (const c of corners) {
        if (mx >= c.x && mx <= c.x + hs && my >= c.y && my <= c.y + hs) {
          textDragState.value = { active: true, type: 'resize', handle: c.type, startX: mx, startY: my, startCX: clip.centerX, startCY: clip.centerY, startFS: clip.fontSize, startScale: clip.scale }
          document.addEventListener('mousemove', onCanvasMouseMove)
          document.addEventListener('mouseup', onCanvasMouseUp)
          return
        }
      }
      // Check if inside box
      if (mx >= box.x && mx <= box.x + box.w && my >= box.y && my <= box.y + box.h) {
        textDragState.value = { active: true, type: 'drag', handle: '', startX: mx, startY: my, startCX: clip.centerX, startCY: clip.centerY, startFS: clip.fontSize, startScale: clip.scale }
        document.addEventListener('mousemove', onCanvasMouseMove)
        document.addEventListener('mouseup', onCanvasMouseUp)
      }
    }
    function onCanvasMouseMove(ev) {
      const ds = textDragState.value
      if (!ds.active) return
      const clip = selectedClip.value
      if (!clip) return
      const canvas = previewCanvas.value
      if (!canvas) return
      const rect = canvas.getBoundingClientRect()
      const mx = ev.clientX - rect.left
      const my = ev.clientY - rect.top
      const dx = mx - ds.startX
      const dy = my - ds.startY
      const frameW = currentRatio.value.width
      const frameH = currentRatio.value.height
      // Get frame display size to convert pixel delta to percentage
      const canvasW = canvas.width / (window.devicePixelRatio || 1)
      const canvasH = canvas.height / (window.devicePixelRatio || 1)
      let dispW = canvasW, dispH = canvasH
      const aspect = frameW / frameH
      if (playerZoom.value === 'fit') {
        dispW = canvasW; dispH = Math.floor(dispW / aspect)
        if (dispH > canvasH) { dispH = canvasH; dispW = Math.floor(dispH * aspect) }
      } else {
        const z = playerZoom.value
        dispW = Math.floor(frameW * z)
        dispH = Math.floor(frameH * z)
      }
      if (ds.type === 'drag') {
        if (dispW > 0 && dispH > 0) {
          clip.centerX = Math.max(0, Math.min(100, ds.startCX + (dx / dispW) * 100))
          clip.centerY = Math.max(0, Math.min(100, ds.startCY + (dy / dispH) * 100))
        }
      } else if (ds.type === 'resize') {
        const d = Math.max(dx, dy) * (ds.handle === 'nw' || ds.handle === 'se' ? 1 : -1)
        if (clip.type === 'image') {
          clip.scale = Math.max(10, Math.min(300, ds.startScale + d * 0.5))
        } else {
          clip.fontSize = Math.max(14, Math.min(300, ds.startFS + d * 0.5))
          clip.scale = Math.max(10, Math.min(300, ds.startScale + d * 0.3))
        }
      }
      drawToCanvas(false)
    }
    function onCanvasMouseUp() {
      textDragState.value = { active: false, type: '', handle: '', startX: 0, startY: 0, startCX: 50, startCY: 50, startFS: 48, startScale: 100 }
      document.removeEventListener('mousemove', onCanvasMouseMove)
      document.removeEventListener('mouseup', onCanvasMouseUp)
    }

    // ── Video playback ──
    const playingVideoId = ref(null)
    const videoRefs = {}
    const toggleVideo = (m) => {
      if (playingVideoId.value === m.id) {
        const el = videoRefs[m.id]
        if (el) { el.pause(); el.currentTime = 0 }
        playingVideoId.value = null
        return
      }
      // Stop previous
      if (playingVideoId.value !== null && videoRefs[playingVideoId.value]) {
        videoRefs[playingVideoId.value].pause()
        videoRefs[playingVideoId.value].currentTime = 0
      }
      // Play new
      const el = videoRefs[m.id]
      if (el) {
        el.muted = false
        el.play().catch(() => {})
        playingVideoId.value = m.id
      }
    }
    const onVideoEnded = (id) => {
      if (playingVideoId.value === id) {
        playingVideoId.value = null
      }
    }

    // ── Audio playback ──
    let audioEl = null
    const playingAudioId = ref(null)
    const toggleAudio = (m) => {
      if (playingAudioId.value === m.id) {
        if (audioEl) { audioEl.pause(); audioEl = null }
        playingAudioId.value = null
        return
      }
      if (audioEl) { audioEl.pause(); audioEl = null }
      const el = new Audio(`/api/materials/${m.id}/file`)
      el.onended = () => { playingAudioId.value = null; audioEl = null }
      el.onerror = () => { playingAudioId.value = null; audioEl = null }
      el.play().catch(() => { playingAudioId.value = null; audioEl = null })
      audioEl = el
      playingAudioId.value = m.id
    }

    // ── Materials loading ──
    const loadLocalMaterials = async (reset = true) => {
      if (!localHasMore.value && !reset) return
      if (localLoading.value) return
      if (reset) { localPage.value = 1; localHasMore.value = true }
      localLoading.value = true
      try {
        const skip = (localPage.value - 1) * localPageSize
        const params = { skip, limit: localPageSize, status: 1 }
        if (matFolderId.value) params.folder_id = matFolderId.value
        const res = await materialApi.list(params)
        const items = res.data?.items || res.data || []
        if (reset) { localMaterials.value = items; localPage.value = 2 }
        else { localMaterials.value = [...localMaterials.value, ...items]; localPage.value++ }
        localHasMore.value = items.length >= localPageSize
      } catch (e) { localMaterials.value = [] }
      finally { localLoading.value = false }
    }

    let matScrollTimer = null
    const onMatScroll = (e) => {
      if (matScrollTimer) return
      matScrollTimer = setTimeout(() => { matScrollTimer = null }, 200)
      const el = e.target
      if (!el || localLoading.value || !localHasMore.value) return
      if (el.scrollHeight - el.scrollTop - el.clientHeight < 200) {
        loadLocalMaterials(false)
      }
    }

    const loadTypeMaterials = async (type) => {
      try {
        const params = { type, limit: 200, status: 1 }
        if (matFolderId.value) params.folder_id = matFolderId.value
        const res = await materialApi.list(params)
        const items = res.data?.items || res.data || []
        if (type === 'video') videoMatItems.value = items
        else if (type === 'image') imageMatItems.value = items
        else if (type === 'audio') audioMatItems.value = items
        else if (type === 'text') textMatItems.value = items
      } catch (e) { /* ignore */ }
    }

    const loadGeneratedVideo = async () => {
      if (!editId.value) return
      try {
        const res = await generatedApi.get(editId.value)
        const data = res.data
        form.value.title = data.title || ''
        editVoice.value = data.tts_voice || ''
        // Restore tracks from data JSON (full editor state)
        let parsed = null
        if (data.data) {
          try { parsed = JSON.parse(data.data) } catch (e) { /* ignore */ }
        }
        if (parsed && parsed.tracks && parsed.tracks.length > 0) {
          trackLines.value = parsed.tracks.map(t => ({
            ...t,
            visible: t.visible !== false,
            locked: t.locked || false,
            muted: t.muted || false,
          }))
          updateTotalFrames()
        } else {
          trackLines.value = [makeTrack('video', true)]
        }
        // Restore aspect ratio from saved frame dimensions
        if (data.frame_width && data.frame_height) {
          const idx = ratioOptions.findIndex(r => r.width === data.frame_width && r.height === data.frame_height)
          if (idx >= 0) playerRatioIndex.value = idx
        }
      } catch (e) { toast.error('加载混剪数据失败') }
    }

    const truncate = (s, n) => s && s.length > n ? s.slice(0, n) + '...' : (s || '')

    // ── Init ──
    onMounted(() => {
      loadLocalMaterials()
      loadMatFolders()
      // Load all type panels on first mount
      loadTypeMaterials('video')
      loadTypeMaterials('image')
      loadTypeMaterials('audio')
      loadTypeMaterials('text')
      if (isEditMode.value) loadGeneratedVideo()
      else {
        trackLines.value = [makeTrack('video', true)]
      }
      nextTick(() => {
        drawRuler()
        resizeCanvas()
      })
      if (playerContentRef.value) {
        resizeObserver = new ResizeObserver(() => resizeCanvas())
        resizeObserver.observe(playerContentRef.value)
      }
    })

    onUnmounted(() => {
      if (playRaf) cancelAnimationFrame(playRaf)
      document.removeEventListener('mousemove', onTrimMove)
      document.removeEventListener('mouseup', endTrim)
      document.removeEventListener('mousemove', onMoveMove)
      document.removeEventListener('mouseup', endMove)
      document.removeEventListener('mousemove', onCanvasMouseMove)
      document.removeEventListener('mouseup', onCanvasMouseUp)
      if (resizeObserver) resizeObserver.disconnect()
    })

    watch(trackScale, () => { nextTick(drawRuler) })
    watch(previewItem, () => { nextTick(() => drawToCanvas(false)) }, { immediate: true })
    watch(playStartFrame, () => { drawToCanvas(false); drawRuler() })
    watch([playerZoom, playerRatioIndex], () => { nextTick(resizeCanvas) })
    watch(matFolderId, () => { loadLocalMaterials() })
    watch(activeMenu, (key) => {
      if (key === 'local') loadLocalMaterials()
      else if (key === 'video' && videoMatItems.value.length === 0) loadTypeMaterials('video')
      else if (key === 'image' && imageMatItems.value.length === 0) loadTypeMaterials('image')
      else if (key === 'audio' && audioMatItems.value.length === 0) loadTypeMaterials('audio')
      else if (key === 'text' && textMatItems.value.length === 0) loadTypeMaterials('text')
    })
    // Watch clip attribute changes (position, scale, text style) for live preview
    watch(() => selectedClip.value ? `${selectedClip.value.centerX}-${selectedClip.value.centerY}-${selectedClip.value.scale}-${selectedClip.value.fontSize}-${selectedClip.value.fontColor}-${selectedClip.value.bold}-${selectedClip.value.italic}-${selectedClip.value.outline}-${selectedClip.value.shadow}-${selectedClip.value.bgEnabled}-${selectedClip.value.bgColor}-${selectedClip.value.outlineColor}-${selectedClip.value.fontFamily}-${selectedClip.value.textAlign}-${selectedClip.value.effect}-${selectedClip.value.transitionIn?.key}-${selectedClip.value.content}` : null,
      () => { drawToCanvas(false) })

    // ── Effect / Transition icon renderers ──
    const effectSvgs = {
      none: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="8"/><line x1="4" y1="4" x2="20" y2="20"/></svg>',
      gray: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="2" x2="12" y2="22" opacity="0.5"/><circle cx="12" cy="12" r="5" fill="currentColor" opacity="0.15"/></svg>',
      sepia: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="6" width="16" height="12" rx="2"/><circle cx="12" cy="12" r="3"/><rect x="8" y="4" width="8" height="2" rx="1"/><line x1="16" y1="18" x2="16" y2="20"/><line x1="8" y1="18" x2="8" y2="20"/></svg>',
      bright: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5.64 5.64l2.12 2.12M16.24 16.24l2.12 2.12M5.64 18.36l2.12-2.12M16.24 7.76l2.12-2.12"/></svg>',
      dark: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2A10 10 0 0 0 2 12a10 10 0 0 0 10 10c-4-3-6-8-6-12s2-9 6-10z"/></svg>',
      hcontrast: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 2v20" stroke-width="2"/><path d="M12 2a10 10 0 0 1 0 10z" fill="currentColor" opacity="0.2"/></svg>',
      saturate: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2Q8 10 8 14a4 4 0 008 0c0-4-4-12-4-12z"/><path d="M8 14a4 4 0 008 0" stroke-width="0.5" opacity="0.3"/></svg>',
      desat: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2Q8 10 8 14a4 4 0 008 0c0-4-4-12-4-12z" opacity="0.4"/><line x1="4" y1="20" x2="20" y2="4"/></svg>',
      vintage: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="6" y="5" width="12" height="14" rx="2"/><circle cx="12" cy="12" r="4"/><rect x="7" y="3" width="10" height="3" rx="1"/><circle cx="8" cy="10" r="1" opacity="0.4"/><circle cx="16" cy="10" r="1" opacity="0.4"/></svg>',
      cool: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 3v18M3 12h18" opacity="0.3"/><line x1="5.5" y1="5.5" x2="8.5" y2="8.5"/><line x1="18.5" y1="5.5" x2="15.5" y2="8.5"/><line x1="5.5" y1="18.5" x2="8.5" y2="15.5"/><line x1="18.5" y1="18.5" x2="15.5" y2="15.5"/></svg>',
      warm: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 3c0 0-5 7-5 11a5 5 0 0010 0c0-4-5-11-5-11z"/><path d="M12 18v4M9 22h6"/></svg>',
      blur: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10" opacity="0.2"/><circle cx="12" cy="12" r="7" opacity="0.5"/><circle cx="12" cy="12" r="3"/></svg>',
      noir: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="5" width="18" height="14" rx="1"/><rect x="5" y="7" width="4" height="10"/><rect x="10" y="7" width="4" height="10"/><rect x="15" y="7" width="4" height="10"/></svg>',
      dramatic: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="12 2 15 9 22 9 16 14 18 22 12 17 6 22 8 14 2 9 9 9"/></svg>',
      soft: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 12c0-6 12-6 12 0s-12 6-12 0z" opacity="0.4"/><path d="M10 12c0-4 4-4 4 0s-4 4-4 0z"/></svg>',
      invert: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="2" x2="12" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/></svg>',
      pastel: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10" opacity="0.3"/><circle cx="12" cy="12" r="6" opacity="0.6"/><circle cx="12" cy="12" r="2"/><path d="M12 2a10 10 0 010 20" opacity="0.15" fill="currentColor"/></svg>',
      neon: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="4" x2="12" y2="20"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="12" y1="4" x2="12" y2="20" stroke-width="5" opacity="0.15"/><line x1="4" y1="12" x2="20" y2="12" stroke-width="5" opacity="0.15"/></svg>',
      edgeglow: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="5" y="5" width="14" height="14" rx="2"/><rect x="3" y="3" width="18" height="18" rx="3" opacity="0.35"/></svg>',
    }
    const transitionSvgs = {
      none: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="8"/><line x1="4" y1="4" x2="20" y2="20"/></svg>',
      crossfade: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="12" r="6" opacity="0.4"/><circle cx="16" cy="12" r="6" opacity="0.4"/><circle cx="12" cy="12" r="3" opacity="0.7"/></svg>',
      fadeblack: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="5" fill="currentColor" opacity="0.25"/></svg>',
      fadewhite: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="5" fill="currentColor" opacity="0.1"/></svg>',
      wipeleft: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="1"/><polyline points="16,8 10,12 16,16"/></svg>',
      wiperight: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="1"/><polyline points="8,8 14,12 8,16"/></svg>',
      wipeup: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="1"/><polyline points="8,16 12,10 16,16"/></svg>',
      wipedown: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="1"/><polyline points="8,8 12,14 16,8"/></svg>',
      zoomblur: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10" opacity="0.2"/><circle cx="12" cy="12" r="6" opacity="0.5"/><circle cx="12" cy="12" r="2"/></svg>',
      pagecurl: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="4" y="4" width="16" height="16" rx="1"/><path d="M14 4v4h4" opacity="0.5"/><path d="M14 8l4 12m0 0H4"/></svg>',
      shutter: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="4" width="20" height="16" rx="1"/><line x1="12" y1="4" x2="12" y2="20"/><line x1="6" y1="4" x2="6" y2="20"/><line x1="18" y1="4" x2="18" y2="20"/></svg>',
      radial: '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="2"/><circle cx="12" cy="12" r="6" opacity="0.5"/><circle cx="12" cy="12" r="10" opacity="0.2"/></svg>',
    }
    function effectSvg(key) { return effectSvgs[key] || effectSvgs.none }
    function transitionSvg(key) { return transitionSvgs[key] || transitionSvgs.none }

    return {
      h, icons,
      isEditMode, editId, form, saving, generating, editVoice,
      localMaterials, localFilteredMaterials, localLoading, localHasMore,
      videoMatItems, imageMatItems, audioMatItems, textMatItems,
      matSearch, matListRef, onMatScroll, activeMenu, menuItems, activeMenuLabel,
      matFolders, matFolderId,
      textForm, textStylePresets, fontFamilies, viewMode, panelVisible, togglePanel,
      trackScale, trackLines, selectLine, selectIndex, totalFrames,
      playStartFrame, isPlaying, selectedClip, canSplit,
      playerContentRef, previewCanvas, hiddenVideoRef, hiddenAudioRef, previewLoaded,
      previewItem, attrWidth, trackHeight,
      dragClipId, trackListRef, trackRowsRef, trackIconsRef,
      rulerCanvas, rulerWrapRef,
      playerZoom, playerRatioIndex, ratioOptions, zoomOptions, currentRatio,
      getClipStyle, playheadLeft, trackHeightClass, trackTypeName,
      trackIconComp, typeLabel,
      addToTimeline, addTextToTimeline, selectClip, deleteSelected, addTrack, deleteTrack, canDeleteTrack, splitClip,
      hasAudioTracks: canExtractSubtitles, extractingSubtitles, extractSubtitles,
      showSubtitles, toggleSubtitles, hasGroupTracks,
      startTrim, onResourceDragStart, onTrackDragOver, onTrackDrop,
      onClipMouseDown,
      changeScale, togglePlay, formatFrame,
      startAttrResize, startTrackResize,
      onTrackScroll, onTimelineSeek,
      showUploadDialog, uploadForm, uploadFileInput, uploading,
      onFileChange, uploadMaterial,
      save, generate, goBack, truncate,
      onCanvasMouseDown,
      effectPresets, transitionPresets,
      effectSvg, transitionSvg,
      applyEffect, setTransition, applyTransitionAtPlayhead, getTransitionName,
      playingVideoId, videoRefs, toggleVideo, onVideoEnded,
      playingAudioId, toggleAudio,
    }
  }
}
