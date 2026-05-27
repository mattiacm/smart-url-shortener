import boto3
from src.shared.config import DYNAMODB_ENDPOINT

# boto3 client is created once at module load — reused across warm Lambda invocations.
# This is the standard pattern for reducing cold-start overhead on stateless functions.
_kwargs = {}
if DYNAMODB_ENDPOINT:
    # local DynamoDB (docker-compose) — overrides endpoint only in dev
    _kwargs["endpoint_url"] = DYNAMODB_ENDPOINT

dynamodb = boto3.resource("dynamodb", region_name="eu-south-1", **_kwargs)


def get_table(name: str):
    return dynamodb.Table(name)
