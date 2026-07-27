# utils.py
import hashlib

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def encode_base62(num: int) -> str:
    if num < 0:
        raise ValueError("Base62 encoding requires a non-negative integer")
    if num == 0:
        return BASE62_ALPHABET[0]

    encoded = ""
    while num:
        num, remainder = divmod(num, len(BASE62_ALPHABET))
        encoded = BASE62_ALPHABET[remainder] + encoded

    return encoded


def generate_sha256_code(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:7]