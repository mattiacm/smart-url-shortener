import json
import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import patch


TABLE_NAME = "urls"


@pytest.fixture
def dynamodb_table():
    with mock_aws():
        dynamodb: Any = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "code", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "code", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield table


@pytest.fixture
def valid_item():
    return {
        "code": "abc1234",
        "original_url": "https://example.com",
        "clicks": 0,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }


@mock_aws
class TestRedirectHandler:

    def _call(self, code: str) -> dict:
        from src.redirect.handler import handler
        event = {"pathParameters": {"code": code}}
        return handler(event, None)

    def test_valid_code_returns_301(self, dynamodb_table, valid_item):
        dynamodb_table.put_item(Item=valid_item)
        with patch("src.redirect.handler.get_table", return_value=dynamodb_table):
            response = self._call("abc1234")
        assert response["statusCode"] == 301
        assert response["headers"]["Location"] == "https://example.com"

    def test_missing_code_returns_400(self, dynamodb_table):
        with patch("src.redirect.handler.get_table", return_value=dynamodb_table):
            from src.redirect.handler import handler
            response = handler({"pathParameters": {}}, None)
        assert response["statusCode"] == 400

    def test_unknown_code_returns_404(self, dynamodb_table):
        with patch("src.redirect.handler.get_table", return_value=dynamodb_table):
            response = self._call("notexist")
        assert response["statusCode"] == 404

    def test_expired_url_returns_404(self, dynamodb_table):
        expired_item = {
            "code": "expired1",
            "original_url": "https://example.com",
            "clicks": 0,
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        }
        dynamodb_table.put_item(Item=expired_item)
        with patch("src.redirect.handler.get_table", return_value=dynamodb_table):
            response = self._call("expired1")
        assert response["statusCode"] == 404

    def test_click_counter_incremented(self, dynamodb_table, valid_item):
        dynamodb_table.put_item(Item=valid_item)
        with patch("src.redirect.handler.get_table", return_value=dynamodb_table):
            self._call("abc1234")
        item = dynamodb_table.get_item(Key={"code": "abc1234"})["Item"]
        assert item["clicks"] == 1