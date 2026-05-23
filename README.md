# Video Capture — AI 智能混剪工具

Video Capture 是一款 Windows 桌面端视频处理工具，集视频下载、语音识别（ASR）、AI 文案处理、素材管理、时间线混剪、TTS 配音、字幕擦除等功能于一体，帮助内容创作者高效完成视频二次创作。

---

## 一、核心功能

### 视频下载
- 支持多平台视频下载：抖音、快手、小红书、B站、YouTube 等
- 下载完成后自动提取音频并进行语音识别，生成带时间戳的字幕文本
- 支持 SSE 流式推送下载和 ASR 处理进度

### 语音识别（ASR）
- 自动将视频音频转为带时间戳的字幕文本
- 支持多种 ASR 模型（whisper-tiny / whisper-base / SenseVoiceSmall）
- 后台异步处理队列，不阻塞其他操作

### AI 智能拆分
- 语义拆分：通过大模型分析视频内容，自动过滤片头片尾，合并相关段落
- 时间间隔拆分：按指定停顿间隔划分段落
- 支持软字幕提取或实时语音识别获取时间戳
- 智能去人声：提取中置声道 + 带通滤波器分离人声，保留背景音

### 素材管理
- 支持视频、图片、音频、文本等多种素材类型
- 手动裁剪视频片段（按帧范围）
- TTS 文字转语音生成音频素材，支持多种音色
- 向量语义搜索：素材内容自动索引，支持自然语言搜索
- 字幕擦除：上传视频到云端擦除硬字幕，可随时切换回原始文件
- 素材导出：批量导出素材文件到本地目录

### 时间线混剪编辑器
- 多轨道时间线编辑：视频轨、音频轨、字幕轨
- 支持拖拽排序、裁剪、删除片段
- 18 种视频滤镜效果：灰度、复古、暖色、冷色、模糊、霓虹等
- 11 种转场效果：淡入淡出、左右擦除、缩放、卷页、快门等
- ASS 高级字幕支持，可自定义字体样式
- 实时预览和帧级精确编辑
- 混剪方案保存和重新编辑

### 自动混剪
- 输入主题文案，AI 自动扩展内容并搜索匹配素材
- 支持素材来源过滤（全部 / 当前文件夹）
- 自动排序和拼接，生成完整混剪视频
- 批量自动生成：随机变化旁白角度，一次生成多个版本
- SSE 流式推送生成进度
- 组合生成：将多个素材进行笛卡尔积排列，批量产出变体

### TTS 语音合成
- 多种音色可选（Alex、Anna、Bella、Benjamin、Charles、Claire、David、Diana 等）
- 自动按语义断句分组合成，FFmpeg 无损拼接
- MD5 缓存：相同文本不重复合成
- 支持为混剪视频一键配音

### 笔记管理
- 树形层级笔记系统，支持文件夹和笔记混合组织
- Markdown 编辑和实时预览
- AI 智能格式化整理笔记内容
- 系统文件夹保护，防止误删

### 智能体（Agent）
- 预置 4 个默认智能体：内容扩展、字幕优化、语义分段、笔记助手
- 支持自定义创建智能体，绑定个性化提示词
- 通过大模型 API 执行各类文本处理任务

### 其他功能
- 文件夹分类管理：视频、素材、混剪视频各自独立的文件夹体系
- 系统配置：数据库存储配置项，管理后台可动态修改
- 用户中心：查看用量记录、积分充值
- 系统托盘：最小化到托盘，后台持续运行

---

## 二、安装

### 环境要求

- 操作系统：Windows 10 / Windows 11（64 位）
- 内存：8 GB 以上
- 硬盘：至少 5 GB 可用空间
- 网络：首次启动需联网下载资源

### 源码运行

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/video-capture.git
cd video-capture

# 2. 安装后端依赖
uv sync

# 3. 启动后端
python main.py

# 4. 安装前端依赖
cd gui
npm install

# 5. 启动前端开发服务器
npm run dev

# 6. 启动 Electron 桌面端
npm run electron:dev
```

### 打包构建

```bash
# 构建后端（PyInstaller）
python build.py

