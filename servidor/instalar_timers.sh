#!/usr/bin/env bash
# Instala y habilita el timer de respaldo horario como unidad systemd de USUARIO.
#   ./instalar_timers.sh servidor   # en la máquina que corre MariaDB (dump local)
#   ./instalar_timers.sh cliente    # en cada PC con la app (jala el dump por red)
# Genera las unidades con la ruta real de este repo, así funcionan sin editar
# nada aunque el repo esté clonado en otra carpeta u otra máquina.
set -euo pipefail
rol="${1:-}"
dir_servidor="$(cd "$(dirname "$0")" && pwd)"
unidades="$HOME/.config/systemd/user"
mkdir -p "$unidades"

case "$rol" in
    servidor) script="$dir_servidor/respaldo.sh";       nombre="arch-respaldo";;
    cliente)  script="$dir_servidor/jalar_respaldo.sh"; nombre="arch-jalar-respaldo";;
    *) echo "Uso: $0 servidor|cliente"; exit 1;;
esac

cat > "$unidades/$nombre.service" <<EOF
[Unit]
Description=Respaldo de la BD de Arch Tracker (rol: $rol)

[Service]
Type=oneshot
ExecStart=$script
EOF

cat > "$unidades/$nombre.timer" <<EOF
[Unit]
Description=Cada hora: $nombre

[Timer]
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "$nombre.timer"
# Que el timer corra aunque no haya sesión iniciada
loginctl enable-linger "$USER" 2>/dev/null || true
echo "Timer $nombre.timer habilitado. Verifica con: systemctl --user list-timers"
