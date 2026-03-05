from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "votacion_app"
APP_PATH = APP_DIR / "app.py"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

if not APP_PATH.exists():
    raise FileNotFoundError(
        f"Entrypoint Flask no encontrado en {APP_PATH}. Asegúrese de que exista votacion_app/app.py."
    )

spec = importlib.util.spec_from_file_location("votacion_app_app", APP_PATH)
if spec is None or spec.loader is None:
    raise ImportError(
        f"No se pudo cargar el entrypoint Flask en {APP_PATH}. Verifique que el archivo sea válido y accesible."
    )

module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

app = getattr(module, "app", None)
if app is None:
    raise AttributeError(f"El módulo {APP_PATH} no expone una variable llamada 'app'.")

if __name__ == "__main__":
    import os

    env = os.getenv("FLASK_ENV", "").lower()
    if env == "development":
        debug_flag = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    else:
        debug_flag = False
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=debug_flag)
