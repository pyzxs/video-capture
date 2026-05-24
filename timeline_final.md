# Timeline 时间线配置说明

时间线是将素材按照视频创意进行编排和特效设计的产物。时间线包含**轨道（Track）**、**素材片段（Clip）**、**效果（Effect）** 3 种对象，描述一个**确定的、可播放的**时空序列——播放器可以逐帧渲染出单一输出。

批量组合生产的需求由独立的 [BatchComposition](#batchcomposition-批量编排) 模型承载，不混入时间线。

---

## Timeline 整体结构

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| videoTracks | [VideoTrack](#videotrack)[] | 否，videoTracks 为空时 audioTracks 必须非空 | 视频轨列表。多个轨道的层叠顺序与数组元素顺序一致：数组中第一个元素的图层在最底层，第二个元素在其之上，以此类推。 |
| audioTracks | [AudioTrack](#audiotrack)[] | 否，audioTracks 为空时 videoTracks 必须非空 | 音频轨列表。 |
| imageTracks | 已合并至 videoTracks，不再独立维护 | - | 图片素材使用 VideoTrack 编排，通过 `clip.type = "image"` 区分。 |
| subtitleTracks | [SubtitleTrack](#subtitletrack)[] | 否 | 字幕轨列表。当前文字片段（`type = "text"`）存放在 VideoTrack 的 `list` 中，SubtitleTrack 是渲染层的抽象——生成时系统收集所有 `type = "text"` 的 clip 统一走 ASS 字幕压制管线。 |
| effectTracks | [EffectTrack](#effecttrack)[] | 否 | 特效轨列表（预留）。 |
| showSubtitles | Boolean | 否 | 是否在生成时自动 ASR 生成字幕并压制到视频。默认 `false`。 |
| fps | Int | 否 | 帧率，用于帧与秒之间的换算。默认 `30`。 |

> Timeline 不包含 GroupTrack。批量组合生产使用独立的 BatchComposition 模型。

---

## VideoTrack

视频轨 VideoTrack 用于编排图像素材，包括视频和图片（imageTracks 能力已合并至本轨道）。

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| type | String | 否 | 默认为 `"video"`。 |
| name | String | 否 | 轨道名称，编辑器用于轨道标签显示。如 `"主轨道"`、`"画中画"`。 |
| list | Clip[] | 是 | 素材片段列表。 |
| visible | Boolean | 否 | 轨道是否可见。默认 `true`。 |
| locked | Boolean | 否 | 轨道是否锁定。默认 `false`。 |
| muted | Boolean | 否 | 轨道是否静音。默认 `false`。 |
| mainTrack | Boolean | 否 | **预留**。指定当前轨道是否为主轨道，主轨道时长决定成片时长。默认 `false`。 |
| trackShortenMode | String | 否 | **预留**。当前轨道比主轨道长时的自适应缩短模式。 |
| trackExpandMode | String | 否 | **预留**。当前轨道比主轨道短时的自适应扩展模式。 |

### Clip（VideoTrackClip / AudioTrackClip 通用）

Clip 描述素材在时间线上的位置和样式。**本系统采用帧定位**（`fps` 默认 30），换算关系：秒 × fps = 帧。

想把一段视频的 150~300 帧（5~10s）放在时间线 450~600 帧（15~20s）位置上：
`offsetL = 0, offsetR = 0, start = 450, end = 600`，素材入点第150帧，出点第300帧。

#### 通用字段（所有 type 共用）

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| id | String | 是 | 片段唯一标识，如 `"c-<uuid>"`。 |
| type | String | 否 | 片段类型。默认 `"video"`。取值：`"video"` / `"image"` / `"audio"` / `"text"`。 |
| materialId | Int | 否 | 素材库 Material 主键。`materialId` 和 `filepath` 有且仅有一个不为空。 |
| filepath | String | 否 | 素材文件路径。`materialId` 和 `filepath` 有且仅有一个不为空。 |
| content | String | 否 | 素材描述文案。`type = "text"` 时为文字内容。 |
| start | Float | 是 | 片段在时间线上的入点。单位：帧。 |
| end | Float | 是 | 片段在时间线上的出点。单位：帧。 |
| frameCount | Float | 否 | 片段总帧数（`end - start`），编辑器自动计算。 |
| offsetL | Float | 否 | 从素材头部裁切帧数。默认 `0`。 |
| offsetR | Float | 否 | 从素材尾部裁切帧数。默认 `0`。 |
| effect | String | 否 | 效果名称（预留）。编辑器预留字段。 |
| transitionIn | String | 否 | 入场转场名称（预留）。编辑器预留字段。 |

#### 位置与尺寸（`type = "video"` / `"image"`）

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| centerX | Float | 否 | 素材中心 X 坐标，百分比 0~100。默认 `50`（水平居中）。 |
| centerY | Float | 否 | 素材中心 Y 坐标，百分比 0~100。默认 `50`（垂直居中）。 |
| scale | Float | 否 | 缩放比例 0~100，`100` 为原始大小。默认 `100`。 |
| width | Int | 否 | 素材原始宽度（像素）。 |
| height | Int | 否 | 素材原始高度（像素）。 |

#### 文字样式（仅 `type = "text"`）

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| content | String | 是 | 文字内容。 |
| fontSize | Int | 否 | 字号。默认 `48`。 |
| fontFamily | String | 否 | 字体名称。如 `"sans-serif"`、`"Noto Sans SC"`。 |
| fontColor | String | 否 | 字体颜色 `#RRGGBB`。如 `"#ffffff"`。 |
| bold | Boolean | 否 | 是否加粗。默认 `false`。 |
| italic | Boolean | 否 | 是否斜体。默认 `false`。 |
| outline | Boolean | 否 | 是否描边。默认 `false`。 |
| outlineColor | String | 否 | 描边颜色 `#RRGGBB`。如 `"#000000"`。 |
| shadow | Boolean | 否 | 是否阴影。默认 `false`。 |
| bgEnabled | Boolean | 否 | 文字背景色是否启用。默认 `false`。 |
| bgColor | String | 否 | 背景颜色 RGBA。如 `"rgba(0,0,0,0.5)"`。 |
| textAlign | String | 否 | 对齐方式：`"left"` / `"center"` / `"right"`。默认 `"center"`。 |

#### 预留字段

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| speed | Float | 否 | **预留**。素材速率 0.1~100。 |
| opacity | Float | 否 | **预留**。不透明度 0~1。 |
| effects | Effect[] | 否 | **预留**。效果列表。 |

---

## AudioTrack

音频轨 AudioTrack 用于编排音频素材。

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| type | String | 否 | 固定 `"audio"`。 |
| name | String | 否 | 轨道名称。如 `"配音"`、`"背景音乐"`。 |
| list | Clip[] | 是 | 音频素材片段列表（Clip 中 `type = "audio"`）。 |
| visible | Boolean | 否 | 轨道是否可见。默认 `false`。 |
| locked | Boolean | 否 | 轨道是否锁定。默认 `false`。 |
| muted | Boolean | 否 | 轨道是否静音。默认 `false`。 |
| mainTrack | Boolean | 否 | **预留**。 |
| trackShortenMode | String | 否 | **预留**。 |
| trackExpandMode | String | 否 | **预留**。 |

AudioTrack 的 Clip 使用 [通用 Clip 字段](#通用字段所有-type-共用)，`type` 默认为 `"audio"`。音频 Clip 不涉及位置、尺寸、文字样式字段。

---

## SubtitleTrack

字幕轨 SubtitleTrack 用于编排字幕。

**当前实现**：文字片段（`type = "text"`）存放在 VideoTrack 的 `list` 中。SubtitleTrack 是生成时的渲染层抽象——系统遍历所有 Track 的 `list`，收集 `type = "text"` 的 Clip，统一通过 ASS 字幕渲染管线压制到视频。

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| type | String | 否 | 固定 `"text"`。 |
| name | String | 否 | 轨道名称。如 `"字幕"`。 |
| list | Clip[] | 是 | 文字片段列表（Clip 使用 [文字样式字段](#文字样式仅-type--text)）。 |
| visible | Boolean | 否 | 默认 `true`。 |
| locked | Boolean | 否 | 默认 `false`。 |

---

## EffectTrack

特效轨 EffectTrack 用于为视频整体添加特效（**预留，当前未实现**）。

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| type | String | 否 | 固定 `"effect"`。 |
| name | String | 否 | 轨道名称。 |
| list | EffectItem[] | 是 | 全局特效列表。 |

### EffectItem（预留）

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| type | String | 是 | 效果类型。 |
| subType | String | 否 | 效果子类型。 |
| timelineIn | Float | 否 | 特效起始帧。 |
| timelineOut | Float | 否 | 特效结束帧。 |

---

## 编辑器使用流程

编辑器操作 Timeline 的完整链路：

```
 加载工程                   编辑                      保存
─────────  ─────────────────────────────────  ────────────────
                                                           
GeneratedVideo.data       用户在时间轴上             更新 GeneratedVideo.data
  ─→ JSON 解析             拖入素材                      ← tracks JSON 回写
  ─→ 渲染轨道列表           调整 clip 位置（start/end）
  ─→ 渲染时间轴             裁切 clip（offsetL/offsetR）
                            调整文字样式
                            调整位置/缩放
                            增删轨道
```

**加载**：`GET /generated/{id}` → 取 `data` 字段 → `JSON.parse(data).tracks` → 按 Track 逐个渲染时间轴行。

**创建 Clip**：用户从素材库拖入文件到轨道 → 创建 Clip 对象：

```
{
  id: "c-" + uuid(),
  type: "video",       // 根据素材类型决定
  materialId: 素材库ID,
  filepath: 素材路径,
  start: 当前时间轴游标位置,
  end: 当前时间轴游标位置 + frameCount,
  frameCount: 素材总帧数,
  offsetL: 0,
  offsetR: 0,
  centerX: 50,
  centerY: 50,
  scale: 100,
  width: 素材原始宽度,
  height: 素材原始高度,
  // 文字默认值
  fontSize: 48,
  fontFamily: "sans-serif",
  fontColor: "#ffffff",
  bold: false, italic: false,
  outline: false, shadow: false,
  outlineColor: "#000000",
  bgEnabled: false,
  bgColor: "#000000",
  textAlign: "center",
  content: "",
  effect: "",
  transitionIn: null
}
```

**接续排列**：Clip 的 `start` 默认取同一轨道前一个 Clip 的 `end`，形成连续序列。用户拖拽调整 `start` 可留空或重叠。

**嵌套规则**：`type = "text"` 的 Clip 可以放在 VideoTrack.list 或独立的 SubtitleTrack 中。生成时系统统一从所有 Track 收集后走 ASS 渲染。

**保存**：编辑器将 tracks 数组序列化 → `PUT /generated/{id}` → `data = JSON.stringify({ tracks, showSubtitles, fps })`。

**生成**：`POST /generated/{id}/generate` → 后端读取 `data.tracks` → 遍历裁剪 → concat 拼接 → 字幕压制 → 缩略图 → 返回成品路径。

---

## 时序模型

### 帧定位换算

本系统采用**帧定位**（frame-based），`fps` 默认 30。

| 概念 | 本系统（帧） | 阿里云 IMS（秒） |
|---|---|---|
| 定位单位 | 帧（frame） | 秒（精确到 4 位小数） |
| 素材入点 | offsetL | In |
| 素材出点 | offsetR | Out / MaxOut |
| 时间线入点 | start | TimelineIn |
| 时间线出点 | end | TimelineOut |
| 片段时长 | frameCount（帧） | Duration（秒） |

### 裁剪逻辑

ffmpeg 命令通过帧换算：

```
start_sec = offsetL / fps
dur_sec   = (end - start - offsetR) / fps
```

---

## 生成管线

```
描述/文案 ──→ LLM 展开 ──→ 脚本
                │
素材检索/匹配 ←──┘
                │
        ┌───────┴────────┐
        │  TTS 配音生成   │
        └───────┬────────┘
                │
时间线 JSON ──→ 素材裁剪(segments) ──→ concat 拼接 ──→ 字幕压制 ──→ 成品
                                        (ASS 渲染)
```

### 三种生成模式

| 模式 | 入口 | 描述 |
|---|---|---|
| 自动混剪 | `POST /generated/auto-generate` | LLM 展开文案 → 检索/匹配素材 → TTS 配音 → 合成 |
| 编辑器生成 | `POST /generated/{id}/generate` | 读取 `data.tracks` → 逐 Clip 裁剪 → concat 拼接 → 字幕压制 |
| 批量组合生成 | `POST /generated/{id}/batch-generate-groups` | 基于 BatchComposition 模型，笛卡尔积展开 → 逐组合生成 |

### 编辑器生成流程（详细）

```
data.tracks[]
  │
  ├── 遍历所有 Track.list
  │     ├── type = "text"    → 收集到 textClips[], 统一写 ASS
  │     ├── type = "audio"   → 收集到 audioPaths[], 混音
  │     └── type = "video"/"image"
  │           ├── filepath 存在?   → 调用 _makeSegment 裁剪
  │           └── 否则查 materialId → 从 Material 表取 filepath 再裁剪
  │
  ├── concat 拼接所有 segment → 中间视频
  ├── 混入 audioPaths → 中间视频
  ├── textClips 渲染 ASS → 压制字幕 → 最终视频
  └── 生成缩略图 → 更新 GeneratedVideo 记录
```

---

## BatchComposition 批量编排

BatchComposition 是**独立于 Timeline** 的批量生产模型。

| | Timeline | BatchComposition |
|---|---|---|
| 职责 | 播放、单次渲染 | 批量组合生产 |
| 确定性 | 确定（给定时间线 → 唯一输出） | 非确定（展开后产生 N 条临时 Timeline） |
| 播放器 | 可播放 | 不可播放 |
| 产出 | 1 个视频 | N 个视频 |

### 整体结构

```
BatchComposition
  │
  ├── sharedTracks: Track[]    ← 所有组合共用的确定性轨道
  │
  └── groups: [               ← 组合组列表
        {
          videoClips: Clip[],   ← 该组的视频片段（原位嵌入 Clip 数据）
          audioClips: Clip[]    ← 该组的音频片段（原位嵌入 Clip 数据）
        },
        ...
      ]
```

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| sharedTracks | Track[] | 否 | 所有组合共用的轨道。结构与 Timeline tracks 一致。这些轨道只裁剪一次，所有组合复用。典型用途：片头片尾。 |
| groups | [CompositionGroup](#compositiongroup)[] | 是 | 批量组合组列表。组间执行笛卡尔积。 |
| fps | Int | 否 | 帧率，默认 `30`。 |

### CompositionGroup

每个 CompositionGroup 内嵌完整的 Clip 数据（非 ID 引用），自包含：

| 名称 | 类型 | 是否必填 | 描述 |
|---|---|---|---|
| videoClips | Clip[] | 是 | 该组可选的视频片段列表。不能为空。 |
| audioClips | Clip[] | 否 | 该组可选的音频片段列表。可以为空。 |

### 笛卡尔积展开

```
BatchComposition
  ├── sharedTracks: [片头 VideoTrack]
  └── groups:
       ├── Group A: { videoClips: [V1, V2], audioClips: [A1, A2] }
       └── Group B: { videoClips: [V3],      audioClips: [A2] }

↓ 展开 ↓

Group A 内配对:  (V1,A1) (V1,A2) (V2,A1) (V2,A2)  →  4 对
Group B 内配对:  (V3,A2)                          →  1 对

跨 Group 笛卡尔积: 4 × 1 = 4 条临时 Timeline

每条临时 Timeline = sharedTracks + Group A 选中片段 + Group B 选中片段
                   → 依次生成 4 个输出视频
```

**组内配对规则**：videoClips 和 audioClips 按索引一一配对。audioClips 数量不足时，多余视频无音频；videoClips 仅 1 个而 audioClips 多个时，只取第一个音频。

**去重**：相同 `(videoClip.filepath, audioClip.filepath)` 元组只保留第一个。

### 生成流程

```
BatchComposition JSON
      │
      ├── sharedTracks  →  预裁剪 1 次，所有组合复用
      │
      └── groups[] ──→ 笛卡尔积展开  →  组合列表（去重）
                            │
                 ┌──────────┴──────────┐
                 │  ThreadPoolExecutor  │  (max 10 线程)
                 └──────────┬──────────┘
                            │
            每个组合:  裁剪 Group 内视频 + 提取音频段 + 混音
                            │
            concat(共享片段 + Group 片段) → 字幕压制 → 缩略图
                            │
                      新 GeneratedVideo 记录
```

### API 端点

| 方法 | 路径 | 描述 |
|---|---|---|
| POST | `/generated/{genId}/batch-generate-groups` | 批量生成所有组合（同步） |
| POST | `/generated/{genId}/batch-generate-groups-stream` | 批量生成所有组合（SSE 流式推送） |

SSE 事件：
```
data: {"type":"progress","current":3,"total":8,"video":{...}}
data: {"type":"complete","count":8,"results":[...]}
data: {"type":"error","message":"..."}
```

### 并发控制

同步接口内部使用 `ThreadPoolExecutor`（最多 10 线程）。每个线程使用独立的数据库 Session，确保线程安全。

### 完整示例

```json
{
  "sharedTracks": [
    {
      "type": "video",
      "name": "片头",
      "list": [
        { "id": "c-intro", "type": "video", "filepath": "/videos/intro.mp4",
          "start": 0, "end": 150, "frameCount": 150 }
      ]
    }
  ],
  "groups": [
    {
      "videoClips": [
        { "id": "c-v1", "type": "video", "filepath": "/videos/cut1.mp4",
          "start": 0, "end": 300, "frameCount": 300 },
        { "id": "c-v2", "type": "video", "filepath": "/videos/cut2.mp4",
          "start": 0, "end": 300, "frameCount": 300 }
      ],
      "audioClips": [
        { "id": "c-a1", "type": "audio", "filepath": "/audio/bgm1.mp3",
          "start": 0, "end": 300, "frameCount": 300 },
        { "id": "c-a2", "type": "audio", "filepath": "/audio/bgm2.mp3",
          "start": 0, "end": 300, "frameCount": 300 }
      ]
    },
    {
      "videoClips": [
        { "id": "c-v3", "type": "video", "filepath": "/videos/cut3.mp4",
          "start": 0, "end": 300, "frameCount": 300 }
      ],
      "audioClips": [
        { "id": "c-a2", "type": "audio", "filepath": "/audio/bgm2.mp3",
          "start": 0, "end": 300, "frameCount": 300 }
      ]
    }
  ],
  "fps": 30
}
```

展开结果：

```
临时 Timeline 1: 片头 + cut1(bgm1) + cut3(bgm2)  →  video_1.mp4
临时 Timeline 2: 片头 + cut1(bgm2) + cut3(bgm2)  →  video_2.mp4
临时 Timeline 3: 片头 + cut2(bgm1) + cut3(bgm2)  →  video_3.mp4
临时 Timeline 4: 片头 + cut2(bgm2) + cut3(bgm2)  →  video_4.mp4
```

---

## 与阿里云 IMS Timeline 概念对照

| 概念 | 本系统 | 阿里云 IMS |
|---|---|---|
| 顶层结构 | `videoTracks` / `audioTracks` / `subtitleTracks` / `effectTracks` | VideoTracks / AudioTracks / ImageTracks / SubtitleTracks / EffectTracks |
| 图片轨 | 合并至 videoTracks（`clip.type = "image"`） | ImageTracks 已废弃，合并至 VideoTracks |
| 时间单位 | 帧（frame），fps 默认 30 | 秒（精确到 4 位小数） |
| Clip 数组字段 | `list` | VideoTrackClips / AudioTrackClips ... |
| 素材入点 | `offsetL` | In |
| 素材出点 | `offsetR` | Out / MaxOut |
| 时间线入点 | `start` | TimelineIn |
| 时间线出点 | `end` | TimelineOut |
| 素材位置 | `centerX` / `centerY`（百分比 0~100） | X / Y（百分比或像素） |
| 素材尺寸 | `scale` / `width` / `height` | Width / Height / AdaptMode |
| 变速 | `speed`（预留） | Speed (0.1~100) |
| 透明度 | `opacity`（预留） | Opacity (0~1) |
| 文字轨 | VideoTrack 中 `type = "text"`，ASS 管线渲染 | SubtitleTrack（云端渲染） |
| 文字样式 | `fontSize` / `fontFamily` / `fontColor` 等 | FontSize / Font / FontColor 等 |
| 转场 | `transitionIn`（预留） | Transition / DLTransition |
| 滤镜 | 未实现 | Filter |
| 特效 | `effect`（预留） | VFX |
| 遮罩 | 未支持 | mask_circle / mask_rec / mask_linear |
| 裁剪/缩放/贴边 | 未实现 | Crop / Scale / Pad / Background |
| 音量控制 | 未实现 | Volume / AFade / ALoudNorm / AEqualize |
| ASR | 本地 Whisper 引擎 | AI_ASR（云端 API） |
| 批量组合 | BatchComposition（独立模型） | 无直接对应 |
