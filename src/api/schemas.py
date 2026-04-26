from datetime import datetime
from pydantic import BaseModel, Field


# ── Video ──

class VideoOut(BaseModel):
    id: int
    filename: str
    filepath: str
    duration: float
    frame_width: int
    frame_height: int
    frame_rate: float
    content: str | None = ""
    status: str = "completed"
    folder_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoStatusOut(BaseModel):
    id: int
    status: str
    content: str = ""
    filename: str = ""


class VideoCreate(BaseModel):
    filename: str = ""
    filepath: str
    duration: float = 0.0
    frame_width: int = 0
    frame_height: int = 0
    frame_rate: float = 0.0
    content: str = ""


class VideoUpdate(BaseModel):
    filename: str | None = None
    content: str | None = None


class VideoSplitRequest(BaseModel):
    language: str = "zh"


class VideoSplitOut(BaseModel):
    material_count: int
    material_ids: list[int] = []


class ParagraphItem(BaseModel):
    seq_index: int
    start: float
    end: float
    text: str
    title: str = ""


class SplitAnalyzeOut(BaseModel):
    paragraphs: list[ParagraphItem]
    total_duration: float


class SplitCutRequest(BaseModel):
    paragraphs: list[ParagraphItem]




class VideoDubRequest(BaseModel):
    voice: str | None = None
class VideoDownloadRequest(BaseModel):
    channel: str = ""
    urls: str = ""
    proxy: str = ""
    folder_id: int | None = None


# ── Material ──

class MaterialBase(BaseModel):
    type: str = "video"
    content: str | None = ""
    start_time: float = 0.0
    end_time: float = 0.0
    frame_width: int = 0
    frame_height: int = 0
    frame_rate: float = 0.0
    filename: str | None = ""
    filepath: str | None = ""
    status: int = 1
    folder_id: int | None = None


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    type: str | None = None
    content: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    frame_rate: float | None = None
    filename: str | None = None
    filepath: str | None = None
    status: int | None = None
    folder_id: int | None = None


class MaterialOut(MaterialBase):
    id: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

class SplitCutOut(BaseModel):
    material_count: int
    material_ids: list[int] = []
    materials: list[MaterialOut] = []


# ── GeneratedVideo ──

class GeneratedVideoOut(BaseModel):
    id: int
    title: str
    script: str
    tts_voice: str
    output_filepath: str
    duration: float
    frame_width: int
    frame_height: int
    frame_rate: float
    status: str
    error_message: str
    material_count: int
    data: str = "{}"
    folder_id: int | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class GeneratedVideoCreate(BaseModel):
    title: str = ""
    script: str = ""
    tts_voice: str = ""
    output_filepath: str = ""
    data: str = "{}"
    frame_width: int = 0
    frame_height: int = 0
    folder_id: int | None = None


class GeneratedVideoUpdate(BaseModel):
    title: str | None = None
    script: str | None = None
    data: str | None = None
    output_filepath: str | None = None
    frame_width: int | None = None
    frame_height: int | None = None


class MaterialTtsRequest(BaseModel):
    text: str = ""
    voice: str | None = None


class GenDubRequest(BaseModel):
    voice: str | None = None


class AutoGenerateRequest(BaseModel):
    title: str = ""
    description: str = ""
    script: str = ""
    skip_expand: bool = False
    material_ids: list[int] | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    frame_rate: float | None = None
    tts_voice: str | None = None
    folder_id: int | None = None


# ── Paginated ──

class PaginatedVideos(BaseModel):
    items: list[VideoOut]
    total: int


class PaginatedMaterials(BaseModel):
    items: list[MaterialOut]
    total: int


# ── Settings ──

class SettingOut(BaseModel):
    id: int
    key: str
    value: str
    group: str
    description: str
    is_active: int = 1

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    value: str = ""


# ── Agent ──

class AgentOut(BaseModel):
    id: int
    key: str = ""
    name: str
    prompt: str = ""
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    key: str = ""
    name: str = ""
    prompt: str = ""


class AgentUpdate(BaseModel):
    key: str | None = None
    name: str | None = None
    prompt: str | None = None


class AgentChatRequest(BaseModel):
    messages: list[dict] = []
    prompt: str = ""
    max_tokens: int = 2000


class AgentChatResponse(BaseModel):
    content: str


# ── Notes ──

class NoteOut(BaseModel):
    id: int
    title: str = ""
    content: str = ""
    parent_id: int | None = None
    tp: str = "note"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class NoteTreeOut(NoteOut):
    children: list["NoteTreeOut"] = []


class NoteCreate(BaseModel):
    title: str = ""
    content: str = ""
    parent_id: int | None = None
    tp: str = "note"


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    parent_id: int | None = None
    tp: str | None = None
