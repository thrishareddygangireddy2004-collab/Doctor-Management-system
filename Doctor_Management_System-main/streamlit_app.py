import streamlit as st
import mysql.connector
from mysql.connector import Error
import datetime

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HCL Hospital Management",
    page_icon="🏥",
    layout="wide",
)

# ── DB CONFIG ─────────────────────────────────────────────────────────────────
DB = {
    "host":     "localhost",
    "user":     "root",
    "password": "Prashanth@09112004",
    "database": "hcl",
}

def get_db():
    try:
        return mysql.connector.connect(**DB)
    except Error as e:
        st.error(f"❌ DB connection error: {e}")
        return None

def run_query(sql, params=(), fetch=None):
    conn = get_db()
    if not conn:
        return None
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        if fetch == "all":
            return cur.fetchall()
        if fetch == "one":
            return cur.fetchone()
        conn.commit()
        return True
    except Error as e:
        st.error(f"❌ Query error: {e}")
        return None
    finally:
        cur.close()
        conn.close()

# ── CUSTOM CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ---- Global ---- */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
}

/* White background with dark text for main content */
.stApp {
    background-color: #f5f2eb !important;
}

/* All text dark by default */
p, label, span, div, .stMarkdown, .stText {
    color: #1a1a1a !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* ---- Headings ---- */
h1 {
    font-family: 'DM Serif Display', serif !important;
    color: #1a6b6b !important;
    border-bottom: 3px solid #c5913a;
    padding-bottom: 8px;
    font-size: 2rem !important;
}
h2, h3 {
    font-family: 'DM Serif Display', serif !important;
    color: #144f4f !important;
    font-size: 1.4rem !important;
}

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background: #144f4f !important;
    min-width: 220px !important;
}
section[data-testid="stSidebar"] .stRadio label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #ffffff !important;
    font-size: 1rem !important;
}
section[data-testid="stSidebar"] .stRadio > div {
    gap: 12px;
}
section[data-testid="stSidebar"] .stRadio > div > label {
    background: rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 8px 12px;
    color: #ffffff !important;
    font-weight: 500;
    transition: background 0.2s;
    cursor: pointer;
}
section[data-testid="stSidebar"] .stRadio > div > label:hover {
    background: rgba(255,255,255,0.18);
}

/* ---- Buttons ---- */
.stButton > button {
    background: #1a6b6b !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 0.5rem 1.4rem !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    transition: background 0.2s;
}
.stButton > button:hover {
    background: #144f4f !important;
    color: #ffffff !important;
}

/* ---- Form inputs ---- */
.stTextInput input, .stTextArea textarea, .stSelectbox select,
input[type="text"], input[type="email"], textarea {
    background: #ffffff !important;
    color: #1a1a1a !important;
    border: 1.5px solid #b0aba0 !important;
    border-radius: 6px !important;
    font-size: 0.95rem !important;
}
.stTextInput label, .stTextArea label, .stSelectbox label,
.stDateInput label, .stTimeInput label {
    color: #1a1a1a !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
}

/* ---- Forms / Expanders ---- */
.stForm {
    background: #edeade !important;
    border: 1px solid #c8c4b8 !important;
    border-radius: 10px !important;
    padding: 1.2rem !important;
}
.streamlit-expanderHeader, [data-testid="stExpander"] summary {
    background: #e0ddd4 !important;
    color: #144f4f !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border-radius: 8px !important;
    border: 1px solid #c8c4b8 !important;
    padding: 10px 16px !important;
}

/* ---- Dataframe ---- */
[data-testid="stDataFrame"] {
    border-radius: 8px !important;
    overflow: hidden;
}
[data-testid="stDataFrame"] thead tr th {
    background: #1a6b6b !important;
    color: #ffffff !important;
    font-weight: 700 !important;
}
[data-testid="stDataFrame"] tbody tr:nth-child(even) {
    background: #f0ede4 !important;
}

