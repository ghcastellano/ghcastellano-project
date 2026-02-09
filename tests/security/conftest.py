"""
Security tests configuration.

Tests that require database fixtures (auth_client, manager_client, admin_client)
are skipped when using SQLite because the models use PostgreSQL-specific types.
"""

import os
import pytest


# List of fixtures that require PostgreSQL
POSTGRES_FIXTURES = {'auth_client', 'manager_client', 'admin_client', 'db_session', 'session'}


def pytest_collection_modifyitems(config, items):
    """Skip tests using database fixtures when using SQLite."""
    db_url = os.environ.get('DATABASE_URL', '')

    if db_url.startswith('sqlite'):
        skip_marker = pytest.mark.skip(
            reason="Test requires PostgreSQL (fixtures use JSONB columns)"
        )
        for item in items:
            # Check if test uses any of the postgres-requiring fixtures
            if 'security' in str(item.fspath):
                # Get fixture names used by this test
                fixture_names = set(getattr(item, 'fixturenames', []))
                if fixture_names & POSTGRES_FIXTURES:
                    item.add_marker(skip_marker)
