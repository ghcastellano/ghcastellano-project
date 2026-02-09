"""
Rate limiting configuration for the application.

Provides centralized rate limiting that can be imported across blueprints
without circular import issues.
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# Create limiter instance - will be initialized with app later
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window"
)


def init_limiter(app):
    """Initialize the limiter with the Flask app."""
    limiter.init_app(app)


# Commonly used rate limit decorators
def login_limit():
    """Rate limit for login attempts: 5 per minute per IP."""
    return limiter.limit("5 per minute", error_message="Muitas tentativas de login. Aguarde um minuto.")


def upload_limit():
    """Rate limit for file uploads: 10 per minute per IP."""
    return limiter.limit("10 per minute", error_message="Limite de uploads excedido. Aguarde um minuto.")


def api_limit():
    """Rate limit for general API calls: 30 per minute per IP."""
    return limiter.limit("30 per minute", error_message="Limite de requisições excedido.")
