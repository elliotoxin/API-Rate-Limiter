# API Documentation

## Rate Limiter API Endpoints

### Health Check

**Endpoint:** `GET /api/health`

Check if API is running.

**Response (200):**
```json
{
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:45.123456",
    "version": "1.0.0"
}
```

---

### Public Endpoint

**Endpoint:** `GET /api/public`

Public endpoint with generous rate limit (100 req/min).

**Headers:**
- `X-API-Key` (optional): API key for identification

**Response (200):**
```json
{
    "message": "Public endpoint",
    "timestamp": "2024-01-15T10:30:45.123456",
    "data": {
        "value": 42
    }
}
```

**Rate Limit Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1705319445
```

**Response (429 - Rate Limited):**
```json
{
    "error": "Rate limit exceeded",
    "message": "Maximum 100 requests per 60s allowed",
    "retry_after": 30,
    "reset_at": "2024-01-15T10:31:45.123456"
}
```

---

### Search Endpoint

**Endpoint:** `GET /api/search`

Search endpoint with sliding window rate limit (30 req/min).

**Parameters:**
- `q` (string, required): Search query

**Example:**
```
GET /api/search?q=python
```

**Response (200):**
```json
{
    "query": "python",
    "results": [
        "result1",
        "result2",
        "result3"
    ],
    "count": 3
}
```

---

### Premium Endpoint

**Endpoint:** `GET /api/premium`

Premium endpoint with high rate limit (1000 req/hour).

**Headers:**
- `X-API-Key` (required): Valid premium API key

**Response (200):**
```json
{
    "message": "Premium content",
    "tier": "premium",
    "data": [0, 1, 2, ..., 99]
}
```

---

### Write Endpoint

**Endpoint:** `POST /api/write`

Write/Create endpoint with strict rate limit (10 req/min).

**Headers:**
- `Content-Type: application/json`
- `X-API-Key` (optional): API key

**Request Body:**
```json
{
    "name": "John Doe",
    "email": "john@example.com",
    "message": "Hello World"
}
```

**Response (201 - Created):**
```json
{
    "message": "Data received",
    "received": {
        "name": "John Doe",
        "email": "john@example.com",
        "message": "Hello World"
    },
    "id": 12345
}
```

---

### Rate Limit Status

**Endpoint:** `GET /api/status`

Get current rate limit status for your client.

**Headers:**
- `X-API-Key` (optional): API key

**Response (200):**
```json
{
    "client_id": "api_key_123",
    "timestamp": "2024-01-15T10:30:45.123456",
    "limiters": {
        "public_endpoint_100_60_token_bucket": {
            "algorithm": "token_bucket",
            "tokens": 95.5,
            "max_tokens": 100,
            "refill_rate": 1.67
        },
        "search_endpoint_30_60_sliding_window": {
            "algorithm": "sliding_window",
            "requests_in_window": 5,
            "max_requests": 30,
            "window_size": 60
        }
    }
}
```

---

### Reset Rate Limit (Admin)

**Endpoint:** `POST /api/reset`

Reset rate limit for a specific client. **Admin only.**

**Headers:**
- `X-Admin-Key` (required): Admin secret key

**Parameters:**
- `client_id` (string, required): Client ID to reset

**Example:**
```
POST /api/reset?client_id=user_123
Header: X-Admin-Key: admin-secret-key
```

**Response (200):**
```json
{
    "message": "Rate limit reset for client: user_123",
    "timestamp": "2024-01-15T10:30:45.123456"
}
```

**Response (403 - Unauthorized):**
```json
{
    "error": "Unauthorized"
}
```

**Response (400 - Bad Request):**
```json
{
    "error": "Missing client_id parameter"
}
```

---

## Rate Limit Headers

All responses include rate limit information:

| Header | Description | Example |
|--------|-------------|---------|
| `X-RateLimit-Limit` | Max requests in current window | `100` |
| `X-RateLimit-Remaining` | Requests remaining in window | `47` |
| `X-RateLimit-Reset` | Unix timestamp when limit resets | `1705319445` |
| `Retry-After` | Seconds to wait before retry (if limited) | `30` |

---

## HTTP Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | OK | Successful request |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Missing or invalid parameters |
| 403 | Forbidden | Unauthorized (admin endpoints) |
| 404 | Not Found | Endpoint doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

---

## Client Identification

The API identifies clients in this order:

1. **API Key** - `X-API-Key` header (highest priority)
2. **IP Address** - Fallback if no API key

### Example with API Key:
```bash
curl -H "X-API-Key: user_token_123" \
     https://api.example.com/api/public
