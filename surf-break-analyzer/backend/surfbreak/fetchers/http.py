"""Shared HTTP client with a small TTL cache (data sources update every 10-60 min)."""
from __future__ import annotations

import time

import httpx

from .. import config
from . import FetchError

_cache: dict[str, tuple[float, str]] = {}
_client: httpx.Client | None = None


def set_client(client: httpx.Client | None) -> None:
    """Swap the HTTP client (tests inject an httpx.MockTransport client)."""
    global _client
    _client = client
    _cache.clear()


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=config.HTTP_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
            follow_redirects=True,
        )
    return _client


def get_text(url: str, params: dict | None = None, ttl: float | None = None) -> str:
    ttl = config.FETCH_TTL_SECONDS if ttl is None else ttl
    key = str(httpx.URL(url, params=params))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    try:
        r = _get_client().get(url, params=params)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise FetchError(f"{url}: {e}") from e
    _cache[key] = (time.time(), r.text)
    return r.text


def get_json(url: str, params: dict | None = None, ttl: float | None = None):
    import json

    text = get_text(url, params=params, ttl=ttl)
    try:
        return json.loads(text)
    except ValueError as e:
        raise FetchError(f"{url}: bad JSON ({e})") from e
