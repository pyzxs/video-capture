from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import SettingOut, SettingUpdate
from src.config import save_config
from src.db.engine import init_db
from src.logger import get_logger
from src.db.models import Setting

logger = get_logger("api.settings")

router = APIRouter(prefix="/settings", tags=["系统配置"])


def _sync_config(db: Session):
    """将 DB 中所有配置写入 config.json。"""
    items = db.query(Setting).all()
    data = {s.key: s.value for s in items if s.is_active}
    save_config(data)


@router.get("")
def list_settings(group: str | None = None, db: Session = Depends(get_db)):
    """获取所有配置项，可按分组筛选。"""
    init_db()
    query = db.query(Setting).order_by(Setting.group, Setting.key)
    if group:
        query = query.filter(Setting.group == group)
    items = query.all()
    groups = {}
    for s in items:
        groups.setdefault(s.group, []).append(s)
    return {"groups": groups, "all": items}


@router.get("/groups")
def list_groups(db: Session = Depends(get_db)):
    """获取所有配置分组。"""
    init_db()
    rows = db.query(Setting.group).distinct().order_by(Setting.group).all()
    return {"groups": [r[0] for r in rows]}


@router.put("/{setting_id}", response_model=SettingOut)
def update_setting(setting_id: int, data: SettingUpdate, db: Session = Depends(get_db)):
    s = db.query(Setting).get(setting_id)
    if not s:
        raise HTTPException(404, "配置项不存在")
    if data.value is not None:
        s.value = data.value
    db.commit()
    db.refresh(s)
    _sync_config(db)
    return s
