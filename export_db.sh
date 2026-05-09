#!/bin/bash
# Export full PostgreSQL database untuk local testing

DB_NAME="zenith"
BACKUP_FILE="zenith_full_backup.sql"
BACKUP_FILE_BINARY="zenith_full_backup.dump"

echo "🔄 Exporting full database: $DB_NAME"

# Binary format (smaller, faster restore)
pg_dump "$DATABASE_URL" -Fc -f "$BACKUP_FILE_BINARY"
echo "✅ Binary backup: $BACKUP_FILE_BINARY"

# Plain SQL (human-readable, for inspection)
pg_dump "$DATABASE_URL" -f "$BACKUP_FILE"
echo "✅ SQL backup: $BACKUP_FILE"

ls -lh "$BACKUP_FILE_BINARY" "$BACKUP_FILE"
echo ""
echo "🚀 Next steps:"
echo "  docker run --name wyckoff-db -e POSTGRES_PASSWORD=password"
echo "    -e POSTGRES_DB=wyckoff_sim -p 5432:5432 -d postgres:15"
echo "  pg_restore -U postgres -h localhost -d wyckoff_sim -Fc $BACKUP_FILE_BINARY"
