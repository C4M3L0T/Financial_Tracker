import sqlite3
import os
import glob
from datetime import date

DB_NAME = "data.db"
DIR_RESPALDOS = "backups"
MAX_RESPALDOS = 30

# "Ahorros" es transferencia de riqueza, no consumo: la analítica de gasto
# (VaR, runway, pronóstico, PMC, flujos) la excluye. La conciliación de
# Auditoría NO la excluye porque trabaja base caja (el ahorro sí mueve liquidez).
CATEGORIA_AHORRO = "Ahorros"

# Regla 50/30/20: qué categorías son necesidad; el resto (menos Ahorros) son
# deseos, y el ahorro es el residuo del ingreso. Mantener en sincronía con
# CATEGORIAS_GASTOS de tabs/tesoreria.py.
CATEGORIAS_NECESIDAD = ("Vivienda", "Comida", "Transporte", "Salud",
                        "Servicios", "Seguros", "Impuestos", "Deuda")


def respaldar_db():
    """Un respaldo por día en backups/, con la API de backup de SQLite
    (segura aunque haya conexiones escribiendo). Conserva los 30 más recientes."""
    if not os.path.exists(DB_NAME):
        return
    os.makedirs(DIR_RESPALDOS, exist_ok=True)
    destino = os.path.join(DIR_RESPALDOS, f"data_{date.today().isoformat()}.db")
    if os.path.exists(destino):
        return
    origen = sqlite3.connect(DB_NAME)
    copia = sqlite3.connect(destino)
    with copia:
        origen.backup(copia)
    copia.close()
    origen.close()

    respaldos = sorted(glob.glob(os.path.join(DIR_RESPALDOS, "data_*.db")))
    for viejo in respaldos[:-MAX_RESPALDOS]:
        os.remove(viejo)


def obtener_saldos_cuentas():
    """Única fuente de saldos derivados. Devuelve (id, nombre, tipo, tasa_anual, saldo)
    donde saldo = inicial + Σingresos − Σgastos + Σtransf. recibidas − Σenviadas."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.nombre, c.tipo, COALESCE(c.tasa_anual, 0), c.saldo_inicial
             + COALESCE((SELECT SUM(i.monto) FROM ingresos i WHERE i.cuenta_id = c.id), 0)
             - COALESCE((SELECT SUM(g.monto) FROM gastos g WHERE g.cuenta_id = c.id), 0)
             + COALESCE((SELECT SUM(t.monto) FROM transferencias t WHERE t.cuenta_destino = c.id), 0)
             - COALESCE((SELECT SUM(t.monto) FROM transferencias t WHERE t.cuenta_origen = c.id), 0)
        FROM cuentas c ORDER BY c.nombre
    """)
    filas = cursor.fetchall()
    conn.close()
    return filas


def obtener_metas_con_progreso():
    """(id, nombre, objetivo, cuenta_nombre, saldo, aporte_mensual_reciente, fecha_limite)
    por meta activa. El aporte reciente = flujo neto hacia la cuenta en los
    últimos 90 días ÷ 3, para proyectar la fecha de cumplimiento."""
    from datetime import timedelta
    saldos = {cid: (nombre, saldo) for cid, nombre, _t, _ta, saldo in obtener_saldos_cuentas()}
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, monto_objetivo, cuenta_id, fecha_limite FROM metas WHERE activo = 1")
    metas = cursor.fetchall()
    hace_90 = (date.today() - timedelta(days=90)).isoformat()

    resultado = []
    for mid, nombre, objetivo, cuenta_id, fecha_limite in metas:
        cta_nombre, saldo = saldos.get(cuenta_id, ("(cuenta eliminada)", 0.0))
        cursor.execute("SELECT COALESCE(SUM(monto),0) FROM ingresos WHERE cuenta_id=? AND fecha>=?", (cuenta_id, hace_90))
        entradas = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE cuenta_id=? AND fecha>=?", (cuenta_id, hace_90))
        salidas = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(monto),0) FROM transferencias WHERE cuenta_destino=? AND fecha>=?", (cuenta_id, hace_90))
        transf_in = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(monto),0) FROM transferencias WHERE cuenta_origen=? AND fecha>=?", (cuenta_id, hace_90))
        transf_out = cursor.fetchone()[0]
        aporte_mensual = (entradas + transf_in - salidas - transf_out) / 3.0
        resultado.append((mid, nombre, objetivo, cta_nombre, saldo, aporte_mensual, fecha_limite))
    conn.close()
    return resultado


