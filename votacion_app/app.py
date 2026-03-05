"""Aplicación web Flask — Sistema de Registro Electoral.

Esta app reemplaza la UI de Streamlit conservando la misma lógica de negocio
en services/ y la misma capa de datos en models/.
"""

from __future__ import annotations

import io
import os
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

import pandas as pd
from flask import Flask, abort, flash, redirect, render_template, request, send_file, url_for

sys.path.insert(0, ".")

from models.database import init_db
import services.electoral as svc


@dataclass(frozen=True)
class _ExportItem:
    content: bytes
    mimetype: str
    filename: str
    expires_at: float


_EXPORT_CACHE: dict[str, _ExportItem] = {}


@dataclass(frozen=True)
class _UploadItem:
    content: bytes
    filename: str
    sep: str
    enc: str
    expires_at: float


_UPLOAD_CACHE: dict[str, _UploadItem] = {}


def _cache_export(*, content: bytes, mimetype: str, filename: str, ttl_seconds: int = 15 * 60) -> str:
    token = uuid.uuid4().hex
    _EXPORT_CACHE[token] = _ExportItem(
        content=content,
        mimetype=mimetype,
        filename=filename,
        expires_at=time.time() + ttl_seconds,
    )
    return token


def _cache_upload(*, content: bytes, filename: str, sep: str, enc: str, ttl_seconds: int = 15 * 60) -> str:
    token = uuid.uuid4().hex
    _UPLOAD_CACHE[token] = _UploadItem(
        content=content,
        filename=filename,
        sep=sep,
        enc=enc,
        expires_at=time.time() + ttl_seconds,
    )
    return token


def _prune_exports() -> None:
    now = time.time()
    for token, item in list(_EXPORT_CACHE.items()):
        if item.expires_at <= now:
            _EXPORT_CACHE.pop(token, None)

    for token, item in list(_UPLOAD_CACHE.items()):
        if item.expires_at <= now:
            _UPLOAD_CACHE.pop(token, None)


