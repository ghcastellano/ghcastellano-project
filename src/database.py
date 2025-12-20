import os
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy.engine import make_url

# Modelo Declarativo Base
# Devemos importar Base de models_db se existir, ou definir aqui se for a origem.
# Para evitar circularidade, melhor models_db definir Base ou importar daqui.
# Verificando models_db depois.

# Variáveis Globais
engine = None
db_session = None
SessionLocal = None

from .config import config
import logging

logger = logging.getLogger("mvp-app")

def normalize_database_url(database_url: Optional[str]) -> Optional[str]:
    """
    Normaliza a URL do banco.
    - Se for Postgres, garante que sslmode=require esteja presente.
    """
    if not database_url:
        return None

    try:
        url = make_url(database_url)
    except Exception:
        # Mantém a URL como está se não for parseável pelo SQLAlchemy
        return database_url

    # Garante SSL mode require se não estiver presente (boas práticas nuvem)
    if url.drivername.startswith("postgresql") and "sslmode" not in url.query:
        url = url.set(query={**url.query, "sslmode": "require"})
            
    return url.render_as_string(hide_password=False)

def init_db():
    global engine, db_session, SessionLocal
    # Restore normalization
    database_url = normalize_database_url(config.DATABASE_URL)
    # database_url = config.DATABASE_URL
    if database_url:
        try:
            # Masking URL for security in logs
            masked_url = database_url.split("@")[-1] if "@" in database_url else "configured"
            logger.info(f"🔌 Tentando conectar ao banco: {masked_url}")
            
            # Defaults conservadores para evitar estouro de conexões em cenários serverless.
            pool_size = int(os.getenv("DB_POOL_SIZE", "2"))
            max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "3"))
            pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
            pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # 30 min

            # Em provedores como Supabase, SSL é obrigatório. Mesmo que `sslmode=require`
            # esteja na URL, passar `connect_args` ajuda a evitar edge-cases em que a
            # query string não é propagada corretamente.
            # connect_args = {} removed to rely on URL string

            engine = create_engine(
                database_url,
                pool_pre_ping=True,
                poolclass=NullPool,
            )
            # scoped_session registry
            db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
            SessionLocal = db_session
            logger.info("✅ Conexão com Banco de Dados Inicializada")
        except Exception as e:
            logger.error(f"❌ Erro ao criar engine do banco: {e}")
            raise e
    else:
        logger.warning("⚠️ DATABASE_URL não encontrada na Config. Verifique as variáveis de ambiente.")

# Alias for compatibility if app.py uses SessionLocal
# Alias for compatibility
SessionLocal = None # updated in init_db

def get_db():
    """Generates a session (Legacy support). Prefer using db_session directly."""
    if db_session is None:
        init_db()
    
    if db_session:
        # scoped_session returns the same session for the thread
        db = db_session() 
        try:
            yield db
        finally:
            # scoped_session management handles cleanup often, but explicit remove() 
            # is done in app.teardown_appcontext. 
            # If using 'yield', caller expects to close.
            # db_session.remove() # Don't remove here if we want to reuse in same request?
            # actually get_db() is typically for Dependency Injection (FastAPI-style) 
            # In Flask with scoped_session, we just use the proxy.
            pass
    else:
        yield None
