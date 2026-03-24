from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


# PUBLIC_INTERFACE
def get_engine() -> AsyncEngine:
    """Get (and lazily create) the global async SQLAlchemy engine."""
    global _engine, _session_maker
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            future=True,
        )
        _session_maker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


# PUBLIC_INTERFACE
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get the global async sessionmaker."""
    get_engine()
    assert _session_maker is not None
    return _session_maker


# PUBLIC_INTERFACE
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session
