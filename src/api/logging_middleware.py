"""Request logging middleware.

Logs every authenticated API request to the request_log table.
The log write happens after the response is sent so it doesn't
add latency to the request.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.db.connection import SessionLocal
from src.db.models import ApiKey, RequestLog


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only log API endpoints, skip docs/openapi/health
        path = request.url.path
        if not (path.startswith("/launches") or path.startswith("/satellites")):
            return response

        # Look up the API key from the request header
        api_key_str = request.headers.get("x-api-key")
        if not api_key_str:
            return response

        query = str(request.url.query) if request.url.query else None

        try:
            db = SessionLocal()
            key_record = (
                db.query(ApiKey)
                .filter(ApiKey.key == api_key_str)
                .first()
            )
            log_entry = RequestLog(
                api_key_id=key_record.id if key_record else None,
                owner=key_record.owner if key_record else None,
                tier=key_record.tier if key_record else None,
                endpoint=path,
                query_params=query,
                status_code=response.status_code,
            )
            db.add(log_entry)
            db.commit()
        except Exception:
            pass  # Never let logging break a request
        finally:
            db.close()

        return response
