# Getting Started - Quick Reference

## ⚡ 5-Minute Quick Start

### Step 1: Setup (1 min)
```bash
python -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate
pip install flask redis
```

### Step 2: Run Tests (1 min)
```bash
python test_rate_limiter.py
```

### Step 3: View Examples (2 min)
```bash
python examples.py
```

### Step 4: Start Server (1 min)
```bash
python app.py
# Server on http://localhost:5000
```

---

## 🚀 First API Call

### Terminal 1: Start Server
```bash
python app.py
```

### Terminal 2: Make Requests
```bash
# Request 1 (allowed)
curl -i http://localhost:5000/api/public

# Check remaining
curl -H "X-API-Key: user1" http://localhost:5000/api/status

# Make many requests (until rate limited)
for i in {1..150}; do curl http://localhost:5000/api/public; done
```

---

## 📚 File Guide

| File | Purpose | Read Time |
|------|---------|-----------|
| **README.md** | Overview & features | 10 min |
| **QUICK_START.md** | This file | 2 min |
| **examples.py** | 10 working examples | Run it |
| **test_rate_limiter.py** | Complete tests | Browse |
| **API_DOCS.md** | Endpoint details | 15 min |
| **ARCHITECTURE.md** | Deep dive | 20 min |
| **INSTALL.md** | Setup guide | 10 min |

---

## 🎯 Choose Your Path

### Path A: Just Want to Use It
1. Read: README.md (15 min)
2. Run: examples.py (5 min)
3. Copy code: Use app.py as template
4. Done! ✓

### Path B: Want to Understand It
1. Run: examples.py (5 min)
2. Read: ARCHITECTURE.md (20 min)
3. Browse: rate_limiter.py (15 min)
4. Review: test_rate_limiter.py (10 min)
5. Understand! ✓

### Path C: Want to Extend It
1. Understand Path B first
2. Read: "Extending the Project" in README.md
3. Copy: TokenBucketLimiter as template
4. Implement: Your custom algorithm
5. Test: Write unit tests
6. Extend! ✓

---

## 💻 Common Tasks

### Task 1: Use in Your Flask App
```python
from rate_limiter import RateLimitConfig, RateLimitAlgorithm
from app import rate_limiter

@app.route('/api/myendpoint')
@rate_limiter.limit(
    max_requests=100,
    time_window=60,
    algorithm=RateLimitAlgorithm.TOKEN_BUCKET
)
def my_endpoint():
    return {'data': 'value'}
```

### Task 2: Check Rate Limit Status
```python
limiter = RateLimiterFactory.create(config)
status = limiter.get_status('user_id')
print(f"Requests: {status['requests_in_window']}")
print(f"Max: {status['max_requests']}")
```

### Task 3: Reset Client's Limit
```python
limiter.reset('problematic_user_id')
```

### Task 4: Use with Redis
```python
config = RateLimitConfig(
    max_requests=1000,
    time_window=3600,
    distributed=True,
    redis_url="redis://localhost:6379/0"
)
limiter = RateLimiterFactory.create(config)
```

### Task 5: Implement Custom Logic
```python
def get_user_id():
    # Custom logic to extract user ID
    auth_header = request.headers.get('Authorization')
    return extract_user_from_token(auth_header)

@rate_limiter.limit(
    max_requests=100,
    time_window=60,
    key_func=get_user_id  # Use custom function
)
def protected_endpoint():
    return {'data': 'value'}
```

---

## 🔍 Understand the Algorithms (Simplified)

### Token Bucket
Think of a bucket of tokens that refills over time:
- Start with N tokens
- Each request costs 1 token
- Tokens refill at a rate (tokens/second)
- If empty: reject request
```
Bucket: [●●●●●●●●●●] 10/10 tokens
Request: [●●●●●●●●○] 9/10 tokens
After 5 sec: [●●●●●] 10/10 tokens (refilled)
```

