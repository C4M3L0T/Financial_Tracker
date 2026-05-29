import sqlite3

DB_NAME = "data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Módulo de Hábitos y Agenda
    cursor.execute("CREATE TABLE IF NOT EXISTS habitos_lista (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT, categoria TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS habitos_log (habito_id INTEGER, fecha TEXT, PRIMARY KEY (habito_id, fecha))")
    cursor.execute("CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY AUTOINCREMENT, tarea TEXT, fecha TEXT, hora TEXT)")
    
    # Módulo de Tesorería (Ingresos y Egresos con SAT)
    cursor.execute("CREATE TABLE IF NOT EXISTS ingresos (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, monto REAL, fuente TEXT, fecha TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS gastos (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, monto REAL, categoria TEXT, fecha TEXT, con_factura INTEGER, es_deducible INTEGER)")
    
    # Módulo de Planeación (Presupuestos y Deudas/MSI)
    cursor.execute("CREATE TABLE IF NOT EXISTS presupuestos (categoria TEXT PRIMARY KEY, limite REAL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS deudas_msi (id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, monto_total REAL, mensualidad REAL, meses_totales INTEGER, meses_pagados INTEGER, fecha_inicio TEXT)")
    
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
