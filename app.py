import streamlit as st
import pandas as pd
from fpdf import FPDF
import os
import datetime
import re
import zipfile
from io import BytesIO
import hashlib
import sqlite3
from PIL import Image
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Welcome To KInder Zentrum ", layout="centered")

# --- STYLING: Light Green + Sky Blue, Times New Roman for TEXT ONLY ---
st.markdown("""
<style>
  /* Only apply Times New Roman to text elements, NOT icons */
.stApp,.main.block-container, h1, h2, h3, p, label, input, textarea, select,.stMarkdown,.stTextInput,.stSelectbox {
        font-family: 'Times New Roman', Times, serif!important;
    }
.stApp {
        background: linear-gradient(135deg, #81e6d9 0%, #90cdf4 100%);
    }
.main.block-container {
        background-color: rgba(255, 255, 255, 0.97);
        padding: 2.5rem;
        border-radius: 20px;
        box-shadow: 0 10px 30px 0 rgba(0, 0, 0, 0.1);
    }
    h1, h2, h3 {
        color: #1a365d;
        font-weight: 700;
    }
    h1 {
        text-align: center;
        color: #2c5282;
    }
    h2 {
        color: #38a169;
        border-bottom: 2px solid #81e6d9;
        padding-bottom: 5px;
    }
    label,.stMarkdown p,.stCaption {
        color: #2d3748!important;
        font-weight: 500;
    }
.stButton>button {
        background: linear-gradient(135deg, #48bb78 0%, #4299e1 100%);
        color: white;
        border-radius: 10px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-weight: 600;
        box-shadow: 0 4px 6px rgba(66, 153, 225, 0.3);
        width: 100%;
    }
.stButton>button:hover {
        background: linear-gradient(135deg, #38a169 0%, #3182ce 100%);
        transform: translateY(-2px);
    }
.stTextInput>div>div>input,.stSelectbox>div>div>div,.stTextArea>div>div>textarea,.stNumberInput>div>div>input {
        background-color: #f0fff4;
        border: 2px solid #9ae6b4;
        border-radius: 8px;
        color: #1a202c;
    }
.stDateInput>div>div>input {
        background-color: #ebf8ff;
        border: 2px solid #90cdf4;
    }
  /* Let Streamlit keep its default font for icons/arrows */
 [data-testid="stExpander"] summary svg {
        font-family: initial!important;
    }
</style>

<script>
// Make Enter key behave like Tab - moves to next input
document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.target.tagName!== 'TEXTAREA' && e.target.type!== 'submit') {
        e.preventDefault();
        const formElements = Array.from(document.querySelectorAll('input, select, textarea')).filter(el =>!el.disabled && el.type!== 'hidden');
        const index = formElements.indexOf(e.target);
        if (index > -1 && index < formElements.length - 1) {
            formElements[index + 1].focus();
        }
    }
});
</script>
""", unsafe_allow_html=True)

# --- CONFIG ---
SCHOOL_NAME = "KINDER ZENTRUM INTERNATIONAL SCHOOL"
CLASSES = ["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6", "JHS 1", "JHS 2", "JHS 3"]
PROMOTE_OPTIONS = ["None"] + CLASSES
SUBJECTS = ["English Language", "Mathematics", "Natural Science", "History",
            "Creative Arts", "R. M.E", "Computing", "French", "Ghanaian Language"]
DB_FILE = "school.db"
LOGO_FILE = "logo.png.jpeg"

DEVELOPER_USERNAME = "AXIOS"
DEVELOPER_PASSWORD = "AXIOS1"

# --- SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'user_class' not in st.session_state:
    st.session_state.user_class = ""
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'batch' not in st.session_state:
    st.session_state.batch = []

