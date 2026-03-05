"""Servicio transaccional - Sistema de Registro Electoral"""
import re
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func
from models.database import SessionLocal, Lider, Votante, ControlCedula, EstadoCedula, EstadoLider


class Resultado:
    def __init__(self, ok, mensaje, datos=None):
        self.ok = ok; self.mensaje = mensaje; self.datos = datos
    def __bool__(self): return self.ok


# ── Líderes ──────────────────────────────────────────────────────

def crear_lider(nombre):
    nombre = nombre.strip()
    if not nombre: return Resultado(False, "Nombre vacío.")
    with SessionLocal() as s:
        if s.execute(select(Lider).where(func.lower(Lider.nombre)==nombre.lower())).scalar_one_or_none():
            return Resultado(False, f"Ya existe un líder '{nombre}'.")
        l = Lider(nombre=nombre, estado=EstadoLider.ACTIVO, total_votantes=0)
        s.add(l); s.commit(); s.refresh(l)
        return Resultado(True, f"Líder '{nombre}' creado.", {"id": l.id})

def listar_lideres(solo_activos=False):
    with SessionLocal() as s:
        q = select(Lider)
        if solo_activos: q = q.where(Lider.estado==EstadoLider.ACTIVO)
        return [{"id":l.id,"nombre":l.nombre,"total_votantes":l.total_votantes,
                 "estado":l.estado,"fecha_creacion":l.fecha_creacion}
                for l in s.execute(q.order_by(Lider.total_votantes.desc())).scalars().all()]

def cambiar_estado_lider(lider_id, nuevo_estado):
    with SessionLocal() as s:
        l = s.get(Lider, lider_id)
        if not l: return Resultado(False, "Líder no encontrado.")
        l.estado = nuevo_estado; s.commit()
        return Resultado(True, f"Líder actualizado a {nuevo_estado}.")


# ── Censo Electoral ───────────────────────────────────────────────

def cargar_censo_masivo(cedulas: list) -> dict:
    """Carga cédulas como DISPONIBLES. NO registra votantes."""
    nuevas = ya_disponibles = ya_inhabilitadas = invalidas = 0
    vistas = set()
    with SessionLocal() as s:
        for c in cedulas:
            c = str(c).strip().replace(".0","")
            if not c or c.lower() in ("nan","none",""):
                invalidas += 1; continue
            if c in vistas:
                ya_disponibles += 1; continue
            vistas.add(c)
            ex = s.get(ControlCedula, c)
            if ex:
                if ex.estado == EstadoCedula.DISPONIBLE: ya_disponibles += 1
                else: ya_inhabilitadas += 1
                continue
            s.add(ControlCedula(cedula=c, estado=EstadoCedula.DISPONIBLE))
            nuevas += 1
        s.commit()
    return {"nuevas":nuevas,"ya_disponibles":ya_disponibles,
            "ya_inhabilitadas":ya_inhabilitadas,"invalidas":invalidas,
            "total_procesadas":nuevas+ya_disponibles+ya_inhabilitadas+invalidas}

def stats_censo() -> dict:
    """Estadísticas completas del censo electoral."""
    with SessionLocal() as s:
        total   = s.execute(select(func.count(ControlCedula.cedula))).scalar() or 0
        disp    = s.execute(select(func.count(ControlCedula.cedula))
                    .where(ControlCedula.estado==EstadoCedula.DISPONIBLE)).scalar() or 0
        inh     = total - disp
        votan   = s.execute(select(func.count(Votante.id))).scalar() or 0
        cob     = round(inh/total*100,2) if total > 0 else 0.0
    return {"total_padron":total,"disponibles":disp,"inhabilitadas":inh,
            "total_votantes":votan,"cobertura_pct":cob}

def stats_cedulas():
    sc = stats_censo()
    return {"total":sc["total_padron"],"disponibles":sc["disponibles"],"inhabilitadas":sc["inhabilitadas"]}


# ── Registro transaccional ────────────────────────────────────────

