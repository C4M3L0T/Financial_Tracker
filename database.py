"""Capa de datos: conexión a la MariaDB compartida + esquema único.

La base vive en un servidor MariaDB (normalmente la máquina siempre encendida,
ver servidor/README.md); la app de escritorio en cualquier computadora y el
bot de Telegram se conectan a ella por red.

Los datos de conexión se leen de config.py (gitignorado, ver config.example.py):
    DB_HOST = "192.168.1.50"   # IP del servidor (127.0.0.1 en el propio servidor)
    DB_PORT = 3306
    DB_USER = "arch"
    DB_PASSWORD = "..."
    DB_NAME = "arch_tracker"

Los respaldos ya no se hacen aquí: son dumps del servidor (servidor/respaldo.sh)
que cada cliente puede jalar por red (servidor/jalar_respaldo.sh).
"""
import pymysql
from pymysql.err import IntegrityError, MySQLError  # noqa: F401 — los tabs los usan como database.IntegrityError
from datetime import date

try:
    import config as _config
except ImportError:
    _config = None


def _cfg(nombre, default):
    return getattr(_config, nombre, default) if _config is not None else default


DB_HOST = _cfg("DB_HOST", "127.0.0.1")
DB_PORT = _cfg("DB_PORT", 3306)
DB_USER = _cfg("DB_USER", "arch")
DB_PASSWORD = _cfg("DB_PASSWORD", "arch")
DB_NAME = _cfg("DB_NAME", "arch_tracker")

# "Ahorros" es transferencia de riqueza, no consumo: la analítica de gasto
# (VaR, runway, pronóstico, PMC, flujos) la excluye. La conciliación de
# Auditoría NO la excluye porque trabaja base caja (el ahorro sí mueve liquidez).
CATEGORIA_AHORRO = "Ahorros"

# Regla 50/30/20: qué categorías son necesidad; el resto (menos Ahorros) son
# deseos, y el ahorro es el residuo del ingreso. Mantener en sincronía con
# CATEGORIAS_GASTOS de tabs/tesoreria.py.
CATEGORIAS_NECESIDAD = ("Vivienda", "Comida", "Transporte", "Salud",
                        "Servicios", "Seguros", "Impuestos", "Deuda")


class _Cursor:
    """El SQL del proyecto usa placeholders '?' (herencia de sqlite3); PyMySQL
    usa '%s'. Este proxy traduce, y conserva la semántica de sqlite3 de que
    execute() devuelve el propio cursor (hay llamadas .execute(...).fetchone()
    encadenadas). Ningún SQL del proyecto contiene '?' o '%' literales."""

    def __init__(self, cursor):
        self._c = cursor

    def execute(self, sql, params=()):
        self._c.execute(sql.replace("?", "%s"), params or None)
        return self

    def executemany(self, sql, seq_params):
        self._c.executemany(sql.replace("?", "%s"), seq_params)
        return self

    def fetchone(self):
        return self._c.fetchone()

    def fetchall(self):
        return self._c.fetchall()

    def __iter__(self):
        return iter(self._c)

    @property
    def lastrowid(self):
        return self._c.lastrowid

    @property
    def rowcount(self):
        return self._c.rowcount


class _Conexion:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _Cursor(self._conn.cursor())

    def execute(self, sql, params=()):
        return self.cursor().execute(sql, params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def conectar():
    """Única puerta de acceso a la base. Patrón del proyecto: una conexión
    corta por operación (abrir → consultar/escribir → commit → cerrar)."""
    return _Conexion(pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset="utf8mb4", connect_timeout=5))