def _normalize_columns(cols: list[Any]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for c in cols:
        base = str(c).strip().lower()
        if base in seen:
            seen[base] += 1
            out.append(f"{base}_{seen[base]}")
        else:
            seen[base] = 0
            out.append(base)
    return out


def _read_bytes(raw: bytes, *, filename: str, sep: str = ",", enc: str = "utf-8") -> tuple[pd.DataFrame, str]:
    name = (filename or "").lower()
    if name.endswith((".xlsx", ".xls")):
        xf = pd.ExcelFile(io.BytesIO(raw))
        best_sheet: str | None = None
        best_n = -1
        for sheet in xf.sheet_names:
            try:
                t = pd.read_excel(io.BytesIO(raw), sheet_name=sheet, nrows=3, dtype=str)
                if len(t.columns) > best_n:
                    best_n = len(t.columns)
                    best_sheet = sheet
            except Exception:
                continue
        if not best_sheet:
            raise ValueError("No se pudo leer ninguna hoja del Excel.")
        df = pd.read_excel(io.BytesIO(raw), sheet_name=best_sheet, dtype=str)
        df.columns = _normalize_columns(list(df.columns))
        df = df.dropna(how="all").reset_index(drop=True)
        aliases_lider = {"lider", "lider_nombre", "nombre_lider", "leader"}
        if not any(c in aliases_lider for c in df.columns):
            df["lider"] = str(best_sheet).strip()
        return df, f"Excel · hoja {best_sheet}"

    df = pd.read_csv(io.BytesIO(raw), sep=sep, encoding=enc, dtype=str)
    df.columns = _normalize_columns(list(df.columns))
    df = df.dropna(how="all").reset_index(drop=True)
    return df, "CSV"


def _read_upload(file_storage, *, sep: str = ",", enc: str = "utf-8") -> tuple[pd.DataFrame, str, bytes, str]:
    raw = file_storage.read()
    filename = file_storage.filename or ""
    df, info = _read_bytes(raw, filename=filename, sep=sep, enc=enc)
    return df, info, raw, filename


def _df_preview(df: pd.DataFrame, n: int = 10) -> tuple[list[str], list[dict[str, Any]]]:
    if df is None or df.empty:
        return [], []
    cols = list(df.columns)
    rows = df.head(n).fillna("").to_dict(orient="records")
    return cols, rows


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")

    init_db()

    @app.template_filter("fmt")
    def fmt_number(value: Any) -> str:
        try:
            return f"{int(value):,}"
        except Exception:
            return str(value)

    @app.context_processor
    def inject_globals():
        return {
            "sidebar_stats": svc.stats_censo(),
        }

    @app.get("/")
    def root():
        return redirect(url_for("dashboard"))

    @app.get("/dashboard")
    def dashboard():
        sc = svc.stats_censo()
        lideres = svc.listar_lideres()
        total_v = sum(l["total_votantes"] for l in lideres) if lideres else 0
        maximo = max((l["total_votantes"] for l in lideres), default=1) or 1
        ranking = []
        for i, l in enumerate(lideres, 1):
            pct = (l["total_votantes"] / maximo) * 100
            pct_t = (l["total_votantes"] / total_v) * 100 if total_v else 0
            med = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"#{i}")
            ranking.append({**l, "med": med, "pct": pct, "pct_total": pct_t})
        return render_template("dashboard.html", active="dashboard", sc=sc, lideres=lideres, ranking=ranking)

    @app.route("/leaders", methods=["GET", "POST"])
    def leaders():
        if request.method == "POST":
            action = request.form.get("action", "")
            if action == "create":
                nombre = request.form.get("nombre", "")
                r = svc.crear_lider(nombre)
                flash(r.mensaje, "success" if r.ok else "danger")
                return redirect(url_for("leaders"))
            if action == "state":
                try:
                    lider_id = int(request.form.get("lider_id", "0"))
                except Exception:
                    lider_id = 0
                nuevo = request.form.get("estado", "ACTIVO")
                r = svc.cambiar_estado_lider(lider_id, nuevo)
                flash(r.mensaje, "success" if r.ok else "danger")
                return redirect(url_for("leaders"))
            flash("Acción inválida.", "warning")
            return redirect(url_for("leaders"))

        lideres = svc.listar_lideres()
        return render_template("leaders.html", active="leaders", lideres=lideres)

    @app.route("/voters", methods=["GET", "POST"])
    def voters():
        lideres_activos = svc.listar_lideres(solo_activos=True)
        resultado: dict[str, Any] | None = None

        if request.method == "POST":
            cedula = request.form.get("cedula", "")
            nombre = request.form.get("nombre", "")
            lider_id = request.form.get("lider_id", "")
            confirm = request.form.get("confirm", "")
            if not confirm:
                flash("Debes confirmar que la acción es irreversible.", "warning")
                return redirect(url_for("voters"))
            try:
                lider_id_int = int(lider_id)
            except Exception:
                lider_id_int = 0
            r = svc.registrar_votante(cedula, nombre, lider_id_int)
            if r.ok:
                flash(r.mensaje, "success")
                resultado = r.datos
            else:
                flash(r.mensaje, "danger")

        recientes = []
        for g in svc.consolidado_por_lider():
            for v in g.get("votantes", []):
                fr = v.get("fecha_registro")
                recientes.append(
                    {
                        "fecha": fr.strftime("%d/%m %H:%M") if fr else "",
                        "cedula": v.get("cedula", ""),
                        "nombre": v.get("nombre", ""),
                        "lider": g.get("lider_nombre", ""),
                    }
                )
        recientes = sorted(recientes, key=lambda x: x.get("fecha", ""), reverse=True)[:10]

        return render_template(
            "voters.html",
            active="voters",
            lideres_activos=lideres_activos,
            resultado=resultado,
            recientes=recientes,
        )

    @app.get("/bulk")
    def bulk_get():
        return render_template("bulk.html", active="bulk")

    @app.post("/bulk")
    def bulk_post():
        _prune_exports()
        archivo = request.files.get("archivo")
        upload_token = request.form.get("upload_token", "")
        sep = request.form.get("sep", ",")
        enc = request.form.get("enc", "utf-8")
        confirm = request.form.get("confirm", "")

        raw: bytes | None = None
        filename: str = ""

        if upload_token:
            item = _UPLOAD_CACHE.get(upload_token)
            if not item:
                flash("La vista previa expiró. Sube el archivo de nuevo.", "warning")
                return redirect(url_for("bulk_get"))
            raw = item.content
            filename = item.filename
            sep = item.sep
            enc = item.enc
            try:
                df_raw, info_fmt = _read_bytes(raw, filename=filename, sep=sep, enc=enc)
            except Exception as e:
                flash(f"Error leyendo archivo: {e}", "danger")
                return redirect(url_for("bulk_get"))
        else:
            if not archivo or not getattr(archivo, "filename", ""):
                flash("Selecciona un archivo CSV o Excel.", "warning")
                return redirect(url_for("bulk_get"))
            try:
                df_raw, info_fmt, raw, filename = _read_upload(archivo, sep=sep, enc=enc)
            except Exception as e:
                flash(f"Error leyendo archivo: {e}", "danger")
                return redirect(url_for("bulk_get"))

        preview_cols, preview_rows = _df_preview(df_raw)
        valido, msg = svc.validar_dataframe_csv(df_raw.copy())
        if not valido:
            flash(str(msg), "danger")
            return render_template(
                "bulk.html",
                active="bulk",
                info_fmt=info_fmt,
                total_filas=len(df_raw),
                preview_cols=preview_cols,
                preview_rows=preview_rows,
            )

        cols_d = str(msg).split("|")
        als = {"source.name", "source_name"}
        col_src = next((c for c in df_raw.columns if c in als), None)
        if col_src:
            lideres_csv = sorted(
                {
                    svc.extraer_nombre_lider(v)
                    for v in df_raw[col_src].dropna().unique()
                    if str(v).strip().lower() not in ("nan", "none", "")
                }
            )
        else:
            lideres_csv = df_raw[cols_d[2]].astype(str).str.strip().dropna().unique().tolist()

        sis = {l["nombre"].lower() for l in svc.listar_lideres()}
        nuevos = [n for n in lideres_csv if n and n.lower() not in sis]
        existentes = [n for n in lideres_csv if n and n.lower() in sis]

        ok_rows: list[dict[str, Any]] = []
        err_rows: list[dict[str, Any]] = []
        export_ok: str | None = None
        export_err: str | None = None

        if confirm:
            if nuevos:
                for n in nuevos:
                    svc.crear_lider(n)

            total_f = len(df_raw)
            LOTE = 100
            for ini in range(0, total_f, LOTE):
                fin = min(ini + LOTE, total_f)
                r = svc.cargar_votantes_csv(df_raw.iloc[ini:fin].copy(), modo_lider="nombre")
                ok_rows.extend(r.exitosos)
                err_rows.extend(r.fallidos)

            if ok_rows:
                df_ok = pd.DataFrame(ok_rows)
                export_ok = _cache_export(
                    content=df_ok[["fila", "cedula", "nombre", "lider"]].to_csv(index=False).encode(),
                    mimetype="text/csv",
                    filename="exitosos.csv",
                )
            if err_rows:
                df_e = pd.DataFrame(err_rows)
                export_err = _cache_export(
                    content=df_e[["fila", "cedula", "nombre", "lider", "error"]].to_csv(index=False).encode(),
                    mimetype="text/csv",
                    filename="errores.csv",
                )
            flash(f"Carga completada: {len(ok_rows)} registrados, {len(err_rows)} errores.", "success")
        else:
            preview_token = upload_token or _cache_upload(content=raw or b"", filename=filename, sep=sep, enc=enc)
            flash("Vista previa generada. Puedes ejecutar sin re-subir el archivo.", "info")

        return render_template(
            "bulk.html",
            active="bulk",
            info_fmt=info_fmt,
            total_filas=len(df_raw),
            preview_cols=preview_cols,
            preview_rows=preview_rows,
            cols_detectadas=cols_d,
            col_src=col_src,
            nuevos=nuevos,
            existentes=existentes,
            ok_rows=ok_rows,
            err_rows=err_rows,
            export_ok=export_ok,
            export_err=export_err,
            upload_token=(preview_token if not confirm else ""),
        )

    @app.route("/census", methods=["GET", "POST"])
    def census():
        sc = svc.stats_censo()
        preview_cols: list[str] = []
        preview_rows: list[dict[str, Any]] = []
        resumen: dict[str, Any] | None = None
        buscado: dict[str, Any] | None = None

        if request.method == "POST":
            action = request.form.get("action", "")
            if action == "search":
                cedula = request.form.get("cedula", "").strip()
                if not cedula:
                    flash("Ingresa una cédula.", "warning")
                else:
                    buscado = svc.buscar_cedula(cedula)
                return render_template(
                    "census.html",
                    active="census",
                    sc=sc,
                    resumen=resumen,
                    preview_cols=preview_cols,
                    preview_rows=preview_rows,
                    buscado=buscado,
                )

            _prune_exports()
            archivo = request.files.get("archivo")
            sep = request.form.get("sep", ",")
            confirm = request.form.get("confirm", "")
            upload_token = request.form.get("upload_token", "")

            raw: bytes | None = None
            filename: str = ""
            if upload_token:
                item = _UPLOAD_CACHE.get(upload_token)
                if not item:
                    flash("La vista previa expiró. Sube el archivo de nuevo.", "warning")
                    return redirect(url_for("census"))
                raw = item.content
                filename = item.filename
                sep = item.sep
                try:
                    df_c, info_fmt = _read_bytes(raw, filename=filename, sep=sep, enc=item.enc)
                except Exception as e:
                    flash(f"Error leyendo archivo: {e}", "danger")
                    return redirect(url_for("census"))
            else:
                if not archivo or not getattr(archivo, "filename", ""):
                    flash("Selecciona un archivo CSV o Excel.", "warning")
                    return redirect(url_for("census"))
                try:
                    df_c, info_fmt, raw, filename = _read_upload(archivo, sep=sep, enc="utf-8")
                except Exception as e:
                    flash(f"Error leyendo archivo: {e}", "danger")
                    return redirect(url_for("census"))

            df_c.columns = [c.strip().lower() for c in df_c.columns]
            alias_ced = {"cedula", "cc", "documento", "id", "num_doc", "numero_documento"}
            col_ced = next((c for c in df_c.columns if c in alias_ced), df_c.columns[0] if len(df_c.columns) else None)
            if not col_ced:
                flash("No se detectaron columnas en el archivo.", "danger")
                return redirect(url_for("census"))

            cedulas_list = df_c[col_ced].dropna().tolist()
            preview_cols, preview_rows = _df_preview(df_c[[col_ced]].rename(columns={col_ced: "cedula"}))

            if confirm:
                total_c = len(cedulas_list)
                LOTE_C = 500
                acc = {"nuevas": 0, "ya_disponibles": 0, "ya_inhabilitadas": 0, "invalidas": 0}
                for ini in range(0, total_c, LOTE_C):
                    fin = min(ini + LOTE_C, total_c)
                    res = svc.cargar_censo_masivo(cedulas_list[ini:fin])
                    for k in acc:
                        acc[k] += res.get(k, 0)
                resumen = {**acc, "total": total_c, "formato": info_fmt, "col": col_ced}
                flash("Censo cargado correctamente.", "success")
            else:
                preview_token = upload_token or _cache_upload(content=raw or b"", filename=filename, sep=sep, enc="utf-8")
                resumen = {"total": len(cedulas_list), "formato": info_fmt, "col": col_ced, "upload_token": preview_token}
                flash("Vista previa generada. Puedes cargar sin re-subir el archivo.", "info")

        return render_template(
            "census.html",
            active="census",
            sc=sc,
            resumen=resumen,
            preview_cols=preview_cols,
            preview_rows=preview_rows,
            buscado=buscado,
        )

    @app.route("/cedula", methods=["GET", "POST"])
    def cedula():
        res: dict[str, Any] | None = None
        if request.method == "POST":
            ced = request.form.get("cedula", "").strip()
            if not ced:
                flash("Ingresa una cédula.", "warning")
            else:
                res = svc.buscar_cedula(ced)
        return render_template("cedula.html", active="cedula", res=res)

    @app.get("/download/plantilla_votantes.csv")
    def download_template():
        content = svc.generar_csv_plantilla().encode()
        return send_file(
            io.BytesIO(content),
            mimetype="text/csv",
            as_attachment=True,
            download_name="plantilla_votantes.csv",
        )

    @app.get("/download/<token>")
    def download_export(token: str):
        _prune_exports()
        item = _EXPORT_CACHE.get(token)
        if not item:
            abort(404)
        return send_file(
            io.BytesIO(item.content),
            mimetype=item.mimetype,
            as_attachment=True,
            download_name=item.filename,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)

