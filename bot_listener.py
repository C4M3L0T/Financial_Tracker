import telebot
import config
import database
import threading
import time
import re
from datetime import datetime

# =========================================================
# CONFIGURACIÓN (Mantén tus credenciales anteriores)
# =========================================================
BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
MI_TELEGRAM_ID = config.MI_CHAT_ID

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
    "dp": "Deportes",
    "o": "Otros"
}

def guardar_gasto_bd(desc, monto, categoria):
    try:
        conn = database.conectar()
        cursor = conn.cursor()
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute("""
            INSERT INTO gastos (`desc`, monto, categoria, fecha, con_factura, es_deducible)
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
    conn = database.conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT limite FROM presupuestos WHERE categoria=?", (categoria,))
    row = cursor.fetchone()
    if not row or not row[0] or row[0] <= 0:
        conn.close()
        return None
    limite = row[0]
    mes = datetime.now().strftime("%Y-%m")
    cursor.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE categoria=? AND LEFT(fecha, 7)=?",
                   (categoria, mes))
    gastado = cursor.fetchone()[0]
    conn.close()

    uso = gastado / limite
    if uso > 1.0: icono = "🚨"
    elif uso >= 0.8: icono = "⚠️"
    else: icono = "✅"
    return f"{icono} Presupuesto {categoria}: ${gastado:,.0f} / ${limite:,.0f} ({uso*100:.0f}%)"

def construir_resumen():
    conn = database.conectar()
    cursor = conn.cursor()
    mes = datetime.now().strftime("%Y-%m")
    cursor.execute("""
        SELECT p.categoria, p.limite,
               COALESCE((SELECT SUM(g.monto) FROM gastos g
                         WHERE g.categoria = p.categoria AND LEFT(g.fecha, 7) = ?), 0)
        FROM presupuestos p ORDER BY p.categoria
    """, (mes,))
    presupuestos = cursor.fetchall()
    cursor.execute("SELECT `desc`, mensualidad, meses_totales, meses_pagados FROM deudas_msi")
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
    conn = database.conectar()
    cursor = conn.cursor()
    mes = datetime.now().strftime("%Y-%m")
    cursor.execute("""
        SELECT p.categoria, p.limite,
               COALESCE((SELECT SUM(g.monto) FROM gastos g
                         WHERE g.categoria = p.categoria AND LEFT(g.fecha, 7) = ?), 0)
        FROM presupuestos p
    """, (mes,))
    presupuestos = cursor.fetchall()
    cursor.execute("SELECT `desc`, meses_totales - meses_pagados FROM deudas_msi WHERE meses_totales - meses_pagados <= 1")
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

# =========================================================
# CUENTAS: RESOLUCIÓN Y CUENTA POR DEFECTO
# =========================================================
def resolver_cuenta(texto_busqueda):
    """Devuelve (id, nombre) de la cuenta que mejor coincida, o None.
    Prioridad: nombre exacto > prefijo > subcadena — así 'nu' resuelve a
    'Nu' y no a 'Cajitas Nu' por orden alfabético."""
    conn = database.conectar()
    cursor = conn.cursor()
    texto = texto_busqueda.lower()
    row = None
    for patron in (texto, f"{texto}%", f"%{texto}%"):
        cursor.execute("SELECT id, nombre FROM cuentas WHERE LOWER(nombre) LIKE ? ORDER BY nombre", (patron,))
        row = cursor.fetchone()
        if row:
            break
    conn.close()
    return row

def cuenta_por_defecto():
    valor = obtener_estado("cuenta_default")
    if not valor:
        return None
    conn = database.conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre FROM cuentas WHERE id=?", (valor,))
    row = cursor.fetchone()
    conn.close()
    return row  # None si la cuenta default fue eliminada desde la app

def obtener_estado(clave):
    conn = database.conectar()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS bot_estado (clave VARCHAR(64) PRIMARY KEY, valor TEXT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
    cursor.execute("SELECT valor FROM bot_estado WHERE clave=?", (clave,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def guardar_estado(clave, valor):
    conn = database.conectar()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS bot_estado (clave VARCHAR(64) PRIMARY KEY, valor TEXT) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4")
    cursor.execute("REPLACE INTO bot_estado (clave, valor) VALUES (?, ?)", (clave, valor))
    conn.commit()
    conn.close()

def vigilante_diario():
    """Cada hora: materialización de recurrentes (con aviso inmediato de lo
    generado). Además, una vez al día (después de las 9:00) manda las alertas;
    la marca en bot_estado evita duplicados aunque systemd reinicie el proceso
    varias veces al día. (Los respaldos ya no van aquí: son dumps del servidor
    MariaDB — ver servidor/respaldo.sh y sus timers.)"""
    while True:
        try:
            generados = database.generar_recurrentes()
            if generados:
                bot.send_message(MI_TELEGRAM_ID,
                                 "🔁 *Recurrentes registrados:*\n" + "\n".join(generados),
                                 parse_mode="Markdown")

            rendimientos = database.generar_rendimientos()
            if rendimientos:
                bot.send_message(MI_TELEGRAM_ID,
                                 "📈 *Rendimientos devengados:*\n" + "\n".join(rendimientos),
                                 parse_mode="Markdown")

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
        " `dp` = Deportes\n"
        " `o`  = Otros\n\n"
        " 💳 **Cuentas:** agrega `@nombre` al final para asignar cuenta\n"
        " *Ejemplo:* `450 c Tacos @nu`\n"
        " `/cuenta nombre` fija tu cuenta por defecto | `/cuenta` las lista\n"
        " `/pago monto origen destino` paga tarjeta o transfiere entre cuentas\n\n"
        " Envía /resumen para ver el semáforo de presupuestos y tus deudas."
    )
    bot.reply_to(message, ayuda, parse_mode="Markdown")


# Resumen bajo demanda: presupuestos + deudas (registrado ANTES del catch-all)
@bot.message_handler(commands=['resumen'])
def enviar_resumen(message):
    bot.reply_to(message, construir_resumen(), parse_mode="Markdown")


# Gestión de cuentas: /cuenta lista, /cuenta <nombre> fija la default
@bot.message_handler(commands=['cuenta', 'cuentas'])
def gestionar_cuenta(message):
    partes = message.text.split(" ", 1)
    if len(partes) == 2 and partes[1].strip():
        cuenta = resolver_cuenta(partes[1].strip())
        if cuenta:
            guardar_estado("cuenta_default", str(cuenta[0]))
            bot.reply_to(message, f"✅ Cuenta por defecto: *{cuenta[1]}*\nTodos los gastos sin `@cuenta` se cargarán ahí.", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❌ Ninguna cuenta contiene '{partes[1].strip()}'. Envía /cuenta para listarlas.")
        return

    cuentas = [(cid, nombre, tipo, saldo)
               for cid, nombre, tipo, _tasa, saldo in database.obtener_saldos_cuentas()]

    if not cuentas:
        bot.reply_to(message, "No tienes cuentas aún. Créalas en la app: Tesorería → ⚙ Administrar.")
        return

    default = cuenta_por_defecto()
    lineas = ["💳 *Tus cuentas:*", ""]
    for cid, nombre, tipo, saldo in cuentas:
        marca = " ⭐ (default)" if default and cid == default[0] else ""
        lineas.append(f"• {nombre} ({tipo}): ${saldo:,.2f}{marca}")
    lineas += ["", "Fijar default: `/cuenta nombre`", "Por gasto: agrega `@nombre` al mensaje"]
    bot.reply_to(message, "\n".join(lineas), parse_mode="Markdown")


# Pago de tarjeta / transferencia entre cuentas propias desde el celular
# (ni ingreso ni gasto: solo mueve saldo — registrado ANTES del catch-all)
@bot.message_handler(commands=['pago', 'transferir'])
def transferir_bot(message):
    partes = message.text.split()
    if len(partes) != 4:
        bot.reply_to(message,
                     "Formato: `/pago monto origen destino`\n*Ejemplo:* `/pago 2000 bbva nu`\nEnvía /cuenta para ver tus cuentas.",
                     parse_mode="Markdown")
        return
    try:
        monto = float(partes[1])
        if monto <= 0: raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ El monto debe ser un número positivo.")
        return

    origen = resolver_cuenta(partes[2])
    destino = resolver_cuenta(partes[3])
    if not origen or not destino:
        faltante = partes[2] if not origen else partes[3]
        bot.reply_to(message, f"❌ No encontré la cuenta '{faltante}'. Envía /cuenta para listarlas.")
        return
    if origen[0] == destino[0]:
        bot.reply_to(message, "❌ Origen y destino deben ser cuentas distintas.")
        return

    conn = database.conectar()
    conn.cursor().execute(
        "INSERT INTO transferencias (cuenta_origen, cuenta_destino, monto, fecha, descripcion) VALUES (?,?,?,?,?)",
        (origen[0], destino[0], monto, datetime.now().strftime("%Y-%m-%d"), "Pago desde Telegram"))
    conn.commit()
    conn.close()

    saldos = {cid: saldo for cid, _n, _t, _ta, saldo in database.obtener_saldos_cuentas()}
    bot.reply_to(message,
                 f"✅ *Transferencia registrada:* ${monto:,.2f}\n{origen[1]} → {destino[1]}\n\n"
                 f"💳 {origen[1]}: ${saldos.get(origen[0], 0):,.2f}\n"
                 f"💳 {destino[1]}: ${saldos.get(destino[0], 0):,.2f}",
                 parse_mode="Markdown")


# Procesador de Mensajes de Texto con Ingeniería de Flags Fiscales (SAT)
@bot.message_handler(func=lambda message: True)
def procesar_gasto(message):
    texto = message.text.strip()

    # 0. Cuenta destino: @nombre en el mensaje > cuenta por defecto > sin cuenta
    cuenta_sel = None
    aviso_cuenta = ""
    m_cuenta = re.search(r"@(\S+)", texto)
    if m_cuenta:
        cuenta_sel = resolver_cuenta(m_cuenta.group(1))
        if not cuenta_sel:
            aviso_cuenta = f"\n⚠️ No encontré la cuenta '@{m_cuenta.group(1)}'"
        texto = re.sub(r"@\S+", "", texto).strip()
    if not cuenta_sel:
        cuenta_sel = cuenta_por_defecto()

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
        conn = database.conectar()
        cursor = conn.cursor()
        fecha_envio = datetime.fromtimestamp(message.date).strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO gastos (`desc`, monto, categoria, fecha, con_factura, es_deducible, cuenta_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (desc.strip(), monto, categoria_real, fecha_envio, con_factura, es_deducible,
              cuenta_sel[0] if cuenta_sel else None))
        
        conn.commit()
        conn.close()
        
        # Confirmación visual con estatus fiscal
        status_fiscal = ""
        if con_factura: status_fiscal += "[CFDI Solicitado]"
        if es_deducible: status_fiscal += "[Deducible Art. 151]"

        respuesta = f"✅ **Registrado:**\n `${monto:,.2f}` en *{categoria_real}*\n `{desc.strip()}`\n⚖️ *Status:* {status_fiscal if status_fiscal else 'Gasto Corriente'}"

        if cuenta_sel:
            respuesta += f"\n💳 Cuenta: {cuenta_sel[1]}"
        respuesta += aviso_cuenta

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
