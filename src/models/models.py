from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from src.core.database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(1024), nullable=False)
    duration = Column(Float, default=0.0)
    frame_width = Column(Integer, default=0)
    frame_height = Column(Integer, default=0)
    frame_rate = Column(Float, default=0.0)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(String(50), nullable=False, default="text")  # video, text, image, scene, sticker
    content = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False, default=0.0)
    end_time = Column(Float, nullable=False, default=0.0)
    frame_width = Column(Integer, default=0)
    frame_height = Column(Integer, default=0)
    frame_rate = Column(Float, default=0.0)
    filename = Column(String(255), default="")
    filepath = Column(String(1024), default="")


class GeneratedVideo(Base):
    """混剪生成视频 — 记录每次生成的混剪视频及其元信息。"""
    __tablename__ = "generated_videos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), default="")
    script = Column(Text, default="")
    tts_voice = Column(String(255), default="")
    output_filepath = Column(String(1024), default="")
    duration = Column(Float, default=0.0)
    frame_width = Column(Integer, default=0)
    frame_height = Column(Integer, default=0)
    frame_rate = Column(Float, default=0.0)
    status = Column(String(50), nullable=False, default="created")  # created, processing, completed, failed
    error_message = Column(Text, default="")
    material_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class GeneratedVideoMaterial(Base):
    """混剪素材关联 — 记录每个混剪视频使用了哪些素材片段及顺序。"""
    __tablename__ = "generated_video_materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    generated_video_id = Column(Integer, ForeignKey("generated_videos.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    sequence_order = Column(Integer, nullable=False, default=0)
    segment_start_time = Column(Float, default=0.0)
    segment_end_time = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