/* ---- Alerts ---- */
.stAlert {
    border-radius: 8px !important;
}

/* ---- Info boxes ---- */
[data-testid="stInfo"] {
    background: #dff0f0 !important;
    color: #144f4f !important;
    border-left: 4px solid #1a6b6b !important;
}

/* ---- Divider ---- */
hr {
    border-color: #c5913a !important;
    margin: 0.5rem 0 !important;
}
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🏥 HCL Hospital")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["🧑‍⚕️ Patients", "📅 Appointments", "🗓️ Doctor Leaves", "🛠️ Service Requests"],
)
st.sidebar.markdown("---")
st.sidebar.caption("HCL Hospital Management System")

# ── PAGE: PATIENTS ────────────────────────────────────────────────────────────
def patients_page():
    st.title("🧑‍⚕️ Patient Management")

    with st.expander("➕ Register New Patient", expanded=False):
        with st.form("form_add_patient", clear_on_submit=True):
            c1, c2 = st.columns(2)
            pid   = c1.text_input("Patient ID *")
            name  = c2.text_input("Full Name *")
            dob   = c1.date_input("Date of Birth", value=datetime.date(2000, 1, 1))
            email = c2.text_input("Email")
            phone = c1.text_input("Phone")
            submitted = st.form_submit_button("Register Patient")
            if submitted:
                if not pid or not name:
                    st.error("Patient ID and Name are required.")
                else:
                    ok = run_query(
                        "INSERT INTO patients (patient_id, name, dob, email, phone) VALUES (%s,%s,%s,%s,%s)",
                        (pid, name, dob, email, phone),
                    )
                    if ok:
                        st.success(f"✅ Patient '{name}' registered successfully!")

    st.subheader("All Patients")
    rows = run_query("SELECT patient_id, name, dob, email, phone, created_at FROM patients ORDER BY created_at DESC", fetch="all")
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No patients found.")

# ── PAGE: APPOINTMENTS ────────────────────────────────────────────────────────
def appointments_page():
    st.title("📅 Appointment Booking")

    patients = run_query("SELECT patient_id, name FROM patients", fetch="all") or []
    doctors  = run_query("SELECT doctor_id, name FROM doctors", fetch="all") or []

    p_options = {f"{p['patient_id']} — {p['name']}": p['patient_id'] for p in patients}
    d_options = {f"{d['doctor_id']} — {d['name']}": d['doctor_id'] for d in doctors}

    with st.expander("➕ Book New Appointment", expanded=False):
        with st.form("form_add_appointment", clear_on_submit=True):
            c1, c2 = st.columns(2)
            pat_label = c1.selectbox("Patient *", ["— Select —"] + list(p_options.keys()))
            doc_label = c2.selectbox("Doctor *",  ["— Select —"] + list(d_options.keys()))
            appt_date = c1.date_input("Appointment Date *", value=datetime.date.today())
            appt_time = c2.time_input("Appointment Time *", value=datetime.time(9, 0))
            status    = c1.selectbox("Status", ["scheduled", "completed", "cancelled"])
            notes     = c2.text_area("Notes / Reason")
            submitted = st.form_submit_button("Book Appointment")
            if submitted:
                if pat_label == "— Select —" or doc_label == "— Select —":
                    st.error("Please select both patient and doctor.")
                else:
                    ok = run_query(
                        "INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, status, notes) VALUES (%s,%s,%s,%s,%s,%s)",
                        (p_options[pat_label], d_options[doc_label], appt_date, appt_time, status, notes),
                    )
                    if ok:
                        st.success("✅ Appointment booked successfully!")

    st.subheader("All Appointments")
    rows = run_query(
        """SELECT a.id, p.name as patient, d.name as doctor,
                  a.appointment_date, a.appointment_time, a.status, a.notes, a.created_at
           FROM appointments a
           LEFT JOIN patients p ON a.patient_id = p.patient_id
           LEFT JOIN doctors  d ON a.doctor_id  = d.doctor_id
           ORDER BY a.appointment_date DESC""",
        fetch="all",
    )
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No appointments found.")