# 构建前端 + Electron 安装包
cd gui
npm run electron:build
```

---

## 三、项目结构

```
video-capture/
├── main.py                  # 后端入口
├── build.py                 # PyInstaller 打包脚本
├── src/
│   ├── api/                 # FastAPI 应用
│   │   ├── routes/          # 路由（videos / materials / generated / folders / agents / notes / settings / profile / editor / export）
│   │   ├── services/        # 业务逻辑层
│   │   ├── schemas.py       # Pydantic 模型
│   │   └── deps.py          # 依赖注入
│   ├── db/                  # 数据库
│   │   ├── models.py        # SQLAlchemy ORM 模型
│   │   ├── engine.py        # 数据库引擎
│   │   └── vector.py        # ChromaDB 向量存储
│   ├── services/            # 核心服务
│   │   ├── llm.py           # 大模型调用
│   │   ├── tts.py           # 语音合成
│   │   ├── agents.py        # 智能体管理
│   │   ├── asr_queue.py     # ASR 后台队列
│   │   └── search.py        # 语义搜索
│   ├── processing/          # 媒体处理
│   │   ├── ffmpeg.py        # FFmpeg 封装（18 滤镜 + 11 转场）
│   │   ├── asr.py           # 语音识别
│   │   ├── paragraph.py     # 段落合并
│   │   └── subtitle.py      # 字幕解析
│   ├── download/            # 多平台下载器
│   │   ├── douyin.py        # 抖音
│   │   ├── kuaishou.py      # 快手
│   │   ├── bilibili.py      # B站
│   │   ├── youtube.py       # YouTube
│   │   └── ...
│   ├── pipelines/           # 处理流水线
│   │   ├── download.py      # 下载流水线
│   │   ├── generate.py      # 自动混剪流水线
│   │   └── ingest.py        # 视频摄入流水线
│   ├── migrations/          # 数据库迁移脚本
│   ├── auth.py              # 机器码认证
│   ├── config.py            # 加密配置
│   └── logger.py            # 日志
├── gui/                     # 前端（Vue 3 + Electron）
│   ├── src/
│   │   ├── views/           # 页面视图
│   │   │   ├── video/       # 原始视频管理
│   │   │   ├── material/    # 素材管理
│   │   │   ├── mashup/      # 混剪编辑器 & 管理 & 自动混剪
│   │   │   ├── note/        # 笔记管理
│   │   │   ├── agent/       # 智能体管理
│   │   │   ├── settings/    # 系统配置
│   │   │   └── profile/     # 用户中心
│   │   ├── components/      # 通用 UI 组件
│   │   ├── composables/     # 组合式函数
│   │   ├── router/          # 路由
│   │   └── api/             # API 客户端
│   └── electron/            # Electron 主进程 & 预加载
└── bin/                     # 运行时工具（ffmpeg、you-get 等）
```

---

## 四、技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python / FastAPI |
| 数据库 | SQLite + SQLAlchemy ORM |
| 向量存储 | ChromaDB + BGE-M3 嵌入模型 |
| 媒体处理 | FFmpeg + MoviePy |
| AI 模型 | DeepSeek / CosyVoice2 / Whisper / SenseVoiceSmall |
| 前端框架 | Vue 3（组合式 API）+ Vue Router |
| 桌面端 | Electron（系统托盘、单实例锁、无边框窗口） |
| 构建 | PyInstaller + electron-builder |
| 包管理 | uv（Python）+ npm（Node.js） |

---

## 五、常见问题

**Q：下载视频失败？**
A：部分平台可能需要配置代理（YouTube）或 cookie。可在系统配置中设置代理地址。

**Q：合成视频失败？**
A：确保 `bin/` 目录中的 ffmpeg 可用，或将 bin 目录加入系统 PATH 环境变量。

**Q：软件占用空间较大？**
A：主要空间消耗在视频文件和模型缓存上。可定期清理不需要的视频素材，或在系统配置中调整存储路径。

**Q：ASR 结果不理想？**
A：可在系统配置中切换 ASR 模型。whisper-tiny 速度快但准确度一般，SenseVoiceSmall 对中文支持更好。

---

## 六、联系方式

如有问题或合作意向，欢迎微信联系：

<img src="gui/public/weixin.png" alt="微信二维码" width="200">

---

## 七、License

MIT License
