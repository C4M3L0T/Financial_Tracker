#!/usr/bin/env bash
# Dump horario de la BD (se corre EN el servidor vía arch-respaldo.timer).
# Deja gzips en servidor/respaldos/ y conserva los 72 más recientes (3 días).
# Ojo: estos dumps viven en la misma máquina que la BD; las copias que de
# verdad te salvan si la máquina desaparece son las que jalan los clientes
# (jalar_respaldo.sh).
set -euo pipefail
cd "$(dirname "$0")"
source .env

mkdir -p respaldos
marca=$(date +%Y%m%d_%H%M)
destino="respaldos/arch_tracker_${marca}.sql.gz"

docker exec -e MYSQL_PWD="${MARIADB_PASSWORD}" arch_tracker_db \
    mariadb-dump -u arch --single-transaction arch_tracker | gzip > "$destino"

# Poda: conservar los 72 más recientes
ls -1t respaldos/arch_tracker_*.sql.gz | tail -n +73 | xargs -r rm --
echo "Respaldo OK: $destino"
