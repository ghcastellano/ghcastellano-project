"""
Rate limiting configuration for the application.

Provides centralized rate limiting that can be imported across blueprints
without circular import issues.
"""

from flask import request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def _get_real_ip():
    """Get the real client IP behind Cloud Run / load balancer."""
    return (
        request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
        or request.remote_addr
        or '127.0.0.1'
    )


# Create limiter instance - will be initialized with app later
limiter = Limiter(
    key_func=_get_real_ip,
    default_limits=["500 per day", "100 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)


def init_limiter(app):
    """Initialize the limiter with the Flask app."""
    limiter.init_app(app)


# Commonly used rate limit decorators
def login_limit():
    """Rate limit for login attempts: 20 per minute per IP."""
    return limiter.limit("20 per minute", error_message="Muitas tentativas de login. Aguarde um minuto.")


def upload_limit():
    """Rate limit for file uploads: 10 per minute per IP."""
    return limiter.limit("10 per minute", error_message="Limite de uploads excedido. Aguarde um minuto.")


def api_limit():
    """Rate limit for general API calls: 30 per minute per IP."""
    return limiter.limit("30 per minute", error_message="Limite de requisições excedido.")
