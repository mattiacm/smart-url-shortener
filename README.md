# Smart URL Shortener

A production-grade serverless URL shortener built on AWS, featuring real-time click analytics via DynamoDB Streams and a fully automated CI/CD pipeline with GitHub Actions.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Data Model](#data-model)
- [Local Development](#local-development)
- [Testing](#testing)
- [Deployment](#deployment)
- [CI/CD Pipeline](#cicd-pipeline)
- [Design Decisions](#design-decisions)

---

## Overview

Smart URL Shortener exposes a REST API that accepts a long URL and returns a short code. When a user visits the short URL, the service redirects them to the original destination and asynchronously records the click for analytics — without any latency impact on the redirect itself.

**Key capabilities:**

- Shorten any valid URL with an auto-generated or custom alias
- Automatic link expiration via DynamoDB TTL (default: 30 days)
- Atomic click counting with no race conditions
- Per-day click analytics aggregated asynchronously via DynamoDB Streams
- Zero-downtime deploys via SAM + CloudFormation

---

## Architecture

```
Client
  │
  ▼
API Gateway (REST)
  ├── POST /shorten  ──────────► ShortenFunction (Lambda)
  │                                      │
  │                                      ▼
  │                               DynamoDB: urls
  │                                      │
  └── GET /{code}   ──────────► RedirectFunction (Lambda)
                                         │
                                         ├── 301 redirect to original URL
                                         │
                                         └── ADD clicks :1 (atomic)
                                                    │
                                                    ▼
                                         DynamoDB Streams
                                                    │
                                                    ▼
                                      AnalyticsFunction (Lambda)
                                                    │
                                                    ▼
                                         DynamoDB: analytics
```

### Components

| Component | Type | Purpose |
|---|---|---|
| API Gateway | REST API | Routes HTTP requests to Lambda functions |
| ShortenFunction | AWS Lambda (Python 3.12) | Validates input, generates short code, writes to DynamoDB |
| RedirectFunction | AWS Lambda (Python 3.12) | Reads original URL, increments click counter, returns 301 |
| AnalyticsFunction | AWS Lambda (Python 3.12) | Consumes DynamoDB Streams, aggregates click data by day |
| DynamoDB `urls` | NoSQL Table | Stores URL mappings with TTL and Streams enabled |
| DynamoDB `analytics` | NoSQL Table | Stores per-day click counts per short code |

---

## Project Structure

```
smart-url-shortener/
├── src/
│   ├── shorten/
│   │   ├── handler.py        # POST /shorten Lambda handler
│   │   ├── models.py         # Pydantic request/response schemas
│   │   └── requirements.txt  # Lambda-specific dependencies
│   ├── redirect/
│   │   ├── handler.py        # GET /{code} Lambda handler
│   │   └── requirements.txt
│   ├── analytics/
│   │   ├── handler.py        # DynamoDB Streams consumer
│   │   └── requirements.txt
│   └── shared/
│       ├── config.py         # Environment variable bindings
│       ├── db.py             # DynamoDB client singleton
│       └── errors.py         # Custom exceptions
├── tests/
│   └── unit/
│       ├── test_shorten.py
│       ├── test_redirect.py
│       └── test_analytics.py
├── .github/
│   └── workflows/
│       └── deploy.yml        # CI/CD pipeline
├── template.yaml             # AWS SAM infrastructure definition
├── docker-compose.yml        # DynamoDB Local for offline development
├── requirements.txt          # Production dependencies
├── requirements-dev.txt      # Development and test dependencies
└── pyproject.toml            # Pytest and Ruff configuration
```

---

## API Reference

### POST /shorten

Creates a short URL from a long URL.

**Request**

```http
POST /Prod/shorten
Content-Type: application/json

{
  "url": "https://www.example.com/very/long/path",
  "alias": "my-link",       // optional: custom short code
  "ttl_days": 30            // optional: expiration in days (default: 30)
}
```

**Response `201 Created`**

```json
{
  "short_url": "https://<api-id>.execute-api.eu-south-1.amazonaws.com/Prod/CvKdTyh",
  "original_url": "https://www.example.com/very/long/path",
  "code": "CvKdTyh",
  "expires_at": "2026-06-27T11:18:43+00:00",
  "created_at": "2026-05-28T11:18:43+00:00"
}
```

**Response `400 Bad Request`**

```json
{
  "error": "..."
}
```

Returned when the URL is invalid, the alias contains special characters, or the request body is malformed.

---

### GET /{code}

Redirects to the original URL associated with the short code.

**Request**

```http
GET /Prod/CvKdTyh
```

**Response `301 Moved Permanently`**

```
Location: https://www.example.com/very/long/path
```

A 301 (permanent) redirect is used for browser caching benefits. The click counter is incremented atomically before the redirect is issued.

**Response `404 Not Found`**

```json
{
  "error": "Short URL not found"
}
```

Returned when the code does not exist or the link has expired.

---

## Data Model

### Table: `urls`

| Attribute | Type | Description |
|---|---|---|
| `code` | String (PK) | The short code (e.g. `CvKdTyh`) |
| `original_url` | String | The full destination URL |
| `created_at` | String (ISO 8601) | Creation timestamp |
| `expires_at` | String (ISO 8601) | Expiration timestamp |
| `ttl` | Number | Unix epoch for DynamoDB native TTL |
| `clicks` | Number | Total click count (atomically incremented) |

DynamoDB Streams is enabled on this table with `NEW_AND_OLD_IMAGES` — every modification triggers the AnalyticsFunction.

### Table: `analytics`

| Attribute | Type | Description |
|---|---|---|
| `pk` | String (PK) | Composite key: `{code}#{YYYY-MM-DD}` |
| `sk` | String (SK) | Always `"clicks"` |
| `click_count` | Number | Clicks recorded on that day |
| `code` | String | The short code |
| `day` | String | The date bucket (`YYYY-MM-DD`) |

---

## Local Development

### Prerequisites

- Python 3.12+
- Docker Desktop
- AWS SAM CLI

### Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements-dev.txt

# 3. Start DynamoDB Local
docker compose up -d

# 4. Run tests
pytest tests/ -v
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `URLS_TABLE` | `urls` | DynamoDB table name for URL mappings |
| `ANALYTICS_TABLE` | `analytics` | DynamoDB table name for analytics |
| `BASE_URL` | `http://localhost:3000` | Base URL prepended to short codes |
| `CODE_LENGTH` | `7` | Length of auto-generated short codes |
| `DEFAULT_TTL_DAYS` | `30` | Default link expiration in days |
| `DYNAMODB_ENDPOINT` | *(none)* | Set to `http://localhost:8000` for local development |

---

## Testing

Tests use `pytest` with `moto` to mock AWS services in memory — no AWS account or running DynamoDB required.

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=src --cov-report=term-missing
```

### Test coverage

| Module | Coverage |
|---|---|
| `src/shorten/handler.py` | 6 tests — valid URL, custom alias, invalid URL, special chars, empty body, DynamoDB write |
| `src/redirect/handler.py` | 5 tests — 301 redirect, missing code, unknown code, expired URL, click increment |
| `src/analytics/handler.py` | 4 tests — click written, multiple clicks, INSERT ignored, zero delta ignored |

---

## Deployment

### Prerequisites

1. AWS account with permissions for Lambda, DynamoDB, API Gateway, CloudFormation, IAM, S3
2. An S3 bucket for SAM deployment artifacts
3. AWS credentials configured

### Manual deploy

```bash
# Build Lambda packages
sam build --template template.yaml --no-cached

# Deploy to AWS
sam deploy \
  --template .aws-sam/build/template.yaml \
  --stack-name smart-url-shortener \
  --capabilities CAPABILITY_IAM \
  --region eu-south-1 \
  --s3-bucket <your-deployment-bucket>
```

### Stack outputs

After a successful deploy, CloudFormation outputs:

| Output | Description |
|---|---|
| `ApiUrl` | Base URL of the API |
| `ShortenUrl` | Full endpoint for `POST /shorten` |

---

## CI/CD Pipeline

Every push to `main` triggers the GitHub Actions pipeline defined in `.github/workflows/deploy.yml`.

### Pipeline stages

```
push to main
     │
     ▼
┌─────────┐
│  Test   │  • Install dependencies
│         │  • Lint with Ruff
│         │  • Run 15 unit tests with coverage
└────┬────┘
     │ passes
     ▼
┌─────────┐
│ Deploy  │  • Install SAM CLI
│         │  • Configure AWS credentials (from GitHub Secrets)
│         │  • sam build
│         │  • sam deploy
└─────────┘
```

The deploy stage only runs on pushes to `main`, not on pull requests.

### Required GitHub Secrets

| Secret | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | IAM user access key |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key |

---

## Design Decisions

**301 vs 302 redirect**
The redirect Lambda returns `301 Moved Permanently`. This allows browsers to cache the redirect and skip future requests to the short URL, reducing latency for repeat visitors. The trade-off is that click counts may be undercounted for cached redirects. Use `302` if accurate per-visit analytics are required.

**Atomic click counting**
Click increments use DynamoDB's `ADD` operation (`UpdateExpression="ADD clicks :one"`), which is atomic at the item level. This avoids race conditions when multiple users click the same link simultaneously, without requiring transactions or locks.

**Event-driven analytics**
The redirect Lambda does not write to the analytics table directly. Instead, it increments a counter on the URL item, which triggers DynamoDB Streams. The AnalyticsFunction processes the stream asynchronously. This decouples the redirect latency from analytics processing — a slow analytics write never delays a redirect.

**DynamoDB TTL + application-layer expiry check**
Link expiration is enforced at two levels: DynamoDB's native TTL field deletes expired items automatically (eventually consistent, up to 48h delay), and the redirect handler also checks `expires_at` explicitly to catch items that have logically expired but not yet been deleted by DynamoDB.

**DynamoDB client singleton**
The DynamoDB resource is instantiated at module load time, outside the handler function. Lambda reuses the execution environment across warm invocations, so the connection is reused rather than re-established on every request — reducing cold-start overhead and connection latency.
