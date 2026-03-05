"""Root-level Flask entrypoint for Vercel deployment.

Vercel looks for a Flask ``app`` variable in standard locations such as
``app.py`` at the repository root.  This module adds the ``votacion_app``
package directory to ``sys.path`` so that all internal imports
(``models``, ``services``, etc.) resolve correctly, then re-exports the
Flask application instance.
"""

import os
import sys

# Ensure votacion_app is on the Python path so that its internal
# imports (models, services, …) work regardless of the working directory.
_votacion_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "votacion_app")
if _votacion_dir not in sys.path:
    sys.path.insert(0, _votacion_dir)

from votacion_app.app import app  # noqa: F401
