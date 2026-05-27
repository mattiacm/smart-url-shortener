import json
import os
import pytest
import boto3
from moto import mock_aws

# Point to fake DynamoDB before any app import
os.environ.setdefault("URLS_TABLE", "urls-test")
os.environ.setdefault("BASE_URL", "https://short.test")
os.environ.setdefault("AWS_DEFAULT_REGION", "eu-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")


@pytest.fixture
def ddb_table():
    """Spin up a moto-mocked DynamoDB table for each test."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name="eu-south-1")
        table = ddb.create_table(
            TableName="urls-test",
            KeySchema=[{"AttributeName": "code", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "code", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="urls-test")
        yield table


def _shorten_event(url: str, alias: str = None, ttl_days: int = None) -> dict:
    body = {"url": url}
    if alias:
        body["alias"] = alias
    if ttl_days:
        body["ttl_days"] = ttl_days
    return {"body": json.dumps(body)}


class TestShortenHandler:
    def test_valid_url_returns_201(self, ddb_table):
        from src.shorten.handler import handler
        resp = handler(_shorten_event("https://example.com/very/long/path"), None)
        assert resp["statusCode"] == 201
        body = json.loads(resp["body"])
        assert body["short_url"].startswith("https://short.test/")
        assert len(body["code"]) == 7

    def test_custom_alias_is_used(self, ddb_table):
        from src.shorten.handler import handler
        resp = handler(_shorten_event("https://example.com", alias="myalias"), None)
        body = json.loads(resp["body"])
        assert body["code"] == "myalias"
        assert body["short_url"] == "https://short.test/myalias"

    def test_invalid_url_returns_400(self, ddb_table):
        from src.shorten.handler import handler
        resp = handler(_shorten_event("not-a-url"), None)
        assert resp["statusCode"] == 400

    def test_alias_with_special_chars_returns_400(self, ddb_table):
        from src.shorten.handler import handler
        resp = handler(_shorten_event("https://example.com", alias="bad alias!"), None)
        assert resp["statusCode"] == 400

    def test_empty_body_returns_400(self, ddb_table):
        from src.shorten.handler import handler
        resp = handler({"body": "{}"}, None)
        assert resp["statusCode"] == 400

    def test_item_written_to_dynamo(self, ddb_table):
        from src.shorten.handler import handler
        handler(_shorten_event("https://example.com", alias="testcode"), None)
        item = ddb_table.get_item(Key={"code": "testcode"})["Item"]
        assert item["original_url"] == "https://example.com/"
        assert item["clicks"] == 0
        assert "ttl" in item
