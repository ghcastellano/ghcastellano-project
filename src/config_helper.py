import os
import logging

logger = logging.getLogger(__name__)

def get_config(key, default=None):
    """
    Busca configuracao com prioridade:
    1. Tabela AppConfig no banco de dados
    2. Variavel de ambiente (os.getenv)
    3. Valor default
    """
    try:
        from src.database import get_db
        from src.models_db import AppConfig
        db = next(get_db())
        try:
            entry = db.query(AppConfig).get(key)
            if entry and entry.value is not None and entry.value.strip() != '':
                return entry.value
        finally:
            db.close()
    except Exception:
        pass  # Fallback silencioso para env var

    return os.getenv(key, default)
