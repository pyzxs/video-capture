from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.db.engine import Base


class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, default="")
    folder_type = Column(String(50), nullable=False, default="video")  # video, material, generated
    created_at = Column(DateTime, default=datetime.utcnow)

    videos = relationship("Video", back_populates="folder", lazy="select")
    materials = relationship("Material", back_populates="folder", lazy="select")
    generated_videos = relationship("GeneratedVideo", back_populates="folder", lazy="select")


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
    status = Column(String(50), default="completed")  # completed, processing, failed
    thumbnail = Column(String(1024), default="")
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    folder = relationship("Folder", back_populates="videos", lazy="joined")


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
    thumbnail = Column(String(1024), default="")
    status = Column(Integer, default=1)  # 1=有效, 0=缓存
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)

    folder = relationship("Folder", back_populates="materials", lazy="joined")


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
    thumbnail = Column(String(1024), default="")
    data = Column(Text, default="{}")
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    folder = relationship("Folder", back_populates="generated_videos", lazy="joined")


class Agent(Base):
    """智能体 — 绑定提示词，用于自动生成内容（大模型从系统配置读取）。"""
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, default="")
    name = Column(String(255), nullable=False, default="")
    prompt = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Note(Base):
    """笔记 — 支持笔记和文件夹，通过 parent_id 实现树形结构。"""
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False, default="")
    content = Column(Text, default="")
    parent_id = Column(Integer, ForeignKey("notes.id"), nullable=True)
    tp = Column(String(20), nullable=False, default="note")  # note or folder
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Setting(Base):
    """系统配置 — 从数据库读取，替代 .env 环境变量。"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, default="")
    group = Column(String(100), default="general")
    description = Column(String(500), default="")
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
