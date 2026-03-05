"""WSGI entrypoint for platforms that auto-detect `wsgi.py`.

Vercel's Flask detection can look for common entrypoint filenames.
"""

from app import app  # noqa: F401
