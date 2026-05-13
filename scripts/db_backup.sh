#!/bin/bash
# Backup PostgreSQL DB `bep_an`.
# Chạy qua systemd timer `db-backup.timer` (xem `scripts/db-backup.service`).
# Phải chạy với quyền root để chuyển sang user postgres dump được.

set -e

BACKUP_DIR="/home/ipcdkv2/db_backups"
DB_NAME="bep_an"
RETENTION_COUNT=7
OWNER="ipcdkv2:ipcdkv2"

mkdir -p "$BACKUP_DIR"
chown "$OWNER" "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# Cảnh báo nếu disk gần đầy (< 500MB free trên /home) nhưng vẫn chạy.
AVAILABLE_KB=$(df --output=avail /home | tail -n 1)
if [ "$AVAILABLE_KB" -lt 512000 ]; then
    echo "WARN: Free disk on /home < 500MB — backup vẫn tiếp tục."
fi

TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/bep_an_${TIMESTAMP}.sql.gz"

# Dump qua user postgres (peer auth, không cần password). Pipe gzip để nén.
sudo -u postgres pg_dump "$DB_NAME" | gzip > "$BACKUP_FILE"

chown "$OWNER" "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE"

# Xoá bản cũ — giữ lại $RETENTION_COUNT bản mới nhất.
cd "$BACKUP_DIR"
ls -1t bep_an_*.sql.gz 2>/dev/null | tail -n +$((RETENTION_COUNT + 1)) | xargs -r rm -v

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
COUNT=$(ls -1 bep_an_*.sql.gz 2>/dev/null | wc -l)
echo "Backup OK: $BACKUP_FILE ($SIZE) — tổng $COUNT bản đang giữ."
