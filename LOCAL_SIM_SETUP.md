# Local Wyckoff Simulation Engine Setup

## Prerequisites
- Docker Desktop installed
- PostgreSQL client tools: `apt-get install postgresql-client` (Linux/WSL) or `brew install postgresql` (Mac)
- Python 3.10+

## Step 1: Export Production Database

```bash
# Dari zenith_saas root dir
bash export_db.sh
```

Output: `zenith_full_backup.dump` (~50-100MB depending on data size)

## Step 2: Start Local PostgreSQL

```bash
# Start container
docker run --name wyckoff-db \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=wyckoff_sim \
  -p 5432:5432 \
  -d postgres:15

# Verify
docker logs wyckoff-db | grep "database system is ready"
```

## Step 3: Restore Backup

```bash
# Wait 5s for DB to be ready
sleep 5

# Restore binary backup
pg_restore -U postgres -h localhost -d wyckoff_sim -Fc zenith_full_backup.dump

# Verify tables exist
psql -U postgres -h localhost -d wyckoff_sim -c "\dt"
```

## Step 4: Setup Python Environment

```bash
# Create venv
python -m venv venv_sim
source venv_sim/bin/activate  # Linux/Mac
# atau: venv_sim\Scripts\activate  (Windows)

# Install deps
pip install psycopg2-binary python-dotenv
```

## Step 5: Create .env for local DB

```bash
# .env (local)
DATABASE_URL=postgresql://postgres:password@localhost:5432/wyckoff_sim
FLASK_ENV=development
```

## Step 6: Run Simulation Engine

```bash
python sim_engine.py --algo wyckoff --days 90
```

---

## Cleanup

```bash
docker stop wyckoff-db && docker rm wyckoff-db
```

## Troubleshooting

**Port 5432 already in use:**
```bash
lsof -i :5432  # Find process
kill -9 <PID>
# atau ganti port: -p 5433:5432
```

**Restore fails with permission error:**
```bash
# Reset Docker volume
docker volume rm wyckoff-db-data
```

**Check DB size:**
```bash
psql -U postgres -h localhost -d wyckoff_sim -c "
  SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
  FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```
