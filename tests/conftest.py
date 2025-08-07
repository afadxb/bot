import os
import sys

# Ensure the project root is on sys.path so `import core` works when tests are
# executed directly from the ``tests`` directory.
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
