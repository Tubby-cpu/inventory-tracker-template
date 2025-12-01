import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib

# ====================== CONFIG ======================
st.set_page_config(page_title="Clinic Inventory Pro", layout="wide")
DB_PATH = "inventory.db"

# ====================== USERS ======================
USERS = {
    "admin": {"password": hashlib.sha256("admin123".encode()).hexdigest(), "role": "admin", "clinic": "All"},
    "clinic1": {"password": hashlib.sha256("clinic1pass".encode()).hexdigest(), "role": "user", "clinic": "Clinic 1 - Nairobi"},
    "clinic2": {"password": hashlib.sha256("clinic2pass".encode()).hexdigest(), "role": "user", "clinic": "Clinic 2 - Mombasa"},
    "clinic3": {"password": hashlib.sha256("clinic3pass".encode()).hexdigest(), "role": "user", "clinic": "Clinic 3 - Kisumu"},
    "clinic4": {"password": hashlib.sha256("clinic4pass".encode()).hexdigest(), "role": "user", "clinic": "Clinic 4 - Nakuru"},
    "clinic5": {"password": hashlib.sha256("clinic5pass".encode()).hexdigest(), "role": "user", "clinic": "Clinic 5 - Eldoret"},
    "clinic6": {"password": hashlib.sha256("clinic6pass".encode()).hexdigest(), "role": "user", "clinic": "Clinic 6 - Thika"},
    "clinic7": {"password": hashlib.sha256("clinic7pass".encode()).hexdigest(), "role": "user", "clinic": "Clinic 7 - Machakos"},
}

# ====================== DATABASE ======================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS medicines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clinic TEXT NOT NULL,
                    drug_name TEXT NOT NULL,
                    generic_name TEXT,
                    strength TEXT,
                    batch_no TEXT,
                    expiry_date DATE,
                    quantity INTEGER,
                    low_stock_threshold INTEGER DEFAULT 20,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    clinic TEXT,
                    drug_id INTEGER,
                    type TEXT,
                    quantity INTEGER,
                    patient_name TEXT,
                    remarks TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
init_db()

# ====================== AUTH ======================
def login():
    if "user" not in st.session_state:
        st.sidebar.title("Login")
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
            hashed = hashlib.sha256(password.encode()).hexdigest()
            if username in USERS and USERS[username]["password"] == hashed:
                st.session_state.user = username
                st.session_state.role = USERS[username]["role"]
                st.session_state.clinic = USERS[username]["clinic"]
                st.rerun()
            else:
                st.sidebar.error("Wrong credentials")
        st.stop()

login()
st.sidebar.success(f"Logged in: {st.session_state.user}")
st.sidebar.write(f"**{st.session_state.clinic}**")
if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.rerun()

# ====================== HELPERS ======================
def get_df(clinic_filter=None):
    conn = sqlite3.connect(DB_PATH)
    if clinic_filter and clinic_filter != "All":
        df = pd.read_sql_query("SELECT * FROM medicines WHERE clinic = ?", conn, params=(clinic_filter,))
    else:
        df = pd.read_sql_query("SELECT * FROM medicines", conn)
    conn.close()
    if not df.empty:
        df["expiry_date"] = pd.to_datetime(df["expiry_date"])
    return df

def add_transaction(clinic, drug_id, type_, qty, patient="", remarks=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO transactions (clinic, drug_id, type, quantity, patient_name, remarks) VALUES (?,?,?,?,?,?)",
                 (clinic, drug_id, type_, qty, patient, remarks))
    conn.commit()
    conn.close()

# ====================== MAIN ======================
st.title("Clinic Inventory Pro")

role = st.session_state.role
user_clinic = st.session_state.clinic

if role == "admin":
    clinic_options = ["All", "Clinic 1 - Nairobi", "Clinic 2 - Mombasa", "Clinic 3 - Kisumu",
                      "Clinic 4 - Nakuru", "Clinic 5 - Eldoret", "Clinic 6 - Thika", "Clinic 7 - Machakos"]
    selected_clinic = st.selectbox("View Clinic", clinic_options)
else:
    selected_clinic = user_clinic

df = get_df("All" if (role == "admin" and selected_clinic == "All") else selected_clinic)

tab1, tab2, tab3, tab4 = st.tabs(["Current Stock", "Receive Stock", "Issue Stock", "Reports"])

