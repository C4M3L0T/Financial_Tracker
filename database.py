import sqlite3

DB_NAME = "data.db"

def init_db():
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
