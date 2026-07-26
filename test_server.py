from fastapi.testclient import TestClient
import re

from server import app, url_db

client = TestClient(app)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


def test_shorten_url():
    """Test 1: Shorten a URL - should return a valid shortened URL"""
    url_db.clear()
    
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
    url_db.clear()
    
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
    url_db.clear()
    
    response = client.get("/invalid99")
    
    assert response.status_code == 404
    data = response.json()
    
    assert "detail" in data
    assert data["detail"] == "Short code 'invalid99' not found"


def test_multiple_urls_get_unique_codes():
    """Test 4: Multiple URLs - should get unique short codes for each URL"""
    url_db.clear()
    
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
