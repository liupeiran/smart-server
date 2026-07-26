import random
import string
import hashlib
from urllib.parse import urlsplit, urlunsplit

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, HttpUrl, field_validator

app = FastAPI(
    title="URL Shortener",
    description="A MVP evolving URL shortener system"
)

STRATEGY = "COUNTER"
GLOBAL_COUNTER = 62**6
BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

# In-memory database
url_db = {}


class ShortenRequest(BaseModel):
    long_url: HttpUrl

    @field_validator("long_url", mode="before")
    @classmethod
    def trim_long_url(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ShortenResponse(BaseModel):
    short_url: str


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(
    _: Request, _exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": "Invalid request"})


def normalize_url(url: str) -> str:
    """Return the canonical representation used for storage and lookup."""
    parsed = urlsplit(url.strip())
    hostname = (parsed.hostname or "").lower()

    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    userinfo = ""
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo = f"{userinfo}:{parsed.password}"
        userinfo = f"{userinfo}@"

    port = parsed.port
    is_default_port = (parsed.scheme == "http" and port == 80) or (
        parsed.scheme == "https" and port == 443
    )
    port_suffix = "" if port is None or is_default_port else f":{port}"
    path = parsed.path.rstrip("/")

    return urlunsplit(
        (
            parsed.scheme.lower(),
            f"{userinfo}{hostname}{port_suffix}",
            path,
            parsed.query,
            parsed.fragment,
        )
    )

def generate_random_code(length: int = 7) -> str:
    """Generate a random alphanumeric short code."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_sha256_code(url: str) -> str:
    """Return the first seven hexadecimal characters of a URL's SHA-256 hash."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:7]


def encode_base62(num: int) -> str:
    """Encode a non-negative base-10 integer with the Base62 alphabet."""
    if num < 0:
        raise ValueError("Base62 encoding requires a non-negative integer")
    if num == 0:
        return BASE62_ALPHABET[0]

    encoded = ""
    while num:
        num, remainder = divmod(num, len(BASE62_ALPHABET))
        encoded = BASE62_ALPHABET[remainder] + encoded

    return encoded


def generate_counter_code() -> str:
    """Return the current Base62 counter value and advance the counter."""
    global GLOBAL_COUNTER

    short_code = encode_base62(GLOBAL_COUNTER)
    GLOBAL_COUNTER += 1
    return short_code


def generate_short_code(url: str) -> str:
    """Generate a short code using the configured key-generation strategy."""
    if STRATEGY == "COUNTER":
        return generate_counter_code()
    if STRATEGY == "SHA256":
        return generate_sha256_code(url)
    if STRATEGY == "RANDOM":
        return generate_random_code(url)
    raise ValueError(f"Unsupported key-generation strategy: {STRATEGY}")


@app.get("/")
def read_root():
    return {"message": "Hello World"}


@app.post("/shorten", response_model=ShortenResponse)
def shorten_url(request: ShortenRequest):
    """Create a shortened URL from a long URL."""
    normalized_url = normalize_url(str(request.long_url))

    for short_code, stored_url in url_db.items():
        if stored_url == normalized_url:
            return ShortenResponse(
                short_url=f"http://localhost:8000/{short_code}"
            )

    short_code = generate_short_code(normalized_url)

    # Counter codes can be regenerated; a hash collision needs explicit handling.
    while short_code in url_db:
        if STRATEGY == "SHA256":
            raise HTTPException(
                status_code=409,
                detail="Short code collision for a different URL",
            )
        short_code = generate_short_code(normalized_url)

    url_db[short_code] = normalized_url
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
    print("Launching Stage 3 URL Shortener...")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)