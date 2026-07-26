from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl, ValidationError
import uvicorn
import random
import string
import re
from urllib.parse import urlparse, urlunparse

app = FastAPI(
    title="URL Shortener",
    description="A MVP evolving URL shortener system"
)

# In-memory database
url_db = {}


class ShortenRequest(BaseModel):
    long_url: HttpUrl


class ShortenResponse(BaseModel):
    short_url: str


def generate_short_code(length: int = 7) -> str:
    """Generate a random alphanumeric short code."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


@app.get("/")
def read_root():
    return {"message": "Hello World"}


@app.post("/shorten", response_model=ShortenResponse)
def shorten_url(request: ShortenRequest):
    """Create a shortened URL from a long URL."""
    short_code = generate_short_code()
    
    # Ensure uniqueness (re-generate if collision)
    while short_code in url_db:
        short_code = generate_short_code()
    
    url_db[short_code] = request.long_url
    short_url = f"http://localhost:8000/{short_code}"
    
    return ShortenResponse(short_url=short_url)


@app.get("/{short_code}")
def redirect_to_long_url(short_code: str):
    """Redirect to the original long URL using the short code."""
    if short_code not in url_db:
        raise HTTPException(
            status_code=404,
            detail=f"Short code '{short_code}' not found"
        )
    
    long_url = url_db[short_code]
    return RedirectResponse(url=long_url, status_code=302)


# You can launch the script directly using 'python server.py'
if __name__ == "__main__":
    print("🚀 Launching Stage 1 URL Shortener...")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)