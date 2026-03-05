from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "votacion_app"
APP_PATH = APP_DIR / "app.py"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

spec = importlib.util.spec_from_file_location("votacion_app_app", APP_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"No se pudo cargar el entrypoint Flask en {APP_PATH}")

module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

app = module.app
create_app = module.create_app

if __name__ == "__main__":
    import os

    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
