"""
Integration tests configuration.

Integration tests require PostgreSQL because they use features like JSONB.
These tests are automatically skipped when DATABASE_URL is SQLite.
"""

import os
import pytest


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when using SQLite."""
    db_url = os.environ.get('DATABASE_URL', '')

    if db_url.startswith('sqlite'):
        skip_marker = pytest.mark.skip(
            reason="Integration tests require PostgreSQL (SQLite doesn't support JSONB)"
        )
        for item in items:
            # Skip all tests in the integration folder when using SQLite
            if 'integration' in str(item.fspath):
                item.add_marker(skip_marker)
