import hashlib
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy import BigInteger

import server
from database import Base, get_db, get_redis
from models import URLMapping
from server import (
    GLOBAL_COUNTER,
    app,
    generate_counter_code,
)
from utils import (
    BASE62_ALPHABET,
    encode_base62,
    generate_sha256_code,
)


class InMemoryRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str, ex: int) -> bool:
        self.values[key] = value
        self.expirations[key] = ex
        return True

    def clear(self) -> None:
        self.values.clear()
        self.expirations.clear()


test_redis = InMemoryRedis()


def override_get_redis() -> InMemoryRedis:
    return test_redis

# Compiler Hook: Forces SQLite to treat BigInteger as an auto-incrementing type
@compiles(BigInteger, "sqlite")
def compile_bigint_sqlite(element, compiler, **kw):
    return "INTEGER"


test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_redis] = override_get_redis
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with test_engine.connect() as conn:
        conn.execute(
            text("INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('url_mappings', :start_id)"),
            {"start_id": 62**6 - 1}
        )
        conn.commit()
    test_redis.clear()
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_shorten_persists_url_mapping():
    response = client.post(
        "/shorten",
        json={"long_url": "https://example.com/articles"},
    )

    assert response.status_code == 200
    short_code = response.json()["short_url"].rsplit("/", maxsplit=1)[1]

    with TestSessionLocal() as db:
        mapping = (
            db.query(URLMapping)
            .filter(URLMapping.short_code == short_code)
            .first()
        )

        assert mapping is not None
        assert mapping.long_url == "https://example.com/articles"
        assert mapping.short_code == short_code


def test_short_code_redirects_to_persisted_url():
    shorten_response = client.post(
        "/shorten",
        json={"long_url": "https://example.com/articles"},
    )
    short_code = shorten_response.json()["short_url"].rsplit("/", maxsplit=1)[1]

    response = client.get(f"/{short_code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/articles"

client = TestClient(app)
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_redis] = override_get_redis


def get_mapping(short_code: str) -> URLMapping | None:
    with TestSessionLocal() as db:
        return (
            db.query(URLMapping)
            .filter(URLMapping.short_code == short_code)
            .first()
        )


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    test_redis.clear()
    server.STRATEGY = "COUNTER"
    server.GLOBAL_COUNTER = GLOBAL_COUNTER
    yield
    Base.metadata.drop_all(bind=test_engine)
    test_redis.clear()
    server.STRATEGY = "COUNTER"
    server.GLOBAL_COUNTER = GLOBAL_COUNTER


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


