# Advanced API Rate Limiter - Architecture & Design

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Requests                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
            ┌──────────────────────────────────┐
            │      Flask API Server            │
            │  (rate_limiter middleware)       │
            └──────────────┬───────────────────┘
                           │
                           ▼
            ┌──────────────────────────────────┐
            │   RateLimitMiddleware            │
            │  - Route decoration              │
            │  - Client identification         │
            │  - Response header injection     │
            └──────────────┬───────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │      RateLimiterFactory                  │
        │  (creates appropriate limiter)           │
        └──────────────┬───────────────────────────┘
                       │
        ┌──────────────┴──────────────┬──────────────┬──────────────┐
        ▼                             ▼              ▼              ▼
  ┌──────────────┐  ┌─────────────┐ ┌───────────┐ ┌─────────────┐ ┌─────────────┐
  │ Token Bucket │  │   Sliding   │ │  Leaky    │ │    Fixed    │ │ Distributed │
  │   Limiter    │  │   Window    │ │   Bucket  │ │   Window    │ │  (Redis)    │
  │              │  │   Limiter   │ │  Limiter  │ │   Limiter   │ │             │
  └──────────────┘  └─────────────┘ └───────────┘ └─────────────┘ └─────────────┘
        │                  │              │             │               │
        └──────────────────┴──────────────┴─────────────┴───────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │         Storage Backend                  │
        │  In-Memory (dict/deque) or Redis        │
        └──────────────────────────────────────────┘
```

## Component Details

### 1. BaseRateLimiter (Abstract Base Class)

```python
class BaseRateLimiter(ABC):
    - is_allowed(client_id) → RateLimitResponse
    - reset(client_id) → None
    - get_status(client_id) → Dict
```

**Responsibilities:**
- Define interface for all rate limiters
- Enforce common behavior
- Provide logging capabilities

---

### 2. TokenBucketLimiter

**Algorithm:**
```
1. Each client has a token bucket
2. Bucket fills at constant refill_rate
3. Each request costs 1 token
4. If tokens >= 1: allow request, decrement token
5. If tokens < 1: reject request, return retry_after
```

**Data Structure:**
```python
buckets[client_id] = {
    'tokens': 95.5,              # Current tokens (float)
    'last_refill': 1234567890.5, # Last refill timestamp
    'burst_size': 100            # Max tokens allowed
}
```

**Time Complexity:**
- Check: O(1)
- Refill: O(1)
- Memory: O(n) where n = unique clients

**Advantages:**
- Handles bursts naturally
- Efficient memory usage
- Smooth traffic shaping

**Disadvantages:**
- Doesn't strictly enforce window boundaries
- Can allow bursts beyond intended rate

---

### 3. SlidingWindowLimiter

**Algorithm:**
```
1. Maintain ordered list of request timestamps
2. For new request, remove timestamps older than window
3. If count < max_requests: allow, add timestamp
4. Otherwise: reject, return retry_after
```

**Data Structure:**
```python
windows[client_id] = deque([
    1234567890.1,  # Timestamp of request 1
    1234567890.2,  # Timestamp of request 2
    1234567890.3,  # Timestamp of request 3
    ...
])
```

**Time Complexity:**
- Check: O(m) where m = requests in window (worst case)
- Add: O(1)
- Memory: O(n × m) - high for many requests

**Advantages:**
- Accurate request counting
- No edge case issues
- Precise enforcement

**Disadvantages:**
- Higher memory usage
- O(m) complexity for cleanup
- Not scalable for high request volumes

---

### 4. LeakyBucketLimiter

**Algorithm:**
```
1. Requests are queued in a bucket
2. Queue has max capacity
3. Requests "leak" (are processed) at fixed rate
4. If queue is full: reject request
5. Otherwise: queue request, allow
```

**Data Structure:**
```python
buckets[client_id] = {
    'queue': deque([...]),    # Queued requests
    'last_leak_time': 1234567890.5,
    'total_leaked': 42
}
```

**Time Complexity:**
- Check: O(1)
- Leak: O(k) where k = leaked requests
- Memory: O(n × capacity)

**Advantages:**
- Smooth, predictable traffic
- Prevents sudden spikes
- Fair resource distribution

**Disadvantages:**
- Rejects bursts (no burst handling)
- Requires regular leak operations
- Can drop legitimate bursty requests

---

### 5. FixedWindowLimiter

**Algorithm:**
```
1. Divide time into fixed windows
2. Count requests in current window
3. If count < max_requests: allow, increment
4. When window expires: reset counter
```

**Data Structure:**
```python
windows[client_id] = {
    'count': 45,           # Requests in current window
    'window_start': 1234567890.0
}
```

**Time Complexity:**
- Check: O(1)
- Memory: O(n) - minimal

**Advantages:**
- Simplest implementation
- Lowest memory usage
- Fastest execution

**Disadvantages:**
- Edge case at boundaries (burst at boundary)
- Not precise enforcement
- Can allow 2× rate temporarily

---

### 6. DistributedRateLimiter

Uses Redis with Lua scripts for atomic operations.

**Lua Script Logic:**
```lua
1. Get current key from Redis (sorted set)
2. Remove entries older than window
3. Count remaining entries
4. If count < max: add new entry
5. Return: (allowed, remaining, total)
```

**Data Structure (Redis):**
```
key: "rate_limit:client_id"
type: sorted set (zset)
members: timestamps of requests
scores: timestamps for range queries
```

**Time Complexity:**
- Check: O(1) network call + O(log n) Redis internal
- Memory: Distributed across Redis cluster

**Advantages:**
- Works across multiple instances
- Atomic operations
- Scalable to many servers
- Persistent across restarts

**Disadvantages:**
- Network latency
- Redis dependency
- Higher resource usage

---

## Data Flow

### Request Flow

```
1. HTTP Request arrives
   ↓
