from __future__ import annotations


def fetch_all_emotional_factors() -> dict:
    """Return placeholder emotional factor data.

    The real project aggregates data from social networks. For the purposes of
    these tests we simply return a static dictionary so that the import works
    without requiring external services or credentials.
    """
    return {"sentiment": 0.0, "source": "placeholder"}
