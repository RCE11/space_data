import hashlib

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.db.models import ApiKey

api_key_header = APIKeyHeader(name="X-API-Key")


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def get_api_key(
    key: str = Security(api_key_header),
    db: Session = Depends(get_db),
) -> ApiKey:
    key_hash = hash_api_key(key)
    api_key = db.query(ApiKey).filter(
        ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True)
    ).first()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return api_key
