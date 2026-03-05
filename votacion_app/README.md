# 🗳️ Sistema de Registro Electoral

Aplicación transaccional en Python + Streamlit para gestión de líderes y votantes con garantías de atomicidad, consistencia y antifraude.

---

## 📁 Estructura del Proyecto

```
votacion_app/
├── app.py                    # Aplicación Streamlit principal
├── requirements.txt          # Dependencias
├── models/
│   ├── __init__.py
│   └── database.py           # Modelos SQLAlchemy + Engine
├── services/
│   ├── __init__.py
│   └── electoral.py          # Lógica de negocio transaccional
└── tests/
    └── test_electoral.py     # Suite de pruebas
```

---

## 🚀 Instalación y Ejecución

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Ejecutar la aplicación

```bash
cd votacion_app
python app.py
```

La app abre en: **http://localhost:5000**

> Nota: la UI original en Streamlit quedó respaldada como `streamlit_app.py`.

### 3. Ejecutar las pruebas

```bash
cd votacion_app
python tests/test_electoral.py
```

---

## 🗂️ Modelo de Datos

| Tabla | Descripción |
|-------|-------------|
| `lider` | Líderes con contador atómico |
| `votante` | Votantes con cédula UNIQUE |
| `control_cedula` | Censo electoral y estado de cédulas |

---

## 🔐 Garantías del Sistema

| Garantía | Implementación |
|----------|----------------|
| **Atomicidad** | Transacción única: INSERT votante + UPDATE cédula + UPDATE líder |
| **Unicidad** | UNIQUE constraint en `votante.cedula` |
| **Antifraude** | Doble validación: `ControlCedula` + `Votante` antes de insertar |
| **Concurrencia** | `SELECT FOR UPDATE` en líder y cédula + `busy_timeout` SQLite |
| **Rollback** | `session.rollback()` ante cualquier excepción |

---

## 📌 Flujo Transaccional (CORE)

```
INICIO TRANSACCIÓN
  │
  ├─ [1] Bloquear fila del líder (FOR UPDATE)
  ├─ [2] Verificar líder activo
  ├─ [3] Verificar cédula no registrada como votante
  ├─ [4] Verificar cédula no inhabilitada en control
  ├─ [5] INSERT en VOTANTE
  ├─ [6] UPDATE CONTROL_CEDULA → INHABILITADA
  ├─ [7] lider.total_votantes += 1
  │
  └─ COMMIT ──── o ──── ROLLBACK TOTAL
```

---

## 🧪 Tests incluidos

1. ✅ Crear líder
2. ✅ Rechazar líder duplicado
3. ✅ Registrar votante exitosamente
4. ✅ Rechazar cédula duplicada
5. ✅ Verificar incremento del contador del líder
6. ✅ Verificar cédula dada de baja
7. ✅ Rechazar líder inexistente
8. ✅ Consolidado por líder

---

## 🌐 Despliegue

### ¿Se puede desplegar en Vercel?

La versión original en Streamlit **no** se despliega directamente en Vercel.

Esta repo ahora incluye una versión **Flask** (entrada en `app.py`) y un entrypoint serverless para Vercel en `api/index.py`.

### Recomendado: Streamlit Community Cloud (o Render/Railway)

1. Sube el repo a GitHub.
2. En Streamlit Community Cloud, crea una nueva app y selecciona el repo.
3. Archivo de entrada: `app.py`.

### Despliegue Flask

Para desplegar esta versión Flask en un servicio tipo PaaS (Render/Railway/Fly), normalmente se usa el comando:

```bash
python app.py
```

o un servidor WSGI (gunicorn/waitress) según tu plataforma.

### Base de datos en producción

Por defecto se usa SQLite local (`./votacion.db`). Para producción, se recomienda una BD externa.

- Variable de entorno `DATABASE_URL`: si está definida, se usa esa URL (por ejemplo Postgres).
- Para tests: `TEST_MODE=1` usa SQLite en memoria.

### Vercel (Flask)

1. Asegúrate de tener `vercel.json` y `api/index.py` en el repo.
2. En Vercel: **New Project** → Importa el repo.
3. Configura variables de entorno:
  - Recomendado: `DATABASE_URL` apuntando a Postgres (Neon/Supabase/etc) para persistencia real.
  - Opcional: `SECRET_KEY`.

Nota: si NO defines `DATABASE_URL`, en Vercel se usa SQLite en `/tmp/votacion.db` (funciona, pero no garantiza persistencia entre despliegues/instancias).
