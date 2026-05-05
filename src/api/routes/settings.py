from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import SettingOut, SettingUpdate
from src.api.services.settings_service import list_groups, list_settings, update_setting

router = APIRouter(prefix="/settings", tags=["系统配置"])


@router.get("")
def _list_settings(group: str | None = None, db: Session = Depends(get_db)):
    return list_settings(db, group)


@router.get("/groups")
def _list_groups(db: Session = Depends(get_db)):
    return list_groups(db)


@router.put("/{setting_id}", response_model=SettingOut)
def _update_setting(setting_id: int, data: SettingUpdate, db: Session = Depends(get_db)):
    return update_setting(db, setting_id, data.value)
