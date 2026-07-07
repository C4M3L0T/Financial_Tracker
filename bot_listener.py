import sqlite3
import telebot
import config
import threading
import time
from datetime import datetime

# =========================================================
# CONFIGURACIÓN (Mantén tus credenciales anteriores)
# =========================================================
BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
MI_TELEGRAM_ID = config.MI_CHAT_ID
DB_PATH = "data.db"                    

bot = telebot.TeleBot(BOT_TOKEN)

# =========================================================
# DICCIONARIO AMPLIADO Y MAPEADO SIN CONFLICTOS
# =========================================================
CATEGORIAS = {
    "v": "Vivienda",
    "c": "Comida",
    "t": "Transporte",
    "i": "Impuestos",
    "a": "Ahorros",
    "s": "Salud",
    "r": "Recreación",
    "su": "Suscripciones",
    "se": "Seguros",
    "sv": "Servicios",
    "ve": "Vestimenta",
    "p": "Personal",
    "m": "Mascota",
    "d": "Deuda",
    "o": "Otros"
}

def guardar_gasto_bd(desc, monto, categoria):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute("""
            INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible)
            VALUES (?, ?, ?, ?, 0, 0)
        """, (desc, monto, categoria, fecha_hoy))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error en BD: {e}")
        return False

# =========================================================
# PRESUPUESTOS Y ALERTAS
# =========================================================
def linea_presupuesto(categoria):
    """Estado del presupuesto de una categoría en el mes actual, o None si no hay límite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT limite FROM presupuestos WHERE categoria=?", (categoria,))
    row = cursor.fetchone()
    if not row or not row[0] or row[0] <= 0:
        conn.close()
        return None
    limite = row[0]
    mes = datetime.now().strftime("%Y-%m")
    cursor.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE categoria=? AND strftime('%Y-%m',fecha)=?",
                   (categoria, mes))
    gastado = cursor.fetchone()[0]
    conn.close()

    uso = gastado / limite
    if uso > 1.0: icono = "🚨"
    elif uso >= 0.8: icono = "⚠️"
    else: icono = "✅"
    return f"{icono} Presupuesto {categoria}: ${gastado:,.0f} / ${limite:,.0f} ({uso*100:.0f}%)"

def construir_resumen():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    mes = datetime.now().strftime("%Y-%m")
    cursor.execute("""
        SELECT p.categoria, p.limite,
               COALESCE((SELECT SUM(g.monto) FROM gastos g
                         WHERE g.categoria = p.categoria AND strftime('%Y-%m', g.fecha) = ?), 0)
        FROM presupuestos p ORDER BY p.categoria
    """, (mes,))
    presupuestos = cursor.fetchall()
    cursor.execute("SELECT desc, mensualidad, meses_totales, meses_pagados FROM deudas_msi")
    deudas = cursor.fetchall()
    conn.close()

    lineas = [f"📊 *Resumen {mes}*", ""]
    if presupuestos:
        for cat, limite, gastado in presupuestos:
            uso = gastado / limite if limite > 0 else 0
            icono = "🚨" if uso > 1.0 else ("⚠️" if uso >= 0.8 else "✅")
            lineas.append(f"{icono} {cat}: ${gastado:,.0f}/${limite:,.0f} ({uso*100:.0f}%)")
    else:
        lineas.append("Sin presupuestos definidos (pestaña Planeación).")
    if deudas:
        lineas.append("")
        lineas.append("💳 *Deudas activas:*")
        for desc, men, mt, mp in deudas:
            restantes = mt - mp
            lineas.append(f"• {desc}: ${men:,.0f}/mes, faltan {restantes} pago(s)")
    return "\n".join(lineas)

def construir_alertas():
    """Solo lo urgente: presupuestos ≥90% y deudas con 1 pago o menos por delante."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    mes = datetime.now().strftime("%Y-%m")
    cursor.execute("""
        SELECT p.categoria, p.limite,
               COALESCE((SELECT SUM(g.monto) FROM gastos g
                         WHERE g.categoria = p.categoria AND strftime('%Y-%m', g.fecha) = ?), 0)
        FROM presupuestos p
    """, (mes,))
    presupuestos = cursor.fetchall()
    cursor.execute("SELECT desc, meses_totales - meses_pagados FROM deudas_msi WHERE meses_totales - meses_pagados <= 1")
    deudas_por_vencer = cursor.fetchall()
    conn.close()

    lineas = []
    for cat, limite, gastado in presupuestos:
        if limite > 0 and gastado / limite >= 0.9:
            icono = "🚨" if gastado > limite else "⚠️"
            lineas.append(f"{icono} {cat}: ${gastado:,.0f} de ${limite:,.0f} ({gastado/limite*100:.0f}%)")
    for desc, restantes in deudas_por_vencer:
        lineas.append(f"🎉 '{desc}': {'último pago este mes' if restantes == 1 else 'liquidada'} — tu liquidez mensual sube pronto")
    if not lineas:
        return None
    return "🔔 *Alertas ArchTracker*\n\n" + "\n".join(lineas)