def generar_recurrentes():
    """Materializa las ocurrencias vencidas de los movimientos recurrentes.
    Idempotente: cada ocurrencia se genera una sola vez (ultima_generacion).
    Devuelve las descripciones generadas, para poder notificarlas."""
    import calendar
    hoy = date.today()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, tipo, descripcion, monto, categoria, dia_mes, cuenta_id,
               COALESCE(ultima_generacion, '')
        FROM recurrentes WHERE activo = 1
    """)
    generados = []
    for rid, tipo, desc, monto, cat, dia, cuenta_id, ultima in cursor.fetchall():
        if ultima:
            anio, mes, _ = map(int, ultima.split("-"))
            mes += 1
            if mes > 12:
                mes, anio = 1, anio + 1
        else:
            # Plantilla nueva: arranca en el mes actual (genera la ocurrencia
            # de este mes si su día ya pasó — el usuario la está poniendo al día)
            anio, mes = hoy.year, hoy.month

        while True:
            dia_real = min(dia, calendar.monthrange(anio, mes)[1])
            ocurrencia = date(anio, mes, dia_real)
            if ocurrencia > hoy:
                break
            fecha_str = ocurrencia.isoformat()
            if tipo == "ingreso":
                cursor.execute("INSERT INTO ingresos (desc, monto, fuente, fecha, cuenta_id) VALUES (?,?,?,?,?)",
                               (desc, monto, cat, fecha_str, cuenta_id))
            else:
                cursor.execute("""INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible, cuenta_id)
                                  VALUES (?,?,?,?,0,0,?)""",
                               (desc, monto, cat, fecha_str, cuenta_id))
            cursor.execute("UPDATE recurrentes SET ultima_generacion=? WHERE id=?", (fecha_str, rid))
            generados.append(f"{'📈' if tipo == 'ingreso' else '📉'} {desc}: ${monto:,.2f} ({fecha_str})")
            mes += 1
            if mes > 12:
                mes, anio = 1, anio + 1

    conn.commit()
    conn.close()
    return generados


def init_db():
    respaldar_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Módulo de Agenda: Eventos (con hora) y Tareas (checkbox, sin hora)
    cursor.execute("CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY AUTOINCREMENT, tarea TEXT, fecha TEXT, hora TEXT)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT,
            fecha TEXT,
            completada INTEGER DEFAULT 0
        )
    """)

    # Módulo de Habit Game: Hábitos personalizados (recurrentes por día de semana)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habitos_custom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            dias_semana TEXT,
            categoria TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habitos_custom_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habito_id INTEGER,
            fecha TEXT,
            UNIQUE(habito_id, fecha)
        )
    """)

    # Módulo de Habit Game: Fuerza (Push/Pull/Legs/Upper/Lower) y Natación
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entrenamiento_dias (
            dia_semana TEXT PRIMARY KEY,
            dia_tipo TEXT
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM entrenamiento_dias")
    if cursor.fetchone()[0] == 0:
        asignacion_default = [
            ("Lunes", "Push"), ("Martes", "Pull"), ("Miércoles", "Legs"),
            ("Jueves", "Upper"), ("Viernes", "Lower"), ("Sábado", "Descanso"), ("Domingo", "Descanso"),
        ]
        cursor.executemany("INSERT INTO entrenamiento_dias (dia_semana, dia_tipo) VALUES (?, ?)", asignacion_default)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entrenamiento_ejercicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dia_tipo TEXT,
            nombre TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entrenamiento_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ejercicio_id INTEGER,
            semana TEXT,
            fecha TEXT,
            UNIQUE(ejercicio_id, semana)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS natacion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            semana TEXT,
            fecha TEXT,
            distancia_m REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS natacion_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            meta_sesiones INTEGER NOT NULL DEFAULT 3
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO natacion_config (id, meta_sesiones) VALUES (1, 3)")

    cursor.execute("SELECT COUNT(*) FROM entrenamiento_ejercicios")
    if cursor.fetchone()[0] == 0:
        ejercicios_default = [
            ("Push", "Press de banca"), ("Push", "Press militar"), ("Push", "Fondos en paralelas"),
            ("Push", "Elevaciones laterales"), ("Push", "Extensión de tríceps"),
            ("Pull", "Dominadas"), ("Pull", "Remo con barra"), ("Pull", "Jalón al pecho"),
            ("Pull", "Curl de bíceps"), ("Pull", "Face pull"),
            ("Legs", "Sentadilla"), ("Legs", "Peso muerto rumano"), ("Legs", "Prensa"),
            ("Legs", "Zancadas"), ("Legs", "Elevación de gemelos"),
            ("Upper", "Press inclinado"), ("Upper", "Remo en polea"), ("Upper", "Press Arnold"),
            ("Upper", "Curl martillo"), ("Upper", "Extensión de tríceps en polea"),
            ("Lower", "Sentadilla frontal"), ("Lower", "Hip thrust"), ("Lower", "Zancadas búlgaras"),
            ("Lower", "Curl femoral"), ("Lower", "Elevación de gemelos de pie"),
        ]
        cursor.executemany("INSERT INTO entrenamiento_ejercicios (dia_tipo, nombre) VALUES (?, ?)", ejercicios_default)

    # Módulo de Tesorería (Ingresos y Egresos con SAT)
    cursor.execute("CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, monto REAL, fuente TEXT, fecha TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, monto REAL, categoria TEXT, fecha TEXT, con_factura INTEGER, es_deducible INTEGER)")

    # Cuentas reales (banco/efectivo/crédito/inversión) para saldos y conciliación
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cuentas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            tipo TEXT,
            saldo_inicial REAL DEFAULT 0,
            fecha_inicial TEXT
        )
    """)

    # Transferencias entre cuentas (p.ej. pago de tarjeta de crédito):
    # mueven saldo sin ser ingreso ni gasto — no tocan los flujos de Tesorería
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transferencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cuenta_origen INTEGER,
            cuenta_destino INTEGER,
            monto REAL,
            fecha TEXT,
            descripcion TEXT
        )
    """)

    # Metas de ahorro: el progreso se mide con el saldo de la cuenta vinculada
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            monto_objetivo REAL,
            cuenta_id INTEGER,
            fecha_limite TEXT,
            activo INTEGER DEFAULT 1
        )
    """)

    # Plantillas de movimientos recurrentes (quincenas, renta, suscripciones)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurrentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            descripcion TEXT,
            monto REAL,
            categoria TEXT,
            dia_mes INTEGER,
            cuenta_id INTEGER,
            activo INTEGER DEFAULT 1,
            ultima_generacion TEXT
        )
    """)

    # Migración: clasificación SAT del gasto deducible (Art. 151 LISR / decreto colegiaturas)
    cursor.execute("PRAGMA table_info(gastos)")
    columnas_gastos = [c[1] for c in cursor.fetchall()]
    if "tipo_deduccion" not in columnas_gastos:
        cursor.execute("ALTER TABLE gastos ADD COLUMN tipo_deduccion TEXT")
    if "cuenta_id" not in columnas_gastos:
        cursor.execute("ALTER TABLE gastos ADD COLUMN cuenta_id INTEGER")

    cursor.execute("PRAGMA table_info(ingresos)")
    columnas_ingresos = [c[1] for c in cursor.fetchall()]
    if "cuenta_id" not in columnas_ingresos:
        cursor.execute("ALTER TABLE ingresos ADD COLUMN cuenta_id INTEGER")

    # Migración: CAT/tasa anual de las tarjetas de crédito (para el plan de pago)
    cursor.execute("PRAGMA table_info(cuentas)")
    columnas_cuentas = [c[1] for c in cursor.fetchall()]
    if "tasa_anual" not in columnas_cuentas:
        cursor.execute("ALTER TABLE cuentas ADD COLUMN tasa_anual REAL DEFAULT 0")

    # Módulo de Planeación (Presupuestos y Deudas/MSI)
    cursor.execute("CREATE TABLE IF NOT EXISTS presupuestos (categoria TEXT PRIMARY KEY, limite REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS deudas_msi (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, monto_total REAL, mensualidad REAL, meses_totales INTEGER, meses_pagados INTEGER, fecha_inicio TEXT)")

    # Migración: tasa de interés anual (0 = MSI puro; >0 = crédito con amortización francesa)
    cursor.execute("PRAGMA table_info(deudas_msi)")
    columnas_msi = [c[1] for c in cursor.fetchall()]
    if "tasa_interes" not in columnas_msi:
        cursor.execute("ALTER TABLE deudas_msi ADD COLUMN tasa_interes REAL DEFAULT 0")
    
    # Módulo de Balance General 
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS balance_general (
        fecha TEXT PRIMARY KEY, -- Formato YYYY-MM
        activos_liquidos REAL,  -- Efectivo, Débito, Fondos
        activos_fijos REAL,     -- Auto, Afore, PPR, Bienes
        pasivos_corto REAL,     -- Tarjetas de crédito, deudas inmediatas
        pasivos_largo REAL      -- Crédito automotriz, hipoteca
    )
""")
    conn.commit()
    conn.close()