def registrar_votante(cedula, nombre, lider_id):
    cedula = cedula.strip(); nombre = nombre.strip()
    if not cedula: return Resultado(False, "Cédula vacía.")
    if not nombre: return Resultado(False, "Nombre vacío.")
    if not lider_id: return Resultado(False, "Seleccione un líder.")
    with SessionLocal() as s:
        try:
            lider = s.execute(select(Lider).where(Lider.id==lider_id).with_for_update()).scalar_one_or_none()
            if not lider: return Resultado(False, "Líder no existe.")
            if lider.estado != EstadoLider.ACTIVO: return Resultado(False, "Líder inactivo.")
            if s.execute(select(Votante).where(Votante.cedula==cedula)).scalar_one_or_none():
                return Resultado(False, f"⚠️ Cédula {cedula} ya registrada.")
            ctrl = s.execute(select(ControlCedula).where(ControlCedula.cedula==cedula).with_for_update()).scalar_one_or_none()
            if ctrl and ctrl.estado == EstadoCedula.INHABILITADA:
                return Resultado(False, f"🚫 Cédula {cedula} inhabilitada.")
            s.add(Votante(cedula=cedula,nombre=nombre,lider_id=lider_id,fecha_registro=datetime.utcnow()))
            s.flush()
            if ctrl:
                ctrl.estado = EstadoCedula.INHABILITADA
                ctrl.fecha_inhabilitacion = datetime.utcnow()
            else:
                s.add(ControlCedula(cedula=cedula,estado=EstadoCedula.INHABILITADA,fecha_inhabilitacion=datetime.utcnow()))
            lider.total_votantes += 1
            s.commit()
            return Resultado(True, f"✅ '{nombre}' registrado bajo '{lider.nombre}'.",
                             {"cedula":cedula,"nombre":nombre,"lider":lider.nombre,"total_lider":lider.total_votantes})
        except IntegrityError:
            s.rollback(); return Resultado(False, f"⚠️ Cédula {cedula} duplicada. Rollback.")
        except Exception as e:
            s.rollback(); return Resultado(False, f"❌ Error: {str(e)}")


# ── Consultas ─────────────────────────────────────────────────────

def consolidado_por_lider():
    with SessionLocal() as s:
        lideres = s.execute(select(Lider).order_by(Lider.total_votantes.desc())).scalars().all()
        return [{"lider_id":l.id,"lider_nombre":l.nombre,"lider_estado":l.estado,
                 "total_votantes":l.total_votantes,
                 "votantes":[{"cedula":v.cedula,"nombre":v.nombre,"fecha_registro":v.fecha_registro}
                              for v in s.execute(select(Votante).where(Votante.lider_id==l.id)
                                        .order_by(Votante.fecha_registro.desc())).scalars().all()]}
                for l in lideres]

def total_votantes_registrados():
    with SessionLocal() as s:
        return s.execute(select(func.count(Votante.id))).scalar() or 0

def buscar_cedula(cedula):
    cedula = cedula.strip()
    with SessionLocal() as s:
        ctrl  = s.get(ControlCedula, cedula)
        votan = s.execute(select(Votante).where(Votante.cedula==cedula)).scalar_one_or_none()
        return {
            "cedula": cedula,
            "control": {"existe":ctrl is not None,"estado":ctrl.estado if ctrl else "NO REGISTRADA",
                        "fecha_inhabilitacion":ctrl.fecha_inhabilitacion if ctrl else None},
            "votante": {"registrado":votan is not None,"nombre":votan.nombre if votan else None,
                        "lider_id":votan.lider_id if votan else None,
                        "fecha_registro":votan.fecha_registro if votan else None},
        }


# ── Carga masiva CSV / Excel ──────────────────────────────────────

class ResultadoCargaMasiva:
    def __init__(self):
        self.exitosos = []; self.fallidos = []; self.total = 0
    @property
    def ok(self): return len(self.exitosos) > 0
    @property
    def resumen(self):
        return f"{len(self.exitosos)} registrados, {len(self.fallidos)} errores de {self.total} filas."

