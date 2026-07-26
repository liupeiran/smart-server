import hashlib
import re

import pytest
from fastapi.testclient import TestClient

import server
from server import (
    BASE62_ALPHABET,
    GLOBAL_COUNTER,
    app,
    encode_base62,
    generate_counter_code,
    generate_sha256_code,
    url_db,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_url_db():
    url_db.clear()
    server.STRATEGY = "COUNTER"
    server.GLOBAL_COUNTER = GLOBAL_COUNTER
    yield
    url_db.clear()
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
    assert len(short_code) == 7
    assert re.match(r'^[a-zA-Z0-9]{7}$', short_code)
    
    assert short_code in url_db
    assert url_db[short_code] == "https://www.google.com"


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
        
        assert len(short_code) == 7
        assert short_code not in short_codes
        
        short_codes.append(short_code)
        assert url_db[short_code] == url
    
    assert len(short_codes) == 3
    assert len(set(short_codes)) == 3


def test_malformed_long_url_returns_400():
    response = client.post("/shorten", json={"long_url": "not a valid URL"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request"}
    assert url_db == {}


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
    assert url_db[short_code] == expected_url


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
    assert len(url_db) == 1


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
    assert response.json()["short_url"] == "http://localhost:8000/1000000"
    assert url_db == {"1000000": "https://example.com/counter"}


def test_shorten_uses_sha256_strategy(monkeypatch):
    monkeypatch.setattr(server, "STRATEGY", "SHA256")
    long_url = "https://example.com/sha256"

    response = client.post("/shorten", json={"long_url": long_url})

    expected_code = generate_sha256_code(long_url)
    assert response.status_code == 200
    assert response.json()["short_url"] == f"http://localhost:8000/{expected_code}"
    assert url_db == {expected_code: long_url}
