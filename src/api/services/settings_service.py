"""Settings business logic: CRUD, config sync between DB and config.enc."""
from sqlalchemy.orm import Session

from src.api.response import fail_response
from src.config import save_config
from src.db.engine import init_db
from src.db.models import Setting

_VALID_KEYS = {
    "llm_model", "llm_provider", "asr_api_model",
    "vector_db_path", "embedding_model",
    "tts_model", "tts_voice", "source_dir", "material_dir", "mixed_dir",
    "thumbnail_dir", "paragraph_gap_threshold", "subtitle_crop_bottom",
    "log_level", "log_dir", "cms_base_url", "user_id", "api_key",
}


def _sync_config(db: Session):
    items = db.query(Setting).all()
    stale_ids = [s.id for s in items if s.key not in _VALID_KEYS]
    if stale_ids:
        db.query(Setting).filter(Setting.id.in_(stale_ids)).delete(synchronize_session=False)
        db.commit()
    data = {s.key: s.value for s in items if s.is_active and s.key in _VALID_KEYS}
    save_config(data)


def list_settings(db: Session, group: str | None = None) -> dict:
    init_db()
    query = db.query(Setting).filter(Setting.is_hidden == 0).order_by(Setting.group, Setting.key)
    if group:
        query = query.filter(Setting.group == group)
    items = query.all()
    groups = {}
    for s in items:
        groups.setdefault(s.group, []).append(s)
    return {"groups": groups, "all": items}


def list_groups(db: Session) -> dict:
    init_db()
    rows = db.query(Setting.group).distinct().order_by(Setting.group).all()
    return {"groups": [r[0] for r in rows]}


def update_setting(db: Session, setting_id: int, value: str) -> Setting:
    s = db.query(Setting).get(setting_id)
    if not s:
        raise fail_response(status_code=404, message="配置项不存在")
    if value is not None:
        s.value = value
    db.commit()
    db.refresh(s)
    _sync_config(db)
    return s
