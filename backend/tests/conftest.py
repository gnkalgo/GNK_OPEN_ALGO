import os

import pytest
from fakeredis import FakeRedis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["ENVIRONMENT"] = "test"
os.environ["COOKIE_SECURE"] = "false"
os.environ["FRONTEND_URL"] = "http://testserver"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")
from app.db import Base, get_db
from app.main import app
from app.security import get_redis


@pytest.fixture
def client():
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    if url != "sqlite://" and make_url(url).database != "gnk_test":
        raise RuntimeError("Integration tests require the disposable database named gnk_test.")
    engine = create_engine(
        url,
        **(
            {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
            if url == "sqlite://"
            else {}
        ),
    )
    # A dedicated disposable test database only; CI runs the Alembic migration first.
    if url == "sqlite://":
        Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    cache = FakeRedis(decode_responses=True)

    def db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_redis] = lambda: cache
    with TestClient(app, headers={"Origin": "http://testserver"}) as c:
        c.db = factory
        c.cache = cache
        yield c
    app.dependency_overrides.clear()
    if url == "sqlite://":
        Base.metadata.drop_all(engine)
    else:
        with engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())
    engine.dispose()
