import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch
from datetime import datetime, timezone
from typing import Any


ANALYTICS_TABLE = "analytics"


@pytest.fixture
def analytics_table():
    with mock_aws():
        dynamodb: Any = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName=ANALYTICS_TABLE,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


def _make_stream_record(code: str, old_clicks: int, new_clicks: int) -> dict:
    return {
        "eventName": "MODIFY",
        "dynamodb": {
            "NewImage": {
                "code": {"S": code},
                "clicks": {"N": str(new_clicks)},
            },
            "OldImage": {
                "code": {"S": code},
                "clicks": {"N": str(old_clicks)},
            },
        },
    }


@mock_aws
class TestAnalyticsHandler:

    def _call(self, records: list, table) -> None:
        with patch("src.analytics.handler.get_table", return_value=table):
            from src.analytics.handler import handler
            handler({"Records": records}, None)

    def test_click_written_to_analytics(self, analytics_table):
        record = _make_stream_record("abc1234", old_clicks=0, new_clicks=1)
        self._call([record], analytics_table)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        item = analytics_table.get_item(
            Key={"pk": f"abc1234#{today}", "sk": "clicks"}
        ).get("Item")
        assert item is not None
        assert item["click_count"] == 1

    def test_multiple_clicks_aggregated(self, analytics_table):
        record = _make_stream_record("abc1234", old_clicks=0, new_clicks=5)
        self._call([record], analytics_table)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        item = analytics_table.get_item(
            Key={"pk": f"abc1234#{today}", "sk": "clicks"}
        ).get("Item")
        assert item["click_count"] == 5

    def test_insert_event_ignored(self, analytics_table):
        record = {
            "eventName": "INSERT",
            "dynamodb": {
                "NewImage": {"code": {"S": "abc1234"}, "clicks": {"N": "0"}},
                "OldImage": {},
            },
        }
        self._call([record], analytics_table)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        item = analytics_table.get_item(
            Key={"pk": f"abc1234#{today}", "sk": "clicks"}
        ).get("Item")
        assert item is None

    def test_no_delta_ignored(self, analytics_table):
        record = _make_stream_record("abc1234", old_clicks=3, new_clicks=3)
        self._call([record], analytics_table)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        item = analytics_table.get_item(
            Key={"pk": f"abc1234#{today}", "sk": "clicks"}
        ).get("Item")
        assert item is None