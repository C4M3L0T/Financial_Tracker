"""Migración única: copia todos los datos del data.db (SQLite) local a la
MariaDB compartida definida en config.py.

Uso:
    python migrar_a_mariadb.py            # se niega si el destino ya tiene datos
    python migrar_a_mariadb.py --forzar   # vacía las tablas destino y recopia

El data.db de origen NO se modifica — consérvalo como respaldo histórico.
Los ids se preservan tal cual (las referencias cuenta_id/habito_id/ejercicio_id
entre tablas dependen de ello).
"""
import os
import sqlite3
import sys

import database

ORIGEN = "data.db"

# tabla → columnas a copiar. Si el data.db viejo no tiene alguna columna
# (p.ej. deudas_msi.fecha_inicio en bases creadas por los mocks), se omite
# y en MariaDB queda NULL/default.
TABLAS = {
    "agenda": ["id", "tarea", "fecha", "hora"],
    "tareas": ["id", "descripcion", "fecha", "completada"],
    "habitos_custom": ["id", "nombre", "dias_semana", "categoria"],
    "habitos_custom_log": ["id", "habito_id", "fecha"],
    "entrenamiento_dias": ["dia_semana", "dia_tipo"],
    "entrenamiento_ejercicios": ["id", "dia_tipo", "nombre"],
    "entrenamiento_log": ["id", "ejercicio_id", "semana", "fecha"],
    "natacion_log": ["id", "semana", "fecha", "distancia_m"],
    "natacion_config": ["id", "meta_sesiones"],
    "cuentas": ["id", "nombre", "tipo", "saldo_inicial", "fecha_inicial", "tasa_anual"],
    "ingresos": ["id", "desc", "monto", "fuente", "fecha", "cuenta_id"],
    "gastos": ["id", "desc", "monto", "categoria", "fecha", "con_factura",
               "es_deducible", "tipo_deduccion", "cuenta_id"],
    "transferencias": ["id", "cuenta_origen", "cuenta_destino", "monto", "fecha", "descripcion"],
    "metas": ["id", "nombre", "monto_objetivo", "cuenta_id", "fecha_limite", "activo"],
    "recurrentes": ["id", "tipo", "descripcion", "monto", "categoria", "dia_mes",
                    "cuenta_id", "activo", "ultima_generacion"],
    "presupuestos": ["categoria", "limite"],
    "deudas_msi": ["id", "desc", "monto_total", "mensualidad", "meses_totales",
                   "meses_pagados", "fecha_inicio", "tasa_interes"],
    "balance_general": ["fecha", "activos_liquidos", "activos_fijos", "pasivos_corto", "pasivos_largo"],
    "bot_estado": ["clave", "valor"],
}

# Tablas cuyo contenido en destino indica "ya hay datos reales" (las demás
# pueden traer solo los seeds de init_db y no cuentan como datos del usuario)
TABLAS_GUARDIA = ("gastos", "ingresos", "cuentas", "deudas_msi", "balance_general")


def tablas_origen(cur_sqlite):
    cur_sqlite.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cur_sqlite.fetchall()}


def columnas_origen(cur_sqlite, tabla):
    cur_sqlite.execute(f'PRAGMA table_info("{tabla}")')
    return {row[1] for row in cur_sqlite.fetchall()}


def main():
    forzar = "--forzar" in sys.argv

    if not os.path.exists(ORIGEN):
        print(f"[!] No existe {ORIGEN} en este directorio; nada que migrar.")
        sys.exit(1)

    print(f"Destino: MariaDB {database.DB_USER}@{database.DB_HOST}:{database.DB_PORT}/{database.DB_NAME}")
    print("Creando/verificando esquema destino (init_db)...")
    database.init_db()

    conn_maria = database.conectar()
    cur_maria = conn_maria.cursor()
    # bot_estado normalmente la crea el bot sobre la marcha; garantizarla aquí
    cur_maria.execute("""CREATE TABLE IF NOT EXISTS bot_estado
                         (clave VARCHAR(64) PRIMARY KEY, valor TEXT)
                         ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")

    # Guardia contra doble migración
    if not forzar:
        for tabla in TABLAS_GUARDIA:
            cur_maria.execute(f"SELECT COUNT(*) FROM {tabla}")
            if cur_maria.fetchone()[0] > 0:
                print(f"[!] La tabla '{tabla}' del destino ya tiene datos.")
                print("    Si de verdad quieres reemplazarlos: python migrar_a_mariadb.py --forzar")
                conn_maria.close()
                sys.exit(1)

    conn_sqlite = sqlite3.connect(ORIGEN)
    cur_sqlite = conn_sqlite.cursor()
    existentes = tablas_origen(cur_sqlite)

    errores = 0
    for tabla, columnas in TABLAS.items():
        if tabla not in existentes:
            print(f"  – {tabla}: no existe en el data.db origen, se omite")
            continue

        cols = [c for c in columnas if c in columnas_origen(cur_sqlite, tabla)]
        sel = ", ".join(f'"{c}"' for c in cols)
        cur_sqlite.execute(f'SELECT {sel} FROM "{tabla}"')
        filas = cur_sqlite.fetchall()

        # Vaciar destino (incluye los seeds de init_db: los datos reales mandan)
        cur_maria.execute(f"DELETE FROM {tabla}")
        if filas:
            marcadores = ", ".join("?" * len(cols))
            col_list = ", ".join(f"`{c}`" for c in cols)
            cur_maria.executemany(
                f"INSERT INTO {tabla} ({col_list}) VALUES ({marcadores})", filas)
        conn_maria.commit()

        cur_maria.execute(f"SELECT COUNT(*) FROM {tabla}")
        copiadas = cur_maria.fetchone()[0]
        estado = "✓" if copiadas == len(filas) else "✗ ¡DISCREPANCIA!"
        if copiadas != len(filas):
            errores += 1
        print(f"  {estado} {tabla}: {len(filas)} filas origen → {copiadas} destino")

    conn_sqlite.close()
    conn_maria.close()

    if errores:
        print(f"\n[!] Migración terminó con {errores} tabla(s) con discrepancias.")
        sys.exit(1)
    print("\nMigración completada. data.db queda intacto como respaldo histórico.")
    print("Siguiente paso: arranca la app (python main.py) y verifica tus saldos.")


if __name__ == "__main__":
    main()
