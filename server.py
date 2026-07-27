# main.py
import random
import string
from urllib.parse import urlsplit, urlunsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import URLMapping
from schemas import ShortenRequest, ShortenResponse
from utils import encode_base62, generate_sha256_code

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="URL Shortener",
    description="A MVP evolving URL shortener system",
)

STRATEGY = "COUNTER"
GLOBAL_COUNTER = 62**6


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(
    _: Request, _exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": "Invalid request"})


def normalize_url(url: str) -> str:
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

    return urlunsplit(
        (
            parsed.scheme.lower(),
            f"{userinfo}{hostname}{port_suffix}",
            parsed.path.rstrip("/"),
            parsed.query,
            parsed.fragment,
        )
    )


def generate_random_code(length: int = 7) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(length))


def generate_counter_code() -> str:
    global GLOBAL_COUNTER

    short_code = encode_base62(GLOBAL_COUNTER)
    GLOBAL_COUNTER += 1
    return short_code


def generate_short_code(url: str) -> str:
    if STRATEGY == "COUNTER":
        return generate_counter_code()
    if STRATEGY == "SHA256":
        return generate_sha256_code(url)
    if STRATEGY == "RANDOM":
        return generate_random_code()
    raise ValueError(f"Unsupported key-generation strategy: {STRATEGY}")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.post("/shorten", response_model=ShortenResponse)
def shorten_url(
    request: ShortenRequest,
    db: Session = Depends(get_db),
) -> ShortenResponse:
    normalized_url = normalize_url(str(request.long_url))

    existing_mapping = (
        db.query(URLMapping)
        .filter(URLMapping.long_url == normalized_url)
        .first()
    )
    if existing_mapping is not None:
        return ShortenResponse(
            short_url=f"http://localhost:8000/{existing_mapping.short_code}"
        )

    url_mapping = URLMapping(long_url=normalized_url)
    db.add(url_mapping)

    if STRATEGY == "COUNTER":
        db.flush()
        assert url_mapping.id is not None
        short_code = encode_base62(url_mapping.id)
    else:
        short_code = generate_short_code(normalized_url)

        while (
            db.query(URLMapping)
            .filter(URLMapping.short_code == short_code)
            .first()
            is not None
        ):
            if STRATEGY == "SHA256":
                raise HTTPException(
                    status_code=409,
                    detail="Short code collision for a different URL",
                )
            short_code = generate_short_code(normalized_url)

    url_mapping.short_code = short_code
    db.commit()

    return ShortenResponse(short_url=f"http://localhost:8000/{short_code}")


@app.get("/{short_code}")
def redirect_to_long_url(
    short_code: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    url_mapping = (
        db.query(URLMapping)
        .filter(URLMapping.short_code == short_code)
        .first()
    )
    if url_mapping is None:
        raise HTTPException(
            status_code=404,
            detail=f"Short code '{short_code}' not found",
        )

    return RedirectResponse(url=url_mapping.long_url, status_code=302)
