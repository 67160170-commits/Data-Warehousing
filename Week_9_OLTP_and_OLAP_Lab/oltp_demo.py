from pathlib import Path
import sqlite3
p=Path(__file__).resolve().parent/'data'/'oltp.db'
if not p.exists():raise SystemExit('Run lab.py first')
with sqlite3.connect(p) as con:
    print('Before:',con.execute('SELECT * FROM orders').fetchall())
    # UPDATE ที่ guarded: ตรวจทั้ง order_id และ status เพื่อ idempotent
    cursor = con.execute(
        'UPDATE orders SET status = ? WHERE order_id = ? AND status = ?',
        ('PAID', 'O1004', 'PENDING')
    )
    print(f'Rowcount: {cursor.rowcount}')
    con.commit()
    print('After:',con.execute('SELECT * FROM orders').fetchall())
# รอบแรก: แก้ไข 1 แถว (PENDING → PAID)
# รอบสอง: แก้ไข 0 แถว (เพราะ O1004 เป็น PAID แล้ว ไม่ match PENDING)
