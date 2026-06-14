
"""
SPYM Hospital Management System
================================
Run:  python app.py
Open: http://127.0.0.1:5000

All HTML is embedded — no /templates folder needed.
MySQL config at the top of this file.
"""

from flask import Flask, jsonify, request as flask_request
import mysql.connector
from mysql.connector import Error
import urllib.request
import urllib.parse
import json as json_mod
import csv
import os

app = Flask(__name__)

# ── CONFIG ────────────────────────────────────────────────────────────────────
DB = {
    "host":     "localhost",
    "user":     "root",
    "password": "Prashanth@09112004",
    "database": "hcl"
}

# ── DB HELPERS ────────────────────────────────────────────────────────────────
def get_db():
    try:
        return mysql.connector.connect(**DB)
    except Error as e:
        print(f"[DB] connect error: {e}")
        return None

def q(sql, params=(), fetch=None):
    conn = get_db()
    if not conn:
        raise RuntimeError("Cannot connect to MySQL — check DB config")
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        if fetch == 'all':
            return cur.fetchall()
        if fetch == 'one':
            return cur.fetchone()
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()

def init_db():
    conn = get_db()
    if not conn:
        print("[DB] WARNING: could not connect — tables not created")
        return
    cur = conn.cursor(dictionary=True)

    cur.execute("""CREATE TABLE IF NOT EXISTS patients (
        patient_id VARCHAR(20) PRIMARY KEY,
        name       VARCHAR(100) NOT NULL,
        dob        DATE,
        email      VARCHAR(100),
        phone      VARCHAR(20),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS doctors (
        doctor_id VARCHAR(20) PRIMARY KEY,
        name      VARCHAR(100) NOT NULL,
        specialty VARCHAR(100),
        email     VARCHAR(100),
        phone     VARCHAR(20)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS appointments (
        id               INT AUTO_INCREMENT PRIMARY KEY,
        patient_id       VARCHAR(20),
        doctor_id        VARCHAR(20),
        appointment_date DATE,
        appointment_time TIME,
        notes            TEXT,
        status           ENUM('scheduled','completed','cancelled') DEFAULT 'scheduled',
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
        FOREIGN KEY (doctor_id)  REFERENCES doctors(doctor_id)   ON DELETE CASCADE
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS service_requests (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        title       VARCHAR(200) NOT NULL,
        description TEXT,
        status      ENUM('pending','in_progress','resolved') DEFAULT 'pending',
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS doctor_leaves (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        doctor_id   VARCHAR(20) NOT NULL,
        leave_date  DATE NOT NULL,
        reason      VARCHAR(255),
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_doctor_leave (doctor_id, leave_date),
        INDEX idx_doctor_leave_doc (doctor_id)
    )""")
    conn.commit()

    # Add missing columns to pre-existing tables
    missing_cols = [
        ('patients',         'dob',              'DATE'),
        ('patients',         'email',            'VARCHAR(100)'),
        ('patients',         'phone',            'VARCHAR(20)'),
        ('patients',         'created_at',       'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('patients',         'pincode',          'VARCHAR(20)'),
        ('patients',         'location',         'VARCHAR(255)'),
        ('doctors',          'specialty',        'VARCHAR(100)'),
        ('doctors',          'email',            'VARCHAR(100)'),
        ('doctors',          'phone',            'VARCHAR(20)'),
        ('appointments',     'notes',            'TEXT'),
        ('appointments',     'status',           "VARCHAR(20) DEFAULT 'scheduled'"),
        ('appointments',     'created_at',       'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('appointments',     'pincode',          'VARCHAR(20)'),
        ('appointments',     'location',         'VARCHAR(255)'),
        ('service_requests', 'description',      'TEXT'),
        ('service_requests', 'status',           "VARCHAR(20) DEFAULT 'pending'"),
        ('service_requests', 'created_at',       'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
    ]
    for table, column, col_def in missing_cols:
        cur.execute("""SELECT COUNT(*) AS cnt FROM information_schema.COLUMNS
                       WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s""",
                    (DB['database'], table, column))
        row = cur.fetchone()
        if row['cnt'] == 0:
            try:
                cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {col_def}")
                conn.commit()
                print(f"[DB] added {table}.{column}")
            except Exception as e:
                print(f"[DB] could not add {table}.{column}: {e}")

    # Print actual columns
    for tbl in ['patients', 'doctors', 'appointments', 'service_requests']:
        cur.execute(f"SHOW COLUMNS FROM `{tbl}`")
        cols = [r['Field'] for r in cur.fetchall()]
        print(f"[DB] {tbl}: {cols}")

    cur.close()
    conn.close()
    print("[DB] All tables ready.")

    # ── SEED CSV DATA ─────────────────────────────────────────────────────────
    _seed_csv_data()


def _seed_csv_data():
    """Load patients and doctors from CSV seed files (skip duplicates/invalid rows)."""
    base = os.path.join(os.path.dirname(__file__), 'all_csv_samples', 'all_csv_samples')

    # ── SEED PATIENTS ─────────────────────────────────────────────────────────
    patients_csv = os.path.join(base, 'patients_seed.csv')
    if os.path.exists(patients_csv):
        inserted_p = 0
        skipped_p  = 0
        try:
            conn = get_db()
            cur  = conn.cursor(dictionary=True)
            with open(patients_csv, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pid  = str(row.get('id', '')).strip()
                    name = str(row.get('name', '')).strip()
                    if not pid or not name:
                        skipped_p += 1
                        continue
                    patient_id = f'P{pid}'
                    dob_raw    = str(row.get('dob', '')).strip() or None
                    email      = str(row.get('email', '')).strip() or None
                    phone      = str(row.get('phone', '')).strip() or None
                    pincode    = str(row.get('pincode', '')).strip() or None
                    # parse DOB (handles MM/DD/YYYY and DD-MM-YYYY)
                    dob = None
                    if dob_raw:
                        for fmt in ('%m/%d/%Y', '%d-%m-%Y', '%Y-%m-%d'):
                            try:
                                from datetime import datetime as _dt
                                dob = _dt.strptime(dob_raw, fmt).date().isoformat()
                                break
                            except ValueError:
                                pass
                    try:
                        cur.execute(
                            "INSERT IGNORE INTO patients (patient_id,name,dob,email,phone,pincode) "
                            "VALUES (%s,%s,%s,%s,%s,%s)",
                            (patient_id, name, dob, email, phone, pincode)
                        )
                        if cur.rowcount:
                            inserted_p += 1
                        else:
                            skipped_p  += 1
                    except Exception:
                        skipped_p += 1
            conn.commit()
            cur.close(); conn.close()
            print(f"[SEED] patients — inserted: {inserted_p}, skipped/duplicate: {skipped_p}")
        except Exception as e:
            print(f"[SEED] patients error: {e}")
    else:
        print(f"[SEED] patients_seed.csv not found at {patients_csv}")

    # ── SEED DOCTORS ──────────────────────────────────────────────────────────
    doctors_csv = os.path.join(base, 'doctors_seed.csv')
    if os.path.exists(doctors_csv):
        inserted_d = 0
        skipped_d  = 0
        try:
            conn = get_db()
            cur  = conn.cursor(dictionary=True)
            with open(doctors_csv, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    did  = str(row.get('id', '')).strip()
                    name = str(row.get('name', '')).strip()
                    if not did or not name:
                        skipped_d += 1
                        continue
                    doctor_id = f'D{did}'
                    specialty = str(row.get('specialty', '')).strip() or None
                    email     = str(row.get('email', '')).strip() or None
                    phone     = str(row.get('phone', '')).strip() or None
                    try:
                        cur.execute(
                            "INSERT IGNORE INTO doctors (doctor_id,name,specialty,email,phone) "
                            "VALUES (%s,%s,%s,%s,%s)",
                            (doctor_id, name, specialty, email, phone)
                        )
                        if cur.rowcount:
                            inserted_d += 1
                        else:
                            skipped_d  += 1
                    except Exception:
                        skipped_d += 1
            conn.commit()
            cur.close(); conn.close()
            print(f"[SEED] doctors  — inserted: {inserted_d}, skipped/duplicate: {skipped_d}")
        except Exception as e:
            print(f"[SEED] doctors error: {e}")
    else:
        print(f"[SEED] doctors_seed.csv not found at {doctors_csv}")


# ── CSS + NAV (shared) ────────────────────────────────────────────────────────
BASE_CSS = """
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet"/>
<style>
:root{--ink:#0f1117;--paper:#f5f2eb;--cream:#ede9de;--teal:#1a6b6b;--teal2:#144f4f;--gold:#c5913a;--red:#b84040;--border:#ccc8bc;--sh:0 4px 24px rgba(15,17,23,.10)}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'DM Sans',sans-serif;background:var(--paper);color:var(--ink);min-height:100vh}
nav{background:var(--ink);display:flex;align-items:center;justify-content:space-between;padding:0 2.5rem;height:62px}
.brand{font-family:'DM Serif Display',serif;color:#fff;font-size:1.5rem}.brand span{color:var(--gold)}
.nav-links{display:flex;gap:1.8rem}
.nav-links a{color:#aaa;text-decoration:none;font-size:.85rem;font-weight:500;letter-spacing:.06em;text-transform:uppercase;transition:color .2s}
.nav-links a:hover,.nav-links a.on{color:#fff}
.hero{padding:2.8rem 2.5rem 2.2rem;color:#fff}
main{max-width:1160px;margin:0 auto;padding:2rem 1.5rem}
.card{background:#fff;border:1px solid var(--border);border-radius:2px;box-shadow:var(--sh);overflow:hidden;margin-bottom:1.8rem}
.ch{background:var(--cream);border-bottom:1px solid var(--border);padding:.85rem 1.4rem;display:flex;align-items:center;justify-content:space-between}
.ch h2{font-family:'DM Serif Display',serif;font-size:1.15rem}
.cb{padding:1.4rem}
.fg{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:.9rem}
.fv{display:flex;flex-direction:column;gap:.3rem}
label{font-size:.75rem;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:#555}
input,select,textarea{border:1px solid var(--border);border-radius:2px;padding:.5rem .75rem;font-size:.9rem;font-family:inherit;background:var(--paper);color:var(--ink);transition:border-color .2s,box-shadow .2s;width:100%}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--teal);box-shadow:0 0 0 3px rgba(26,107,107,.13)}
textarea{resize:vertical;min-height:72px}
.btn{display:inline-flex;align-items:center;gap:.4rem;padding:.55rem 1.3rem;border:none;border-radius:2px;font-family:inherit;font-size:.87rem;font-weight:600;cursor:pointer;transition:all .2s;letter-spacing:.02em}
.btn-p{background:var(--teal);color:#fff}.btn-p:hover{background:var(--teal2)}
.btn-d{background:transparent;color:var(--red);border:1px solid var(--red)}.btn-d:hover{background:var(--red);color:#fff}
.btn-o{background:transparent;border:1px solid var(--border);color:var(--ink)}.btn-o:hover{background:var(--cream)}
.btn-sm{padding:.3rem .85rem;font-size:.78rem}
.fe{display:flex;justify-content:flex-end;margin-top:1rem}
table{width:100%;border-collapse:collapse;font-size:.88rem}
thead tr{border-bottom:2px solid var(--ink)}
th{padding:.65rem 1rem;text-align:left;font-size:.73rem;text-transform:uppercase;letter-spacing:.07em;color:#555;font-weight:600}
tbody tr{border-bottom:1px solid var(--cream);transition:background .15s}
tbody tr:hover{background:var(--cream)}
td{padding:.7rem 1rem}
.bx{display:inline-block;padding:.18rem .65rem;border-radius:99px;font-size:.7rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.empty{text-align:center;padding:3rem;color:#888;font-size:.88rem}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:1.8rem}
@media(max-width:720px){.grid2{grid-template-columns:1fr}}
#toast{position:fixed;bottom:2rem;right:2rem;background:var(--ink);color:#fff;padding:.85rem 1.4rem;border-radius:2px;font-size:.87rem;box-shadow:var(--sh);transform:translateY(200%);transition:transform .3s;z-index:9999;border-left:4px solid var(--teal);max-width:320px}
#toast.show{transform:translateY(0)}
#toast.err{border-left-color:var(--red)}
.seg{display:flex;gap:0;border:1px solid var(--border);border-radius:2px;overflow:hidden;margin-bottom:1.4rem}
.seg button{flex:1;padding:.55rem;border:none;background:#fff;font-family:inherit;font-size:.85rem;font-weight:500;cursor:pointer;transition:background .15s,color .15s;border-right:1px solid var(--border)}
.seg button:last-child{border-right:none}
.seg button.active{background:var(--teal);color:#fff;font-weight:600}
.section{display:none}.section.on{display:block}

/* ── BUSY MODAL ─────────────────────────────────────────────── */
#busyOverlay{
  position:fixed;inset:0;background:rgba(15,17,23,.55);backdrop-filter:blur(3px);
  z-index:10000;display:flex;align-items:center;justify-content:center;
  opacity:0;pointer-events:none;transition:opacity .25s;
}
#busyOverlay.show{opacity:1;pointer-events:all;}
#busyModal{
  background:#fff;border-radius:4px;max-width:420px;width:90%;
  box-shadow:0 20px 60px rgba(15,17,23,.28);
  overflow:hidden;transform:translateY(18px) scale(.97);
  transition:transform .25s cubic-bezier(.34,1.56,.64,1);
}
#busyOverlay.show #busyModal{transform:translateY(0) scale(1);}
.busy-header{
  background:var(--red);color:#fff;padding:1.1rem 1.4rem;
  display:flex;align-items:center;gap:.7rem;
}
.busy-header svg{flex-shrink:0;}
.busy-header h3{font-family:'DM Serif Display',serif;font-size:1.2rem;font-weight:400;}
.busy-body{padding:1.3rem 1.4rem;}
.busy-body p{font-size:.9rem;color:#444;line-height:1.6;margin-bottom:1rem;}
.busy-slot{
  background:var(--cream);border:1px solid var(--border);border-radius:2px;
  padding:.8rem 1rem;font-size:.85rem;display:grid;
  grid-template-columns:auto 1fr;gap:.35rem .8rem;
}
.busy-slot .lbl{font-weight:600;font-size:.73rem;text-transform:uppercase;letter-spacing:.05em;color:#666;}
.busy-slot .val{color:var(--ink);}
.busy-footer{padding:.9rem 1.4rem;display:flex;justify-content:flex-end;gap:.6rem;border-top:1px solid var(--cream);}

/* ── ON-LEAVE MODAL ─────────────────────────────────────────── */
#leaveOverlay{
  position:fixed;inset:0;background:rgba(15,17,23,.55);backdrop-filter:blur(3px);
  z-index:10000;display:flex;align-items:center;justify-content:center;
  opacity:0;pointer-events:none;transition:opacity .25s;
}
#leaveOverlay.show{opacity:1;pointer-events:all;}
#leaveModal{
  background:#fff;border-radius:4px;max-width:400px;width:90%;
  box-shadow:0 20px 60px rgba(15,17,23,.28);overflow:hidden;
  transform:translateY(18px) scale(.97);
  transition:transform .25s cubic-bezier(.34,1.56,.64,1);
}
#leaveOverlay.show #leaveModal{transform:translateY(0) scale(1);}
.leave-header{
  background:#8b4513;color:#fff;padding:1.1rem 1.4rem;
  display:flex;align-items:center;gap:.7rem;
}
.leave-header svg{flex-shrink:0;}
.leave-header h3{font-family:'DM Serif Display',serif;font-size:1.2rem;font-weight:400;}
.leave-body{padding:1.3rem 1.4rem;}
.leave-body p{font-size:.9rem;color:#444;line-height:1.6;margin-bottom:1rem;}
.leave-info{
  background:#fdf6ee;border:1px solid #e8d5b7;border-radius:2px;
  padding:.8rem 1rem;font-size:.85rem;display:grid;
  grid-template-columns:auto 1fr;gap:.35rem .8rem;
}
.leave-info .lbl{font-weight:600;font-size:.73rem;text-transform:uppercase;letter-spacing:.05em;color:#7a5c30;}
.leave-info .val{color:var(--ink);}
.leave-footer{padding:.9rem 1.4rem;display:flex;justify-content:flex-end;gap:.6rem;border-top:1px solid var(--cream);}
</style>"""

NAV = """<nav>
  <span class="brand">SPYM <span>Health</span></span>
  <div class="nav-links">
    <a href="/" id="n-home">Home</a>
    <a href="/patients" id="n-p">Patients</a>
    <a href="/appointments" id="n-a">Appointments</a>
    <a href="/leave-management" id="n-l">Leave</a>
    <a href="/service-requests" id="n-r">Requests</a>
  </div>
</nav>
<div id="toast"></div>

<!-- DOCTOR BUSY MODAL -->
<div id="busyOverlay">
  <div id="busyModal">
    <div class="busy-header">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><circle cx="12" cy="16" r=".5" fill="currentColor"/>
      </svg>
      <h3>Doctor Unavailable</h3>
    </div>
    <div class="busy-body">
      <p>This doctor already has an appointment scheduled within the <strong>30-minute window</strong> of your selected time. Please choose a different time slot.</p>
      <div class="busy-slot" id="busySlotDetails">
        <span class="lbl">Doctor</span>   <span class="val" id="bDoctor">—</span>
        <span class="lbl">Date</span>     <span class="val" id="bDate">—</span>
        <span class="lbl">Booked at</span><span class="val" id="bTime">—</span>
        <span class="lbl">Patient</span>  <span class="val" id="bPatient">—</span>
      </div>
    </div>
    <div class="busy-footer">
      <button class="btn btn-o" onclick="closeBusyModal()">Choose Different Time</button>
    </div>
  </div>
</div>

<!-- DOCTOR ON LEAVE MODAL -->
<div id="leaveOverlay">
  <div id="leaveModal">
    <div class="leave-header">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="9" y1="15" x2="15" y2="15"/>
      </svg>
      <h3>Doctor on Leave</h3>
    </div>
    <div class="leave-body">
      <p>This doctor is on <strong>approved leave</strong> on the selected date. Please choose a different date or doctor.</p>
      <div class="leave-info">
        <span class="lbl">Doctor</span>  <span class="val" id="lDoctor">—</span>
        <span class="lbl">Date</span>    <span class="val" id="lDate">—</span>
        <span class="lbl">Reason</span>  <span class="val" id="lReason">—</span>
      </div>
    </div>
    <div class="leave-footer">
      <button class="btn btn-o" onclick="closeLeaveModal()">Choose Different Date</button>
    </div>
  </div>
</div>

<script>
function toast(msg,isErr){const t=document.getElementById('toast');t.textContent=msg;t.className='show'+(isErr?' err':'');clearTimeout(t._t);t._t=setTimeout(()=>t.className='',3200);}
const p=location.pathname;
if(p==='/'||p==='/home')document.getElementById('n-home').classList.add('on');
else if(p==='/patients')document.getElementById('n-p').classList.add('on');
else if(p.startsWith('/appointments'))document.getElementById('n-a').classList.add('on');
else if(p.startsWith('/leave-management'))document.getElementById('n-l').classList.add('on');
else if(p.startsWith('/service-requests'))document.getElementById('n-r').classList.add('on');

function showBusyModal(conflict) {
  document.getElementById('bDoctor').textContent  = conflict.doctor_name  || conflict.doctor_id  || '—';
  document.getElementById('bDate').textContent    = conflict.appointment_date || '—';
  document.getElementById('bTime').textContent    = conflict.appointment_time || '—';
  document.getElementById('bPatient').textContent = conflict.patient_name || conflict.patient_id || '—';
  document.getElementById('busyOverlay').classList.add('show');
}
function closeBusyModal() {
  document.getElementById('busyOverlay').classList.remove('show');
}
document.getElementById('busyOverlay').addEventListener('click', function(e){
  if(e.target === this) closeBusyModal();
});

function showLeaveModal(info) {
  document.getElementById('lDoctor').textContent = info.doctor_name || info.doctor_id || '—';
  document.getElementById('lDate').textContent   = info.leave_date || '—';
  document.getElementById('lReason').textContent = info.reason || 'No reason specified';
  document.getElementById('leaveOverlay').classList.add('show');
}
function closeLeaveModal() {
  document.getElementById('leaveOverlay').classList.remove('show');
}
document.getElementById('leaveOverlay').addEventListener('click', function(e){
  if(e.target === this) closeLeaveModal();
});
</script>"""


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE — HOME
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/')
def page_home():
    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SPYM Health — Home</title>{BASE_CSS}
<style>
.home-hero{{
  background:linear-gradient(135deg,#1a5c35 0%,#2d8653 40%,#52b788 75%,#74c69d 100%);
  padding:4rem 2.5rem 3.5rem;color:#fff;text-align:center;
  position:relative;overflow:hidden;
}}
.home-hero::before{{
  content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse at 70% 30%,rgba(255,255,255,.08) 0%,transparent 60%);
  pointer-events:none;
}}
.home-hero h1{{font-family:'DM Serif Display',serif;font-size:3rem;letter-spacing:-.01em;line-height:1.1}}
.home-hero h1 em{{font-style:italic;color:#b7e4c7}}
.home-hero p{{margin-top:.9rem;font-size:1.05rem;opacity:.88;max-width:560px;margin-left:auto;margin-right:auto}}
.portals{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.6rem;margin-top:2.5rem}}
.portal-card{{
  background:#fff;border-radius:10px;overflow:hidden;
  box-shadow:0 6px 32px rgba(26,92,53,.13);
  transition:transform .22s cubic-bezier(.34,1.56,.64,1),box-shadow .22s;
  border:1.5px solid rgba(82,183,136,.18);
  display:flex;flex-direction:column;
}}
.portal-card:hover{{transform:translateY(-6px) scale(1.012);box-shadow:0 16px 48px rgba(26,92,53,.2)}}
.portal-icon{{
  padding:2rem 1.5rem 1.2rem;text-align:center;
  background:linear-gradient(135deg,#e8f8ef 0%,#d8f0e4 100%);
}}
.portal-icon svg{{stroke:#2d8653}}
.portal-icon .picon-label{{
  margin-top:.7rem;font-family:'DM Serif Display',serif;
  font-size:1.2rem;color:#1a5c35;
}}
.portal-body{{padding:1rem 1.4rem 1.4rem;flex:1;display:flex;flex-direction:column;}}
.portal-body p{{font-size:.85rem;color:#555;line-height:1.6;flex:1}}
.portal-btn{{
  display:inline-block;margin-top:1rem;padding:.6rem 1.4rem;
  background:linear-gradient(90deg,#2d8653,#52b788);color:#fff;
  border:none;border-radius:6px;font-family:inherit;font-weight:600;
  font-size:.87rem;cursor:pointer;text-decoration:none;text-align:center;
  transition:filter .18s,transform .15s;
}}
.portal-btn:hover{{filter:brightness(1.1);transform:scale(1.03)}}
.stats-bar{{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
  gap:1rem;margin-bottom:2.5rem;
}}
.stat-pill{{
  background:linear-gradient(135deg,#e8f8ef,#d0f0e0);
  border:1px solid #a8dbc0;border-radius:10px;
  padding:1.1rem 1.4rem;text-align:center;
}}
.stat-pill .stat-num{{font-size:2rem;font-weight:700;color:#1a5c35;font-family:'DM Serif Display',serif}}
.stat-pill .stat-label{{font-size:.75rem;color:#3a7a55;font-weight:600;letter-spacing:.06em;text-transform:uppercase;margin-top:.2rem}}
</style>
</head><body>
{NAV}
<div class="home-hero">
  <h1>Welcome to <em>SPYM</em> Health</h1>
  <p>Your integrated hospital management portal — manage patients, doctors, appointments and more from one place.</p>
</div>
<main>
  <!-- Stats Row -->
  <div class="stats-bar" id="statsBar">
    <div class="stat-pill"><div class="stat-num" id="stat-patients">—</div><div class="stat-label">Patients</div></div>
    <div class="stat-pill"><div class="stat-num" id="stat-doctors">—</div><div class="stat-label">Doctors</div></div>
    <div class="stat-pill"><div class="stat-num" id="stat-appts">—</div><div class="stat-label">Appointments</div></div>
    <div class="stat-pill"><div class="stat-num" id="stat-req">—</div><div class="stat-label">Service Requests</div></div>
  </div>

  <!-- Portal Cards -->
  <div class="portals">
    <div class="portal-card">
      <div class="portal-icon">
        <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
        <div class="picon-label">Patients Portal</div>
      </div>
      <div class="portal-body">
        <p>Register new patients, view all patient records, manage demographics and contact information.</p>
        <a href="/patients" class="portal-btn">Open Patients Portal →</a>
      </div>
    </div>
    <div class="portal-card">
      <div class="portal-icon">
        <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/>
          <line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
          <path d="M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01"/>
        </svg>
        <div class="picon-label">Appointments</div>
      </div>
      <div class="portal-body">
        <p>Book and manage appointments, add doctors to the system, view schedules and handle conflicts.</p>
        <a href="/appointments" class="portal-btn">Open Appointments →</a>
      </div>
    </div>
    <div class="portal-card">
      <div class="portal-icon">
        <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          <path d="M9 12l2 2 4-4"/>
        </svg>
        <div class="picon-label">Leave Management</div>
      </div>
      <div class="portal-body">
        <p>Mark and track doctor leave days. Appointments are automatically blocked on approved leave dates.</p>
        <a href="/leave-management" class="portal-btn">Manage Leave →</a>
      </div>
    </div>
    <div class="portal-card">
      <div class="portal-icon">
        <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
        </svg>
        <div class="picon-label">Service Requests</div>
      </div>
      <div class="portal-body">
        <p>Raise and track internal service requests. Monitor status from pending through to resolved.</p>
        <a href="/service-requests" class="portal-btn">View Requests →</a>
      </div>
    </div>
  </div>
</main>
<script>
async function loadStats() {{
  try {{
    const r = await fetch('/api/debug'); const d = await r.json();
    if (d.tables) {{
      document.getElementById('stat-patients').textContent = d.tables.patients ?? '—';
      document.getElementById('stat-doctors').textContent  = d.tables.doctors  ?? '—';
      document.getElementById('stat-appts').textContent    = d.tables.appointments ?? '—';
      document.getElementById('stat-req').textContent      = d.tables.service_requests ?? '—';
    }}
  }} catch(e) {{}}
}}
loadStats();
</script></body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE — PATIENTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/patients')
def page_patients():
    _s = '\\s'
    _d = '\\d'
    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SPYM — Patients</title>{BASE_CSS}</head><body>
{NAV}
<div class="hero" style="background:var(--teal)">
  <h1 style="font-family:'DM Serif Display',serif;font-size:2.2rem">Patient <em style="font-style:italic;color:#a8d8d8">Management</em></h1>
  <p style="margin-top:.6rem;opacity:.8;font-size:.9rem">Register and manage patient records.</p>
</div>
<main>
  <div class="card">
    <div class="ch"><h2>Register New Patient</h2></div>
    <div class="cb">
      <div class="fg">
        <div class="fv"><label>Full Name *</label><input id="pname" placeholder="Ananya Kumar"/></div>
        <div class="fv"><label>Date of Birth</label><input type="date" id="pdob"/></div>
        <div class="fv"><label>Email</label><input type="email" id="pemail" placeholder="patient@email.com"/></div>
        <div class="fv">
          <label>Phone (10 digits) *</label>
          <input id="pphone" type="tel" placeholder="10-digit number" maxlength="10"
            oninput="this.value=this.value.replace(/[^0-9]/g,''); validatePhone(this,'pphone-err')"/>
          <span id="pphone-err" style="color:var(--red);font-size:.75rem;display:none">Phone number must be exactly 10 digits.</span>
        </div>
        <div class="fv"><label>Pincode</label><input id="ppincode" placeholder="e.g. 600001" maxlength="10"/></div>
        <div class="fv"><label>Location / Area</label><input id="pplocation" placeholder="e.g. Anna Nagar, Chennai"/></div>
      </div>
      <p style="font-size:.78rem;color:#888;margin-top:.6rem">Patient ID is auto-assigned from the dataset (e.g. P101, P102).</p>
      <div class="fe"><button class="btn btn-p" onclick="addPatient()">+ Register Patient</button></div>
    </div>
  </div>
  <div class="card">
    <div class="ch"><h2>All Patients</h2><button class="btn btn-o btn-sm" onclick="loadPatients()">Refresh</button></div>
    <div style="overflow-x:auto">
      <table><thead><tr><th>Patient ID</th><th>Name</th><th>Date of Birth</th><th>Email</th><th>Phone</th><th>Pincode</th><th>Location</th><th>Registered</th><th></th></tr></thead>
      <tbody id="ptbody"><tr><td colspan="9" class="empty">Loading...</td></tr></tbody></table>
    </div>
  </div>
</main>
<script>
function validatePhone(input, errId) {{
  const err = document.getElementById(errId);
  // Condition 1: maxlength on input already prevents > 10 chars
  // Condition 2: show error if not exactly 10 digits
  if (input.value.length > 0 && input.value.length < 10) {{
    err.style.display = 'inline';
  }} else {{
    err.style.display = 'none';
  }}
}}
async function loadPatients() {{
  const tb = document.getElementById('ptbody');
  tb.innerHTML = '<tr><td colspan="9" class="empty">Loading...</td></tr>';
  try {{
    const r = await fetch('/api/patients'); const d = await r.json();
    if (!r.ok) {{ tb.innerHTML=`<tr><td colspan="7" class="empty" style="color:var(--red)">Error: ${{d.error}}</td></tr>`; return; }}
    if (!d.length) {{ tb.innerHTML='<tr><td colspan="9" class="empty">No patients yet.</td></tr>'; return; }}
    tb.innerHTML = d.map(p=>`<tr>
      <td><strong>${{p.patient_id}}</strong></td><td>${{p.name}}</td>
      <td>${{p.dob||'—'}}</td><td>${{p.email||'—'}}</td><td>${{p.phone||'—'}}</td>
      <td style="font-size:.82rem">${{p.pincode||'—'}}</td>
      <td style="max-width:140px;font-size:.82rem" title="${{p.location||}}">  ${{p.location?p.location.slice(0,28)+(p.location.length>28?'…':''):'—'}}</td>
      <td style="font-size:.78rem;color:#777">${{(p.created_at||'').slice(0,10)}}</td>
      <td><button class="btn btn-d btn-sm" onclick="delPatient('${{p.patient_id}}')">Delete</button></td>
    </tr>`).join('');
  }} catch(e) {{ tb.innerHTML='<tr><td colspan="9" class="empty" style="color:var(--red)">Cannot reach Flask backend.</td></tr>'; }}
}}
async function addPatient() {{
  const name    = document.getElementById('pname').value.trim();
  const phone   = document.getElementById('pphone').value.trim();
  // Condition 1 (frontend): maxlength="10" on the input blocks >10 digits from being typed
  // Condition 2 (frontend): must be exactly 10 digits before submitting
  if (phone && phone.length !== 10) {{
    toast('Phone number must be exactly 10 digits.', true);
    document.getElementById('pphone-err').style.display = 'inline';
    return;
  }}
  if (!name) {{ toast('Full Name is required.', true); return; }}
  const email = document.getElementById('pemail').value.trim();
  if (email && !email.includes('@')) {{ toast('Enter a valid email address.', true); return; }}
  const payload = {{
    name:     name,
    dob:      document.getElementById('pdob').value,
    email:    email,
    phone:    phone,
    pincode:  document.getElementById('ppincode').value.trim(),
    location: document.getElementById('pplocation').value.trim(),
  }};
  const r = await fetch('/api/patients', {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});
  const d = await r.json();
  if (r.ok) {{
    toast('Patient registered! ID: ' + d.patient_id);
    ['pname','pdob','pemail','pphone','ppincode','pplocation'].forEach(i=>document.getElementById(i).value='');
    document.getElementById('pphone-err').style.display = 'none';
    loadPatients();
  }} else toast('Error: '+d.error, true);
}}
async function delPatient(id) {{
  if (!confirm('Delete patient '+id+'?')) return;
  const r = await fetch('/api/patients/'+id, {{method:'DELETE'}});
  if (r.ok) {{ toast('Deleted.'); loadPatients(); }} else toast('Delete failed.', true);
}}
loadPatients();
</script></body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE — APPOINTMENTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/appointments')
def page_appointments():
    _d = '\\d'
    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>SPYM — Appointments</title>{BASE_CSS}
<style>
.status-scheduled{{background:#d0e4ed;color:#2a4f6e}}
.status-completed{{background:#d0eddc;color:#2a7a4b}}
.status-cancelled{{background:#f5d8d8;color:#b84040}}
</style>
</head><body>
{NAV}
<div class="hero" style="background:#2a4f6e">
  <h1 style="font-family:'DM Serif Display',serif;font-size:2.2rem">Appointment <em style="font-style:italic;color:#a8c8e8">Booking</em></h1>
  <p style="margin-top:.6rem;opacity:.8;font-size:.9rem">Manage appointments, doctors and schedules.</p>
</div>
<main>
  <div class="seg">
    <button class="active" onclick="showTab('book',this)">Book Appointment</button>
    <button onclick="showTab('list',this)">All Appointments</button>
    <button onclick="showTab('doctors',this)">Doctors</button>
  </div>

  <!-- BOOK -->
  <div id="tab-book" class="section on">
    <div class="card">
      <div class="ch"><h2>Book New Appointment</h2></div>
      <div class="cb">
        <div class="fg">
          <div class="fv"><label>Patient *</label>
            <select id="appt_patient"><option value="">— Select Patient —</option></select></div>
          <div class="fv"><label>Doctor *</label>
            <select id="appt_doctor" onchange="onDoctorChange()"><option value="">— Select Doctor —</option></select></div>
          <div class="fv"><label>Specialty</label>
            <input id="appt_specialty" readonly placeholder="Auto-filled" style="background:#f0f0f0"/></div>
          <div class="fv"><label>Appointment Date *</label>
            <input type="date" id="appt_date"/></div>
          <div class="fv"><label>Appointment Time *</label>
            <input type="time" id="appt_time"/></div>
          <div class="fv"><label>Status</label>
            <select id="appt_status">
              <option value="scheduled">Scheduled</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select></div>
          <div class="fv"><label>Pincode *</label>
            <input id="appt_pincode" placeholder="e.g. 600001" maxlength="10"/></div>
          <div class="fv"><label>Location / Area *</label>
            <input id="appt_location" placeholder="e.g. Anna Nagar, Chennai"/></div>
          <div class="fv" style="grid-column:1/-1"><label>Notes / Reason for Visit</label>
            <textarea id="appt_notes" placeholder="Symptoms, reason for visit, special instructions..." style="min-height:90px"></textarea></div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:1rem">
          <span id="appt_msg" style="font-size:.83rem;color:var(--red)"></span>
          <div style="display:flex;gap:.7rem">
            <button class="btn btn-o" onclick="clearForm()">Clear</button>
            <button class="btn btn-p" onclick="bookAppointment()">Book Appointment</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- LIST -->
  <div id="tab-list" class="section">
    <div class="card">
      <div class="ch">
        <h2>All Appointments</h2>
        <div style="display:flex;gap:.6rem;align-items:center">
          <select id="filter_status" onchange="loadAppointments()" style="font-size:.8rem;padding:.3rem .6rem">
            <option value="">All Statuses</option>
            <option value="scheduled">Scheduled</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <button class="btn btn-o btn-sm" onclick="loadAppointments()">Refresh</button>
        </div>
      </div>
      <div style="overflow-x:auto">
        <table><thead><tr><th>#</th><th>Patient</th><th>Doctor</th><th>Specialty</th><th>Date</th><th>Time</th><th>Pincode</th><th>Location</th><th>Notes</th><th>Status</th><th></th></tr></thead>
        <tbody id="appt_tbody"><tr><td colspan="11" class="empty">Loading...</td></tr></tbody></table>
      </div>
    </div>
  </div>

  <!-- DOCTORS -->
  <div id="tab-doctors" class="section">
    <div class="grid2">
      <div class="card">
        <div class="ch"><h2>Add Doctor</h2></div>
        <div class="cb">
          <div class="fg" style="grid-template-columns:1fr 1fr">
            <div class="fv"><label>Full Name *</label><input id="dname" placeholder="Dr. Rajan Mehta"/></div>
            <div class="fv"><label>Specialty</label><input id="dspec" placeholder="Cardiology"/></div>
            <div class="fv"><label>Email</label><input id="demail" placeholder="dr@spym.com"/></div>
            <div class="fv">
              <label>Phone (10 digits)</label>
              <input id="dphone" type="tel" placeholder="10-digit number" maxlength="10"
                oninput="this.value=this.value.replace(/[^0-9]/g,''); validateDPhone(this)"/>
              <span id="dphone-err" style="color:var(--red);font-size:.75rem;display:none">Phone number must be exactly 10 digits.</span>
            </div>
          </div>
          <p style="font-size:.78rem;color:#888;margin-top:.6rem">Doctor ID is auto-assigned from the dataset (e.g. D1, D2).</p>
          <div class="fe"><button class="btn btn-p" onclick="addDoctor()">+ Add Doctor</button></div>
        </div>
      </div>
      <div class="card">
        <div class="ch"><h2>Doctors on Record</h2><button class="btn btn-o btn-sm" onclick="loadDoctors()">Refresh</button></div>
        <div style="overflow-x:auto">
          <table><thead><tr><th>ID</th><th>Name</th><th>Specialty</th><th>Email</th><th>Phone</th></tr></thead>
          <tbody id="doc_tbody"><tr><td colspan="5" class="empty">Loading...</td></tr></tbody></table>
        </div>
      </div>
    </div>
  </div>
</main>
<script>
function showTab(name, btn) {{
  document.querySelectorAll('.section').forEach(s=>s.classList.remove('on'));
  document.querySelectorAll('.seg button').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('on');
  btn.classList.add('active');
  if(name==='list') loadAppointments();
  if(name==='doctors') loadDoctors();
}}

let doctorMap = {{}};
async function loadDropdowns() {{
  const [pr,dr] = await Promise.all([fetch('/api/patients').then(r=>r.json()), fetch('/api/doctors').then(r=>r.json())]);
  document.getElementById('appt_patient').innerHTML = '<option value="">— Select Patient —</option>' +
    pr.map(p=>`<option value="${{p.patient_id}}">${{p.patient_id}} — ${{p.name}}</option>`).join('');
  document.getElementById('appt_doctor').innerHTML = '<option value="">— Select Doctor —</option>' +
    dr.map(d=>`<option value="${{d.doctor_id}}">${{d.name}}</option>`).join('');
  doctorMap = {{}};
  dr.forEach(d=>doctorMap[d.doctor_id]=d);
}}

function onDoctorChange() {{
  const doc = doctorMap[document.getElementById('appt_doctor').value];
  document.getElementById('appt_specialty').value = doc ? (doc.specialty||'') : '';
}}

async function bookAppointment() {{
  const msg = document.getElementById('appt_msg');
  const payload = {{
    patient_id:       document.getElementById('appt_patient').value,
    doctor_id:        document.getElementById('appt_doctor').value,
    appointment_date: document.getElementById('appt_date').value,
    appointment_time: document.getElementById('appt_time').value || null,
    status:           document.getElementById('appt_status').value,
    notes:            document.getElementById('appt_notes').value.trim(),
    pincode:          document.getElementById('appt_pincode').value.trim(),
    location:         document.getElementById('appt_location').value.trim(),
  }};
  if (!payload.patient_id) {{ toast('Please select a patient.', true); return; }}
  if (!payload.doctor_id)  {{ toast('Please select a doctor.', true); return; }}
  if (!payload.appointment_date) {{ toast('Please pick a date.', true); return; }}
  if (!payload.appointment_time) {{ toast('Please pick a time — required for conflict checking.', true); return; }}
  if (!payload.pincode)  {{ toast('Please enter a pincode.', true); return; }}
  if (!payload.location) {{ toast('Please enter a location.', true); return; }}
  msg.textContent = 'Checking availability...';
  try {{
    const r = await fetch('/api/appointments', {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});
    const d = await r.json();
    if (r.status === 423 && d.error === 'DOCTOR_ON_LEAVE') {{
      msg.textContent = '';
      showLeaveModal(d.leave);
      return;
    }}
    if (r.status === 409 && d.error === 'DOCTOR_BUSY') {{
      msg.textContent = '';
      showBusyModal(d.conflict);
      return;
    }}
    if (r.ok) {{ toast('Appointment #'+d.id+' booked!'); msg.textContent=''; clearForm(); }}
    else {{ msg.textContent='Error: '+(d.error||'unknown'); toast('Failed: '+(d.error||''), true); }}
  }} catch(e) {{ msg.textContent='Network error'; toast('Network error', true); }}
}}

function clearForm() {{
  document.getElementById('appt_patient').value='';
  document.getElementById('appt_doctor').value='';
  document.getElementById('appt_specialty').value='';
  document.getElementById('appt_date').value='';
  document.getElementById('appt_time').value='';
  document.getElementById('appt_status').value='scheduled';
  document.getElementById('appt_notes').value='';
  document.getElementById('appt_pincode').value='';
  document.getElementById('appt_location').value='';
}}

async function loadAppointments() {{
  const tb = document.getElementById('appt_tbody');
  tb.innerHTML = '<tr><td colspan="11" class="empty">Loading...</td></tr>';
  const filter = document.getElementById('filter_status').value;
  try {{
    const r = await fetch('/api/appointments'); const data = await r.json();
    if (!r.ok) {{ tb.innerHTML=`<tr><td colspan="9" class="empty" style="color:var(--red)">Error: ${{data.error}}</td></tr>`; return; }}
    const rows = filter ? data.filter(a=>a.status===filter) : data;
    if (!rows.length) {{ tb.innerHTML='<tr><td colspan="11" class="empty">No appointments found.</td></tr>'; return; }}
    tb.innerHTML = rows.map(a=>`<tr>
      <td style="color:#888;font-size:.78rem">#${{a.id}}</td>
      <td><strong>${{a.patient_id}}</strong><br/><span style="font-size:.76rem;color:#666">${{a.patient_name||''}}</span></td>
      <td>${{a.doctor_name||a.doctor_id}}</td>
      <td style="font-size:.78rem;color:#666">${{a.specialty||'—'}}</td>
      <td>${{a.appointment_date||'—'}}</td>
      <td>${{a.appointment_time||'—'}}</td>
      <td style="font-size:.82rem">${{a.pincode||'—'}}</td>
      <td style="max-width:140px;font-size:.82rem" title="${{a.location||''}}">${{a.location?a.location.slice(0,28)+(a.location.length>28?'…':''):'—'}}</td>
      <td style="max-width:160px;font-size:.8rem" title="${{a.notes||''}}">${{a.notes?a.notes.slice(0,40)+(a.notes.length>40?'…':''):'—'}}</td>
      <td><select onchange="updateStatus(${{a.id}},this.value)" class="bx status-${{a.status}}" style="font-size:.78rem;padding:.25rem .5rem;border-radius:99px;border:none;font-weight:600;cursor:pointer">
        <option ${{a.status==='scheduled'?'selected':''}}>scheduled</option>
        <option ${{a.status==='completed'?'selected':''}}>completed</option>
        <option ${{a.status==='cancelled'?'selected':''}}>cancelled</option>
      </select></td>
      <td><button class="btn btn-d btn-sm" onclick="deleteAppt(${{a.id}})">Delete</button></td>
    </tr>`).join('');
  }} catch(e) {{ tb.innerHTML='<tr><td colspan="11" class="empty" style="color:var(--red)">Cannot reach Flask backend.</td></tr>'; }}
}}

async function updateStatus(id,status) {{
  const r = await fetch('/api/appointments/'+id,{{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{status}})}});
  if(r.ok) toast('Status updated.'); else toast('Update failed.', true);
}}

async function deleteAppt(id) {{
  if (!confirm('Delete appointment #'+id+'?')) return;
  const r = await fetch('/api/appointments/'+id,{{method:'DELETE'}});
  if(r.ok) {{ toast('Deleted.'); loadAppointments(); }} else toast('Failed.', true);
}}

async function loadDoctors() {{
  const tb = document.getElementById('doc_tbody');
  const r = await fetch('/api/doctors'); const d = await r.json();
  tb.innerHTML = d.length ? d.map(doc=>`<tr>
    <td><strong>${{doc.doctor_id}}</strong></td><td>${{doc.name}}</td>
    <td>${{doc.specialty||'—'}}</td><td>${{doc.email||'—'}}</td><td>${{doc.phone||'—'}}</td>
  </tr>`).join('') : '<tr><td colspan="5" class="empty">No doctors yet.</td></tr>';
}}

async function addDoctor() {{
  const phone = document.getElementById('dphone').value.trim();
  // Condition 1 (frontend): maxlength="10" blocks >10 digits
  // Condition 2 (frontend): must be exactly 10 digits
  if (phone && phone.length !== 10) {{
    toast('Phone number must be exactly 10 digits.', true);
    document.getElementById('dphone-err').style.display = 'inline';
    return;
  }}
  const payload = {{
    name:      document.getElementById('dname').value.trim(),
    specialty: document.getElementById('dspec').value.trim(),
    email:     document.getElementById('demail').value.trim(),
    phone:     phone,
  }};
  if (!payload.name) {{ toast('Doctor Name is required.', true); return; }}
  const r = await fetch('/api/doctors',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}});
  const d = await r.json();
  if(r.ok) {{
    toast('Doctor added! ID: ' + d.doctor_id);
    ['dname','dspec','demail','dphone'].forEach(i=>document.getElementById(i).value='');
    document.getElementById('dphone-err').style.display = 'none';
    loadDoctors(); loadDropdowns();
  }}
  else toast('Error: '+d.error, true);
}}

function validateDPhone(input) {{
  const err = document.getElementById('dphone-err');
  if (input.value.length > 0 && input.value.length < 10) {{
    err.style.display = 'inline';
  }} else {{
    err.style.display = 'none';
  }}
}}

document.getElementById('appt_date').min = new Date().toISOString().split('T')[0];
loadDropdowns();
</script></body></html>"""




# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE — LEAVE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/leave-management')
def page_leave_management():
    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>HCL — Leave Management</title>{BASE_CSS}
<style>
.leave-badge{{display:inline-block;padding:.18rem .7rem;border-radius:99px;font-size:.7rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;background:#fdf0e0;color:#8b4513;border:1px solid #e8c98a}}
.cal-grid{{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-top:.6rem}}
.cal-day{{padding:.45rem .3rem;text-align:center;font-size:.78rem;border-radius:2px;cursor:default;background:var(--cream)}}
.cal-day.leave{{background:#8b4513;color:#fff;font-weight:700;border-radius:2px}}
.cal-day.today{{outline:2px solid var(--teal);outline-offset:1px}}
.cal-day.empty{{background:transparent}}
.cal-hdr{{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-top:.8rem}}
.cal-hdr span{{text-align:center;font-size:.68rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#888;padding:.3rem 0}}
</style>
</head><body>
{NAV}
<div class="hero" style="background:#6b3a1f">
  <h1 style="font-family:'DM Serif Display',serif;font-size:2.2rem">Doctor <em style="font-style:italic;color:#f0c890">Leave</em> Management</h1>
  <p style="margin-top:.6rem;opacity:.8;font-size:.9rem">Mark, review and manage doctor leave days. Appointments are blocked on leave dates.</p>
</div>
<main>
  <div class="grid2">
    <!-- LEFT: Add Leave -->
    <div>
      <div class="card">
        <div class="ch"><h2>Mark Leave</h2></div>
        <div class="cb">
          <div class="fg" style="grid-template-columns:1fr">
            <div class="fv"><label>Doctor *</label>
              <select id="lv_doctor"><option value="">— Select Doctor —</option></select></div>
            <div class="fv"><label>Leave Type</label>
              <select id="lv_type" onchange="toggleLeaveType()">
                <option value="single">Single Day</option>
                <option value="range">Date Range</option>
              </select></div>
            <div class="fv" id="lv_single_wrap"><label>Leave Date *</label>
              <input type="date" id="lv_date"/></div>
            <div id="lv_range_wrap" style="display:none">
              <div class="fg" style="grid-template-columns:1fr 1fr;margin-bottom:.5rem">
                <div class="fv"><label>From Date *</label><input type="date" id="lv_from"/></div>
                <div class="fv"><label>To Date *</label><input type="date" id="lv_to"/></div>
              </div>
            </div>
            <div class="fv"><label>Reason</label>
              <input id="lv_reason" placeholder="e.g. Annual leave, Medical, Conference"/></div>
          </div>
          <div class="fe" style="margin-top:1rem">
            <button class="btn btn-p" onclick="addLeave()" style="background:#6b3a1f">Mark as Leave</button>
          </div>
        </div>
      </div>

      <!-- Calendar preview -->
      <div class="card" id="cal_card" style="display:none">
        <div class="ch">
          <h2 id="cal_title">Leave Calendar</h2>
          <div style="display:flex;gap:.5rem;align-items:center">
            <button class="btn btn-o btn-sm" onclick="calPrev()">&#8249;</button>
            <span id="cal_month_label" style="font-size:.85rem;font-weight:600;min-width:100px;text-align:center"></span>
            <button class="btn btn-o btn-sm" onclick="calNext()">&#8250;</button>
          </div>
        </div>
        <div class="cb">
          <div class="cal-hdr"><span>Sun</span><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span></div>
          <div class="cal-grid" id="cal_grid"></div>
          <p style="font-size:.75rem;color:#888;margin-top:.8rem">&#9608; Leave day &nbsp; <span style="outline:2px solid var(--teal);outline-offset:1px;padding:0 4px">T</span> Today</p>
        </div>
      </div>
    </div>

    <!-- RIGHT: Leave Records -->
    <div>
      <div class="card">
        <div class="ch">
          <h2>Leave Records</h2>
          <div style="display:flex;gap:.6rem;align-items:center">
            <select id="lv_filter_doc" onchange="loadLeaves()" style="font-size:.8rem;padding:.3rem .6rem">
              <option value="">All Doctors</option>
            </select>
            <button class="btn btn-o btn-sm" onclick="loadLeaves()">Refresh</button>
          </div>
        </div>
        <div style="overflow-x:auto">
          <table><thead><tr><th>#</th><th>Doctor</th><th>Leave Date</th><th>Day</th><th>Reason</th><th>Marked On</th><th></th></tr></thead>
          <tbody id="lv_tbody"><tr><td colspan="7" class="empty">Loading...</td></tr></tbody></table>
        </div>
      </div>
    </div>
  </div>
</main>
<script>
const DAYS = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
let calYear, calMonth, calLeaveDates = [];

function toggleLeaveType() {{
  const t = document.getElementById('lv_type').value;
  document.getElementById('lv_single_wrap').style.display = t==='single'?'':'none';
  document.getElementById('lv_range_wrap').style.display  = t==='range'?'':'none';
}}

async function loadDoctorDropdowns() {{
  const r = await fetch('/api/doctors'); const doctors = await r.json();
  const opts = '<option value="">— Select Doctor —</option>' +
    doctors.map(d=>`<option value="${{d.doctor_id}}">${{d.name}}</option>`).join('');
  document.getElementById('lv_doctor').innerHTML = opts;
  const filterOpts = '<option value="">All Doctors</option>' +
    doctors.map(d=>`<option value="${{d.doctor_id}}">${{d.name}}</option>`).join('');
  document.getElementById('lv_filter_doc').innerHTML = filterOpts;
}}

async function addLeave() {{
  const doctor_id = document.getElementById('lv_doctor').value;
  const type      = document.getElementById('lv_type').value;
  const reason    = document.getElementById('lv_reason').value.trim();
  if (!doctor_id) {{ toast('Please select a doctor.', true); return; }}

  let dates = [];
  if (type === 'single') {{
    const d = document.getElementById('lv_date').value;
    if (!d) {{ toast('Please select a leave date.', true); return; }}
    dates = [d];
  }} else {{
    const from = document.getElementById('lv_from').value;
    const to   = document.getElementById('lv_to').value;
    if (!from || !to) {{ toast('Please select from and to dates.', true); return; }}
    if (from > to) {{ toast('From date must be before To date.', true); return; }}
    // expand range
    let cur = new Date(from);
    const end = new Date(to);
    while (cur <= end) {{
      dates.push(cur.toISOString().split('T')[0]);
      cur.setDate(cur.getDate()+1);
    }}
  }}

  let added=0, skipped=0;
  for (const leave_date of dates) {{
    const r = await fetch('/api/doctor-leaves', {{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{doctor_id, leave_date, reason}})
    }});
    if (r.ok) added++; else skipped++;
  }}

  if (added) toast(`${{added}} leave day(s) marked!`);
  if (skipped) toast(`${{skipped}} day(s) already existed — skipped.`, true);
  loadLeaves();
  const docSel = document.getElementById('lv_doctor');
  const docId  = docSel.value;
  const docName = docSel.options[docSel.selectedIndex]?.text || '';
  loadCalendar(docId, docName);
}}

async function deleteLeave(id) {{
  if (!confirm('Remove this leave day?')) return;
  const r = await fetch('/api/doctor-leaves/'+id, {{method:'DELETE'}});
  if (r.ok) {{ toast('Leave removed.'); loadLeaves(); renderCalendar(); }}
  else toast('Failed to remove.', true);
}}

async function loadLeaves() {{
  const tb = document.getElementById('lv_tbody');
  tb.innerHTML = '<tr><td colspan="7" class="empty">Loading...</td></tr>';
  const filter = document.getElementById('lv_filter_doc').value;
  const url = filter ? `/api/doctor-leaves?doctor_id=${{filter}}` : '/api/doctor-leaves';
  try {{
    const r = await fetch(url); const data = await r.json();
    if (!r.ok) {{ tb.innerHTML=`<tr><td colspan="7" class="empty" style="color:var(--red)">Error: ${{data.error}}</td></tr>`; return; }}
    if (!data.length) {{ tb.innerHTML='<tr><td colspan="7" class="empty">No leave records found.</td></tr>'; return; }}
    tb.innerHTML = data.map(lv => {{
      const dt = new Date(lv.leave_date+'T00:00:00');
      const dayName = DAYS[dt.getDay()];
      return `<tr>
        <td style="color:#888;font-size:.78rem">#${{lv.id}}</td>
        <td><strong>${{lv.doctor_name||lv.doctor_id}}</strong><br/><span style="font-size:.74rem;color:#888">${{lv.specialty||''}}</span></td>
        <td><span class="leave-badge">${{lv.leave_date}}</span></td>
        <td style="font-size:.82rem">${{dayName}}</td>
        <td style="font-size:.82rem;color:#555">${{lv.reason||'—'}}</td>
        <td style="font-size:.76rem;color:#777">${{(lv.created_at||'').slice(0,10)}}</td>
        <td><button class="btn btn-d btn-sm" onclick="deleteLeave(${{lv.id}})">Remove</button></td>
      </tr>`;
    }}).join('');
  }} catch(e) {{ tb.innerHTML='<tr><td colspan="7" class="empty" style="color:var(--red)">Cannot reach backend.</td></tr>'; }}
}}

// ── Calendar ──────────────────────────────────────────────────────────────────
async function loadCalendar(doctorId, doctorName) {{
  if (!doctorId) return;
  const now = new Date();
  calYear  = calYear  || now.getFullYear();
  calMonth = calMonth || now.getMonth();
  const r = await fetch(`/api/doctor-leaves?doctor_id=${{doctorId}}`);
  const data = await r.json();
  calLeaveDates = (data||[]).map(lv=>lv.leave_date);
  document.getElementById('cal_card').style.display = '';
  document.getElementById('cal_title').textContent = `${{doctorName}}'s Leave Calendar`;
  renderCalendar();
}}

function renderCalendar() {{
  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];
  const firstDay = new Date(calYear, calMonth, 1).getDay();
  const daysInMonth = new Date(calYear, calMonth+1, 0).getDate();
  document.getElementById('cal_month_label').textContent = `${{MONTHS[calMonth]}} ${{calYear}}`;
  let cells = '';
  for (let i=0;i<firstDay;i++) cells += '<div class="cal-day empty"></div>';
  for (let d=1;d<=daysInMonth;d++) {{
    const ds = `${{calYear}}-${{String(calMonth+1).padStart(2,'0')}}-${{String(d).padStart(2,'0')}}`;
    const isLeave = calLeaveDates.includes(ds);
    const isToday = ds===todayStr;
    cells += `<div class="cal-day${{isLeave?' leave':''}}${{isToday?' today':''}}" title="${{isLeave?'On Leave':''}}">${{d}}</div>`;
  }}
  document.getElementById('cal_grid').innerHTML = cells;
}}

function calPrev() {{ calMonth--; if(calMonth<0){{calMonth=11;calYear--;}} renderCalendar(); }}
function calNext() {{ calMonth++; if(calMonth>11){{calMonth=0;calYear++;}} renderCalendar(); }}

document.getElementById('lv_doctor').addEventListener('change', function() {{
  const docId   = this.value;
  const docName = this.options[this.selectedIndex]?.text || '';
  calYear=null; calMonth=null;
  loadCalendar(docId, docName);
  document.getElementById('lv_filter_doc').value = docId;
  loadLeaves();
}});

const today = new Date().toISOString().split('T')[0];
document.getElementById('lv_date').min = today;
document.getElementById('lv_from').min = today;
document.getElementById('lv_to').min   = today;

loadDoctorDropdowns();
loadLeaves();
</script></body></html>"""

# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE — SERVICE REQUESTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/service-requests')
def page_requests():
    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>HCL — Requests</title>{BASE_CSS}</head><body>
{NAV}
<div class="hero" style="background:#5a3a6b">
  <h1 style="font-family:'DM Serif Display',serif;font-size:2.2rem">Service <em style="font-style:italic;color:#d8b8f0">Requests</em></h1>
  <p style="margin-top:.6rem;opacity:.8;font-size:.9rem">Raise and track internal service requests.</p>
</div>
<main>
  <div class="card">
    <div class="ch"><h2>New Request</h2></div>
    <div class="cb">
      <div class="fv" style="margin-bottom:.9rem"><label>Title *</label><input id="rtitle" placeholder="Brief summary"/></div>
      <div class="fv"><label>Description</label><textarea id="rdesc" placeholder="Detailed description..."></textarea></div>
      <div class="fe"><button class="btn btn-p" onclick="submitRequest()" style="background:#5a3a6b">+ Submit Request</button></div>
    </div>
  </div>
  <div class="card">
    <div class="ch"><h2>All Requests</h2><button class="btn btn-o btn-sm" onclick="loadRequests()">Refresh</button></div>
    <div style="overflow-x:auto">
      <table><thead><tr><th>#</th><th>Title</th><th>Description</th><th>Status</th><th>Created</th></tr></thead>
      <tbody id="rtbody"><tr><td colspan="5" class="empty">Loading...</td></tr></tbody></table>
    </div>
  </div>
</main>
<script>
async function loadRequests() {{
  const tb = document.getElementById('rtbody');
  tb.innerHTML = '<tr><td colspan="5" class="empty">Loading...</td></tr>';
  try {{
    const r = await fetch('/api/service-requests'); const d = await r.json();
    if (!r.ok) {{ tb.innerHTML=`<tr><td colspan="5" class="empty" style="color:var(--red)">Error: ${{d.error}}</td></tr>`; return; }}
    if (!d.length) {{ tb.innerHTML='<tr><td colspan="5" class="empty">No requests yet.</td></tr>'; return; }}
    tb.innerHTML = d.map(x=>`<tr>
      <td style="color:#888;font-size:.78rem">#${{x.id}}</td>
      <td><strong>${{x.title}}</strong></td>
      <td style="max-width:260px;font-size:.83rem;color:#555">${{x.description||'—'}}</td>
      <td><select onchange="updateReqStatus(${{x.id}},this.value)" style="font-size:.8rem;padding:.25rem .5rem">
        <option ${{x.status==='pending'?'selected':''}}>pending</option>
        <option ${{x.status==='in_progress'?'selected':''}}>in_progress</option>
        <option ${{x.status==='resolved'?'selected':''}}>resolved</option>
      </select></td>
      <td style="font-size:.78rem;color:#777">${{(x.created_at||'').slice(0,10)}}</td>
    </tr>`).join('');
  }} catch(e) {{ tb.innerHTML='<tr><td colspan="5" class="empty" style="color:var(--red)">Cannot reach Flask backend.</td></tr>'; }}
}}
async function submitRequest() {{
  const title = document.getElementById('rtitle').value.trim();
  const description = document.getElementById('rdesc').value.trim();
  if (!title) {{ toast('Title is required.', true); return; }}
  try {{
    const r = await fetch('/api/service-requests',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{title,description}})}});
    const d = await r.json();
    if(r.ok) {{ toast('Request #'+d.id+' submitted!'); document.getElementById('rtitle').value=''; document.getElementById('rdesc').value=''; loadRequests(); }}
    else toast('Error: '+(d.error||'unknown'), true);
  }} catch(e) {{ toast('Network error: '+e.message, true); }}
}}
async function updateReqStatus(id,status) {{
  const r = await fetch('/api/service-requests/'+id,{{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{status}})}});
  if(r.ok) toast('Status updated.'); else toast('Update failed.', true);
}}
loadRequests();
</script></body></html>"""


# ═══════════════════════════════════════════════════════════════════════════════
#  API — PATIENTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/api/patients', methods=['GET'])
def api_get_patients():
    try:
        rows = q("SELECT * FROM patients ORDER BY patient_id", fetch='all')
        for r in rows:
            r['dob']        = str(r['dob'])        if r.get('dob')        else None
            r['created_at'] = str(r['created_at']) if r.get('created_at') else None
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/patients', methods=['POST'])
def api_add_patient():
    data = flask_request.get_json(silent=True, force=True)
    if not data or not data.get('name'):
        return jsonify({'error': 'name is required'}), 400
    # Phone validation: must be exactly 10 digits if provided
    phone = str(data.get('phone', '') or '').strip()
    if phone:
        if not phone.isdigit() or len(phone) != 10:
            return jsonify({'error': 'Phone number must be exactly 10 digits'}), 400
    if data.get('email') and '@' not in data['email']:
        return jsonify({'error': 'Email must contain @'}), 400
    # Auto-generate patient_id as dataset format (P + next sequential number)
    try:
        existing = q("SELECT patient_id FROM patients WHERE patient_id LIKE 'P%' ORDER BY patient_id", fetch='all')
        nums = []
        for row in existing:
            pid = row['patient_id']
            suffix = pid[1:]
            if suffix.isdigit():
                nums.append(int(suffix))
        next_num = max(nums) + 1 if nums else 108
        patient_id = f'P{next_num}'
        q("INSERT INTO patients (patient_id,name,dob,email,phone,pincode,location) VALUES (%s,%s,%s,%s,%s,%s,%s)",
          (patient_id, data['name'], data.get('dob') or None,
           data.get('email'), phone or None,
           data.get('pincode'), data.get('location')))
        return jsonify({'message': 'Patient added', 'patient_id': patient_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/patients/<pid>', methods=['DELETE'])
def api_del_patient(pid):
    try:
        q("DELETE FROM patients WHERE patient_id=%s", (pid,))
        return jsonify({'message': 'Deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
#  API — DOCTORS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/api/doctors', methods=['GET'])
def api_get_doctors():
    try:
        return jsonify(q("SELECT * FROM doctors ORDER BY name", fetch='all')), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/doctors', methods=['POST'])
def api_add_doctor():
    data = flask_request.get_json(silent=True, force=True)
    if not data or not data.get('name'):
        return jsonify({'error': 'name is required'}), 400
    # Phone validation: must be exactly 10 digits if provided
    phone = str(data.get('phone', '') or '').strip()
    if phone:
        if not phone.isdigit() or len(phone) != 10:
            return jsonify({'error': 'Phone number must be exactly 10 digits'}), 400
    # Auto-generate doctor_id as dataset format (D + next sequential number)
    try:
        existing = q("SELECT doctor_id FROM doctors WHERE doctor_id LIKE 'D%' ORDER BY doctor_id", fetch='all')
        nums = []
        for row in existing:
            did = row['doctor_id']
            suffix = did[1:]
            if suffix.isdigit():
                nums.append(int(suffix))
        next_num = max(nums) + 1 if nums else 6
        doctor_id = f'D{next_num}'
        q("INSERT INTO doctors (doctor_id,name,specialty,email,phone) VALUES (%s,%s,%s,%s,%s)",
          (doctor_id, data['name'], data.get('specialty'),
           data.get('email'), phone or None))
        return jsonify({'message': 'Doctor added', 'doctor_id': doctor_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
#  API — APPOINTMENTS  (with 30-min conflict check)
# ═══════════════════════════════════════════════════════════════════════════════
def safe_appt_rows(rows):
    from datetime import timedelta, date, datetime
    for r in rows:
        # Primary key — handle both 'id' and 'appointment_id'
        if 'appointment_id' in r and 'id' not in r:
            r['id'] = r['appointment_id']
        # Date columns
        for dc in ('appointment_date', 'appt_date'):
            if isinstance(r.get(dc), date):
                r[dc] = r[dc].strftime('%Y-%m-%d')
        # Normalise to 'appointment_date'
        if 'appt_date' in r and 'appointment_date' not in r:
            r['appointment_date'] = r.get('appt_date')
        # Time columns — timedelta fix
        for tc in ('appointment_time', 'appt_time'):
            if isinstance(r.get(tc), timedelta):
                total = int(r[tc].total_seconds())
                h, m = divmod(total // 60, 60)
                r[tc] = f"{h:02d}:{m:02d}"
        if 'appt_time' in r and 'appointment_time' not in r:
            r['appointment_time'] = r.get('appt_time')
        # Timestamp
        if isinstance(r.get('created_at'), datetime):
            r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
    return rows


def check_doctor_conflict(doctor_id, appointment_date, appointment_time, exclude_id=None):
    """
    Returns the conflicting appointment row (dict) if the doctor has a
    *scheduled* appointment whose time window (±30 min) overlaps the
    requested slot, otherwise returns None.
    """
    if not appointment_time:
        return None   # no time supplied → skip conflict check

    cols = [c['Field'] for c in q("SHOW COLUMNS FROM appointments", fetch='all')]
    pk       = 'appointment_id' if 'appointment_id' in cols else 'id'
    date_col = 'appt_date'      if 'appt_date'      in cols else 'appointment_date'
    time_col = 'appt_time'      if 'appt_time'      in cols else 'appointment_time'

    exclude_clause = f"AND a.{pk} != %s" if exclude_id is not None else ""
    params = [doctor_id, appointment_date, appointment_time]
    if exclude_id is not None:
        params.append(exclude_id)

    conflict = q(f"""
        SELECT a.{pk} AS id,
               a.patient_id,
               a.{date_col} AS appointment_date,
               a.{time_col} AS appointment_time,
               a.status,
               p.name AS patient_name,
               d.name AS doctor_name,
               d.specialty
        FROM   appointments a
        JOIN   patients p ON a.patient_id = p.patient_id
        JOIN   doctors  d ON a.doctor_id  = d.doctor_id
        WHERE  a.doctor_id = %s
          AND  a.{date_col} = %s
          AND  a.status     = 'scheduled'
          AND  ABS(TIMESTAMPDIFF(MINUTE,
                   CAST(%s AS TIME),
                   CAST(a.{time_col} AS TIME))) < 30
          {exclude_clause}
        LIMIT 1
    """, tuple(params), fetch='one')

    return conflict


@app.route('/api/appointments', methods=['GET'])
def api_get_appointments():
    try:
        # Detect actual column names
        cols = [c['Field'] for c in q("SHOW COLUMNS FROM appointments", fetch='all')]
        pk        = 'appointment_id' if 'appointment_id' in cols else 'id'
        date_col  = 'appt_date'      if 'appt_date'      in cols else 'appointment_date'
        time_col  = 'appt_time'      if 'appt_time'      in cols else 'appointment_time'
        rows = q(f"""SELECT a.{pk} AS id, a.patient_id, a.doctor_id,
                            a.{date_col} AS appointment_date,
                            a.{time_col} AS appointment_time,
                            a.notes, a.status, a.created_at,
                            a.pincode, a.location,
                            p.name AS patient_name,
                            d.name AS doctor_name, d.specialty
                     FROM appointments a
                     JOIN patients p ON a.patient_id=p.patient_id
                     JOIN doctors  d ON a.doctor_id=d.doctor_id
                     ORDER BY a.{pk} DESC""", fetch='all')
        return jsonify(safe_appt_rows(rows)), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/appointments', methods=['POST'])
def api_book_appointment():
    data = flask_request.get_json(silent=True, force=True)
    if not data or not data.get('patient_id') or not data.get('doctor_id') or not data.get('appointment_date'):
        return jsonify({'error': 'patient_id, doctor_id, appointment_date required'}), 400

    # ── DOCTOR LEAVE CHECK ───────────────────────────────────────────────────
    leave_row = q("""SELECT dl.id, dl.leave_date, dl.reason, d.name AS doctor_name
                     FROM doctor_leaves dl
                     JOIN doctors d ON dl.doctor_id = d.doctor_id
                     WHERE dl.doctor_id = %s AND dl.leave_date = %s
                     LIMIT 1""",
                  (data['doctor_id'], data['appointment_date']), fetch='one')
    if leave_row:
        from datetime import date as _date
        if isinstance(leave_row.get('leave_date'), _date):
            leave_row['leave_date'] = leave_row['leave_date'].strftime('%Y-%m-%d')
        return jsonify({
            'error':   'DOCTOR_ON_LEAVE',
            'message': 'Doctor is on approved leave on this date.',
            'leave':   leave_row,
        }), 423
    # ─────────────────────────────────────────────────────────────────────────

    # ── 30-MINUTE CONFLICT CHECK ──────────────────────────────────────────────
    appt_time = data.get('appointment_time') or None
    if appt_time:
        conflict = check_doctor_conflict(
            doctor_id        = data['doctor_id'],
            appointment_date = data['appointment_date'],
            appointment_time = appt_time,
        )
        if conflict:
            conflict = safe_appt_rows([conflict])[0]
            return jsonify({
                'error':    'DOCTOR_BUSY',
                'message':  'Doctor already has a scheduled appointment within 30 minutes of this slot.',
                'conflict': conflict,
            }), 409
    # ─────────────────────────────────────────────────────────────────────────

    try:
        cols = [c['Field'] for c in q("SHOW COLUMNS FROM appointments", fetch='all')]
        date_col = 'appt_date' if 'appt_date' in cols else 'appointment_date'
        time_col = 'appt_time' if 'appt_time' in cols else 'appointment_time'
        new_id = q(f"INSERT INTO appointments (patient_id,doctor_id,{date_col},{time_col},notes,status,pincode,location) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                   (data['patient_id'], data['doctor_id'], data['appointment_date'],
                    appt_time, data.get('notes'),
                    data.get('status', 'scheduled'),
                    data.get('pincode'), data.get('location')))
        return jsonify({'message': 'Booked', 'id': new_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/appointments/<int:aid>', methods=['PUT'])
def api_update_appt(aid):
    data = flask_request.get_json(silent=True, force=True)
    status = (data or {}).get('status')
    if status not in ('scheduled', 'completed', 'cancelled'):
        return jsonify({'error': 'Invalid status'}), 400
    try:
        cols = [c['Field'] for c in q("SHOW COLUMNS FROM appointments", fetch='all')]
        pk = 'appointment_id' if 'appointment_id' in cols else 'id'
        q(f"UPDATE appointments SET status=%s WHERE {pk}=%s", (status, aid))
        return jsonify({'message': 'Updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/appointments/<int:aid>', methods=['DELETE'])
def api_delete_appt(aid):
    try:
        cols = [c['Field'] for c in q("SHOW COLUMNS FROM appointments", fetch='all')]
        pk = 'appointment_id' if 'appointment_id' in cols else 'id'
        q(f"DELETE FROM appointments WHERE {pk}=%s", (aid,))
        return jsonify({'message': 'Deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500




# ═══════════════════════════════════════════════════════════════════════════════
#  API — DOCTOR LEAVES
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/api/doctor-leaves', methods=['GET'])
def api_get_leaves():
    try:
        doctor_id = flask_request.args.get('doctor_id')
        if doctor_id:
            rows = q("""SELECT dl.id, dl.doctor_id, dl.leave_date, dl.reason, dl.created_at,
                               d.name AS doctor_name, d.specialty
                        FROM doctor_leaves dl
                        JOIN doctors d ON dl.doctor_id = d.doctor_id
                        WHERE dl.doctor_id = %s
                        ORDER BY dl.leave_date""", (doctor_id,), fetch='all')
        else:
            rows = q("""SELECT dl.id, dl.doctor_id, dl.leave_date, dl.reason, dl.created_at,
                               d.name AS doctor_name, d.specialty
                        FROM doctor_leaves dl
                        JOIN doctors d ON dl.doctor_id = d.doctor_id
                        ORDER BY dl.leave_date DESC""", fetch='all')
        from datetime import date, datetime
        for r in rows:
            if isinstance(r.get('leave_date'), date):
                r['leave_date'] = r['leave_date'].strftime('%Y-%m-%d')
            if isinstance(r.get('created_at'), datetime):
                r['created_at'] = r['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doctor-leaves', methods=['POST'])
def api_add_leave():
    data = flask_request.get_json(silent=True, force=True)
    if not data or not data.get('doctor_id') or not data.get('leave_date'):
        return jsonify({'error': 'doctor_id and leave_date are required'}), 400
    try:
        new_id = q("""INSERT INTO doctor_leaves (doctor_id, leave_date, reason)
                      VALUES (%s, %s, %s)""",
                   (data['doctor_id'], data['leave_date'], data.get('reason', '')))
        return jsonify({'message': 'Leave marked', 'id': new_id}), 201
    except Exception as e:
        if 'Duplicate' in str(e) or '1062' in str(e):
            return jsonify({'error': 'Leave already exists for this date'}), 409
        return jsonify({'error': str(e)}), 500


@app.route('/api/doctor-leaves/<int:lid>', methods=['DELETE'])
def api_delete_leave(lid):
    try:
        q("DELETE FROM doctor_leaves WHERE id=%s", (lid,))
        return jsonify({'message': 'Leave removed'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/doctor-leaves/check', methods=['GET'])
def api_check_leave():
    """Returns leave record if doctor is on leave on a given date."""
    doctor_id = flask_request.args.get('doctor_id')
    leave_date = flask_request.args.get('date')
    if not doctor_id or not leave_date:
        return jsonify({'error': 'doctor_id and date required'}), 400
    try:
        from datetime import date, datetime
        row = q("""SELECT dl.id, dl.doctor_id, dl.leave_date, dl.reason,
                          d.name AS doctor_name
                   FROM doctor_leaves dl
                   JOIN doctors d ON dl.doctor_id = d.doctor_id
                   WHERE dl.doctor_id = %s AND dl.leave_date = %s
                   LIMIT 1""", (doctor_id, leave_date), fetch='one')
        if row:
            if isinstance(row.get('leave_date'), date):
                row['leave_date'] = row['leave_date'].strftime('%Y-%m-%d')
            return jsonify({'on_leave': True, 'leave': row}), 200
        return jsonify({'on_leave': False}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════════
#  API — SERVICE REQUESTS
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/api/service-requests', methods=['GET'])
def api_get_service_requests():
    try:
        rows = q("SELECT * FROM service_requests ORDER BY id DESC", fetch='all')
        for r in rows:
            r['created_at'] = str(r['created_at']) if r.get('created_at') else None
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/service-requests', methods=['POST'])
def api_create_service_request():
    data = flask_request.get_json(silent=True, force=True)
    if not data or not str(data.get('title', '')).strip():
        return jsonify({'error': 'title is required'}), 400
    try:
        new_id = q("INSERT INTO service_requests (title,description) VALUES (%s,%s)",
                   (data['title'].strip(), data.get('description', '').strip()))
        return jsonify({'message': 'Request created', 'id': new_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/service-requests/<int:rid>', methods=['PUT'])
def api_update_service_request(rid):
    data = flask_request.get_json(silent=True, force=True)
    status = (data or {}).get('status')
    if status not in ('pending', 'in_progress', 'resolved'):
        return jsonify({'error': 'Invalid status'}), 400
    try:
        q("UPDATE service_requests SET status=%s WHERE id=%s", (status, rid))
        return jsonify({'message': 'Updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
#  DEBUG
# ═══════════════════════════════════════════════════════════════════════════════
@app.route('/api/debug')
def api_debug():
    conn = get_db()
    if not conn:
        return jsonify({'status': 'FAIL', 'error': 'Cannot connect to MySQL'}), 500
    cur = conn.cursor(dictionary=True)
    cur.execute("SHOW TABLES")
    tables = [list(r.values())[0] for r in cur.fetchall()]
    counts = {}
    for t in tables:
        cur.execute(f"SELECT COUNT(*) as c FROM `{t}`")
        counts[t] = cur.fetchone()['c']
    cur.close(); conn.close()
    return jsonify({'status': 'OK', 'database': DB['database'], 'tables': counts}), 200


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("=" * 55)
    print("  SPYM Health — starting up")
    print(f"  DB: {DB['user']}@{DB['host']}/{DB['database']}")
    print("=" * 55)
    init_db()
    print("\n  Open: http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)