# ── PAGE: DOCTOR LEAVES ───────────────────────────────────────────────────────
def leaves_page():
    st.title("🗓️ Doctor Leave Management")

    doctors  = run_query("SELECT doctor_id, name FROM doctors", fetch="all") or []
    d_options = {f"{d['doctor_id']} — {d['name']}": d['doctor_id'] for d in doctors}

    with st.expander("➕ Mark Doctor Leave", expanded=False):
        with st.form("form_add_leave", clear_on_submit=True):
            c1, c2 = st.columns(2)
            doc_label  = c1.selectbox("Doctor *", ["— Select —"] + list(d_options.keys()))
            leave_type = c2.selectbox("Leave Type", ["Single Day", "Date Range"])
            if leave_type == "Single Day":
                leave_date = c1.date_input("Leave Date *", value=datetime.date.today())
                date_from = date_to = None
            else:
                date_from = c1.date_input("From Date *", value=datetime.date.today())
                date_to   = c2.date_input("To Date *",   value=datetime.date.today())
                leave_date = None
            reason    = st.text_input("Reason (optional)")
            submitted = st.form_submit_button("Add Leave")
            if submitted:
                if doc_label == "— Select —":
                    st.error("Please select a doctor.")
                else:
                    doc_id = d_options[doc_label]
                    if leave_type == "Single Day":
                        ok = run_query(
                            "INSERT INTO doctor_leaves (doctor_id, leave_date, reason) VALUES (%s,%s,%s)",
                            (doc_id, leave_date, reason),
                        )
                        if ok:
                            st.success("✅ Leave recorded!")
                    else:
                        delta = (date_to - date_from).days
                        if delta < 0:
                            st.error("'To Date' must be after 'From Date'.")
                        else:
                            for i in range(delta + 1):
                                d = date_from + datetime.timedelta(days=i)
                                run_query(
                                    "INSERT INTO doctor_leaves (doctor_id, leave_date, reason) VALUES (%s,%s,%s)",
                                    (doc_id, d, reason),
                                )
                            st.success(f"✅ {delta+1} leave day(s) recorded!")

    st.subheader("Leave Records")
    rows = run_query(
        """SELECT l.id, d.name as doctor, l.leave_date, l.reason, l.created_at
           FROM doctor_leaves l
           LEFT JOIN doctors d ON l.doctor_id = d.doctor_id
           ORDER BY l.leave_date DESC""",
        fetch="all",
    )
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No leave records found.")

# ── PAGE: SERVICE REQUESTS ────────────────────────────────────────────────────
def service_requests_page():
    st.title("🛠️ Service Requests")

    with st.expander("➕ Create Service Request", expanded=False):
        with st.form("form_add_service", clear_on_submit=True):
            c1, c2 = st.columns(2)
            title       = c1.text_input("Title *")
            status      = c2.selectbox("Status", ["pending", "in_progress", "resolved"])
            description = st.text_area("Description")
            submitted   = st.form_submit_button("Submit Request")
            if submitted:
                if not title:
                    st.error("Title is required.")
                else:
                    ok = run_query(
                        "INSERT INTO service_requests (title, description, status) VALUES (%s,%s,%s)",
                        (title, description, status),
                    )
                    if ok:
                        st.success("✅ Service request submitted!")

    st.subheader("All Service Requests")
    rows = run_query(
        "SELECT id, title, description, status, created_at FROM service_requests ORDER BY created_at DESC",
        fetch="all",
    )
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No service requests found.")

# ── ROUTER ────────────────────────────────────────────────────────────────────
if page == "🧑‍⚕️ Patients":
    patients_page()
elif page == "📅 Appointments":
    appointments_page()
elif page == "🗓️ Doctor Leaves":
    leaves_page()
elif page == "🛠️ Service Requests":
    service_requests_page()
