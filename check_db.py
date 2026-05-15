from core.db import get_scraper_db, fetchall

conn = get_scraper_db()

print("=== ROWCOUNTS ===")
for table in ['eod_summary', 'price_history', 'raw_messages', 'raw_mf_messages']:
    cnt = fetchall(conn, f'SELECT COUNT(*) as cnt FROM {table}')
    print(f'{table:20}: {cnt[0]["cnt"]:,}')

print("\n=== eod_summary DATE RANGE ===")
rows = fetchall(conn, "SELECT MIN(date) as first, MAX(date) as last, COUNT(DISTINCT date) as days FROM eod_summary")
if rows and rows[0]['first']:
    print(f"From {rows[0]['first']} to {rows[0]['last']} ({rows[0]['days']} dates)")

print("\n=== price_history DATE RANGE ===")
rows = fetchall(conn, "SELECT MIN(date) as first, MAX(date) as last, COUNT(DISTINCT date) as days FROM price_history")
if rows and rows[0]['first']:
    print(f"From {rows[0]['first']} to {rows[0]['last']} ({rows[0]['days']} dates)")
else:
    print("(empty)")

print("\n=== TICKERS ===")
rows = fetchall(conn, "SELECT COUNT(DISTINCT ticker) as cnt FROM eod_summary")
print(f"Unique tickers in eod_summary: {rows[0]['cnt']}")

print("\n=== DATA INTEGRITY ===")
rows = fetchall(conn, "SELECT COUNT(*) as cnt FROM eod_summary WHERE price_close IS NULL")
print(f"eod_summary rows missing price_close: {rows[0]['cnt']}")

rows = fetchall(conn, "SELECT COUNT(*) as cnt FROM eod_summary WHERE price_change_pct IS NULL")
print(f"eod_summary rows missing price_change_pct: {rows[0]['cnt']}")

conn.close()
