"""
Analytics Lambda — triggered by DynamoDB Streams on the urls table.
Every time a redirect increments the click counter, this Lambda receives
the stream record and writes a time-bucketed analytics entry.

This is the event-driven decoupling pattern: redirect Lambda writes data,
analytics Lambda reacts to changes — zero direct coupling between them.
"""
from datetime import datetime, timezone

try:
    from src.shared.config import ANALYTICS_TABLE
    from src.shared.db import get_table
except ImportError:
    from shared.config import ANALYTICS_TABLE
    from shared.db import get_table

def handler(event: dict, context) -> None:
    analytics = get_table(ANALYTICS_TABLE)
    now = datetime.now(timezone.utc)
    day_bucket = now.strftime("%Y-%m-%d")   # partition by day for range queries

    for record in event.get("Records", []):
        # We only care about MODIFY events where clicks changed
        if record["eventName"] != "MODIFY":
            continue

        new_image = record["dynamodb"].get("NewImage", {})
        old_image = record["dynamodb"].get("OldImage", {})

        code = new_image.get("code", {}).get("S")
        if not code:
            continue

        new_clicks = int(new_image.get("clicks", {}).get("N", 0))
        old_clicks = int(old_image.get("clicks", {}).get("N", 0))
        delta = new_clicks - old_clicks

        if delta <= 0:
            continue

        # Upsert time-bucketed analytics row: pk = code#day, increment clicks
        analytics.update_item(
            Key={
                "pk": f"{code}#{day_bucket}",
                "sk": "clicks",
            },
            UpdateExpression="ADD click_count :delta SET #code = :code, #day = :day",
            ExpressionAttributeNames={
                "#code": "code",
                "#day":  "day",
            },
            ExpressionAttributeValues={
                ":delta": delta,
                ":code":  code,
                ":day":   day_bucket,
            },
        )
