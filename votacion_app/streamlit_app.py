import streamlit as st
import sys, io
sys.path.insert(0, ".")
import pandas as pd
from models.database import init_db
import services.electoral as svc

init_db()

st.set_page_config(
    page_title="Sistema Electoral",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebar"] { background-color: #f0f2f6; }
.metric-card { border-radius:10px;padding:16px;color:white;text-align:center;margin-bottom:10px; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ──────────────────────────────────────────────────────
st.sidebar.title("🗳️ Sistema Electoral")

pagina = st.sidebar.radio(
    "Navegación",
    ["📊 Dashboard", "👥 Líderes", "🗳️ Registro de Votantes",
     "📥 Carga Masiva CSV", "📋 Censo Electoral", "🔍 Consulta de Cédula"],
    index=0,
)

st.sidebar.divider()
_sc = svc.stats_censo()
st.sidebar.metric("📋 Padrón", f"{_sc['total_padron']:,}")
c1, c2 = st.sidebar.columns(2)
c1.metric("✅ Disponibles",  f"{_sc['disponibles']:,}")
c2.metric("🚫 Ya votaron",   f"{_sc['inhabilitadas']:,}")
st.sidebar.metric("🗳️ Votantes reg.", f"{_sc['total_votantes']:,}")
if _sc["total_padron"] > 0:
    st.sidebar.progress(_sc["cobertura_pct"]/100,
                        text=f"Cobertura {_sc['cobertura_pct']}%")


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════
if pagina == "📊 Dashboard":
    st.title("📊 Dashboard Electoral")
    st.caption("Consolidación en tiempo real por líder")

    sc = svc.stats_censo()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card" style="background:#1e3a5f"><div style="font-size:2rem;font-weight:bold">{sc["total_votantes"]:,}</div><div>Total Votantes</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card" style="background:#2d6a4f"><div style="font-size:2rem;font-weight:bold">{sc["disponibles"]:,}</div><div>Disponibles</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card" style="background:#c0392b"><div style="font-size:2rem;font-weight:bold">{sc["inhabilitadas"]:,}</div><div>Ya Votaron</div></div>', unsafe_allow_html=True)
    with col4:
        lideres = svc.listar_lideres()
        st.markdown(f'<div class="metric-card" style="background:#7f4f24"><div style="font-size:2rem;font-weight:bold">{len(lideres)}</div><div>Líderes</div></div>', unsafe_allow_html=True)

    if sc["total_padron"] > 0:
        st.progress(sc["cobertura_pct"]/100, text=f"Cobertura: {sc['cobertura_pct']}% — {sc['inhabilitadas']:,} de {sc['total_padron']:,}")

    st.divider()
    st.subheader("🏆 Ranking de líderes")

    lideres = svc.listar_lideres()
    if not lideres:
        st.info("No hay líderes registrados.")
    else:
        maximo = max(l["total_votantes"] for l in lideres) or 1
        total_v = sum(l["total_votantes"] for l in lideres)
        for i, l in enumerate(lideres, 1):
            pct = l["total_votantes"]/maximo*100
            pct_t = l["total_votantes"]/total_v*100 if total_v else 0
            med = {1:"🥇",2:"🥈",3:"🥉"}.get(i, f"#{i}")
            color = "#1e3a5f" if i<=3 else "#4a7fa5"
            st.markdown(f"""
<div style="margin-bottom:8px;padding:10px 14px;background:#f8f9fa;border-radius:8px;border-left:4px solid {color}">
  <div style="display:flex;justify-content:space-between;margin-bottom:5px">
    <span style="font-weight:600;font-size:0.88rem">{med} {l["nombre"]}</span>
    <span style="font-weight:700;color:{color}">{l["total_votantes"]:,} <span style="font-size:0.7rem;color:#999">({pct_t:.1f}%)</span></span>
  </div>
  <div style="background:#dde3ea;border-radius:4px;height:6px">
    <div style="background:{color};width:{pct:.1f}%;height:6px;border-radius:4px"></div>
  </div>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# LÍDERES
# ═══════════════════════════════════════════════════════════════════
elif pagina == "👥 Líderes":
    st.title("👥 Gestión de Líderes")
    col_a, col_b = st.columns([1,1])

    with col_a:
        st.subheader("Crear nuevo líder")
        with st.form("form_lider"):
            nombre_lider = st.text_input("Nombre del líder", placeholder="Ej: Pedro Ramírez")
            if st.form_submit_button("➕ Crear Líder", use_container_width=True, type="primary"):
                r = svc.crear_lider(nombre_lider)
                if r.ok: st.success(r.mensaje); st.rerun()
                else: st.error(r.mensaje)

        st.subheader("Cambiar estado")
        lideres = svc.listar_lideres()
        if lideres:
            sel = st.selectbox("Seleccionar líder", [(l["id"],l["nombre"]) for l in lideres], format_func=lambda x:x[1])
            nuevo = st.radio("Nuevo estado", ["ACTIVO","INACTIVO"], horizontal=True)
            if st.button("Actualizar", use_container_width=True):
                r = svc.cambiar_estado_lider(sel[0], nuevo)
                if r.ok: st.success(r.mensaje); st.rerun()
                else: st.error(r.mensaje)

    with col_b:
        st.subheader(f"Todos los líderes ({len(svc.listar_lideres())})")
        lideres = svc.listar_lideres()
        if not lideres:
            st.info("No hay líderes registrados.")
        else:
            df_lid = pd.DataFrame([{"Nombre":l["nombre"],"Votantes":l["total_votantes"],"Estado":l["estado"]} for l in lideres])
            st.dataframe(df_lid, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# REGISTRO DE VOTANTES
# ═══════════════════════════════════════════════════════════════════
elif pagina == "🗳️ Registro de Votantes":
    st.title("🗳️ Registro Individual de Votantes")
    st.caption("Cada cédula solo puede registrarse **una única vez**. La operación es irreversible.")

    lideres_activos = svc.listar_lideres(solo_activos=True)
    if not lideres_activos:
        st.warning("⚠️ No hay líderes activos. Crea un líder o carga un archivo primero.")
    else:
        col_form, _, col_rank = st.columns([2, 0.15, 2])

        with col_form:
            st.markdown("### 📝 Formulario de registro")
            with st.form("form_votante", clear_on_submit=True):
                cedula = st.text_input("🪪 Número de cédula", placeholder="Ej: 1090123456", max_chars=20)
                nombre_v = st.text_input("👤 Nombre completo", placeholder="Ej: María López García", max_chars=200)
                lider_opts = {f"{l['nombre']}  ({l['total_votantes']} votos)": l["id"] for l in lideres_activos}
                lider_sel = st.selectbox("🏅 Asignar a líder", list(lider_opts.keys()))
                lider_id_sel = lider_opts[lider_sel]
                st.divider()
                confirmar = st.checkbox("✅ Confirmo que los datos son correctos. Esta acción es irreversible.")
                submitted = st.form_submit_button("🗳️ Registrar Votante", use_container_width=True,
                                                   disabled=not confirmar, type="primary")
            if submitted and confirmar:
                r = svc.registrar_votante(cedula, nombre_v, lider_id_sel)
                if r.ok:
                    d = r.datos
                    st.success(f"✅ **{d['nombre']}** registrado exitosamente")
                    st.markdown(f"| Campo | Valor |\n|---|---|\n| 🪪 Cédula | `{d['cedula']}` |\n| 🏅 Líder | {d['lider']} |\n| 📊 Total líder | **{d['total_lider']} votantes** |")
                    st.balloons()
                else:
                    st.error(r.mensaje)

            st.divider()
            st.markdown("### 🕐 Últimos 10 registros")
            recientes = []
            for g in svc.consolidado_por_lider():
                for v in g["votantes"]:
                    recientes.append({"Fecha": v["fecha_registro"].strftime("%d/%m %H:%M") if v["fecha_registro"] else "",
                                      "Cédula": v["cedula"], "Nombre": v["nombre"], "Líder": g["lider_nombre"]})
            if recientes:
                df_r = pd.DataFrame(recientes).sort_values("Fecha", ascending=False).head(10)
                st.dataframe(df_r, use_container_width=True, hide_index=True)
            else:
                st.caption("Sin registros aún.")

        with col_rank:
            st.markdown("### 🏆 Ranking de líderes")
            total_v = sum(l["total_votantes"] for l in lideres_activos)
            maximo  = max((l["total_votantes"] for l in lideres_activos), default=1) or 1
            st.markdown(f'<div style="background:#1e3a5f;border-radius:10px;padding:14px;color:white;text-align:center;margin-bottom:16px"><div style="font-size:2.2rem;font-weight:bold">{total_v:,}</div><div style="font-size:0.85rem;opacity:.85">Total votantes registrados</div></div>', unsafe_allow_html=True)

            ITEMS = 10
            total_l = len(lideres_activos)
            total_p = max(1, -(-total_l//ITEMS))
            pag_r = st.number_input(f"Página ({total_l} líderes)", min_value=1, max_value=total_p, value=1) if total_p>1 else 1
            ini = (pag_r-1)*ITEMS; fin = ini+ITEMS
            for i, l in enumerate(lideres_activos[ini:fin], ini+1):
                pct = l["total_votantes"]/maximo*100
                pct_t = l["total_votantes"]/total_v*100 if total_v else 0
                med = {1:"🥇",2:"🥈",3:"🥉"}.get(i, f"#{i}")
                color = "#1e3a5f" if i<=3 else ("#4a7fa5" if i<=10 else "#7aaecc")
                st.markdown(f"""<div style="margin-bottom:8px;padding:8px 12px;background:#f8f9fa;border-radius:8px;border-left:4px solid {color}">
  <div style="display:flex;justify-content:space-between;margin-bottom:4px">
    <span style="font-weight:600;font-size:0.82rem">{med} {l["nombre"]}</span>
    <span style="font-weight:700;color:{color};font-size:0.88rem">{l["total_votantes"]:,} <span style="font-size:0.68rem;color:#999">{pct_t:.1f}%</span></span>
  </div>
  <div style="background:#dde3ea;border-radius:4px;height:5px"><div style="background:{color};width:{pct:.1f}%;height:5px;border-radius:4px"></div></div>
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# CARGA MASIVA CSV / EXCEL
# ═══════════════════════════════════════════════════════════════════
elif pagina == "📥 Carga Masiva CSV":
    st.title("📥 Carga Masiva de Votantes")
    st.caption("Registra múltiples votantes. Acepta CSV y Excel. Cada fila es una transacción atómica.")

    with st.expander("📋 Ver plantilla CSV de ejemplo", expanded=False):
        plantilla = svc.generar_csv_plantilla()
        st.dataframe(pd.read_csv(io.StringIO(plantilla)), use_container_width=True, hide_index=True)
        st.download_button("⬇️ Descargar plantilla", plantilla, "plantilla_votantes.csv", "text/csv")
        st.caption("El campo `lider` puede ser nuevo — se crea automáticamente. Para Excel con `Source.Name`, el líder se extrae automáticamente.")

    st.divider()
    lideres_activos = svc.listar_lideres(solo_activos=True)
    if lideres_activos:
        with st.expander(f"👥 Líderes en el sistema ({len(lideres_activos)})", expanded=False):
            st.dataframe(pd.DataFrame([{"Nombre":l["nombre"],"Votantes":l["total_votantes"]} for l in lideres_activos]),
                         use_container_width=True, hide_index=True)
    else:
        st.info("ℹ️ Sin líderes previos. Se crearán automáticamente desde el archivo.")

    st.divider()
    st.subheader("1️⃣ Seleccionar archivo")
    archivo = st.file_uploader("Arrastra o selecciona (CSV o Excel .xlsx)", type=["csv","xlsx","xls"])

    es_excel = archivo is not None and archivo.name.lower().endswith((".xlsx",".xls"))
    if archivo and not es_excel:
        cs, ce = st.columns(2)
        with cs: sep_csv = st.selectbox("Separador", [",",";","|","\t"], format_func=lambda x:{",":" Coma (,)",";":"Punto y coma (;)","|":"Pipe (|)","\t":"Tabulador"}[x])
        with ce: enc_csv = st.selectbox("Codificación", ["utf-8","utf-8-sig","latin-1"])
    else:
        sep_csv, enc_csv = ",", "utf-8"

    def leer_archivo(arch, sep, enc):
        raw = arch.read(); nombre = arch.name.lower()
        if nombre.endswith((".xlsx",".xls")):
            xf = pd.ExcelFile(io.BytesIO(raw))
            mejor, mejor_n = None, 0
            for h in xf.sheet_names:
                try:
                    t = pd.read_excel(io.BytesIO(raw), sheet_name=h, nrows=3, dtype=str)
                    if len(t) > mejor_n: mejor_n, mejor = len(t), h
                except: pass
            df = pd.read_excel(io.BytesIO(raw), sheet_name=mejor, dtype=str)
            cols_n, cnt = [], {}
            for c in df.columns:
                cn = c.strip().lower()
                if cn in cnt: cnt[cn]+=1; cn=f"{cn}_{cnt[cn]}"
                else: cnt[cn]=0
                cols_n.append(cn)
            df.columns = cols_n
            df = df.dropna(how="all").reset_index(drop=True)
            al = {"lider","lider_nombre","nombre_lider","leader"}
            if not any(c in al for c in df.columns): df["lider"] = mejor.strip()
            return df, f"Excel · hoja **{mejor}**"
        else:
            df = pd.read_csv(io.BytesIO(raw), sep=sep, encoding=enc, dtype=str)
            cols_n, cnt = [], {}
            for c in df.columns:
                cn = c.strip().lower()
                if cn in cnt: cnt[cn]+=1; cn=f"{cn}_{cnt[cn]}"
                else: cnt[cn]=0
                cols_n.append(cn)
            df.columns = cols_n
            return df.dropna(how="all").reset_index(drop=True), "CSV"

    if archivo:
        try:
            df_raw, info_fmt = leer_archivo(archivo, sep_csv, enc_csv)
            st.subheader("2️⃣ Vista previa")
            st.caption(f"Formato: {info_fmt} · **{len(df_raw):,} filas** · Columnas: `{'` · `'.join(df_raw.columns)}`")
            st.dataframe(df_raw.head(10), use_container_width=True, hide_index=True)

            valido, msg = svc.validar_dataframe_csv(df_raw.copy())
            if not valido:
                st.error(f"❌ {msg}"); st.stop()
            cols_d = msg.split("|")
            st.success(f"✅ cédula:`{cols_d[0]}` · nombre:`{cols_d[1]}` · líder:`{cols_d[2]}`")
            st.divider()

            st.subheader("3️⃣ Análisis previo")
            als = {"source.name","source_name"}
            col_src = next((c for c in df_raw.columns if c in als), None)
            if col_src:
                lideres_csv = sorted({svc.extraer_nombre_lider(v) for v in df_raw[col_src].dropna().unique() if str(v).strip().lower() not in ("nan","none","")})
                st.caption(f"📂 Fuente: columna **`{col_src}`** (nombre extraído automáticamente)")
            else:
                lideres_csv = df_raw[cols_d[2]].str.strip().dropna().unique().tolist()
            sis = {l["nombre"].lower() for l in svc.listar_lideres()}
            nuevos = [n for n in lideres_csv if n.lower() not in sis]
            exist  = [n for n in lideres_csv if n.lower() in sis]
            ca1,ca2,ca3 = st.columns(3)
            ca1.metric("Total filas", f"{len(df_raw):,}")
            ca2.metric("Líderes existentes", len(exist))
            ca3.metric("Líderes nuevos a crear", len(nuevos), delta=f"+{len(nuevos)}" if nuevos else None)
            if nuevos:
                with st.expander(f"👥 {len(lideres_csv)} líderes detectados"):
                    for n in sorted(lideres_csv):
                        st.markdown(f"{'🟢' if n.lower() in sis else '🆕'} {n}")
                st.info(f"🆕 Se crearán automáticamente **{len(nuevos)}** líderes nuevos")
            st.divider()

            st.subheader("4️⃣ Confirmar y ejecutar")
            st.warning("⚠️ **Irreversible.** Cada cédula registrada quedará inhabilitada definitivamente.")
            conf = st.checkbox(f"Confirmo cargar **{len(df_raw):,} registros**")
            if st.button(f"🚀 Iniciar Carga Masiva ({len(df_raw):,} votantes)", disabled=not conf, type="primary", use_container_width=True):
                if nuevos:
                    with st.spinner(f"Creando {len(nuevos)} líderes..."):
                        for n in nuevos: svc.crear_lider(n)
                    st.success(f"✅ {len(nuevos)} líderes creados")
                barra = st.progress(0, text="Iniciando carga...")
                total_f = len(df_raw); LOTE=100; ok_l=[]; err_l=[]
                for ini in range(0, total_f, LOTE):
                    fin = min(ini+LOTE, total_f)
                    r = svc.cargar_votantes_csv(df_raw.iloc[ini:fin].copy(), modo_lider="nombre")
                    ok_l.extend(r.exitosos); err_l.extend(r.fallidos)
                    barra.progress(int(fin/total_f*100), text=f"Procesando {fin:,}/{total_f:,} · ✅{len(ok_l):,} · ❌{len(err_l):,}")
                barra.progress(100, text="✅ Completado")
                st.divider()
                cr1,cr2,cr3 = st.columns(3)
                cr1.metric("Total", f"{total_f:,}"); cr2.metric("✅ Exitosos", f"{len(ok_l):,}"); cr3.metric("❌ Errores", f"{len(err_l):,}")
                t1,t2 = st.tabs([f"✅ Exitosos ({len(ok_l):,})", f"❌ Errores ({len(err_l):,})"])
                with t1:
                    if ok_l:
                        df_ok = pd.DataFrame(ok_l)[["fila","cedula","nombre","lider"]]
                        st.dataframe(df_ok, use_container_width=True, hide_index=True)
                        st.download_button("⬇️ Exportar exitosos", df_ok.to_csv(index=False).encode(), "exitosos.csv","text/csv")
                    else: st.info("Ningún registro exitoso.")
                with t2:
                    if err_l:
                        df_e = pd.DataFrame(err_l)[["fila","cedula","nombre","lider","error"]]
                        st.dataframe(df_e, use_container_width=True, hide_index=True)
                        st.download_button("⬇️ Exportar errores", df_e.to_csv(index=False).encode(), "errores.csv","text/csv")
                    else: st.success("🎉 Sin errores.")
                if ok_l: st.balloons()
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# CENSO ELECTORAL
# ═══════════════════════════════════════════════════════════════════
elif pagina == "📋 Censo Electoral":
    st.title("📋 Censo Electoral")
    st.caption("Carga el padrón electoral. Las cédulas entran como **DISPONIBLES** y se inhabilitan al registrar cada votante.")

    sc = svc.stats_censo()
    k1,k2,k3,k4 = st.columns(4)
    k1.markdown(f'<div class="metric-card" style="background:#1e3a5f"><div style="font-size:2rem;font-weight:bold">{sc["total_padron"]:,}</div><div>Total padrón</div></div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="metric-card" style="background:#2d6a4f"><div style="font-size:2rem;font-weight:bold">{sc["disponibles"]:,}</div><div>✅ Disponibles</div></div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="metric-card" style="background:#c0392b"><div style="font-size:2rem;font-weight:bold">{sc["inhabilitadas"]:,}</div><div>🚫 Ya votaron</div></div>', unsafe_allow_html=True)
    k4.markdown(f'<div class="metric-card" style="background:#7f4f24"><div style="font-size:2rem;font-weight:bold">{sc["cobertura_pct"]}%</div><div>Cobertura</div></div>', unsafe_allow_html=True)

    if sc["total_padron"] > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        st.progress(sc["cobertura_pct"]/100, text=f"🗳️ {sc['inhabilitadas']:,} de {sc['total_padron']:,} cédulas ya votaron ({sc['cobertura_pct']}%)")

    st.divider()
    tab_c, tab_b = st.tabs(["⬆️ Cargar Padrón", "🔍 Buscar Cédula en el padrón"])

    with tab_c:
        st.subheader("Cargar cédulas al padrón electoral")
        st.info("📌 **Solo carga cédulas como DISPONIBLES.**\n\nNo registra votantes ni modifica líderes.\nCuando se registre un votante, su cédula pasa de DISPONIBLE → INHABILITADA automáticamente.")

        arch_c = st.file_uploader("Selecciona el archivo con las cédulas del padrón (CSV o Excel)", type=["csv","xlsx","xls"], key="up_censo")

        if arch_c:
            try:
                raw = arch_c.read(); narch = arch_c.name.lower()
                if narch.endswith((".xlsx",".xls")):
                    xf = pd.ExcelFile(io.BytesIO(raw))
                    mejor, mejor_n = None, 0
                    for h in xf.sheet_names:
                        try:
                            t = pd.read_excel(io.BytesIO(raw), sheet_name=h, nrows=3, dtype=str)
                            if len(t) > mejor_n: mejor_n, mejor = len(t), h
                        except: pass
                    df_c = pd.read_excel(io.BytesIO(raw), sheet_name=mejor, dtype=str)
                    st.caption(f"Excel detectado · hoja: **{mejor}**")
                else:
                    sep2 = st.selectbox("Separador", [",",";","|"], key="sep_censo")
                    df_c = pd.read_csv(io.BytesIO(raw), sep=sep2, dtype=str)

                df_c.columns = [c.strip().lower() for c in df_c.columns]
                alias_ced = {"cedula","cc","documento","id","num_doc","numero_documento"}
                col_ced = next((c for c in df_c.columns if c in alias_ced), df_c.columns[0])
                if col_ced not in alias_ced:
                    st.warning(f"Columna reconocida no encontrada. Usando primera columna: **`{col_ced}`**")
                else:
                    st.success(f"✅ Columna de cédulas: **`{col_ced}`**")

                cedulas_list = df_c[col_ced].dropna().tolist()
                pv1,pv2 = st.columns(2)
                pv1.metric("Cédulas en el archivo", f"{len(cedulas_list):,}")
                pv2.metric("Padrón actual", f"{sc['total_padron']:,}")
                st.dataframe(df_c[[col_ced]].head(10), use_container_width=True, hide_index=True)

                st.divider()
                st.warning("Esta operación carga cédulas como DISPONIBLES. Las ya inhabilitadas no se modifican.")
                conf_c = st.checkbox("Confirmo que deseo cargar este padrón electoral.")
                if st.button(f"📋 Cargar {len(cedulas_list):,} cédulas al padrón", disabled=not conf_c, type="primary", use_container_width=True, key="btn_censo"):
                    bar_c = st.progress(0, text="Cargando...")
                    total_c = len(cedulas_list); LOTE_C=500; acc={"nuevas":0,"ya_disponibles":0,"ya_inhabilitadas":0,"invalidas":0}
                    for ini in range(0, total_c, LOTE_C):
                        fin=min(ini+LOTE_C,total_c)
                        res = svc.cargar_censo_masivo(cedulas_list[ini:fin])
                        for k in acc: acc[k]+=res[k]
                        bar_c.progress(int(fin/total_c*100), text=f"Procesando {fin:,}/{total_c:,}...")
                    bar_c.progress(100, text="✅ Completado")
                    st.divider()
                    ra,rb,rc,rd = st.columns(4)
                    ra.metric("✅ Nuevas", f"{acc['nuevas']:,}")
                    rb.metric("ℹ️ Ya disponibles", f"{acc['ya_disponibles']:,}")
                    rc.metric("🚫 Ya inhabilitadas", f"{acc['ya_inhabilitadas']:,}")
                    rd.metric("⚠️ Inválidas", f"{acc['invalidas']:,}")
                    if acc["nuevas"] > 0:
                        st.success(f"🎉 {acc['nuevas']:,} cédulas nuevas agregadas al padrón.")
                        st.balloons()
                    else:
                        st.info("No se agregaron cédulas nuevas.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

    with tab_b:
        st.subheader("Consultar estado de una cédula en el padrón")
        ced_b = st.text_input("Número de cédula", placeholder="Ej: 1090123456", key="ced_censo")
        if st.button("🔍 Consultar", key="btn_censo_b"):
            if not ced_b.strip():
                st.warning("Ingresa una cédula.")
            else:
                info = svc.buscar_cedula(ced_b.strip())
                ctrl = info["control"]; vot = info["votante"]
                bc1,bc2 = st.columns(2)
                with bc1:
                    st.markdown("#### 📋 En el padrón")
                    if ctrl["existe"]:
                        if ctrl["estado"]=="DISPONIBLE": st.success("🟢 **DISPONIBLE** — Habilitada para votar")
                        else:
                            st.error("🔴 **INHABILITADA** — Ya fue utilizada")
                            if ctrl["fecha_inhabilitacion"]: st.caption(f"Fecha: {ctrl['fecha_inhabilitacion']}")
                    else:
                        st.warning("⚠️ No está en el padrón electoral")
                with bc2:
                    st.markdown("#### 🗳️ Como votante")
                    if vot["registrado"]:
                        st.error("🚫 Ya fue registrada como votante")
                        st.markdown(f"**Nombre:** {vot['nombre']}")
                        st.markdown(f"**Fecha:** {vot['fecha_registro']}")
                        lmap = {l["id"]:l["nombre"] for l in svc.listar_lideres()}
                        st.markdown(f"**Líder:** {lmap.get(vot['lider_id'],'N/A')}")
                    else:
                        st.success("✅ No ha sido registrada como votante aún")

# ═══════════════════════════════════════════════════════════════════
# CONSULTA DE CÉDULA
# ═══════════════════════════════════════════════════════════════════
elif pagina == "🔍 Consulta de Cédula":
    st.title("🔍 Consulta de Estado de Cédula")
    ced_q = st.text_input("Número de cédula", max_chars=20)
    if st.button("🔍 Consultar", use_container_width=False):
        if not ced_q.strip():
            st.warning("Ingresa una cédula.")
        else:
            res = svc.buscar_cedula(ced_q)
            ctrl = res["control"]; vot = res["votante"]
            c1,c2 = st.columns(2)
            with c1:
                st.subheader("Control de Cédula")
                if ctrl["existe"]:
                    color = "🔴" if ctrl["estado"]=="INHABILITADA" else "🟢"
                    st.markdown(f"**Estado:** {color} {ctrl['estado']}")
                    if ctrl["fecha_inhabilitacion"]: st.markdown(f"**Inhabilitada:** {ctrl['fecha_inhabilitacion']}")
                else:
                    st.info("Cédula no registrada en el sistema.")
            with c2:
                st.subheader("Como Votante")
                if vot["registrado"]:
                    st.error("🚫 Ya registrada como votante.")
                    st.markdown(f"**Nombre:** {vot['nombre']}")
                    st.markdown(f"**Fecha:** {vot['fecha_registro']}")
                    lmap = {l["id"]:l["nombre"] for l in svc.listar_lideres()}
                    st.markdown(f"**Líder:** {lmap.get(vot['lider_id'],'Desconocido')}")
                else:
                    st.success("✅ No ha sido registrada como votante.")
