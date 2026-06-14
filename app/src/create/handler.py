import json
import os
import secrets
import string
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

import json, logging
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
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = _table()

    # 3) Try to save a new item with a unique code.
    #    If the code is already taken, generate a new one and try again.
    for _ in range(MAX_RETRIES):
        code = generate_code()
        try:
            table.put_item(
                Item={
                    "PK": f"SHORT#{code}",
                    "SK": "META",
                    "longUrl": long_url,
                    "ownerId": owner_id,
                    "createdAt": created_at,
                    "clickCount": 0,
                    "GSI1PK": f"OWNER#{owner_id}",
                    "GSI1SK": created_at,
                },
                # Only write if no item with this PK exists yet.
                ConditionExpression="attribute_not_exists(PK)",
            )
            log_event("link_created", code=code, owner=owner_id)
            return _response(201, {
                "shortCode": code,
                "longUrl": long_url,
                "createdAt": created_at,
            })
        except ClientError as err:
            if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Code clash (very rare). Loop and pick a new code.
                continue
            # Any other AWS problem: stop and report.
            return _response(500, {"error": "Could not save the link."})

    # All retries used up without finding a free code (almost impossible).
    return _response(500, {"error": "Could not generate a unique code, please retry."})