#!/usr/bin/env bash
# Copia de seguridad DESDE un cliente: jala un dump de la MariaDB remota por
# TCP (sin SSH) y lo deja en backups/ del proyecto. Conserva los 60 más
# recientes. Así los datos nunca viven solo en la máquina servidor (prestada).
#
# Requiere el cliente de MariaDB:  sudo pacman -S mariadb-clients
# Los datos de conexión se leen del config.py del proyecto.
set -euo pipefail
cd "$(dirname "$0")/.."

eval "$(python - <<'EOF'
import config
print(f'DB_HOST={config.DB_HOST}')
print(f'DB_PORT={getattr(config, "DB_PORT", 3306)}')
print(f'DB_USER={config.DB_USER}')
print(f'DB_PASSWORD={config.DB_PASSWORD}')
print(f'DB_NAME={getattr(config, "DB_NAME", "arch_tracker")}')
EOF
)"

mkdir -p backups
marca=$(date +%Y%m%d_%H%M)
destino="backups/arch_tracker_${marca}.sql.gz"

MYSQL_PWD="$DB_PASSWORD" mariadb-dump -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" \
    --single-transaction "$DB_NAME" | gzip > "$destino"

ls -1t backups/arch_tracker_*.sql.gz | tail -n +61 | xargs -r rm --
echo "Respaldo OK: $destino"