# --- HELPERS ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    class TEXT NOT NULL,
                    is_admin INTEGER NOT NULL
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class TEXT NOT NULL,
                    studentname TEXT NOT NULL
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS preset_remarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    remark TEXT NOT NULL
                )''')
    conn.commit()

    user_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        defaults = [
            ("headmaster", hash_password("head123"), "ALL", 1),
            (DEVELOPER_USERNAME, hash_password(DEVELOPER_PASSWORD), "ALL", 1),
            ("grade1", hash_password("grade1"), "Grade 1", 0),
        ]
        c.executemany("INSERT INTO users (username, password, class, is_admin) VALUES (?,?,?,?)", defaults)
        conn.commit()

    preset_count = c.execute("SELECT COUNT(*) FROM preset_remarks").fetchone()[0]
    if preset_count == 0:
        default_conducts = [
            ("conduct", "Excellent behavior"), ("conduct", "Very Good"), ("conduct", "Good"),
            ("conduct", "Satisfactory"), ("conduct", "Needs Improvement")
        ]
        default_interests = [
            ("interest", "Reading"), ("interest", "Sports"), ("interest", "Music"),
            ("interest", "Drawing"), ("interest", "Science"), ("interest", "Drama")
        ]
        default_teacher_remarks = [
            ("teacher_remark", "A hardworking student with great potential."),
            ("teacher_remark", "Shows consistent improvement in all subjects."),
            ("teacher_remark", "Participates actively in class discussions."),
            ("teacher_remark", "Needs to focus more on homework submission."),
            ("teacher_remark", "Excellent performance this term. Keep it up!")
        ]
        c.executemany("INSERT INTO preset_remarks (category, remark) VALUES (?,?)",
                     default_conducts + default_interests + default_teacher_remarks)
        conn.commit()
    conn.close()

init_database()

def get_presets(category):
    conn = get_db()
    rows = conn.execute("SELECT remark FROM preset_remarks WHERE category=?", (category,)).fetchall()
    conn.close()
    return [r["remark"] for r in rows]

def add_preset(category, remark):
    conn = get_db()
    conn.execute("INSERT INTO preset_remarks (category, remark) VALUES (?,?)", (category, remark))
    conn.commit()
    conn.close()

def delete_preset(category, remark):
    conn = get_db()
    conn.execute("DELETE FROM preset_remarks WHERE category=? AND remark=?", (category, remark))
    conn.commit()
    conn.close()

def load_users():
    conn = get_db()
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    return df

def save_user(username, password, user_class, is_admin):
    conn = get_db()
    conn.execute("INSERT INTO users (username, password, class, is_admin) VALUES (?,?,?,?)",
              (username, hash_password(password), user_class, int(is_admin)))
    conn.commit()
    conn.close()

def delete_user(username):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE username =?", (username,))
    conn.commit()
    conn.close()

def login(username, password):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username =? AND password =?",
                       (username, hash_password(password))).fetchone()
    conn.close()
    if user:
        st.session_state.logged_in = True
        st.session_state.username = user["username"]
        st.session_state.user_class = user["class"]
        st.session_state.is_admin = bool(user["is_admin"])
        return True
    return False

def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_class = ""
    st.session_state.is_admin = False
    st.session_state.batch = []
    st.rerun()

# --- LOGIN SCREEN ---
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if os.path.exists(LOGO_FILE):
            st.image(LOGO_FILE, width=150)
        st.title("TEACHERS LOGIN PORTAL")
        st.write(f"*{SCHOOL_NAME}*")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login_btn = st.form_submit_button("Login")

        if login_btn:
            if login(username, password):
                st.success("Logged in!")
                st.rerun()
            else:
                st.error("Invalid username or password")

    st.info("Contact the Headmaster for your login details.")
    st.stop()

# --- MAIN APP ---
def load_students():
    conn = get_db()
    if st.session_state.is_admin:
        df = pd.read_sql_query("SELECT * FROM students", conn)
    else:
        df = pd.read_sql_query("SELECT * FROM students WHERE class =?", conn, params=(st.session_state.user_class,))
    conn.close()
    return df

def save_students(df):
    conn = get_db()
    c = conn.cursor()
    if not st.session_state.is_admin:
        c.execute("DELETE FROM students WHERE class =?", (st.session_state.user_class,))
    else:
        c.execute("DELETE FROM students")
    for _, row in df.iterrows():
        c.execute("INSERT INTO students (class, studentname) VALUES (?,?)", (row["class"], row["studentname"]))
    conn.commit()
    conn.close()

def get_grade(total):
    if total >= 80: return "1"
    elif total >= 68: return "2"
    elif total >= 55: return "3"
    elif total >= 40: return "4"
    else: return "5"

def get_remark(grade):
    return {"1":"MASTERY","2":"PROFICIENT","3":"APPROACHING PROFICIENCY","4":"DEVELOPING","5":"EMERGING"}.get(grade,"")

def validate_text(input_str, field_name):
    if input_str and not re.match(r'^[A-Za-z\s]+$', input_str):
        st.error(f"{field_name}: Please use letters only")
        return False
    return True

def validate_number(input_str, field_name):
    if input_str and not re.match(r'^[0-9\s/]+$', input_str):
        st.error(f"{field_name}: Please use numbers only")
        return False
    return True

# --- PDF - NO WATERMARK ---
class PDF(FPDF):
    pass

def create_pdf(data):
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=False, margin=10)
    pdf.set_margins(15, 10, 15)

    if os.path.exists(LOGO_FILE):
        pdf.image(LOGO_FILE, x=85, y=8, w=40)
        pdf.ln(35)
    else:
        pdf.ln(10)

    pdf.set_font("Times", 'B', 16)
    pdf.cell(0, 8, SCHOOL_NAME, 0, 1, 'C')
    pdf.set_font("Times", 'B', 13)
    pdf.cell(0, 7, "TERMINAL REPORT CARD", 0, 1, 'C')
    pdf.set_font("Times", '', 9)
    pdf.cell(0, 5, "Location: Hobor - Akutuase", 0, 1, 'C')
    pdf.cell(0, 5, "Contact: 0598363194 | 0549762352", 0, 1, 'C')
    pdf.ln(2)

    pdf.set_font("Times", '', 10)
    pdf.cell(0, 6, f"Name: {data['name']}", 0, 1)
    pdf.cell(0, 6, f"No. On Roll: {data['no_on_roll']} Class: {data['form']} Term: {data['term']}", 0, 1)
    pdf.cell(0, 6, f"Date: {data['date']} Next Term: {data['next_term']} Position: {data['position']}", 0, 1)
    pdf.ln(2)

    pdf.set_font("Times", 'B', 9)
    col_widths = [40, 25, 25, 25, 13, 52]
    pdf.cell(col_widths[0], 7, "SUBJECT", 1, 0, 'C')
    pdf.cell(col_widths[1], 7, "CLASS 50%", 1, 0, 'C')
    pdf.cell(col_widths[2], 7, "EXAM 50%", 1, 0, 'C')
    pdf.cell(col_widths[3], 7, "TOTAL 100%", 1, 0, 'C')
    pdf.cell(col_widths[4], 7, "GRADE", 1, 0, 'C')
    pdf.cell(col_widths[5], 7, "REMARKS", 1, 1, 'C')

    pdf.set_font("Times", '', 9)
    for sub, vals in data['scores'].items():
        pdf.cell(col_widths[0], 6, sub[:18], 1, 0)
        pdf.cell(col_widths[1], 6, str(vals['class_score']), 1, 0, 'C')
        pdf.cell(col_widths[2], 6, str(vals['exam_score']), 1, 0, 'C')
        pdf.cell(col_widths[3], 6, str(vals['total']), 1, 0, 'C')
        pdf.cell(col_widths[4], 6, vals['grade'], 1, 0, 'C')
        pdf.cell(col_widths[5], 6, vals['remark'][:20], 1, 1, 'C')

    pdf.ln(3)
    pdf.set_font("Times", '', 9)
    pdf.cell(0, 5, f"ATTENDANCE: {data['attendance']} OUT OF: {data['out_of']}", 0, 1)
    pdf.cell(0, 5, f"PROMOTED TO: {data['promoted_to']}", 0, 1)
    pdf.cell(0, 5, f"CONDUCT: {data['conduct']} INTEREST: {data['interest']}", 0, 1)
    pdf.cell(0, 5, f"SCHOOL FEES: {data['school_fees']} ARREARS: {data['arrears']}", 0, 1)
    pdf.cell(0, 5, f"FURNITURE & FIRST AID DUES: {data['furniture_dues']}", 0, 1)
    pdf.ln(2)

    pdf.set_font("Times", 'B', 9)
    pdf.cell(0, 5, "CLASS TEACHER'S REMARKS:", 0, 1)
    pdf.set_font("Times", '', 9)
    pdf.multi_cell(0, 4, data['teacher_remarks'][:200])
    pdf.ln(5)

    pdf.cell(95, 6, "........................................", 0, 0, 'C')
    pdf.cell(95, 6, "........................................", 0, 1, 'C')
    pdf.cell(95, 5, "CLASS TEACHER'S SIGNATURE", 0, 0, 'C')
    pdf.cell(95, 5, "HEADMASTER'S SIGNATURE", 0, 1, 'C')

    return pdf.output(dest='S')

# --- HEADER ---
col1, col2 = st.columns([3, 1])
with col1:
    if os.path.exists(LOGO_FILE):
        st.image(LOGO_FILE, width=80)
    st.title("KINDER ZENTRUM INTERNATIONAL SCHOOL SBA PORTAL")
    display_class = "All Classes" if st.session_state.user_class == "ALL" else st.session_state.user_class
    st.caption(f"Logged in as: {st.session_state.username} | Access: {display_class}")
with col2:
    st.write("")
    if st.button("Logout"):
        logout()

# --- SIDEBAR ---
st.sidebar.header("Manage Students Database")
students_df = load_students()

with st.sidebar.expander("Add New Student"):
    with st.form("add_student_form", clear_on_submit=True):
        if st.session_state.is_admin:
            new_class = st.selectbox("Select Class", CLASSES)
        else:
            new_class = st.session_state.user_class
            st.write(f"Class: {new_class}")
        new_name = st.text_input("Student Full Name", help="Letters only - e.g. John Mensah")
        if st.form_submit_button("Add Student") and new_name:
            if validate_text(new_name, "Student Name"):
                conn = get_db()
                conn.execute("INSERT INTO students (class, studentname) VALUES (?,?)", (new_class, new_name))
                conn.commit()
                conn.close()
                st.sidebar.success(f"Added {new_name} to {new_class}")
                st.rerun()

if st.session_state.is_admin:
    with st.sidebar.expander("Promote Entire Class"):
        from_class = st.selectbox("From Class", CLASSES[:-1])
        to_class = CLASSES[CLASSES.index(from_class) + 1]
        st.info(f"Move all {from_class} to {to_class}")
        if st.button(f"Promote All {from_class} to {to_class}"):
            conn = get_db()
            c = conn.cursor()
            count = c.execute("SELECT COUNT(*) FROM students WHERE class =?", (from_class,)).fetchone()[0]
            if count > 0:
                c.execute("UPDATE students SET class =? WHERE class =?", (to_class, from_class))
                conn.commit()
                st.sidebar.success(f"Promoted {count} students to {to_class}!")
                conn.close()
                st.rerun()
            else:
                st.sidebar.warning(f"No students found in {from_class}")

with st.sidebar.expander("View and Edit My Students"):
    st.caption("Edit names or delete rows. Click Save Changes when done.")
    display_df = students_df.rename(columns={"class": "Class", "studentname": "Student Name"})
    edited_df = st.data_editor(display_df[["Class", "Student Name"]], num_rows="dynamic", use_container_width=True, hide_index=True)
    if st.button("Save Changes to Database"):
        save_df = edited_df.rename(columns={"Class": "class", "Student Name": "studentname"})
        save_students(save_df)
        st.sidebar.success("Database updated!")
        st.rerun()

# --- HEADMASTER: MANAGE PRESETS ---
if st.session_state.is_admin:
    with st.sidebar.expander("Manage Preset Remarks"):
        st.write("Headmaster can add or remove preset options")
        category = st.selectbox("Category", ["conduct", "interest", "teacher_remark"])
        presets = get_presets(category)

        st.write(f"Current {category.replace('_', ' ').title()} options:")
        for p in presets:
            col1, col2 = st.columns([4,1])
            col1.write(p)
            if col2.button("Remove", key=f"del_{category}_{p}"):
                delete_preset(category, p)
                st.rerun()

        new_preset = st.text_input(f"Add new {category.replace('_', ' ')}", key=f"new_{category}")
        if st.button("Add Preset", key=f"add_{category}") and new_preset:
            add_preset(category, new_preset)
            st.success("Added!")
            st.rerun()

# --- ADMIN: USER MANAGEMENT ---
if st.session_state.is_admin:
    with st.sidebar.expander("Manage Teachers"):
        users_df = load_users()
        display_users = users_df[users_df["username"]!= DEVELOPER_USERNAME]
        clean_users = display_users.rename(columns={"username": "Username", "class": "Class", "is_admin": "Admin"})
        st.dataframe(clean_users[["Username", "Class", "Admin"]], use_container_width=True, hide_index=True)

        with st.form("add_user_form", clear_on_submit=True):
            st.write("Add New Teacher")
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            new_class = st.selectbox("Assign Class", CLASSES + ["ALL"])
            new_is_admin = st.checkbox("Make Admin/Headmaster")
            if st.form_submit_button("Add Teacher") and new_username and new_password:
                if new_username in users_df["username"].values:
                    st.error("Username already exists")
                else:
                    save_user(new_username, new_password, new_class, new_is_admin)
                    st.success(f"Added teacher: {new_username}")
                    st.rerun()

        teachers_to_delete = display_users[
            (display_users["username"]!= st.session_state.username) &
            (display_users["username"]!= DEVELOPER_USERNAME)
        ]["username"].tolist()
        if teachers_to_delete:
            user_to_delete = st.selectbox("Select teacher to remove", teachers_to_delete)
            if st.button("Remove Teacher"):
                delete_user(user_to_delete)
                st.success(f"Removed {user_to_delete}")
                st.rerun()

# --- BATCH DISPLAY ---
st.sidebar.header("Current Batch")
if st.session_state.batch:
    for i, item in enumerate(st.session_state.batch):
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            st.write(f"{i+1}. {item['name']}")
        with col2:
            if st.button("Remove", key=f"remove_{i}"):
                st.session_state.batch.pop(i)
                st.rerun()
    if st.sidebar.button("Clear Entire Batch"):
        st.session_state.batch = []
        st.rerun()
else:
    st.sidebar.info("Batch is empty. Add students using Add to Batch button.")

# --- MAIN FORM ---
with st.form("report_form", clear_on_submit=True):
    st.subheader("Student Details")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.session_state.is_admin:
            selected_class = st.selectbox("Class", CLASSES)
        else:
            selected_class = st.session_state.user_class
            st.write(f"Class: {selected_class}")
        class_students = students_df[students_df["class"] == selected_class]["studentname"].dropna().tolist()
        if class_students:
            student_name = st.selectbox("Student Name", class_students)
        else:
            student_name = ""
            st.warning(f"No students in {selected_class}. Add them in the sidebar.")
    with c2:
        no_on_roll = st.text_input("No. On Roll", help="Numbers only - e.g. 25")
    with c3: term = st.selectbox("Term", ["1st Term", "2nd Term", "3rd Term"])
    with c4:
        position = st.text_input("Overall Position", placeholder="5th", help="Letters and numbers - e.g. 5th")
    c5, c6 = st.columns(2)
    with c5: date = st.date_input("Date")
    with c6: next_term = st.date_input("Next Term Begins")

    st.subheader("Enter Scores - Class Score[50%] And Exams Score[50%]")
    scores = {}
    for sub in SUBJECTS:
        st.write(f"{sub}")
        c1,c2,c3 = st.columns([3,2,2])
        with c1: st.write("")
        with c2: class_score = st.number_input("Class",0,50,key=sub+"class",label_visibility="collapsed")
        with c3: exam_score = st.number_input("Exam",0,50,key=sub+"exam",label_visibility="collapsed")
        total = class_score + exam_score
        grade = get_grade(total)
        remark = get_remark(grade)
        scores[sub] = {"class_score": class_score, "exam_score": exam_score, "total": total, "grade": grade, "remark": remark}
        st.caption(f"Total: {total} | Grade: {grade} | Remark: {remark}")

    st.subheader("Other Details")
    c8, c9, c10 = st.columns(3)
    with c8:
        attendance = st.text_input("Attendance", placeholder="58", help="Numbers only")
    with c9:
        out_of = st.text_input("Out Of", placeholder="60", help="Numbers only")
    with c10:
        current_index = CLASSES.index(selected_class) if selected_class in CLASSES else -1
        if current_index < len(CLASSES) - 1 and current_index!= -1:
            default_promote = CLASSES[current_index + 1]
        else:
            default_promote = "None"
        promoted_to = st.selectbox(
            "Promoted To",
            PROMOTE_OPTIONS,
            index=PROMOTE_OPTIONS.index(default_promote),
            help="Auto-selected based on current class"
        )

    c11, c12 = st.columns(2)
    with c11:
        conduct_options = get_presets("conduct")
        conduct = st.selectbox("Conduct", conduct_options)
    with c12:
        interest_options = get_presets("interest")
        interest = st.selectbox("Interest", interest_options)

    c13, c14, c15 = st.columns(3)
    with c13: school_fees = st.text_input("School Fees", placeholder="Paid")
    with c14: arrears = st.text_input("Arrears From Last Term")
    with c15: furniture_dues = st.text_input("Furniture and First Aid Dues")

    remark_options = get_presets("teacher_remark")
    teacher_remarks = st.selectbox("Class Teacher's Remarks", remark_options)

    add_to_batch = st.form_submit_button("Add to Batch")

if add_to_batch:
    valid = True
    valid &= validate_number(no_on_roll, "No. On Roll")
    valid &= validate_number(attendance, "Attendance")
    valid &= validate_number(out_of, "Out Of")

    if valid and student_name and conduct and interest and teacher_remarks:
        data = {
            "name": student_name, "no_on_roll": no_on_roll, "form": selected_class, "term": term,
            "position": position, "date": date.strftime('%d-%m-%Y'), "next_term": next_term.strftime('%d-%m-%Y'),
            "scores": scores, "attendance": attendance, "out_of": out_of, "promoted_to": promoted_to,
            "conduct": conduct, "interest": interest, "school_fees": school_fees, "arrears": arrears,
            "furniture_dues": furniture_dues, "teacher_remarks": teacher_remarks
        }
        st.session_state.batch.append(data)
        st.success(f"Added {student_name} to batch!")
        st.rerun()
    else:
        st.error("Please fill all required fields: Student, Conduct, Interest, Remarks")

if st.button("Generate All PDFs in Batch"):
    if st.session_state.batch:
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for student_data in st.session_state.batch:
                pdf_bytes = create_pdf(student_data)
                filename = f"{student_data['name']}_{student_data['form']}_{student_data['term']}.pdf"
                filename = re.sub(r'[\\/*?:"<>|]', "", filename)
                zip_file.writestr(filename, pdf_bytes)
        st.download_button(
            label=f"Download All {len(st.session_state.batch)} Reports as ZIP",
            data=zip_buffer.getvalue(),
            file_name=f"Reports_{st.session_state.user_class}_{datetime.datetime.now().strftime('%Y%m%d')}.zip",
            mime="application/zip"
        )
        st.success(f"Generated {len(st.session_state.batch)} PDFs! No watermark - ready for Word conversion.")
    else:
        st.error("Batch is empty. Add students first.")