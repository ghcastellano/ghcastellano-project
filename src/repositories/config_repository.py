"""Repository for AppConfig entities."""
from typing import Optional, List

from src.models_db import AppConfig


class ConfigRepository:
    def __init__(self, session):
        self._session = session

    def get_value(self, key: str) -> Optional[str]:
        config = self._session.query(AppConfig).get(key)
        return config.value if config else None

    def set_value(self, key: str, value: str) -> AppConfig:
        config = self._session.query(AppConfig).get(key)
        if config:
            config.value = value
        else:
            config = AppConfig(key=key, value=value)
            self._session.add(config)
        return config

    def get_all(self) -> List[AppConfig]:
        return self._session.query(AppConfig).all()

    def delete(self, key: str) -> bool:
        config = self._session.query(AppConfig).get(key)
        if config:
            self._session.delete(config)
            return True
        return False