# ───── TAB 1: CURRENT STOCK (FIXED FOREVER) ─────
with tab1:
    st.subheader(f"Stock – {selected_clinic}")

    if df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Expired", 0); col2.metric("Near Expiry", 0); col3.metric("Low Stock", 0)
        st.info("No medicines yet — go to 'Receive Stock' to add some")
    else:
        today = pd.to_datetime("today").normalize()
        df["days_to_expiry"] = (df["expiry_date"] - today).dt.days

        # Calculate status safely
        df["status"] = "normal"
        df.loc[df["quantity"] <= df["low_stock_threshold"], "status"] = "low_stock"
        df.loc[df["days_to_expiry"] <= 90, "status"] = "near_expiry"
        df.loc[df["days_to_expiry"] <= 0, "status"] = "expired"

        # Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Expired", len(df[df["status"] == "expired"]))
        c2.metric("Near Expiry (<90 days)", len(df[df["status"] == "near_expiry"]))
        c3.metric("Low Stock", len(df[df["status"] == "low_stock"]))

        # Prepare display dataframe and keep status for coloring
        display = df[["drug_name", "generic_name", "strength", "batch_no", "expiry_date", "quantity", "low_stock_threshold"]].copy()
        display["expiry_date"] = display["expiry_date"].dt.strftime("%Y-%m-%d")

        # THIS IS THE FIX: pass the status as a separate list that matches display rows
        status_list = df["status"].tolist()

        def highlight_row(row):
            status = status_list[row.name]
            if status == "expired":     return ["background: #ffcccc"] * len(row)
            if status == "near_expiry": return ["background: #ffffcc"] * len(row)
            if status == "low_stock":   return ["background: #ffcc99"] * len(row)
            return [""] * len(row)

        st.dataframe(display.style.apply(highlight_row, axis=1), use_container_width=True)

# ───── TAB 2: RECEIVE STOCK ─────
with tab2:
    st.subheader("Receive New Stock")
    with st.form("receive"):
        drug_name = st.text_input("Drug Name *")
        generic   = st.text_input("Generic Name (optional)")
        strength  = st.text_input("Strength e.g. 500mg")
        batch     = st.text_input("Batch Number *")
        expiry    = st.date_input("Expiry Date", min_value=datetime.today())
        qty       = st.number_input("Quantity", min_value=1)
        threshold = st.number_input("Low-stock alert", value=20)
        submitted = st.form_submit_button("Add Stock")
        if submitted:
            if not drug_name or not batch:
                st.error("Drug name and batch number required")
            else:
                conn = sqlite3.connect(DB_PATH)
                conn.execute("""INSERT INTO medicines 
                    (clinic, drug_name, generic_name, strength, batch_no, expiry_date, quantity, low_stock_threshold)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (selected_clinic, drug_name, generic, strength, batch, expiry, qty, threshold))
                drug_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.commit()
                conn.close()
                add_transaction(selected_clinic, drug_id, "in", qty, remarks=f"Received {batch}")
                st.success(f"Added {qty} × {drug_name}")
                st.balloons()
                st.rerun()

# ───── TAB 3: ISSUE STOCK ─────
with tab3:
    st.subheader("Issue Medicine")
    if df.empty:
        st.info("No stock available")
    else:
        df["option"] = (df["drug_name"] + " | " + df["batch_no"] +
                        " | Exp: " + df["expiry_date"].dt.strftime("%b %Y") +
                        " | Stock: " + df["quantity"].astype(str))
        choice = st.selectbox("Select medicine", df["option"])
        selected_row = df[df["option"] == choice].iloc[0]

        col1, col2 = st.columns(2)
        col1.write(f"**Available:** {selected_row.quantity}")
        issue_qty = col2.number_input("Qty to issue", min_value=1, max_value=int(selected_row.quantity))

        patient = st.text_input("Patient name (optional)")
        remarks = st.text_input("Remarks")

        if st.button("Issue Medicine", type="primary"):
            new_qty = selected_row.quantity - issue_qty
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE medicines SET quantity = ? WHERE id = ?", (new_qty, selected_row.id))
            conn.commit()
            conn.close()
            add_transaction(selected_clinic, selected_row.id, "out", issue_qty, patient, remarks)
            st.success(f"Issued {issue_qty} × {selected_row.drug_name}")
            st.rerun()

# ───── TAB 4: REPORTS ─────
with tab4:
    st.subheader("Export")
    if not df.empty:
        csv = df.to_csv(index=False).encode()
        st.download_button("Download current stock (CSV)", csv, "stock.csv", "text/csv")
    else:
        st.info("No data yet")

st.sidebar.caption("Clinic Inventory • Built with Streamlit")
