import json
import random
import string
from datetime import datetime, timezone, timedelta

from pydantic import ValidationError

from src.shared.config import (
    URLS_TABLE, BASE_URL, CODE_LENGTH, DEFAULT_TTL_DAYS
)
from src.shared.db import get_table
from src.shared.errors import InvalidUrlError
from src.shorten.models import ShortenRequest, ShortenResponse


# ── helpers ──────────────────────────────────────────────────────────────────

def _generate_code(length: int = CODE_LENGTH) -> str:
    """URL-safe random code: uppercase + lowercase + digits."""
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length))


def _response(status: int, body: dict) -> dict:
    """Standard API Gateway proxy response envelope."""
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }


# ── handler ───────────────────────────────────────────────────────────────────

def handler(event: dict, context) -> dict:
    """
    POST /shorten
    Body: { "url": "https://...", "alias": "optional", "ttl_days": 30 }
    Returns: ShortenResponse JSON
    """
    # 1. Parse + validate request body
    try:
        body = json.loads(event.get("body") or "{}")
        req = ShortenRequest(**body)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _response(400, {"error": str(exc)})
    except Exception:
        raise InvalidUrlError()

    # 2. Determine short code — use custom alias if provided
    table = get_table(URLS_TABLE)
    code = req.alias or _generate_code()

    # Collision check for random codes (alias is user's responsibility)
    if not req.alias:
        for _ in range(3):  # max 3 retries before giving up
            resp = table.get_item(Key={"code": code})
            if "Item" not in resp:
                break
            code = _generate_code()

    # 3. Compute timestamps and TTL
    now = datetime.now(timezone.utc)
    ttl_days = req.ttl_days or DEFAULT_TTL_DAYS
    expires_at = now + timedelta(days=ttl_days)
    ttl_epoch = int(expires_at.timestamp())   # DynamoDB TTL expects Unix epoch

    # 4. Write to DynamoDB
    # DynamoDB TTL attribute: when epoch passes, item is deleted automatically.
    # We store original_url as string (HttpUrl is serialised via str()).
    table.put_item(Item={
        "code":         code,
        "original_url": str(req.url),
        "created_at":   now.isoformat(),
        "expires_at":   expires_at.isoformat(),
        "ttl":          ttl_epoch,              # DynamoDB native TTL field
        "clicks":       0,
    })

    # 5. Build and return response
    result = ShortenResponse(
        short_url=f"{BASE_URL}/{code}",
        original_url=str(req.url),
        code=code,
        expires_at=expires_at,
        created_at=now,
    )
    return _response(201, result.model_dump())
