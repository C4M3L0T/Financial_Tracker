import sqlite3
import telebot
import config
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
        " `o`  = Otros"
    )
    bot.reply_to(message, ayuda, parse_mode="Markdown")


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
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute("""
            INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (desc.strip(), monto, categoria_real, fecha_hoy, con_factura, es_deducible))
        
        conn.commit()
        conn.close()
        
        # Confirmación visual con estatus fiscal
        status_fiscal = ""
        if con_factura: status_fiscal += "[CFDI Solicitado]"
        if es_deducible: status_fiscal += "[Deducible Art. 151]"
        
        bot.reply_to(message, f"✅ **Registrado:**\n `${monto:,.2f}` en *{categoria_real}*\n `{desc.strip()}`\n⚖️ *Status:* {status_fiscal if status_fiscal else 'Gasto Corriente'}")
        
    except Exception as e:
        bot.reply_to(message, f" Error en BD: {e}")

if __name__ == "__main__":
    print(" El Bot de Telegram está escuchando con las 15 categorías...")
    bot.infinity_polling()
