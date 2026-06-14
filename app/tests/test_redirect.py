import boto3
from moto import mock_aws

from src.redirect import handler


def _make_table():
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


def _put(table, code, long_url, expires_at=None):
    item = {"PK": f"SHORT#{code}", "SK": "META", "longUrl": long_url, "clickCount": 0}
    if expires_at is not None:
        item["expiresAt"] = expires_at
    table.put_item(Item=item)


@mock_aws
def test_redirect_success():
    table = _make_table()
    _put(table, "abc1234", "https://example.com/target")
    res = handler.lambda_handler({"pathParameters": {"code": "abc1234"}}, None)
    assert res["statusCode"] == 302
    assert res["headers"]["Location"] == "https://example.com/target"
    item = table.get_item(Key={"PK": "SHORT#abc1234", "SK": "META"})["Item"]
    assert item["clickCount"] == 1


@mock_aws
def test_missing_code_404():
    _make_table()
    assert handler.lambda_handler({"pathParameters": {}}, None)["statusCode"] == 404


@mock_aws
def test_unknown_code_404():
    _make_table()
    assert handler.lambda_handler({"pathParameters": {"code": "nope999"}}, None)["statusCode"] == 404


@mock_aws
def test_expired_link_404():
    table = _make_table()
    _put(table, "old1234", "https://example.com/old", expires_at=1)  # 1970, long expired
    assert handler.lambda_handler({"pathParameters": {"code": "old1234"}}, None)["statusCode"] == 404