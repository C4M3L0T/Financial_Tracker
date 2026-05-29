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
    # TABLA CORREGIDA: Se añade monto_total para compatibilidad con planeacion.py
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
        fecha_quincena1 = f"{str_fecha_base}-15"
        fecha_quincena2 = f"{str_fecha_base}-28"
        cursor.execute("INSERT INTO ingresos (desc, monto, fuente, fecha) VALUES (?,?,?,?)",
                       ("Quincena 1", 12500.00, "Salario", fecha_quincena1))
        cursor.execute("INSERT INTO ingresos (desc, monto, fuente, fecha) VALUES (?,?,?,?)",
                       ("Quincena 2", 12500.00, "Salario", fecha_quincena2))
        
        if random.random() > 0.4:
            monto_freelance = round(random.uniform(3000, 8000), 2)
            dia_rnd = random.randint(1, 28)
            cursor.execute("INSERT INTO ingresos (desc, monto, fuente, fecha) VALUES (?,?,?,?)",
                           (f"Proyecto Dev", monto_freelance, "Freelance", f"{str_fecha_base}-{dia_rnd:02d}"))

        # 2. GASTOS
        factor_inflacion = 1.0 + (i * 0.02) 
        cursor.execute("INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible) VALUES (?,?,?,?,?,?)",
                       ("Renta Departamento", 8500.00, "Vivienda", f"{str_fecha_base}-05", 1, 0))
        
        num_transacciones = random.randint(10, 15)
        for _ in range(num_transacciones):
            cat_rnd = random.choice(CATEGORIAS_GASTOS[1:])
            monto_base = random.uniform(150, 1200)
            monto_final = round(monto_base * factor_inflacion, 2)
            dia_rnd = random.randint(1, 28)
            
            es_deducible = 1 if cat_rnd in ["Salud", "Transporte"] and random.random() > 0.5 else 0
            con_factura = 1 if es_deducible == 1 else random.choice([0, 1])
            
            cursor.execute("INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible) VALUES (?,?,?,?,?,?)",
                           (f"Compra {cat_rnd}", monto_final, cat_rnd, f"{str_fecha_base}-{dia_rnd:02d}", con_factura, es_deducible))

    # 3. PASIVOS / MSI CORREGIDOS (Insertando monto_total coherente)
    cursor.execute("""
        INSERT INTO deudas_msi (desc, monto_total, mensualidad, meses_totales, meses_pagados) 
        VALUES (?,?,?,?,?)
    """, ("Laptop ThinkPad", 18000.00, 1500.00, 12, 8))
    
    cursor.execute("""
        INSERT INTO deudas_msi (desc, monto_total, mensualidad, meses_totales, meses_pagados) 
        VALUES (?,?,?,?,?)
    """, ("Monitor Ultrawide", 4800.00, 800.00, 6, 1))

def main():
    print("Reconstruyendo base de datos con tipado compatible...")
    conn = sqlite3.connect("data.db")
    cursor = conn.cursor()
    
    crear_tablas(cursor)
    generar_datos_historicos(cursor)
    
    conn.commit()
    conn.close()
    print("¡Base de datos 'data.db' sincronizada exitosamente!")

if __name__ == "__main__":
    main()
