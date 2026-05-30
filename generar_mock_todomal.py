import sqlite3
import random
from datetime import datetime, timedelta

CATEGORIAS_GASTOS = ["Vivienda", "Comida", "Transporte", "Impuestos", "Ahorros", "Salud", "Recreación", "Suscripciones", "Otros"]
FUENTES_INGRESO = ["Salario", "Freelance", "Rendimientos", "Ventas", "Otros"]

def crear_tablas(cursor):
    cursor.execute("DROP TABLE IF EXISTS ingresos")
    cursor.execute("DROP TABLE IF EXISTS gastos")
    cursor.execute("DROP TABLE IF EXISTS deudas_msi")

    cursor.execute("""
        CREATE TABLE ingresos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, monto REAL, fuente TEXT, fecha TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, monto REAL, categoria TEXT, 
            fecha TEXT, con_factura INTEGER, es_deducible INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE deudas_msi (
            id INTEGER PRIMARY KEY AUTOINCREMENT, desc TEXT, monto_total REAL, mensualidad REAL, 
            meses_totales INTEGER, meses_pagados INTEGER
        )
    """)

def generar_datos_historicos(cursor):
    fecha_actual = datetime(2026, 5, 28)
    
    for i in range(12):
        mes_pivote = fecha_actual - timedelta(days=30 * (11 - i))
        str_fecha_base = mes_pivote.strftime("%Y-%m")
        
        # 1. INGRESOS
        # Recorte salarial a partir del mes 8 (simulando cambio de trabajo o reducción de jornada)
        salario_quincenal = 12500.00 if i < 8 else 9500.00
        
        fecha_quincena1 = f"{str_fecha_base}-15"
        fecha_quincena2 = f"{str_fecha_base}-28"
        cursor.execute("INSERT INTO ingresos (desc, monto, fuente, fecha) VALUES (?,?,?,?)",
                       ("Quincena 1", salario_quincenal, "Salario", fecha_quincena1))
        cursor.execute("INSERT INTO ingresos (desc, monto, fuente, fecha) VALUES (?,?,?,?)",
                       ("Quincena 2", salario_quincenal, "Salario", fecha_quincena2))
        
        # Caída del Freelance: menos probabilidad y menos ingresos con el paso del tiempo
        probabilidad_freelance = max(0.1, 0.6 - (i * 0.05)) 
        if random.random() < probabilidad_freelance:
            monto_freelance = max(1500.00, round(random.uniform(4000, 7000) - (i * 500), 2))
            dia_rnd = random.randint(1, 28)
            cursor.execute("INSERT INTO ingresos (desc, monto, fuente, fecha) VALUES (?,?,?,?)",
                           ("Proyecto Dev", monto_freelance, "Freelance", f"{str_fecha_base}-{dia_rnd:02d}"))

        # 2. GASTOS
        # Inflación de estilo de vida agresiva: los gastos aumentan un 6% cada mes
        factor_inflacion_estilo_vida = 1.0 + (i * 0.06) 
        
        cursor.execute("INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible) VALUES (?,?,?,?,?,?)",
                       ("Renta Departamento", 8500.00, "Vivienda", f"{str_fecha_base}-05", 1, 0))
        
        # Gastos hormiga y descontrol: la cantidad de transacciones aumenta mes a mes
        num_transacciones = random.randint(10, 15) + int(i * 1.5)
        
        for _ in range(num_transacciones):
            cat_rnd = random.choice(CATEGORIAS_GASTOS[1:])
            monto_base = random.uniform(200, 1500)
            monto_final = round(monto_base * factor_inflacion_estilo_vida, 2)
            dia_rnd = random.randint(1, 28)
            
            es_deducible = 1 if cat_rnd in ["Salud", "Transporte"] and random.random() > 0.5 else 0
            con_factura = 1 if es_deducible == 1 else random.choice([0, 1])
            
            cursor.execute("INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible) VALUES (?,?,?,?,?,?)",
                           (f"Compra {cat_rnd}", monto_final, cat_rnd, f"{str_fecha_base}-{dia_rnd:02d}", con_factura, es_deducible))

        # Evento catastrófico en el mes 10 (Rompe la tendencia lineal estrepitosamente)
        if i == 10:
            cursor.execute("INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible) VALUES (?,?,?,?,?,?)",
                           ("Reparación Transmisión Auto", 18500.00, "Transporte", f"{str_fecha_base}-12", 1, 1))

    # 3. PASIVOS / MSI
    # Agregamos deuda agresiva que refleja el descontrol
    cursor.execute("""
        INSERT INTO deudas_msi (desc, monto_total, mensualidad, meses_totales, meses_pagados) 
        VALUES (?,?,?,?,?)
    """, ("Laptop ThinkPad", 18000.00, 1500.00, 12, 8))
    
    cursor.execute("""
        INSERT INTO deudas_msi (desc, monto_total, mensualidad, meses_totales, meses_pagados) 
        VALUES (?,?,?,?,?)
    """, ("Monitor Ultrawide", 4800.00, 800.00, 6, 1))

    cursor.execute("""
        INSERT INTO deudas_msi (desc, monto_total, mensualidad, meses_totales, meses_pagados) 
        VALUES (?,?,?,?,?)
    """, ("Viaje a Cancún (Impulsivo)", 36000.00, 2000.00, 18, 2))

def main():
    print("Reconstruyendo base de datos con tendencia de desaceleración (dW/dT desfavorable)...")
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    
    crear_tablas(cursor)
    generar_datos_historicos(cursor)
    
    conn.commit()
    conn.close()
    print("¡Base de datos 'data.db' sincronizada exitosamente con el escenario catastrófico!")

if __name__ == "__main__":
    main()