def obtener_estado(clave):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS bot_estado (clave TEXT PRIMARY KEY, valor TEXT)")
    cursor.execute("SELECT valor FROM bot_estado WHERE clave=?", (clave,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def guardar_estado(clave, valor):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS bot_estado (clave TEXT PRIMARY KEY, valor TEXT)")
    cursor.execute("INSERT OR REPLACE INTO bot_estado (clave, valor) VALUES (?, ?)", (clave, valor))
    conn.commit()
    conn.close()

def vigilante_diario():
    """Una revisión al día (después de las 9:00). La marca en bot_estado evita
    duplicados aunque systemd reinicie el proceso varias veces al día."""
    while True:
        try:
            hoy = datetime.now().strftime("%Y-%m-%d")
            if datetime.now().hour >= 9 and obtener_estado("ultimo_aviso") != hoy:
                alertas = construir_alertas()
                if alertas:
                    bot.send_message(MI_TELEGRAM_ID, alertas, parse_mode="Markdown")
                guardar_estado("ultimo_aviso", hoy)
        except Exception as e:
            print(f"Error en vigilante diario: {e}")
        time.sleep(3600)

# Middleware de Seguridad
@bot.message_handler(func=lambda message: message.from_user.id != MI_TELEGRAM_ID)
def bloquear_intrusos(message):
    bot.reply_to(message, " Acceso denegado. Este bot es privado.")

# =========================================================
# COMANDO /HELP OPTIMIZADO PARA PANTALLAS MÓVILES
# =========================================================
@bot.message_handler(commands=['start', 'help'])
def enviar_bienvenida(message):
    ayuda = (
        " **ArchTracker: Diccionario de Captura**\n\n"
        "Escribe tu gasto así:\n"
        "`[monto] [categoría_corta] [descripción]`\n"
        "[factura] [deducible] (vacio si no hay)\n"
        " *Ejemplo:* `450 m Croquetas de firulais +f +d`\n\n"
        " **Atajos de Categorías:**\n"
        " `v`  = Vivienda\n"
        " `c`  = Comida\n"
        " `t`  = Transporte\n"
        " `i`  = Impuestos\n"
        " `a`  = Ahorros\n"
        " `s`  = Salud\n"
        " `r`  = Recreación\n"
        " `su` = Suscripciones\n"
        " `se` = Seguros\n"
        " `sv` = Servicios\n"
        " `ve` = Vestimenta\n"
        " `p`  = Personal\n"
        " `m`  = Mascota\n"
        " `d`  = Deuda\n"
        " `o`  = Otros\n\n"
        " Envía /resumen para ver el semáforo de presupuestos y tus deudas."
    )
    bot.reply_to(message, ayuda, parse_mode="Markdown")


# Resumen bajo demanda: presupuestos + deudas (registrado ANTES del catch-all)
@bot.message_handler(commands=['resumen'])
def enviar_resumen(message):
    bot.reply_to(message, construir_resumen(), parse_mode="Markdown")


# Procesador de Mensajes de Texto con Ingeniería de Flags Fiscales (SAT)
@bot.message_handler(func=lambda message: True)
def procesar_gasto(message):
    texto = message.text.strip()
    
    # 1. Extraer flags al final del mensaje (+f = con factura, +d = deducible)
    con_factura = 1 if "+f" in texto.lower() else 0
    es_deducible = 1 if "+d" in texto.lower() else 0
    
    # Limpiar el texto de los flags para no ensuciar la descripción
    texto_limpio = texto.replace("+f", "").replace("+F", "").replace("+d", "").replace("+D", "").strip()
    
    partes = texto_limpio.split(" ", 2) 
    
    if len(partes) < 3:
        bot.reply_to(message, "⚠️ Formato: `monto cat descripción [flags]`\n *Ejemplo:* `1500 s Consulta Dentista +f +d`")
        return
        
    str_monto, atajo_cat, desc = partes
    
    try:
        monto = float(str_monto)
        if monto <= 0: raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ El monto debe ser un número positivo.")
        return
        
    cat_normalizada = atajo_cat.lower()
    if cat_normalizada not in CATEGORIAS:
        bot.reply_to(message, f"❌ Atajo '{atajo_cat}' no reconocido. Envía /help.")
        return
        
    categoria_real = CATEGORIAS[cat_normalizada]
    
    # 2. Guardar en Base de Datos respetando la contabilidad mexicana
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        fecha_envio = datetime.fromtimestamp(message.date).strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (desc.strip(), monto, categoria_real, fecha_envio, con_factura, es_deducible))
        
        conn.commit()
        conn.close()
        
        # Confirmación visual con estatus fiscal
        status_fiscal = ""
        if con_factura: status_fiscal += "[CFDI Solicitado]"
        if es_deducible: status_fiscal += "[Deducible Art. 151]"

        respuesta = f"✅ **Registrado:**\n `${monto:,.2f}` en *{categoria_real}*\n `{desc.strip()}`\n⚖️ *Status:* {status_fiscal if status_fiscal else 'Gasto Corriente'}"

        # Retroalimentación de presupuesto en el momento de la captura
        presupuesto = linea_presupuesto(categoria_real)
        if presupuesto:
            respuesta += f"\n{presupuesto}"

        bot.reply_to(message, respuesta)
        
    except Exception as e:
        bot.reply_to(message, f" Error en BD: {e}")

if __name__ == "__main__":
    print(" El Bot de Telegram está escuchando con las 15 categorías...")
    threading.Thread(target=vigilante_diario, daemon=True).start()
    bot.infinity_polling()
