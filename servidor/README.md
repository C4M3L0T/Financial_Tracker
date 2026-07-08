# Servidor de datos (MariaDB) — guía de operación

## Arquitectura

- La base de datos vive en un contenedor **MariaDB** en la máquina servidor
  (hoy: la HP ZBook que también corre pihole). La app de escritorio en
  cualquier computadora y el bot de Telegram se conectan a ella por red
  (datos de conexión en el `config.py` de cada máquina).
- La máquina servidor se considera **desechable** (es prestada): los datos
  reales están protegidos por dumps horarios locales (`respaldo.sh`) **y**
  por las copias que cada cliente jala a su propio `backups/`
  (`jalar_respaldo.sh`). Perderla cuesta, como mucho, lo capturado en la
  última hora.
- Reponer el servidor en otra máquina = Docker + restaurar el último dump
  (sección 5, ~15 minutos).

## 1. Levantar el servidor desde cero

En la máquina servidor (Arch Linux; en otra distro cambia el gestor de paquetes):

```bash
sudo pacman -S --needed docker docker-compose git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER        # cierra sesión y vuelve a entrar

git clone <URL-de-este-repo> ~/arch_tracker
cd ~/arch_tracker/servidor
cp .env.example .env && nano .env    # contraseñas reales
docker compose up -d
docker compose ps                    # espera a que marque "healthy"

./instalar_timers.sh servidor        # dump horario local
```

Notas:
- Si hay firewall, abre el puerto **3306/tcp** para la LAN.
- Fija la IP del servidor (reserva DHCP o IP estática): los clientes la
  llevan en su `config.py`. Como el pihole de la ZBook es el propio DHCP,
  basta ponerle una reserva a sí misma.
- El directorio de datos del contenedor es `servidor/datos/` (gitignorado).

## 2. Cargar los datos la primera vez (migración desde data.db)

En la máquina donde vive el `data.db` histórico:

```bash
sudo pacman -S --needed python-pymysql
cp config.example.py config.py       # DB_HOST = IP del servidor, DB_PASSWORD = la de .env
python migrar_a_mariadb.py           # copia todo; data.db queda intacto
```

El script se niega a correr si el destino ya tiene datos (`--forzar` para
reemplazarlos). Al terminar abre la app y verifica tus saldos.

## 3. Conectar una computadora nueva a la app

```bash
sudo pacman -S --needed python-customtkinter python-matplotlib python-numpy \
                        python-pymysql mariadb-clients noto-fonts-emoji
git clone <URL-de-este-repo> && cd arch_tracker
cp config.example.py config.py       # DB_HOST = IP del servidor
python main.py

servidor/instalar_timers.sh cliente  # copia horaria del dump a backups/ (requiere mariadb-clients)
```

## 4. Bot de Telegram (corre EN el servidor)

```bash
# En la máquina servidor:
sudo pacman -S --needed python-pymysql

# python-pytelegrambotapi es de AUR, no de los repos oficiales.
# Con un AUR helper:  yay -S python-pytelegrambotapi
# Sin AUR helper:
sudo pacman -S --needed base-devel git
git clone https://aur.archlinux.org/python-pytelegrambotapi.git /tmp/ptba
(cd /tmp/ptba && makepkg -si)
cd ~/arch_tracker
cp config.example.py config.py       # token + MI_CHAT_ID + DB_HOST = "127.0.0.1"

mkdir -p ~/.config/systemd/user
cp systemd/bot_listener.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now bot_listener.service
loginctl enable-linger $USER         # que sobreviva sin sesión iniciada
journalctl --user -u bot_listener.service -f   # verificar que arrancó
```

**Importante:** el bot debe correr en **una sola** máquina a la vez (dos
procesos con el mismo token chocan en el polling de Telegram). Si el bot
corría antes en otra máquina, desactívalo allí:
`systemctl --user disable --now bot_listener.service`.

## 5. Migrar el servidor a otra máquina (la ZBook se fue)

1. En la máquina nueva: sección 1 completa.
2. Consigue el dump más reciente — está en el `backups/` de cualquier
   cliente (o en `servidor/respaldos/` si aún tienes acceso al disco viejo) —
   y restáuralo:
   ```bash
   cd ~/arch_tracker/servidor && source .env
   zcat /ruta/al/arch_tracker_XXXXXXXX_XXXX.sql.gz | \
       docker exec -i -e MYSQL_PWD="$MARIADB_PASSWORD" arch_tracker_db \
       mariadb -u arch arch_tracker
   ```
3. En cada cliente: actualiza `DB_HOST` en su `config.py`.
4. Reinstala el bot en el servidor nuevo (sección 4).

## 6. Verificación rápida

- `docker compose ps` → healthy.
- `python main.py` en un cliente abre y muestra los saldos correctos.
- `systemctl --user list-timers` → `arch-respaldo` (servidor) /
  `arch-jalar-respaldo` (clientes) con próxima ejecución.
- Manda un gasto de prueba al bot y bórralo desde la app en otra máquina:
  eso confirma el ciclo completo por red.
