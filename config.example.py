# Copia este archivo a config.py y ajusta los valores.
# config.py está gitignorado: aquí van credenciales reales.

# --- Base de datos MariaDB compartida (la usan la app Y el bot) ---
DB_HOST = "192.168.1.50"   # IP de la máquina servidor; "127.0.0.1" en el propio servidor
DB_PORT = 3306
DB_USER = "arch"
DB_PASSWORD = "cambia-esta-contrasena"   # = MARIADB_PASSWORD de servidor/.env
DB_NAME = "arch_tracker"

# --- Bot de Telegram (solo necesario en la máquina que corre bot_listener.py) ---
TELEGRAM_BOT_TOKEN = "123456789:AAF..."
MI_CHAT_ID = 123456789   # tu ID numérico de Telegram; el bot bloquea a los demás
