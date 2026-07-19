import sqlite3, sys, os
f = sys.argv[1] if len(sys.argv) > 1 else "hadith_analyzed_subset.db"
print("file:", f, "| ada:", os.path.exists(f), "| ukuran:", os.path.getsize(f) if os.path.exists(f) else 0, "byte")
con = sqlite3.connect(f)
tabel = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tabel:", tabel)
for t in tabel:
    n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {n} baris")
