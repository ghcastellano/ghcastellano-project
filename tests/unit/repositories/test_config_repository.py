"""Tests for ConfigRepository."""
import pytest

from src.repositories.config_repository import ConfigRepository


class TestConfigRepository:

    def test_set_and_get_value(self, db_session):
        repo = ConfigRepository(db_session)

        repo.set_value('test_key', 'test_value')
        db_session.flush()

        assert repo.get_value('test_key') == 'test_value'

    def test_get_value_not_found(self, db_session):
        repo = ConfigRepository(db_session)
        assert repo.get_value('nonexistent_key') is None

    def test_set_value_updates_existing(self, db_session):
        repo = ConfigRepository(db_session)

        repo.set_value('update_key', 'original')
        db_session.flush()
        repo.set_value('update_key', 'updated')
        db_session.flush()

        assert repo.get_value('update_key') == 'updated'

    def test_get_all(self, db_session):
        repo = ConfigRepository(db_session)

        repo.set_value('key_a', 'value_a')
        repo.set_value('key_b', 'value_b')
        db_session.flush()

        results = repo.get_all()
        keys = [r.key for r in results]
        assert 'key_a' in keys
        assert 'key_b' in keys

    def test_delete(self, db_session):
        repo = ConfigRepository(db_session)

        repo.set_value('delete_me', 'temp')
        db_session.flush()

        assert repo.delete('delete_me') is True
        db_session.flush()
        assert repo.get_value('delete_me') is None

    def test_delete_nonexistent(self, db_session):
        repo = ConfigRepository(db_session)
        assert repo.delete('does_not_exist') is False
