"""Core package for trading bot utilities used in tests."""

# The modules are imported in tests directly, but defining __all__ helps
# static analysers and marks this directory as a package.

__all__ = [
    'logger',
    'order_manager',
    'strategy',
    'social_fetcher',
]