def obtener_saldos_cuentas():
    """Única fuente de saldos derivados. Devuelve (id, nombre, tipo, tasa_anual, saldo)
    donde saldo = inicial + Σingresos − Σgastos + Σtransf. recibidas − Σenviadas."""
    conn = conectar()
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
    conn = conectar()
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
    conn = conectar()
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
                cursor.execute("INSERT INTO ingresos (`desc`, monto, fuente, fecha, cuenta_id) VALUES (?,?,?,?,?)",
                               (desc, monto, cat, fecha_str, cuenta_id))
            else:
                cursor.execute("""INSERT INTO gastos (`desc`, monto, categoria, fecha, con_factura, es_deducible, cuenta_id)
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


def _columnas(cursor, tabla):
    """Equivalente MariaDB del PRAGMA table_info: nombres de columna de una tabla."""
    cursor.execute("""SELECT COLUMN_NAME FROM information_schema.COLUMNS
                      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?""", (tabla,))
    return [f[0] for f in cursor.fetchall()]


def init_db():
    conn = conectar()
    cursor = conn.cursor()

    # Módulo de Agenda: Eventos (con hora) y Tareas (checkbox, sin hora)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agenda (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tarea TEXT, fecha TEXT, hora TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tareas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            descripcion TEXT,
            fecha TEXT,
            completada INT DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Módulo de Habit Game: Hábitos personalizados (recurrentes por día de semana)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habitos_custom (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre TEXT,
            dias_semana TEXT,
            categoria TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS habitos_custom_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            habito_id INT,
            fecha VARCHAR(10),
            UNIQUE (habito_id, fecha)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Módulo de Habit Game: Fuerza (Push/Pull/Legs/Upper/Lower) y Natación
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entrenamiento_dias (
            dia_semana VARCHAR(15) PRIMARY KEY,
            dia_tipo TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
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
            id INT AUTO_INCREMENT PRIMARY KEY,
            dia_tipo TEXT,
            nombre TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entrenamiento_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ejercicio_id INT,
            semana VARCHAR(10),
            fecha TEXT,
            UNIQUE (ejercicio_id, semana)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS natacion_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            semana TEXT,
            fecha TEXT,
            distancia_m DOUBLE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS natacion_config (
            id INT PRIMARY KEY CHECK (id = 1),
            meta_sesiones INT NOT NULL DEFAULT 3
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("INSERT IGNORE INTO natacion_config (id, meta_sesiones) VALUES (1, 3)")

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
    # `desc` va con backticks: es palabra reservada en MariaDB (ORDER BY ... DESC)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingresos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            `desc` TEXT, monto DOUBLE, fuente TEXT, fecha TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gastos (
            id INT AUTO_INCREMENT PRIMARY KEY,
            `desc` TEXT, monto DOUBLE, categoria TEXT, fecha TEXT,
            con_factura INT, es_deducible INT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Cuentas reales (banco/efectivo/crédito/inversión) para saldos y conciliación
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cuentas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(100) UNIQUE,
            tipo TEXT,
            saldo_inicial DOUBLE DEFAULT 0,
            fecha_inicial TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Transferencias entre cuentas (p.ej. pago de tarjeta de crédito):
    # mueven saldo sin ser ingreso ni gasto — no tocan los flujos de Tesorería
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transferencias (
            id INT AUTO_INCREMENT PRIMARY KEY,
            cuenta_origen INT,
            cuenta_destino INT,
            monto DOUBLE,
            fecha TEXT,
            descripcion TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Metas de ahorro: el progreso se mide con el saldo de la cuenta vinculada
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre TEXT,
            monto_objetivo DOUBLE,
            cuenta_id INT,
            fecha_limite TEXT,
            activo INT DEFAULT 1
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Plantillas de movimientos recurrentes (quincenas, renta, suscripciones)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recurrentes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tipo TEXT,
            descripcion TEXT,
            monto DOUBLE,
            categoria TEXT,
            dia_mes INT,
            cuenta_id INT,
            activo INT DEFAULT 1,
            ultima_generacion TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Migración: clasificación SAT del gasto deducible (Art. 151 LISR / decreto colegiaturas)
    columnas_gastos = _columnas(cursor, "gastos")
    if "tipo_deduccion" not in columnas_gastos:
        cursor.execute("ALTER TABLE gastos ADD COLUMN tipo_deduccion TEXT")
    if "cuenta_id" not in columnas_gastos:
        cursor.execute("ALTER TABLE gastos ADD COLUMN cuenta_id INT")

    if "cuenta_id" not in _columnas(cursor, "ingresos"):
        cursor.execute("ALTER TABLE ingresos ADD COLUMN cuenta_id INT")

    # Migración: CAT/tasa anual de las tarjetas de crédito (para el plan de pago)
    if "tasa_anual" not in _columnas(cursor, "cuentas"):
        cursor.execute("ALTER TABLE cuentas ADD COLUMN tasa_anual DOUBLE DEFAULT 0")

    # Módulo de Planeación (Presupuestos y Deudas/MSI)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presupuestos (
            categoria VARCHAR(50) PRIMARY KEY,
            limite DOUBLE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deudas_msi (
            id INT AUTO_INCREMENT PRIMARY KEY,
            `desc` TEXT, monto_total DOUBLE, mensualidad DOUBLE,
            meses_totales INT, meses_pagados INT, fecha_inicio TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # Migración: tasa de interés anual (0 = MSI puro; >0 = crédito con amortización francesa)
    if "tasa_interes" not in _columnas(cursor, "deudas_msi"):
        cursor.execute("ALTER TABLE deudas_msi ADD COLUMN tasa_interes DOUBLE DEFAULT 0")

    # Módulo de Balance General
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS balance_general (
            fecha VARCHAR(7) PRIMARY KEY,  -- Formato YYYY-MM
            activos_liquidos DOUBLE,       -- Efectivo, Débito, Fondos
            activos_fijos DOUBLE,          -- Auto, Afore, PPR, Bienes
            pasivos_corto DOUBLE,          -- Tarjetas de crédito, deudas inmediatas
            pasivos_largo DOUBLE           -- Crédito automotriz, hipoteca
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()
    conn.close()
