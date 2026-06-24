import os
import logging
import time
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Ensure .env file exists at the working directory or set it via systemd Environment.")

# Normalise driver prefix — handle both psycopg and psycopg2 variants
DATABASE_URL = (
    DATABASE_URL
    .replace("postgresql+psycopg://", "postgresql+psycopg2://")
    .replace("postgresql://", "postgresql+psycopg2://")
)

# DigitalOcean managed Postgres requires SSL and drops idle connections
# connect_timeout raised to 30s to handle SSL handshake on cold deploy
# pool_recycle set to 180s (well under DO's ~300s idle timeout)
# pool_pre_ping=True re-validates connections before use (handles stale connections)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=180,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    connect_args={
        "connect_timeout": 30,
        "keepalives": 1,
        "keepalives_idle": 60,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def check_db_connection(retries: int = 5, delay: int = 3):
    """Retry DB connection on startup — handles DO deploy race conditions."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection OK")
            return
        except OperationalError as e:
            last_error = e
            logger.warning(f"DB connection attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(delay)
    logger.error(f"Database connection FAILED after {retries} attempts: {last_error}")
    raise RuntimeError(f"Cannot connect to database after {retries} attempts: {last_error}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
