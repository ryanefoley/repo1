"""Data fetchers. Each returns plain dicts and raises FetchError on failure."""


class FetchError(Exception):
    pass