def validar_dataframe_csv(df):
    df.columns = [c.strip().lower() for c in df.columns]
    alias_c = {"cedula","documento","cc","id_votante"}
    alias_n = {"nombre","nombre_votante","name","nombres","nombre completo"}
    alias_l = {"lider","lider_nombre","nombre_lider","leader"}
    cc = next((c for c in df.columns if c in alias_c), None)
    cn = next((c for c in df.columns if c in alias_n), None)
    cl = next((c for c in df.columns if c in alias_l), None)
    if not cc: return False, f"Sin columna cédula. Esperadas: {alias_c}"
    if not cn: return False, f"Sin columna nombre. Esperadas: {alias_n}"
    if not cl: return False, f"Sin columna líder. Esperadas: {alias_l}"
    return True, f"{cc}|{cn}|{cl}"

def extraer_nombre_lider(source_name):
    s = source_name.strip()
    s = re.sub(r"\.xlsx.*","",s,flags=re.IGNORECASE)
    s = re.sub(r"^\d+(\.\d+)*\s+","",s)
    s = re.sub(r"\s*-\s*ZONA\s*\d+\b","",s,flags=re.IGNORECASE)
    s = re.sub(r"\s*-?\s*(COMPLETO\s+VERIFICADO)\s*$","",s,flags=re.IGNORECASE)
    s = re.sub(r"\b\d{4}\b","",s)
    s = re.sub(r"\s*\([^)]*\)\s*"," ",s)
    s = re.sub(r"\.+","",s).strip().strip("-").strip()
    return re.sub(r"\s+"," ",s).title()

def cargar_votantes_csv(df, modo_lider="nombre"):
    resultado = ResultadoCargaMasiva()
    df.columns = [c.strip().lower() for c in df.columns]
    alias_c = {"cedula","documento","cc","id_votante"}
    alias_n = {"nombre","nombre_votante","name","nombres","nombre completo"}
    alias_l = {"lider","lider_nombre","nombre_lider","leader"}
    alias_s = {"source.name","source_name","fuente","archivo"}
    col_c = next((c for c in df.columns if c in alias_c), None)
    col_n = next((c for c in df.columns if c in alias_n), None)
    col_l = next((c for c in df.columns if c in alias_l), None)
    col_s = next((c for c in df.columns if c in alias_s), None)
    cache = {}
    with SessionLocal() as s:
        for l in s.execute(select(Lider)).scalars().all():
            cache[l.nombre.strip().lower()] = l.id
            cache[str(l.id)] = l.id
    for idx, row in df.iterrows():
        fila = idx + 2; resultado.total += 1
        ced  = str(row[col_c]).strip() if col_c else ""
        nom  = str(row[col_n]).strip() if col_n else ""
        lid  = str(row[col_l]).strip() if col_l else ""
        if col_s:
            sv = str(row[col_s]).strip()
            if sv and sv.lower() not in ("nan","none",""):
                lid = extraer_nombre_lider(sv)
        if not ced or ced.lower() in ("nan","none",""):
            resultado.fallidos.append({"fila":fila,"cedula":ced,"nombre":nom,"lider":lid,"error":"Cédula vacía."}); continue
        if not nom or nom.lower() in ("nan","none",""):
            resultado.fallidos.append({"fila":fila,"cedula":ced,"nombre":nom,"lider":lid,"error":"Nombre vacío."}); continue
        if modo_lider == "id":
            try: lid_id = int(lid)
            except: resultado.fallidos.append({"fila":fila,"cedula":ced,"nombre":nom,"lider":lid,"error":f"ID no numérico: {lid}"}); continue
        else:
            lid_id = cache.get(lid.lower())
            if lid_id is None:
                resultado.fallidos.append({"fila":fila,"cedula":ced,"nombre":nom,"lider":lid,"error":f"Líder '{lid}' no encontrado."}); continue
        r = registrar_votante(ced, nom, lid_id)
        if r.ok: resultado.exitosos.append({"fila":fila,"cedula":ced,"nombre":nom,"lider":lid})
        else: resultado.fallidos.append({"fila":fila,"cedula":ced,"nombre":nom,"lider":lid,"error":r.mensaje})
    return resultado

def generar_csv_plantilla():
    return ("cedula,nombre,lider\n1090100001,Ana Maria Torres,Pedro Ramirez\n"
            "1090100002,Luis Gomez Perez,Pedro Ramirez\n1090100003,Sofia Martinez,Carlos Mendez\n"
            "1090100004,Jorge Rodriguez,Carlos Mendez\n1090100005,Valentina Cruz,Ana Torres\n")
