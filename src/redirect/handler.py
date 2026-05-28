import json
from datetime import datetime, timezone

from .shared.config import URLS_TABLE
from .shared.db import get_table
from .shared.errors import CodeNotFoundError


def _response(status: int, body: dict | None = None, location: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if location:
        headers["Location"] = location
    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body or {}),
    }


def handler(event: dict, context) -> dict:
    """
    GET /{code}
    Redirects to original URL (301) and writes a click event to DynamoDB.
    The click event is then processed asynchronously by the analytics Lambda
    via DynamoDB Streams — no synchronous coupling between redirect and analytics.
    """
    code = (event.get("pathParameters") or {}).get("code")
    if not code:
        return _response(400, {"error": "Missing short code"})

    # 1. Fetch URL record
    table = get_table(URLS_TABLE)
    result = table.get_item(Key={"code": code})
    item = result.get("Item")

    if not item:
        return _response(404, {"error": CodeNotFoundError.message})

    # 2. Check expiry in application layer too (belt-and-suspenders over TTL)
    expires_at = datetime.fromisoformat(item["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        return _response(404, {"error": "Short URL has expired"})

    # 3. Write click event — async via DynamoDB Streams, not blocking the redirect.
    # We increment a counter on the item itself; Streams picks up the change
    # and the analytics Lambda processes it separately.
    table.update_item(
        Key={"code": code},
        UpdateExpression="ADD clicks :one",
        ExpressionAttributeValues={":one": 1},
    )

    # 4. 301 redirect
    # Using 301 (permanent) for caching benefits; use 302 if you need accurate analytics
    # on every hit (browsers cache 301 and skip future requests to the short URL).
    return _response(301, location=item["original_url"])
