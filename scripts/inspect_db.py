import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / 'db.sqlite3'
print('DB:', DB)
conn = sqlite3.connect(str(DB))
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
rows = cur.fetchall()
print('Tables:', len(rows))
for r in rows:
    print(r[0])

candidates = ['quote_quoterequest','quote_quote','deals_deal','leads_lead','documents_document','Policys_additionaldocument','policys_additionaldocument']
for t in candidates:
    try:
        cur.execute(f"PRAGMA table_info({t})")
        cols = cur.fetchall()
        if cols:
            print('\nSchema for', t)
            for c in cols:
                print(c)
    except Exception as e:
        pass
conn.close()
