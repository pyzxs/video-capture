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
    content: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoCreate(BaseModel):
    filename: str = ""
    filepath: str
    duration: float = 0.0
    frame_width: int = 0
    frame_height: int = 0
    frame_rate: float = 0.0
    content: str = ""


class VideoSplitRequest(BaseModel):
    language: str = "zh"


class VideoSplitOut(BaseModel):
    material_count: int


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


class MaterialOut(MaterialBase):
    id: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── GeneratedVideo ──

class GenMaterialItem(BaseModel):
    material_id: int
    sequence_order: int
    segment_start_time: float = 0.0
    segment_end_time: float = 0.0
    content: str = ""
    filepath: str = ""


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
    created_at: datetime
    completed_at: datetime | None = None
    materials: list[GenMaterialItem] = []

    model_config = {"from_attributes": True}


class GeneratedVideoCreate(BaseModel):
    title: str = ""
    script: str = ""
    tts_voice: str = ""
    output_filepath: str = ""
    material_ids: list[int] = Field(default_factory=list)


class GeneratedVideoUpdate(BaseModel):
    title: str | None = None
    script: str | None = None
    status: str | None = None
    output_filepath: str | None = None


class GenMaterialAdd(BaseModel):
    material_id: int


class GenMaterialRemove(BaseModel):
    material_id: int


class GenMaterialReorder(BaseModel):
    material_ids: list[int]  # ordered list


class GenDubRequest(BaseModel):
    voice: str | None = None


class AutoGenerateRequest(BaseModel):
    title: str = ""
    description: str = ""
    conent: str = ""
    frame_width: int | None = None
    frame_height: int | None = None
    frame_rate: float | None = None
    tts_voice: str | None = None


# ── Paginated ──

class PaginatedVideos(BaseModel):
    items: list[VideoOut]
    total: int


class PaginatedMaterials(BaseModel):
    items: list[MaterialOut]
    total: int