2. Flask routes to endpoint handler
   ↓
3. Middleware extracts client_id from:
   a. X-API-Key header (priority 1)
   b. X-User-ID header (priority 2)
   c. Remote IP address (fallback)
   ↓
4. RateLimiterFactory creates appropriate limiter
   (reused if already created for endpoint)
   ↓
5. limiter.is_allowed(client_id) returns RateLimitResponse
   ↓
6a. If allowed=True:
    - Add response headers with limit info
    - Call handler function
    - Return response
   ↓
6b. If allowed=False:
    - Add response headers with reset time
    - Return 429 Too Many Requests
    - Include retry_after in Retry-After header
```

### Rate Limit Check Logic

```python
# Pseudo-code
def is_allowed(client_id):
    # 1. Get current state
    state = get_state(client_id)
    
    # 2. Apply algorithm-specific logic
    updated_state = apply_algorithm(state)
    
    # 3. Check if allowed
    if updated_state.remaining >= 1:
        # 4. Update state
        save_state(client_id, updated_state)
        return RateLimitResponse(allowed=True, ...)
    else:
        return RateLimitResponse(allowed=False, ...)
```

---

## Memory Management

### In-Memory Limiters

```python
# Memory growth over time
# Token Bucket: minimal - one dict per client
# Sliding Window: high - dict + deque per client
# Leaky Bucket: medium - dict + deque per client
# Fixed Window: minimal - one dict per client

# Cleanup strategy:
# 1. Remove clients with no activity
# 2. Limit total clients stored
# 3. Use LRU cache for old clients

# Example:
from collections import OrderedDict

class LimitedDict:
    def __init__(self, max_clients=10000):
        self.data = OrderedDict()
        self.max_clients = max_clients
    
    def set(self, key, value):
        if key in self.data:
            del self.data[key]  # Move to end
        elif len(self.data) >= self.max_clients:
            self.data.popitem(last=False)  # Remove oldest
        self.data[key] = value
```

### Redis Cleanup

```python
# TTL-based cleanup
# Each key has automatic expiration
redis_client.setex(key, ttl=300, value=data)  # 5 minute TTL

# Manual cleanup
redis_client.scan_iter(match="rate_limit:*")
```

---

## Concurrency & Thread Safety

### In-Memory Limiters

**Issue:** Race conditions with concurrent requests

**Solution 1: Locks**
```python
import threading

class ThreadSafeTokenBucket:
    def __init__(self, config):
        self.limiter = TokenBucketLimiter(config)
        self.lock = threading.RLock()
    
    def is_allowed(self, client_id):
        with self.lock:
            return self.limiter.is_allowed(client_id)
```

**Solution 2: Atomic Operations**
```python
# Use compare-and-swap patterns
# Not always feasible for Python

