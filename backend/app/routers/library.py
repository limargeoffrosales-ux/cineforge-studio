"""Character Studio, Environment Builder and Asset Library."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import audit, get_current_user
from ..models import Asset, Character, Environment, User
from ..schemas import CharacterIn, EnvironmentIn

router = APIRouter(prefix="/library", tags=["library"])


# ------------------------------------------------------------- characters
@router.get("/characters")
def list_characters(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Character).where(or_(Character.owner_id == user.id, Character.is_shared == True)).order_by(Character.created_at.desc())  # noqa: E712
    ).all()
    return [
        {
            "id": c.id, "name": c.name, "archetype": c.archetype, "description": c.description,
            "traits": c.traits, "voice": c.voice, "expressions": c.expressions,
            "wardrobe": c.wardrobe, "palette": c.palette, "is_shared": c.is_shared,
        }
        for c in rows
    ]


@router.post("/characters")
def create_character(body: CharacterIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = Character(owner_id=user.id, **body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    audit(db, user.id, "character.create", c.id, {"name": c.name})
    return {"id": c.id, **body.model_dump()}


@router.patch("/characters/{char_id}")
def update_character(char_id: str, body: CharacterIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Character, char_id)
    if not c or (c.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Character not found.")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    audit(db, user.id, "character.update", c.id)
    return {"id": c.id, **body.model_dump()}


@router.delete("/characters/{char_id}")
def delete_character(char_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Character, char_id)
    if not c or (c.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Character not found.")
    db.delete(c)
    db.commit()
    audit(db, user.id, "character.delete", char_id)
    return {"ok": True}


# ---------------------------------------------------------- environments
@router.get("/environments")
def list_environments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Environment).where(or_(Environment.owner_id == user.id, Environment.is_shared == True)).order_by(Environment.created_at.desc())  # noqa: E712
    ).all()
    return [
        {
            "id": e.id, "name": e.name, "category": e.category, "description": e.description,
            "lighting": e.lighting, "weather": e.weather, "palette": e.palette, "is_shared": e.is_shared,
        }
        for e in rows
    ]


@router.post("/environments")
def create_environment(body: EnvironmentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = Environment(owner_id=user.id, **body.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    audit(db, user.id, "environment.create", e.id, {"name": e.name})
    return {"id": e.id, **body.model_dump()}


@router.patch("/environments/{env_id}")
def update_environment(env_id: str, body: EnvironmentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = db.get(Environment, env_id)
    if not e or (e.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Environment not found.")
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    db.commit()
    audit(db, user.id, "environment.update", e.id)
    return {"id": e.id, **body.model_dump()}


@router.delete("/environments/{env_id}")
def delete_environment(env_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    e = db.get(Environment, env_id)
    if not e or (e.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Environment not found.")
    db.delete(e)
    db.commit()
    audit(db, user.id, "environment.delete", env_id)
    return {"ok": True}


# ----------------------------------------------------------------- assets
ASSET_KINDS = ["logo", "font", "music", "watermark", "footage", "intro", "outro", "brand_kit"]


@router.get("/assets")
def list_assets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Asset).where(Asset.owner_id == user.id).order_by(Asset.created_at.desc())).all()
    return [
        {"id": a.id, "kind": a.kind, "name": a.name, "url": a.url, "meta": a.meta}
        for a in rows
    ]


@router.post("/assets")
def create_asset(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    kind = body.get("kind", "footage")
    if kind not in ASSET_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {ASSET_KINDS}")
    a = Asset(owner_id=user.id, kind=kind, name=body.get("name", "untitled"), url=body.get("url", ""), meta=body.get("meta", {}))
    db.add(a)
    db.commit()
    db.refresh(a)
    audit(db, user.id, "asset.create", a.id, {"kind": kind})
    return {"id": a.id, "kind": a.kind, "name": a.name, "url": a.url, "meta": a.meta}


@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = db.get(Asset, asset_id)
    if not a or (a.owner_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="Asset not found.")
    db.delete(a)
    db.commit()
    audit(db, user.id, "asset.delete", asset_id)
    return {"ok": True}
