import json
import logging
import os
import secrets
import string
from datetime import datetime, timedelta, timezone

import boto3

from botocore.exceptions import ClientError
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---- settings ----
TABLE_NAME = os.environ.get("TABLE_NAME", "shortify-urls")

# base62 alphabet: 0-9, a-z, A-Z  (62 characters)
ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase
CODE_LENGTH = 7
MAX_RETRIES = 5
ALLOWED_SCHEMES = ("http://", "https://")

def log_event(name, **fields):
    """Emit one JSON log line so CloudWatch can query the fields."""
    logger.info(json.dumps({"event": name, **fields}))

def _table():
    """Return the DynamoDB table object. Made at call time so tests can fake it."""
    return boto3.resource("dynamodb").Table(TABLE_NAME)


def generate_code(length=CODE_LENGTH):
    """Make a random code like 'aB3x9Qz'. Uses 'secrets' so codes aren't guessable."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def is_valid_url(url):
    """Allow only real web links. Reject anything that isn't http/https."""
    if not isinstance(url, str):
        return False
    url = url.strip()
    if not url or len(url) > 2048:
        return False
    return url.startswith(ALLOWED_SCHEMES)


def _response(status_code, body_dict):
    """Build the response shape that API Gateway expects."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body_dict),
    }


def lambda_handler(event, context):
    # 1) Read the request body and turn the JSON text into a Python dict.
    raw_body = event.get("body") or "{}"
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        return _response(400, {"error": "Body must be valid JSON."})

    # 2) Check the URL is a real web link.
    long_url = (data.get("url") or "").strip()
    if not is_valid_url(long_url):
        return _response(400, {"error": "Field 'url' must be a valid http or https link."})

    owner_id = (data.get("ownerId") or "anonymous").strip()

    # Optional expiry. If the caller sends ttlDays, the link auto-deletes after that.
    ttl_days = data.get("ttlDays")
    expires_at = None
    if ttl_days is not None:
        try:
            days = int(ttl_days)
        except (TypeError, ValueError):
            return _response(400, {"error": "ttlDays must be a whole number."})
        if days < 1 or days > 3650:
            return _response(400, {"error": "ttlDays must be between 1 and 3650."})
        expires_at = int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())

        
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = _table()

    # 3) Try to save a new item with a unique code.
    #    If the code is already taken, generate a new one and try again.
    for _ in range(MAX_RETRIES):
        code = generate_code()
        item = {
            "PK": f"SHORT#{code}",
            "SK": "META",
            "longUrl": long_url,
            "ownerId": owner_id,
            "createdAt": created_at,
            "clickCount": 0,
            "GSI1PK": f"OWNER#{owner_id}",
            "GSI1SK": created_at,
        }
        if expires_at is not None:
            item["expiresAt"] = expires_at

        try:
            table.put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
            log_event("link_created", code=code, owner=owner_id)
            response_body = {
                "shortCode": code,
                "longUrl": long_url,
                "createdAt": created_at,
            }
            if expires_at is not None:
                response_body["expiresAt"] = expires_at
            return _response(201, response_body)
        except ClientError as err:
            if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Code clash (very rare). Loop and pick a new code.
                continue
            # Any other AWS problem: stop and report.
            return _response(500, {"error": "Could not save the link."})

    # All retries used up without finding a free code (almost impossible).
    return _response(500, {"error": "Could not generate a unique code, please retry."})