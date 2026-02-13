# Installation & Setup Guide

## System Requirements

- Python 3.8 or higher
- pip (Python package manager)
- Redis (optional, for distributed mode)
- 100MB free disk space

### Supported Operating Systems
- Linux (Ubuntu, CentOS, Debian)
- macOS
- Windows (with WSL2 recommended)

---

## Quick Start (Local Development)

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/api-rate-limiter.git
cd api-rate-limiter
```

### 2. Create Virtual Environment

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Tests

```bash
python test_rate_limiter.py
```

Expected output:
```
Ran 25 tests in 0.523s
OK
```

### 5. Run Examples

```bash
python examples.py
```

### 6. Start API Server

```bash
python app.py
```

Server will be running at `http://localhost:5000`

---

## Docker Setup (Recommended for Production)

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+

### 1. Build Docker Image

```bash
docker build -t api-rate-limiter:latest .
```

### 2. Run with Docker Compose

```bash
docker-compose up -d
```

This starts:
- Redis service on port 6379
- Flask API on port 5000

### 3. Verify Installation

```bash
curl http://localhost:5000/api/health

# Expected response:
# {"status":"healthy","timestamp":"...","version":"1.0.0"}
```

### 4. Run Tests in Docker

```bash
docker-compose --profile test up
```

### 5. Stop Services

```bash
docker-compose down
```

---

## Redis Setup (for Distributed Mode)

### Option 1: Docker (Easiest)

```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

### Option 2: Install Locally

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
```

**macOS (with Homebrew):**
```bash
brew install redis
brew services start redis
```

**Windows:**
```bash
# Download from https://github.com/microsoftarchive/redis/releases
# Or use WSL with Ubuntu instructions above
```

### Option 3: Remote Redis

Update configuration:
```python
config = RateLimitConfig(
    max_requests=1000,
    time_window=3600,
    distributed=True,
    redis_url="redis://your-redis-host:6379/0"
)
```

### Verify Redis Installation

```bash
redis-cli ping
# Expected response: PONG
```

---

## Advanced Configuration

### Environment Variables

Create `.env` file:
```bash
FLASK_ENV=development
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=5000
ADMIN_KEY=your-secret-admin-key
```

Load in application:
```python
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
ADMIN_KEY = os.getenv('ADMIN_KEY', 'default-key')
```

### Production Configuration

```python
# config.py
import os

class Config:
    """Production config"""
    DEBUG = False
    TESTING = False
    LOG_LEVEL = 'WARNING'
    REDIS_URL = os.getenv('REDIS_URL')
    WORKERS = 4

class DevelopmentConfig(Config):
    """Development config"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class TestingConfig(Config):
    """Testing config"""
    TESTING = True
    REDIS_URL = 'redis://localhost:6379/1'
```

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'flask'"

**Solution:**
```bash
pip install flask redis python-dotenv
```

### Issue: "Connection refused" (Redis)

**Solution:**
```bash
# Check if Redis is running
redis-cli ping

# Start Redis if not running
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### Issue: "Port 5000 already in use"

**Solution:**
```bash
# Kill process on port 5000
# Linux/macOS:
lsof -ti:5000 | xargs kill -9

# Windows:
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Or use different port:
python app.py --port 8000
```

### Issue: "Permission denied" on Linux

**Solution:**
```bash
# Use sudo for system commands
sudo apt-get install redis-server

# Or run with user permissions
python -m pip install --user flask redis
```

---

## Performance Tuning

### 1. Increase Worker Processes

For production, use Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Where `-w 4` is number of workers (usually CPU cores).

### 2. Redis Connection Pooling

```python
redis_client = redis.ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50
)
```

### 3. Memory Optimization

For in-memory limiters:
```python
# Prefer Token Bucket over Sliding Window
config = RateLimitConfig(
    algorithm=RateLimitAlgorithm.TOKEN_BUCKET
)

# Or use Redis for distributed mode
config = RateLimitConfig(
    distributed=True,
    redis_url="redis://..."
)
```

### 4. Logging Optimization

```python
import logging

# Production: Less verbose logging
logging.getLogger('rate_limiter').setLevel(logging.WARNING)

# Development: Debug logging
logging.getLogger('rate_limiter').setLevel(logging.DEBUG)
```

---

## Development Setup

### 1. Install Dev Dependencies

```bash
pip install -r requirements.txt
pip install pytest pytest-cov black flake8 mypy
```

### 2. Code Quality

```bash
# Format code
black *.py

# Lint code
flake8 *.py

# Type checking
mypy *.py

# Run tests with coverage
pytest test_rate_limiter.py --cov=rate_limiter
```

### 3. Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black

  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
```

---

## Deployment

### 1. Deploy to Heroku

```bash
# Create app
heroku create your-app-name

# Set environment variables
heroku config:set REDIS_URL=<redis-url>
heroku config:set FLASK_ENV=production

# Deploy
git push heroku main

# Check logs
heroku logs --tail
```

### 2. Deploy to AWS

```bash
# Create EC2 instance
# Install Python and dependencies
sudo apt-get update
sudo apt-get install python3-pip redis-server

# Clone and run
git clone <repo>
cd api-rate-limiter
pip install -r requirements.txt
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 3. Deploy with Kubernetes

Create `deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rate-limiter
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rate-limiter
  template:
    metadata:
      labels:
        app: rate-limiter
    spec:
      containers:
      - name: api
        image: api-rate-limiter:latest
        ports:
        - containerPort: 5000
        env:
        - name: REDIS_URL
          value: "redis://redis-service:6379/0"
```

Deploy:
```bash
kubectl apply -f deployment.yaml
```

---

## Monitoring

### 1. Health Check

```bash
curl http://localhost:5000/api/health
```

### 2. Rate Limit Status

```bash
curl -H "X-API-Key: your-key" http://localhost:5000/api/status
```

### 3. Prometheus Metrics (Future)

Add to `app.py`:
```python
from prometheus_client import Counter, Gauge, generate_latest

rate_limit_exceeded = Counter(
    'rate_limit_exceeded_total',
    'Total rate limit exceeded events'
)

active_limiters = Gauge(
    'active_limiters',
    'Number of active rate limiters'
)
```

---

## Cleanup

### Remove Installation

```bash
# Deactivate virtual environment
deactivate

# Remove venv
rm -rf venv

# Remove project directory
rm -rf api-rate-limiter
```

### Stop Docker Services

```bash
docker-compose down -v  # -v removes volumes
docker system prune      # Clean up unused images
```

---

## Getting Help

1. **Check Documentation:** See README.md and API_DOCS.md
2. **Run Examples:** `python examples.py`
3. **Check Tests:** Review test_rate_limiter.py for usage patterns
4. **Enable Debug:** Set `FLASK_DEBUG=1` environment variable

---

## Next Steps

After installation:

1. ✅ Run tests to verify installation
2. ✅ Explore examples.py
3. ✅ Read API_DOCS.md for endpoint documentation
4. ✅ Customize configuration for your use case
5. ✅ Deploy to your environment

---

