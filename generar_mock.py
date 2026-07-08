import database
import random
from datetime import datetime, timedelta

# Se adaptaron las categorías al perfil de estudiante
CATEGORIAS_GASTOS = ["Vivienda", "Comida", "Transporte", "Educación", "Ahorros", "Salud", "Recreación", "Suscripciones", "Otros"]
FUENTES_INGRESO = ["Salario", "Freelance", "Rendimientos", "Ventas", "Otros"]

def limpiar_tablas(cursor):
    # El esquema lo garantiza database.init_db(); aquí solo se vacían las
    # tablas que este mock repuebla (TRUNCATE reinicia los AUTO_INCREMENT)
    cursor.execute("TRUNCATE TABLE ingresos")
    cursor.execute("TRUNCATE TABLE gastos")
    cursor.execute("TRUNCATE TABLE deudas_msi")

def generar_datos_historicos(cursor):
    # Usando la fecha de hoy como referencia
    fecha_actual = datetime(2026, 5, 30) 
    
    for i in range(12):
        mes_pivote = fecha_actual - timedelta(days=30 * (11 - i))
        str_fecha_base = mes_pivote.strftime("%Y-%m")
        
        # 1. INGRESOS
        # Trabajo 1: $15,000 al mes (dividido en dos quincenas de $7,500)
        cursor.execute("INSERT INTO ingresos (`desc`, monto, fuente, fecha) VALUES (?,?,?,?)",
                       ("Quincena 1 (Principal)", 7500.00, "Salario", f"{str_fecha_base}-15"))
        cursor.execute("INSERT INTO ingresos (`desc`, monto, fuente, fecha) VALUES (?,?,?,?)",
                       ("Quincena 2 (Principal)", 7500.00, "Salario", f"{str_fecha_base}-28"))
        
        # Trabajo 2: $800 a la semana (4 semanas simuladas por mes en días específicos)
        dias_semana = [7, 14, 21, 28]
        for dia in dias_semana:
            cursor.execute("INSERT INTO ingresos (`desc`, monto, fuente, fecha) VALUES (?,?,?,?)",
                           ("Pago Semanal (Secundario)", 800.00, "Salario", f"{str_fecha_base}-{dia:02d}"))

        # 2. GASTOS
        # Objetivo mensual promedio de $8,000. 
        # Definimos un gasto fijo base (ej. renta/cuota escolar de $3,500)
        gasto_fijo = 3500.00
        cursor.execute("INSERT INTO gastos (`desc`, monto, categoria, fecha, con_factura, es_deducible) VALUES (?,?,?,?,?,?)",
                       ("Gasto Fijo (Renta/Escuela)", gasto_fijo, "Vivienda", f"{str_fecha_base}-05", 0, 0))
        
        # El resto de los gastos oscilará para que el total del mes promedie $8,000
        # Media de 4500, desviación de 350 para simular meses donde gastas un poco más o menos
        gasto_variable_objetivo = random.gauss(4500, 350) 
        gasto_acumulado = 0
        
        while gasto_acumulado < gasto_variable_objetivo:
            cat_rnd = random.choice(["Comida", "Transporte", "Educación", "Recreación", "Suscripciones"])
            monto_transaccion = round(random.uniform(80, 500), 2)
            
            # Ajuste para cuadrar exactamente con el objetivo del mes sin pasarnos
            if gasto_acumulado + monto_transaccion > gasto_variable_objetivo:
                monto_transaccion = round(gasto_variable_objetivo - gasto_acumulado, 2)
                
            dia_rnd = random.randint(1, 28)
            es_deducible = 1 if cat_rnd == "Educación" else 0
            
            cursor.execute("INSERT INTO gastos (`desc`, monto, categoria, fecha, con_factura, es_deducible) VALUES (?,?,?,?,?,?)",
                           (f"Gasto en {cat_rnd}", monto_transaccion, cat_rnd, f"{str_fecha_base}-{dia_rnd:02d}", es_deducible, es_deducible))
            
            gasto_acumulado += monto_transaccion

    # 3. PASIVOS / MSI
    # Un gasto común y realista para un estudiante que trabaja (una computadora a plazos)
    cursor.execute("""
        INSERT INTO deudas_msi (`desc`, monto_total, mensualidad, meses_totales, meses_pagados) 
        VALUES (?,?,?,?,?)
    """, ("Laptop Universidad", 12000.00, 1000.00, 12, 5))

def main():
    print("Reconstruyendo base de datos con perfil de estudiante (Ingreso: ~$18.2k, Gasto: ~$8k)...")
    database.init_db()
    conn = database.conectar()
    cursor = conn.cursor()

    limpiar_tablas(cursor)
    generar_datos_historicos(cursor)

    conn.commit()
    conn.close()
    print("¡Base de datos sincronizada exitosamente con tu escenario realista!")

if __name__ == "__main__":
    main()