```

### Example with IP (fallback):
```bash
curl https://api.example.com/api/public
# Uses client IP address for rate limiting
```

---

## Rate Limiting Algorithms

### Endpoint: /api/public
- **Algorithm:** Token Bucket
- **Limit:** 100 requests per 60 seconds
- **Burst:** Allows burst traffic up to limit
- **Best for:** General public APIs

### Endpoint: /api/search
- **Algorithm:** Sliding Window
- **Limit:** 30 requests per 60 seconds
- **Accuracy:** Precise request counting
- **Best for:** Strict rate limiting

### Endpoint: /api/premium
- **Algorithm:** Token Bucket
- **Limit:** 1000 requests per 3600 seconds (1 hour)
- **Burst:** High burst allowance
- **Best for:** Premium/paid tier APIs

### Endpoint: /api/write
- **Algorithm:** Fixed Window
- **Limit:** 10 requests per 60 seconds
- **Hard limit:** Strict enforcement at boundaries
- **Best for:** Write/destructive operations

---

## Examples

### Example 1: Basic Request

```bash
curl -i https://api.example.com/api/public

HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 1705319445

{
    "message": "Public endpoint",
    "timestamp": "2024-01-15T10:30:45.123456",
    "data": {"value": 42}
}
```

### Example 2: Rate Limited Response

```bash
curl -i https://api.example.com/api/public

HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705319445
Retry-After: 30

{
    "error": "Rate limit exceeded",
    "message": "Maximum 100 requests per 60s allowed",
    "retry_after": 30,
    "reset_at": "2024-01-15T10:31:45.123456"
}
```

### Example 3: With API Key

```bash
curl -H "X-API-Key: premium_key_123" \
     https://api.example.com/api/premium

{
    "message": "Premium content",
    "tier": "premium",
    "data": [0, 1, 2, ..., 99]
}
```

### Example 4: POST Request

```bash
curl -X POST \
     -H "Content-Type: application/json" \
     -H "X-API-Key: user_key_456" \
     -d '{
       "name": "John Doe",
       "email": "john@example.com",
       "message": "Hello"
     }' \
     https://api.example.com/api/write

HTTP/1.1 201 Created
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1705319445

{
    "message": "Data received",
    "received": {
        "name": "John Doe",
        "email": "john@example.com",
        "message": "Hello"
    },
    "id": 12345
}
```

### Example 5: Check Rate Limit Status

```bash
curl -H "X-API-Key: user_key_123" \
     https://api.example.com/api/status

{
    "client_id": "user_key_123",
    "timestamp": "2024-01-15T10:30:45.123456",
    "limiters": {
        "public_endpoint_100_60_token_bucket": {
            "algorithm": "token_bucket",
            "tokens": 95.5,
            "max_tokens": 100,
            "refill_rate": 1.67
        },
        "search_endpoint_30_60_sliding_window": {
            "algorithm": "sliding_window",
            "requests_in_window": 5,
            "max_requests": 30,
            "window_size": 60
        }
    }
}
```

---

## Error Responses

### 400 - Bad Request

```json
{
    "error": "Bad Request",
    "message": "Invalid query parameter",
    "timestamp": "2024-01-15T10:30:45.123456"
}
```

### 404 - Not Found

```json
{
    "error": "Not Found",
    "message": "The requested resource was not found",
    "timestamp": "2024-01-15T10:30:45.123456"
}
```

### 500 - Internal Server Error

```json
{
    "error": "Internal Server Error",
    "message": "An unexpected error occurred",
    "timestamp": "2024-01-15T10:30:45.123456"
}
```

---

## Best Practices

### 1. Handle Rate Limits Gracefully

```python
import requests
import time

def call_api_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        
        return response
    
    raise Exception("Max retries exceeded")
```

### 2. Monitor Rate Limit Headers

```python
def check_rate_limit(response):
    limit = response.headers.get('X-RateLimit-Limit')
    remaining = response.headers.get('X-RateLimit-Remaining')
    reset = response.headers.get('X-RateLimit-Reset')
    
    print(f"Requests: {remaining}/{limit}")
    print(f"Resets at: {datetime.fromtimestamp(int(reset))}")
    
    if int(remaining) < 10:
        print("Warning: Low on remaining requests!")
```

### 3. Implement Backoff Strategy

```python
import random

def call_api_with_backoff(url, max_retries=5):
    for attempt in range(max_retries):
        response = requests.get(url)
        
        if response.status_code == 429:
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            print(f"Attempt {attempt + 1}: Waiting {wait_time}s...")
            time.sleep(wait_time)
            continue
        
        return response
    
    raise Exception("Max retries exceeded")
```

### 4. Use Connection Pooling

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    session = requests.Session()
    
    retry = Retry(
        total=3,
        backoff_factor=0.1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    return session
```

---

## Webhooks (Future Feature)

Rate limit exceeded events can be sent as webhooks:

```json
{
    "event": "rate_limit_exceeded",
    "client_id": "user_123",
    "endpoint": "/api/write",
    "limit": 10,
    "window": 60,
    "timestamp": "2024-01-15T10:30:45.123456"
}
```

---


