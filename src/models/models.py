from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

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
