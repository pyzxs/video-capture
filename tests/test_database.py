"""测试数据库模型（使用内存 SQLite）。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.database import Base
from src.models.models import Material, Video


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def test_create_video(session):
    v = Video(
        filename="test.mp4",
        filepath="/path/test.mp4",
        duration=120.0,
        frame_width=1920,
        frame_height=1080,
        frame_rate=30.0,
    )
    session.add(v)
    session.commit()
    assert v.id is not None
    assert v.filename == "test.mp4"
    assert v.frame_width == 1920
    assert v.frame_height == 1080
    assert v.frame_rate == 30.0


def test_create_material(session):
    m = Material(
        type="video",
        content="测试内容",
        start_time=1.0,
        end_time=5.0,
        frame_width=1920,
        frame_height=1080,
        frame_rate=30.0,
        filename="clip_0.mp4",
        filepath="/path/clip_0.mp4",
    )
    session.add(m)
    session.commit()

    assert m.id is not None
    assert m.type == "video"
    assert m.start_time == 1.0
    assert m.end_time == 5.0
    assert m.frame_width == 1920
    assert m.frame_height == 1080
    assert m.frame_rate == 30.0
    assert m.filename == "clip_0.mp4"
    assert m.filepath == "/path/clip_0.mp4"


def test_material_types(session):
    for typ in ("video", "text", "image", "scene", "sticker"):
        m = Material(
            type=typ, content=typ,
            start_time=0.0, end_time=1.0,
        )
        session.add(m)
    session.commit()

    types = [m.type for m in session.query(Material).all()]
    assert "video" in types
    assert "image" in types
    assert "scene" in types
    assert "sticker" in types
    assert "text" in types


def test_material_defaults(session):
    """测试新素材的默认值。"""
    m = Material(content="测试")
    session.add(m)
    session.commit()

    assert m.id is not None
    assert m.type == "text"
    assert m.start_time == 0.0
    assert m.end_time == 0.0
    assert m.frame_width == 0
    assert m.frame_height == 0
    assert m.frame_rate == 0.0
    assert m.filename == ""
    assert m.filepath == ""


def test_material_video_independent(session):
    """素材不依赖视频表，各自独立存储。"""
    m = Material(type="text", content="独立素材", start_time=0.0, end_time=1.0)
    session.add(m)
    session.commit()

    assert m.id is not None
    assert not hasattr(m, "video_id")
