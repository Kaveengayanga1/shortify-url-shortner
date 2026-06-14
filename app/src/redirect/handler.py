import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

import json, logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def _log(event_name, **fields):
    logger.info(json.dumps({"event": event_name, **fields}))
    

TABLE_NAME = os.environ.get("TABLE_NAME", "shortify-urls")


def _table():
    return boto3.resource("dynamodb").Table(TABLE_NAME)


def _redirect(location):
    return {
        "statusCode": 302,
        "headers": {
            "Location": location,
            # Stop browsers caching the redirect, so every click reaches us
            # and the click count stays accurate. This is why we use 302.
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        },
        "body": "",
    }


def _not_found():
    return {
        "statusCode": 404,
        "headers": {"Content-Type": "text/plain"},
        "body": "Short link not found.",
    }


def lambda_handler(event, context):
    # The {code} from the route "GET /{code}" arrives here.
    code = (event.get("pathParameters") or {}).get("code")
    if not code:
        return _not_found()

    table = _table()
    try:
        result = table.get_item(Key={"PK": f"SHORT#{code}", "SK": "META"})
    except ClientError:
        return {"statusCode": 500,
                "headers": {"Content-Type": "text/plain"},
                "body": "Lookup failed."}

    item = result.get("Item")
    if not item:
        return _not_found()

    # TTL deletion isn't instant (can lag up to ~48h), so we check expiry too.
    expires_at = item.get("expiresAt")
    if expires_at is not None and int(expires_at) <= int(datetime.now(timezone.utc).timestamp()):
        return _not_found()

    long_url = item.get("longUrl")
    if not long_url:
        return _not_found()

    # Count the click, but never let a counting failure block the redirect.
    try:
        table.update_item(
            Key={"PK": f"SHORT#{code}", "SK": "META"},
            UpdateExpression="ADD clickCount :one",
            ExpressionAttributeValues={":one": 1},
        )
    except ClientError:
        pass

    return _redirect(long_url)