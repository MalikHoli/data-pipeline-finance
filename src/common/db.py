from sqlalchemy import create_engine
from src.common.config import DB_HOST, DB_PORT, DB_NAME, DB_WRITE_USER, DB_READ_USER

def _make_engine(user):
    return create_engine(
        f"postgresql+psycopg2://{user}@{DB_HOST}:{DB_PORT}/{DB_NAME}",pool_pre_ping=True
    )

def get_read_engine():
    return _make_engine(DB_READ_USER)

def get_write_engine():
    return _make_engine(DB_WRITE_USER)