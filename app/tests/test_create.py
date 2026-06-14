import json
import time

import boto3
from moto import mock_aws

from src.create import handler


def _make_table():
    """Create a fake table in moto that matches our real one's keys."""
    db = boto3.resource("dynamodb", region_name="ap-south-1")
    db.create_table(
        TableName="shortify-urls-test",
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
    )
    return db.Table("shortify-urls-test")


@mock_aws
def test_create_success():
    table = _make_table()
    event = {"body": json.dumps({"url": "https://example.com/page", "ownerId": "user1"})}

    result = handler.lambda_handler(event, None)

    assert result["statusCode"] == 201
    body = json.loads(result["body"])
    assert len(body["shortCode"]) == 7
    assert body["longUrl"] == "https://example.com/page"

    # Confirm the item really landed in the table.
    item = table.get_item(Key={"PK": f"SHORT#{body['shortCode']}", "SK": "META"})["Item"]
    assert item["longUrl"] == "https://example.com/page"
    assert item["ownerId"] == "user1"
    assert item["clickCount"] == 0


@mock_aws
def test_missing_url_returns_400():
    _make_table()
    event = {"body": json.dumps({"ownerId": "user1"})}
    result = handler.lambda_handler(event, None)
    assert result["statusCode"] == 400


@mock_aws
def test_non_http_scheme_rejected():
    _make_table()
    event = {"body": json.dumps({"url": "javascript:alert(1)"})}
    result = handler.lambda_handler(event, None)
    assert result["statusCode"] == 400


@mock_aws
def test_bad_json_returns_400():
    _make_table()
    event = {"body": "{not valid json"}
    result = handler.lambda_handler(event, None)
    assert result["statusCode"] == 400


@mock_aws
def test_missing_owner_defaults_to_anonymous():
    table = _make_table()
    event = {"body": json.dumps({"url": "https://example.com"})}
    result = handler.lambda_handler(event, None)

    assert result["statusCode"] == 201
    body = json.loads(result["body"])
    item = table.get_item(Key={"PK": f"SHORT#{body['shortCode']}", "SK": "META"})["Item"]
    assert item["ownerId"] == "anonymous"
    assert item["GSI1PK"] == "OWNER#anonymous"

@mock_aws
def test_ttl_days_sets_expiry():
    table = _make_table()
    event = {"body": json.dumps({"url": "https://example.com", "ttlDays": 7})}
    result = handler.lambda_handler(event, None)
    assert result["statusCode"] == 201
    body = json.loads(result["body"])
    assert "expiresAt" in body
    # ~7 days from now, allow a little slack
    expected = int(time.time()) + 7 * 86400
    assert abs(body["expiresAt"] - expected) < 120


@mock_aws
def test_bad_ttl_rejected():
    _make_table()
    event = {"body": json.dumps({"url": "https://example.com", "ttlDays": "lots"})}
    assert handler.lambda_handler(event, None)["statusCode"] == 400