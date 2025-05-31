import os

# DynamoDB configuration
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT", "http://localhost:8000")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "dummy")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "dummy")
