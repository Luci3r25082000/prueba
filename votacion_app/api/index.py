"""Vercel serverless entrypoint.

Vercel's Python runtime can serve a WSGI callable named `app`.
We reuse the existing Flask factory from the root `app.py`.
"""

from app import create_app

app = create_app()