# GIL (Global Interpreter Lock) helps:
# - Single-threaded operations are atomic
# - Complex operations need locking
```

### Redis Limiters

**Atomicity Guaranteed by:**
- Redis single-threaded execution model
- Lua script atomic execution
- Network serialization

```
Redis ensures:
1. Only one command at a time
2. Lua scripts execute atomically
3. No race conditions
```

---

## Performance Characteristics

### Throughput (requests/second)

```
Algorithm        | Throughput | Memory | Accuracy
─────────────────┼────────────┼────────┼──────────
Token Bucket     | 500,000+   | Low    | Good
Sliding Window   | 300,000    | High   | Excellent
Leaky Bucket     | 400,000    | Medium | Good
Fixed Window     | 600,000+   | Low    | Fair
Distributed      | 50,000     | N/A    | Good
```

### Memory Usage (per 1M clients)

```
Algorithm      | Memory | Notes
───────────────┼────────┼──────────────────────
Token Bucket   | ~80MB  | Dict only
Sliding Window | ~200MB | Dict + large deques
Leaky Bucket   | ~120MB | Dict + medium deques
Fixed Window   | ~60MB  | Dict only
```

### Latency

```
Algorithm        | P50    | P99    | P99.9
─────────────────┼────────┼────────┼─────────
Token Bucket     | 0.1ms  | 0.5ms  | 1ms
Sliding Window   | 0.2ms  | 1.5ms  | 5ms
Leaky Bucket     | 0.15ms | 1ms    | 2ms
Fixed Window     | 0.05ms | 0.2ms  | 0.5ms
Distributed      | 2ms    | 10ms   | 50ms
```

---

## Error Handling

### Graceful Degradation

```python
def is_allowed(self, client_id):
    try:
        # Perform rate limit check
        return self._check_rate_limit(client_id)
    except Exception as e:
        logger.error(f"Rate limiter error: {e}")
        # Fallback: Allow request
        return RateLimitResponse(allowed=True)
```

### Redis Fallback

```python
def is_allowed(self, client_id):
    try:
        return self._redis_check(client_id)
    except redis.ConnectionError:
        logger.warning("Redis unavailable, using fallback")
        # Switch to in-memory or allow all
        return self._fallback_check(client_id)
```

---

## Scalability Considerations

### Horizontal Scaling

**Problem:** Multiple instances, shared rate limits

**Solution:** Redis-based distributed limiter

```
Instance 1 ──┐
Instance 2 ──┼──→ Redis ← Shared State
Instance 3 ──┘
```

### Vertical Scaling

**Problem:** Single instance running out of memory

**Solution:** Use Redis or switch to Fixed Window algorithm

### Rate Limit Sharding

**Advanced:** Partition clients across multiple Redis instances

```python
def get_redis_client(client_id):
    # Hash-based sharding
    shard = hash(client_id) % num_shards
    return redis_connections[shard]
```

---

## Security Considerations

### 1. Client Identification

```python
# Authenticate clients properly
def get_client_id():
    # Priority 1: Authenticated user
    if auth_token := request.headers.get('Authorization'):
        return verify_token(auth_token)
    
    # Priority 2: API key
    if api_key := request.headers.get('X-API-Key'):
        return api_key
    
    # Priority 3: IP address (least secure)
    return request.remote_addr
```

### 2. Admin Endpoint Protection

```python
@app.route('/api/reset', methods=['POST'])
def reset():
    # Verify admin authentication
    admin_key = request.headers.get('X-Admin-Key')
    if not verify_admin_key(admin_key):
        return {'error': 'Unauthorized'}, 403
    
    # Reset rate limit
    ...
```

### 3. Rate Limit Bypass Prevention

```python
# Don't trust X-Forwarded-For without validation
def get_client_ip():
    # Only trust X-Forwarded-For if behind trusted proxy
    if is_behind_trusted_proxy():
        return request.headers.get('X-Forwarded-For')
    return request.remote_addr
```

---

## Testing Strategy

### Unit Tests

```python
# Test each algorithm independently
- Token Bucket: refill, burst, reset
- Sliding Window: accuracy, expiration
- Leaky Bucket: leaking, queue management
- Fixed Window: boundary conditions
```

### Integration Tests

```python
# Test Flask integration
- Middleware injection
- Header handling
- Multiple endpoints
```

### Concurrency Tests

```python
# Test thread safety
- Race conditions
- Lock contention
- Concurrent request handling
```

### Performance Tests

```python
# Benchmark each algorithm
- Throughput measurement
- Memory profiling
- Latency distribution
```

---

## Future Enhancements

### 1. Adaptive Rate Limiting

```python
# Adjust limits based on system load
def get_limit(client_id):
    if system_load > 80%:
        return config.max_requests * 0.5
    return config.max_requests
```

### 2. Distributed Rate Limits with Consensus

```python
# Using Raft or Paxos for consistency
# Ensures limits across geographically distributed servers
```

### 3. Cost-Based Rate Limiting

```python
# Different operations have different costs
cost_per_request = {
    'read': 1,
    'search': 5,
    'write': 10,
    'delete': 20
}

def is_allowed(client_id, operation):
    cost = cost_per_request[operation]
    return limiter.consume(client_id, cost)
```

### 4. Machine Learning-Based Anomaly Detection

```python
# Detect and flag suspicious patterns
- Sudden increase in requests
- Unusual access patterns
- Distributed attack patterns
```

---

## References
i take help from these!!!
- Redis Documentation: https://redis.io/docs/
- Flask Documentation: https://flask.palletsprojects.com/
- Rate Limiting Patterns: https://cloud.google.com/architecture/rate-limiting-strategies-techniques
- Token Bucket Algorithm: https://en.wikipedia.org/wiki/Token_bucket

---