def test_shorten_url():
    """Test 1: Shorten a URL - should return a valid shortened URL"""
    response = client.post(
        "/shorten",
        json={"long_url": "https://www.google.com"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "short_url" in data
    assert data["short_url"].startswith("http://localhost:8000/")
    
    short_code = data["short_url"].split("/")[-1]
    assert re.match(r"^[a-zA-Z0-9]+$", short_code)

    mapping = get_mapping(short_code)
    assert mapping is not None
    assert mapping.long_url == "https://www.google.com"
    assert short_code == encode_base62(mapping.id)


def test_redirect_with_valid_short_code():
    """Test 2: Redirect using short code - should return 302 and redirect to long URL"""
    response = client.post(
        "/shorten",
        json={"long_url": "https://www.example.com"}
    )
    short_code = response.json()["short_url"].split("/")[-1]
    
    redirect_response = client.get(f"/{short_code}", follow_redirects=False)
    
    assert redirect_response.status_code == 302
    assert redirect_response.headers["location"] == "https://www.example.com"


def test_invalid_short_code_returns_404():
    """Test 3: Try invalid short code - should return 404 with error message"""
    response = client.get("/invalid99")
    
    assert response.status_code == 404
    data = response.json()
    
    assert "detail" in data
    assert data["detail"] == "Short code 'invalid99' not found"


def test_multiple_urls_get_unique_codes():
    """Test 4: Multiple URLs - should get unique short codes for each URL"""
    urls = [
        "https://github.com",
        "https://stackoverflow.com/questions/12345",
        "https://www.python.org"
    ]
    
    short_codes = []
    
    for url in urls:
        response = client.post("/shorten", json={"long_url": url})
        assert response.status_code == 200
        
        short_url = response.json()["short_url"]
        short_code = short_url.split("/")[-1]
        
        assert short_code not in short_codes
        
        short_codes.append(short_code)
        mapping = get_mapping(short_code)
        assert mapping is not None
        assert mapping.long_url == url
    
    assert len(short_codes) == 3
    assert len(set(short_codes)) == 3


def test_malformed_long_url_returns_400():
    response = client.post("/shorten", json={"long_url": "not a valid URL"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request"}
    with TestSessionLocal() as db:
        assert db.query(URLMapping).count() == 0


@pytest.mark.parametrize(
    ("long_url", "expected_url"),
    [
        (
            "\t HTTPS://EXAMPLE.COM:443/a/path///?query=value#fragment \t",
            "https://example.com/a/path?query=value#fragment",
        ),
        (" http://EXAMPLE.COM:80/ ", "http://example.com"),
    ],
)
def test_shorten_normalizes_long_url(long_url, expected_url):
    response = client.post("/shorten", json={"long_url": long_url})

    assert response.status_code == 200
    short_code = response.json()["short_url"].rsplit("/", maxsplit=1)[1]
    mapping = get_mapping(short_code)
    assert mapping is not None
    assert mapping.long_url == expected_url


def test_equivalent_normalized_urls_reuse_short_code():
    first_response = client.post(
        "/shorten",
        json={"long_url": "https://EXAMPLE.COM:443/articles/"},
    )
    second_response = client.post(
        "/shorten",
        json={"long_url": " https://example.com/articles "},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    with TestSessionLocal() as db:
        assert db.query(URLMapping).count() == 1


def test_generate_sha256_code_uses_first_seven_hexadecimal_characters():
    long_url = "https://example.com/articles"

    short_code = generate_sha256_code(long_url)

    expected_code = hashlib.sha256(long_url.encode("utf-8")).hexdigest()[:7]
    assert short_code == expected_code
    assert re.fullmatch(r"[0-9a-f]{7}", short_code)


def test_encode_base62_converts_decimal_numbers():
    assert encode_base62(0) == "0"
    assert encode_base62(61) == BASE62_ALPHABET[-1]
    assert encode_base62(62) == "10"
    assert encode_base62(GLOBAL_COUNTER) == "1000000"


def test_generate_counter_code_encodes_and_increments_counter(monkeypatch):
    monkeypatch.setattr(server, "GLOBAL_COUNTER", GLOBAL_COUNTER)

    first_code = generate_counter_code()
    second_code = generate_counter_code()

    assert first_code == "1000000"
    assert second_code == "1000001"
    assert server.GLOBAL_COUNTER == GLOBAL_COUNTER + 2


def test_shorten_uses_counter_strategy_by_default():
    response = client.post(
        "/shorten",
        json={"long_url": "https://example.com/counter"},
    )

    assert response.status_code == 200
    assert response.json()["short_url"] == "http://localhost:8000/1"
    mapping = get_mapping("1")
    assert mapping is not None
    assert mapping.id == 1
    assert mapping.long_url == "https://example.com/counter"


def test_shorten_uses_sha256_strategy(monkeypatch):
    monkeypatch.setattr(server, "STRATEGY", "SHA256")
    long_url = "https://example.com/sha256"

    response = client.post("/shorten", json={"long_url": long_url})

    expected_code = generate_sha256_code(long_url)
    assert response.status_code == 200
    assert response.json()["short_url"] == f"http://localhost:8000/{expected_code}"
    mapping = get_mapping(expected_code)
    assert mapping is not None
    assert mapping.long_url == long_url


def test_shorten_uses_write_around_without_populating_cache():
    response = client.post(
        "/shorten",
        json={"long_url": "https://example.com/write-around"},
    )
    short_code = response.json()["short_url"].rsplit("/", maxsplit=1)[1]

    assert response.status_code == 200
    assert test_redis.values == {}
    assert test_redis.expirations == {}
    assert server.cache_key(short_code) not in test_redis.values


def test_redirect_populates_cache_with_30_day_ttl():
    shorten_response = client.post(
        "/shorten",
        json={"long_url": "https://example.com/cache-aside"},
    )
    short_code = shorten_response.json()["short_url"].rsplit("/", maxsplit=1)[1]

    response = client.get(f"/{short_code}", follow_redirects=False)

    assert response.status_code == 302
    assert test_redis.values[server.cache_key(short_code)] == (
        "https://example.com/cache-aside"
    )
    assert test_redis.expirations[server.cache_key(short_code)] == 30 * 24 * 60 * 60


def test_redirect_uses_cached_url_when_database_mapping_is_missing():
    shorten_response = client.post(
        "/shorten",
        json={"long_url": "https://example.com/cache-hit"},
    )
    short_code = shorten_response.json()["short_url"].rsplit("/", maxsplit=1)[1]
    client.get(f"/{short_code}", follow_redirects=False)

    with TestSessionLocal() as db:
        db.query(URLMapping).filter(URLMapping.short_code == short_code).delete()
        db.commit()

    response = client.get(f"/{short_code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/cache-hit"
