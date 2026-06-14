import os
import sys

# Add the app/ folder to the import path so tests can do "from src.create import handler".
sys.path.insert(0, os.path.dirname(__file__))

# Fake AWS settings so boto3 and moto don't ask for real credentials during tests.
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("TABLE_NAME", "shortify-urls-test")