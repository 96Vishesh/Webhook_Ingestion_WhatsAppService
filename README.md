# WhatsApp Webhook Service

A production-style FastAPI service for ingesting WhatsApp-like messages with HMAC signature validation, health probes, pagination, analytics, and Prometheus metrics.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Make (optional, for convenience commands)

### Running the Service

```bash
# Set the required environment variable
export WEBHOOK_SECRET="your-secret-key"

# Start the service
make up
# Or: docker compose up -d --build

# Check logs
make logs

# Stop the service
make down
```

The API will be available at: **http://localhost:8000**

## 📚 API Endpoints

### Health Checks

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health/live` | GET | Liveness probe - always 200 if app is running |
| `/health/ready` | GET | Readiness probe - 200 if DB is ready and WEBHOOK_SECRET is set |

### Webhook

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | POST | Ingest WhatsApp-like messages |

**Headers:**
- `Content-Type: application/json`
- `X-Signature: <HMAC-SHA256 hex digest>`

**Request Body:**
```json
{
  "message_id": "m1",
  "from": "+919876543210",
  "to": "+14155550100",
  "ts": "2025-01-15T10:00:00Z",
  "text": "Hello"
}
```

**Compute Signature (Python):**
```python
import hmac
import hashlib
signature = hmac.new(
    WEBHOOK_SECRET.encode(), 
    request_body_bytes, 
    hashlib.sha256
).hexdigest()
```

### Messages

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/messages` | GET | List messages with pagination and filters |

**Query Parameters:**
- `limit` (int, 1-100, default: 50) - Number of results per page
- `offset` (int, ≥0, default: 0) - Number of results to skip
- `from` (string) - Filter by sender (exact match)
- `since` (string) - Filter by timestamp (ISO-8601 UTC, inclusive)
- `q` (string) - Text search (case-insensitive substring)

**Examples:**
```bash
# Basic listing
curl "http://localhost:8000/messages"

# Pagination
curl "http://localhost:8000/messages?limit=10&offset=20"

# Filter by sender
curl "http://localhost:8000/messages?from=%2B919876543210"

# Filter by timestamp
curl "http://localhost:8000/messages?since=2025-01-15T09:00:00Z"

# Text search
curl "http://localhost:8000/messages?q=hello"
```

### Stats

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stats` | GET | Message-level analytics |

**Response:**
```json
{
  "total_messages": 123,
  "senders_count": 10,
  "messages_per_sender": [
    { "from": "+919876543210", "count": 50 },
    { "from": "+911234567890", "count": 30 }
  ],
  "first_message_ts": "2025-01-10T09:00:00Z",
  "last_message_ts": "2025-01-15T10:00:00Z"
}
```

### Metrics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/metrics` | GET | Prometheus-style metrics |

**Metrics Exposed:**
- `http_requests_total{path, status}` - Counter for all HTTP requests
- `webhook_requests_total{result}` - Counter for webhook outcomes (created, duplicate, invalid_signature, validation_error)
- `request_latency_ms_bucket{le}` - Histogram of request latencies

## ⚙️ Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `WEBHOOK_SECRET` | **Required.** Secret for HMAC signature verification | - |
| `DATABASE_URL` | SQLite database URL | `sqlite:////data/app.db` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

## 🧪 Running Tests

```bash
# Run tests inside Docker container
make test

# Or run tests locally (requires dependencies)
pip install -r requirements.txt
pytest tests/ -v
```

## 📁 Project Structure

```
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI app, middleware, routes
│   ├── models.py         # Pydantic request/response models
│   ├── storage.py        # SQLite database operations
│   ├── logging_utils.py  # Structured JSON logging
│   ├── metrics.py        # Prometheus-style metrics
│   └── config.py         # Environment configuration
├── tests/
│   ├── conftest.py       # Test fixtures
│   ├── test_webhook.py   # Webhook endpoint tests
│   ├── test_messages.py  # Messages endpoint tests
│   └── test_stats.py     # Stats endpoint tests
├── Dockerfile            # Multi-stage Docker build
├── docker-compose.yml    # Docker Compose config
├── Makefile              # Convenience commands
├── requirements.txt      # Python dependencies
└── README.md
```

## 📝 Design Decisions

### HMAC Signature Verification
- Signature is computed as `hex(HMAC-SHA256(key=WEBHOOK_SECRET, message=raw_request_body))`
- Uses constant-time comparison (`hmac.compare_digest`) to prevent timing attacks
- Missing or invalid signature returns `401 {"detail": "invalid signature"}`
- Signature validation happens before any JSON parsing for security

### Pagination Contract
- **Default limit:** 50 (min: 1, max: 100)
- **Default offset:** 0 (min: 0)
- **Ordering:** Deterministic - `ORDER BY ts ASC, message_id ASC`
- **Filters:** AND-ed together when multiple are specified
- **Response includes:** `data`, `total` (filtered count), `limit`, `offset`

### /stats Endpoint
- `total_messages`: Count of all messages
- `senders_count`: Count of unique `from` values
- `messages_per_sender`: Top 10 senders by message count, sorted descending
- `first_message_ts` / `last_message_ts`: Earliest/latest `ts` values (null if no messages)
- All aggregations computed via SQL for performance

### /metrics Endpoint
- **Prometheus exposition format** (text/plain)
- `http_requests_total{path, status}`: Counter by endpoint and HTTP status
- `webhook_requests_total{result}`: Counter by webhook outcome
- `request_latency_ms_bucket{le}`: Histogram with buckets [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, +Inf]

### Idempotency
- `message_id` is the PRIMARY KEY in SQLite
- Duplicate inserts are caught via `IntegrityError` and return `200 {"status": "ok"}`
- No stack traces; errors handled gracefully

### Structured Logging
- JSON format, one line per request
- Keys: `ts`, `level`, `request_id`, `method`, `path`, `status`, `latency_ms`
- Webhook-specific: `message_id`, `dup`, `result`

## 🛠️ Setup Used

PyCharm + Claude AI

## Author

Vishesh Srivastava


For the LyftrAI Backend Assesment test

Completed on 28th January 2026 (10:02 am)
