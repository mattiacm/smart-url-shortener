import os

# DynamoDB
URLS_TABLE        = os.environ.get("URLS_TABLE", "urls")
ANALYTICS_TABLE   = os.environ.get("ANALYTICS_TABLE", "analytics")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")   # set only for local dev

# URL settings
BASE_URL          = os.environ.get("BASE_URL", "http://localhost:3000")
CODE_LENGTH       = int(os.environ.get("CODE_LENGTH", "7"))
DEFAULT_TTL_DAYS  = int(os.environ.get("DEFAULT_TTL_DAYS", "30"))

# Rate limiting
RATE_LIMIT_RPM    = int(os.environ.get("RATE_LIMIT_RPM", "60"))  # requests per minute per IP