### Sliding Window
Keep a window of request timestamps:
- Track when each request happened
- Remove old requests outside window
- If count < max: allow request
- Very accurate but uses more memory
```
Window: ←── 10 seconds ──→
Requests: [req1] [req2] [req3] [req4] [req5]
Now: 5 requests in window (out of 10 max)
```

### Leaky Bucket
Queue requests and process at fixed rate:
- Add requests to queue
- Leak/process at constant rate
- If queue full: reject
- Smooths traffic
```
Queue: [req] [req] [req] [req] [req]
Leak: ┌─────────────────────────┐
      └─────────────────────────┘ (fixed rate)
```

### Fixed Window
Simple counter in fixed time window:
- Count requests in current time window
- If count < max: allow request
- When window expires: reset counter
- Simplest, fastest
```
Window 1    Window 2    Window 3
[5 reqs]    [3 reqs]    [7 reqs]
Reset!      Reset!      Reset!
```

---

## ❓ FAQ

**Q: Which algorithm should I use?**  
A: Start with Token Bucket. It's the best default.

**Q: How do I handle rate-limited clients?**  
A: Return HTTP 429 with Retry-After header (done automatically).

**Q: Will it work across multiple instances?**  
A: Yes, use Redis-based distributed limiter.

**Q: How much memory will it use?**  
A: ~60-200MB for 1 million clients (depends on algorithm).

**Q: Can I customize the rate limit keys?**  
A: Yes, use `key_func` parameter in decorator.

**Q: How do I test rate limiting?**  
A: Run `test_rate_limiter.py` or check examples.py.

**Q: What if Redis goes down?**  
A: Implement fallback to in-memory or allow all requests.

**Q: Can I have different limits per user tier?**  
A: Yes, create multiple limiters with different configs.

---

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Port 5000 in use | Kill process: `lsof -ti:5000 \| xargs kill -9` |
| ModuleNotFoundError | Install deps: `pip install flask redis` |
| Redis connection failed | Start Redis: `redis-server` |
| Rate limits not working | Restart server: Ctrl+C then `python app.py` |
| Tests failing | Check Python version: `python --version` (need 3.8+) |

---

## 📞 Need Help?

1. **Installation issues?** → Read INSTALL.md
2. **How to use?** → Run examples.py
3. **API endpoints?** → Check API_DOCS.md
4. **How it works?** → Read ARCHITECTURE.md
5. **Test examples?** → Review test_rate_limiter.py

---

## ✅ Next Steps

- [ ] Run `python test_rate_limiter.py`
- [ ] Run `python examples.py`
- [ ] Start `python app.py`
- [ ] Test with curl
- [ ] Read README.md
- [ ] Customize for your needs
- [ ] Deploy!

---

## 🎓 Learning Path

**Beginner (30 min total)**
1. Read README.md (15 min)
2. Run examples.py (5 min)
3. Try API calls with curl (10 min)

**Intermediate (1 hour total)**
1. Complete Beginner path
2. Read API_DOCS.md (15 min)
3. Review examples.py code (10 min)
4. Modify examples.py (10 min)

**Advanced (2 hours total)**
1. Complete Intermediate path
2. Read ARCHITECTURE.md (30 min)
3. Study rate_limiter.py (30 min)
4. Review test_rate_limiter.py (10 min)
5. Implement custom algorithm (10 min)

---

## 🚀 Deploy in Production

### Option 1: Docker (5 min)
```bash
docker-compose up -d
```

### Option 2: Traditional (10 min)
```bash
pip install gunicorn
gunicorn -w 4 app:app
```

### Option 3: Cloud (varies)
- Heroku: `git push heroku main`
- AWS: Create EC2 instance + RDS Redis
- Google Cloud: Deploy to Cloud Run
- Azure: App Service + Azure Cache

---

**Ready to get started? Run: `python examples.py`**

For detailed help, see the appropriate .md file above.

---


