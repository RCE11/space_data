from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from src.db.connection import get_db
from src.db.models import ApiKey

api_key_header = APIKeyHeader(name="X-API-Key")


def get_api_key(
    key: str = Security(api_key_header),
    db: Session = Depends(get_db),
) -> ApiKey:
    api_key = db.query(ApiKey).filter(ApiKey.key == key, ApiKey.is_active.is_(True)).first()
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return api_key
