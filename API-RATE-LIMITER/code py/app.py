"""
elliotoxin | 2026
Flask API Server with Advanced Rate Limiting
Demonstrates rate limiting in a real-world API context
"""

from flask import Flask, request, jsonify, g
from functools import wraps
from datetime import datetime, timedelta
import logging
from typing import Optional, Callable
import json

from rate_limiter import (
    RateLimitConfig, RateLimitAlgorithm,
    RateLimiterFactory
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False


class RateLimitMiddleware:
    """Middleware for applying rate limits to Flask routes"""
    
    def __init__(self, app: Flask):
        self.app = app
        self.limiters = {}
        self.app.before_request(self._before_request)
        self.app.after_request(self._after_request)
    
    def _before_request(self):
        """Execute before each request"""
        g.rate_limit_info = None
    
    def _after_request(self, response):
        """Add rate limit headers to response"""
        if hasattr(g, 'rate_limit_info') and g.rate_limit_info:
            response.headers['X-RateLimit-Limit'] = str(g.rate_limit_info.requests_in_window)
            response.headers['X-RateLimit-Remaining'] = str(g.rate_limit_info.remaining)
            response.headers['X-RateLimit-Reset'] = str(g.rate_limit_info.reset_time)
            
            if g.rate_limit_info.retry_after:
                response.headers['Retry-After'] = str(g.rate_limit_info.retry_after)
        
        return response
    
    def limit(
        self,
        max_requests: int,
        time_window: int,
        algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET,
        key_func: Optional[Callable] = None,
        storage: str = 'memory'
    ):
        """Decorator for rate limiting endpoints"""
        
        def decorator(func: Callable) -> Callable:
            # Create limiter if not exists
            limiter_key = f"{func.__name__}_{max_requests}_{time_window}_{algorithm.value}"
            
            if limiter_key not in self.limiters:
                config = RateLimitConfig(
                    max_requests=max_requests,
                    time_window=time_window,
                    algorithm=algorithm,
                    distributed=(storage == 'redis')
                )
                self.limiters[limiter_key] = RateLimiterFactory.create(config)
            
            limiter = self.limiters[limiter_key]
            
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get client identifier
                if key_func:
                    client_id = key_func()
                else:
                    client_id = self._get_default_client_id()
                
                # Check rate limit
                response = limiter.is_allowed(client_id)
                g.rate_limit_info = response
                
                if not response.allowed:
                    logger.warning(
                        f"Rate limit exceeded for client {client_id}: "
                        f"{response.requests_in_window}/{max_requests} requests"
                    )
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'message': f'Maximum {max_requests} requests per {time_window}s allowed',
                        'retry_after': response.retry_after,
                        'reset_at': datetime.fromtimestamp(response.reset_time).isoformat()
                    }), 429
                
                return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def _get_default_client_id(self) -> str:
        """Get default client identifier from request"""
        # Try to use API key first
        api_key = request.headers.get('X-API-Key')
        if api_key:
            return api_key
        
        # Fall back to IP address
        return request.remote_addr or 'unknown'


# Initialize middleware
rate_limiter = RateLimitMiddleware(app)


# Example: Custom key function for per-user rate limiting
def get_user_id():
    """Extract user ID from request"""
    api_key = request.headers.get('X-API-Key')
    if api_key:
        return api_key
    return request.remote_addr


# Routes with different rate limits

@app.route('/api/public', methods=['GET'])
@rate_limiter.limit(
    max_requests=100,
    time_window=60,
    algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
    key_func=get_user_id
)
def public_endpoint():
    """Public endpoint with generous rate limit"""
    return jsonify({
        'message': 'Public endpoint',
        'timestamp': datetime.utcnow().isoformat(),
        'data': {'value': 42}
    }), 200


@app.route('/api/search', methods=['GET'])
@rate_limiter.limit(
    max_requests=30,
    time_window=60,
    algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
    key_func=get_user_id
)
def search_endpoint():
    """Search endpoint with medium rate limit"""
    query = request.args.get('q', 'default')
    return jsonify({
        'query': query,
        'results': ['result1', 'result2', 'result3'],
        'count': 3
    }), 200


@app.route('/api/premium', methods=['GET'])
@rate_limiter.limit(
    max_requests=1000,
    time_window=3600,
    algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
    key_func=get_user_id
)
def premium_endpoint():
    """Premium endpoint with high rate limit"""
    return jsonify({
        'message': 'Premium content',
        'tier': 'premium',
        'data': list(range(100))
    }), 200


@app.route('/api/write', methods=['POST'])
@rate_limiter.limit(
    max_requests=10,
    time_window=60,
    algorithm=RateLimitAlgorithm.FIXED_WINDOW,
    key_func=get_user_id
)
def write_endpoint():
    """Write endpoint with strict rate limit"""
    data = request.get_json()
    return jsonify({
        'message': 'Data received',
        'received': data,
        'id': 12345
    }), 201


@app.route('/api/status', methods=['GET'])
def status_endpoint():
    """Get rate limit status"""
    client_id = get_user_id()
    
    status_info = {}
    for limiter_key, limiter in rate_limiter.limiters.items():
        try:
            status = limiter.get_status(client_id)
            status_info[limiter_key] = status
        except Exception as e:
            status_info[limiter_key] = {'error': str(e)}
    
    return jsonify({
        'client_id': client_id,
        'timestamp': datetime.utcnow().isoformat(),
        'limiters': status_info
    }), 200


@app.route('/api/reset', methods=['POST'])
def reset_endpoint():
    """Reset rate limit for client (admin only)"""
    # In production, implement proper authentication
    api_key = request.headers.get('X-Admin-Key')
    if api_key != 'admin-secret-key':
        return jsonify({'error': 'Unauthorized'}), 403
    
    client_id = request.args.get('client_id')
    if not client_id:
        return jsonify({'error': 'Missing client_id parameter'}), 400
    
    for limiter in rate_limiter.limiters.values():
        limiter.reset(client_id)
    
    logger.info(f"Rate limit reset requested for client: {client_id}")
    return jsonify({
        'message': f'Rate limit reset for client: {client_id}',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/api/health', methods=['GET'])
def health_endpoint():
    """Health check endpoint (no rate limit)"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': '1.0.0'
    }), 200


# Error handlers

@app.errorhandler(400)
def bad_request(error):
    """Handle bad request"""
    return jsonify({
        'error': 'Bad Request',
        'message': str(error),
        'timestamp': datetime.utcnow().isoformat()
    }), 400


@app.errorhandler(404)
def not_found(error):
    """Handle not found"""
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found',
        'timestamp': datetime.utcnow().isoformat()
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server error"""
    logger.error(f"Internal error: {error}")
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred',
        'timestamp': datetime.utcnow().isoformat()
    }), 500


if __name__ == '__main__':
    logger.info("Starting API server with rate limiting...")
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
