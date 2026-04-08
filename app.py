import os, io, csv, json, uuid, textwrap
from datetime import datetime

import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth

import gspread
from google.oauth2.service_account import Credentials


# =========================
# Streamlit Config
# =========================
st.set_page_config(
    page_title="PNA-NY Spring Conference 2026 — Evaluation, Post-test, & Certificate",
    page_icon="🎓",
    layout="centered"
)

if os.path.exists("logo.png"):
    st.image("logo.png", width=220)

# =========================
# Settings (from secrets)
# =========================
COURSE = st.secrets.get("course", {})
ORG_NAME = COURSE.get("org_name", "The Philippine Nurses Association of America Foundation")
COURSE_TITLE = COURSE.get(
    "course_title",
    "LEAD TO INSPIRE VIRTUAL SPRING CONFERENCE 2026: Advancing Nursing Excellence Through Research, Evidence, and Innovation",
)
COURSE_DATE = COURSE.get("course_date", "April 18, 2026")
COURSE_TIME = COURSE.get("course_time", "8:00 am – 12:35 pm")
CREDIT_HOURS = float(COURSE.get("credit_hours", 4.5))
PASSING_SCORE = int(COURSE.get("passing_score", 75))
PROVIDER_LINE = COURSE.get(
    "provider_line",
    "The Philippine Nurses Association of America Foundation is approved by the California Board of Registered Nursing, Provider 14143, for 4.5 contact hours"
)
PROGRAM_DIRECTOR = COURSE.get("program_director", "Peter-Reuben Calixto")
PROGRAM_DIRECTOR_TITLE = COURSE.get("program_director_title", "PNAAF Accredited Provider Program Director")

SHEETS = st.secrets.get("sheets", {})
SHEET_ID = SHEETS.get("sheet_id", "")
EVAL_TAB = SHEETS.get("eval_tab", "Spring2026_Eval_PT")
CERT_TAB = SHEETS.get("cert_tab", "Spring2026_Certificates")

SAVE_DIR = "data"
os.makedirs(SAVE_DIR, exist_ok=True)

# =========================
# Load quiz
# =========================
with open("questions.json", "r", encoding="utf-8") as f:
    QUIZ = json.load(f)

# =========================
# Google Sheets helpers
# =========================
GSPREAD_CLIENT = None
if "gcp_service_account" in st.secrets and SHEET_ID:
    SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    GS_CREDS = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SHEETS_SCOPES,
    )
    GSPREAD_CLIENT = gspread.authorize(GS_CREDS)

def sheets_append_dict(sheet_id: str, tab_name: str, row_dict: dict):
    if GSPREAD_CLIENT is None:
        raise RuntimeError("Google Sheets is not configured. Add sheet_id and gcp_service_account to secrets.")

    sh = GSPREAD_CLIENT.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        header = list(row_dict.keys())
        ws = sh.add_worksheet(title=tab_name, rows=2000, cols=max(len(header), 1))
        ws.append_row(header, value_input_option="USER_ENTERED")

    header = ws.row_values(1) or []
    header_set = set(h.strip() for h in header)
    new_cols = [k for k in row_dict.keys() if k not in header_set]

    if new_cols:
        header_extended = header + new_cols
        ws.resize(rows=ws.row_count, cols=len(header_extended))
        ws.update("1:1", [header_extended])
        header = header_extended

    row_vals = [row_dict.get(col, "") for col in header]
    ws.append_row(row_vals, value_input_option="USER_ENTERED")

def save_eval_to_sheets(row_enriched: dict):
    row_enriched = dict(row_enriched)
    row_enriched["topics_interest"] = (row_enriched.get("topics_interest") or "").replace("\n", " ")
    row_enriched["additional_comments"] = (row_enriched.get("additional_comments") or "").replace("\n", " ")
    row_enriched["most_beneficial_topic"] = (row_enriched.get("most_beneficial_topic") or "").replace("\n", " ")
    row_enriched["payload_json"] = json.dumps(row_enriched, ensure_ascii=False)
    sheets_append_dict(SHEET_ID, EVAL_TAB, row_enriched)

def save_cert_to_sheets(cert_row: dict):
    cert_row = dict(cert_row)
    cert_row.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    sheets_append_dict(SHEET_ID, CERT_TAB, cert_row)

def save_row_to_csv(path: str, row: dict):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if new:
            w.writeheader()
        w.writerow(row)

# =========================
# Certificate helper
# =========================
def wrap_centered(c, text, y, font_name="Helvetica", font_size=12, max_width=440, line_gap=16):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    c.setFont(font_name, font_size)
    for line in lines:
        c.drawCentredString(306, y, line)
        y -= line_gap
    return y

def make_certificate_pdf(full_name: str, email: str, score_pct: float, cert_id: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    bg_path = "assets/cert_bg.png"

    if os.path.exists(bg_path):
        c.drawImage(
            ImageReader(bg_path),
            0,
            0,
            width=width,
            height=height,
            preserveAspectRatio=True,
            mask="auto",
        )
    else:
        raise FileNotFoundError("Certificate background image not found at assets/cert_bg.png")

    name_x = width / 2
    name_y = 535
    max_name_width = 400

    font_name = "Helvetica-Bold"
    font_size = 24

    while stringWidth(full_name, font_name, font_size) > max_name_width and font_size > 14:
        font_size -= 1

    c.setFillColor(colors.black)
    c.setFont(font_name, font_size)
    c.drawCentredString(name_x, name_y, full_name)

    c.showPage()
    c.save()
    return buffer.getvalue()
    
# =========================
# UI
# =========================
st.title("PNA-NY Spring Conference 2026 — Evaluation & Post-Test")
st.caption(
    "Complete the attendance form, post-test, and evaluation. "
    "On passing (≥ 75%), your certificate will be generated. "
    "Please make sure your name is spelled correctly, as this will be used for your certificate."
)

st.markdown(f"**Conference Title:** {COURSE_TITLE}")
st.markdown(f"**Date:** {COURSE_DATE} ({COURSE_TIME})")

# ---- Participant info ----
with st.form("info"):
    c1, c2 = st.columns(2)

    with c1:
        full_name = st.text_input("Full Name *")
        credentials = st.text_input("Credentials (e.g., RN, BSN, CCRN, and others)")
        profession = st.text_input("Profession")
        state_or_country = st.text_input("State or Country")

    with c2:
        email = st.text_input("Email Address *")
        pnany_member = st.radio("PNANY Member", ["Yes", "No"], horizontal=True)
        pnaa_member = st.radio("PNAA Member", ["Yes", "No"], horizontal=True)

        pnaa_chapter = ""
        if pnaa_member == "Yes":
            pnaa_chapter = st.text_input("If yes, indicate PNAA Chapter")

        first_time_attending = st.radio(
            "Is this your first time attending a PNA-NY educational conference?",
            ["Yes", "No"],
            horizontal=True,
        )

    attendance = st.checkbox(
        "I certify that I attended and completed this educational activity."
    )
    cont = st.form_submit_button("Continue")

if cont:
    if not full_name or not email or not attendance:
        st.error("Please complete Full Name, Email Address, and confirm attendance.")
    elif pnaa_member == "Yes" and not pnaa_chapter.strip():
        st.error("Please indicate your PNAA Chapter.")
    else:
        st.session_state["participant_ok"] = True
        st.success("Thanks. Continue below.")

# ---- Main form ----
if st.session_state.get("participant_ok"):
    st.subheader("Post-Test Evaluation")
    st.write("Select True or False for each statement below. Aim for a 75% score or higher to earn your continuing education credits.")

    answers = {}
    for i, q in enumerate(QUIZ, start=1):
        st.markdown(f"**{i}. {q['question']}**")
        answers[str(i)] = st.radio(
            f"Answer Q{i}",
            q["options"],
            index=None,
            key=f"quiz_{i}",
            label_visibility="collapsed",
            horizontal=True,
        )

    st.subheader("Course and Speakers’ Evaluation")
    speaker_rating_options = ["Excellent", "Very Good", "Good", "Fair", "Poor"]
    overall_rating_options = ["Strongly Agree", "Agree", "Neutral", "Disagree", "Strongly Disagree"]

    speakers = [
        "Leorey N. Saligan, PhD, RN, CRNP, FAAN",
        "Elvy Barroso, PhD, MD, MSc, MPH, MS, SN, RN, FNYAM",
        "Ray-an B. Talatala, DNP, RN, CNOR, NPD-BC, FNAP, FAORN",
        "Simon Paul P. Navarro, MA, BSN, RN, CCRN, TCRN",
        "Joseph D. Tariman, PhD, MBA, ANP-BC, FAAN",
        "Fidelindo Lim, DNP, CCRN, FAAN",
        "Randelle Sasa, Ph.D., RN-BC, CCRN, CNE, NEA-BC",
        "Meriam Caboral-Stevens, PhD, RN, CNE, NP, FNYAM, FAAN",
    ]

    speaker_ratings = {}
    for idx, speaker in enumerate(speakers, start=1):
        st.markdown(f"**Speaker {idx}: {speaker}**")
        a, b, c = st.columns(3)
        with a:
            speaker_ratings[f"speaker_{idx}_effectiveness"] = st.selectbox(
                "Speaker’s Effectiveness", speaker_rating_options, key=f"speaker_{idx}_effectiveness"
            )
        with b:
            speaker_ratings[f"speaker_{idx}_expertise"] = st.selectbox(
                "Speaker’s Level of Expertise", speaker_rating_options, key=f"speaker_{idx}_expertise"
            )
        with c:
            speaker_ratings[f"speaker_{idx}_teaching_methods"] = st.selectbox(
                "Effectiveness of Teaching Methods", speaker_rating_options, key=f"speaker_{idx}_teaching_methods"
            )
        st.divider()

    overall_well_organized = st.select_slider("It was well organized", options=overall_rating_options, value="Strongly Agree")
    overall_consistent = st.select_slider("It was consistent with the flyer advertising the event.", options=overall_rating_options, value="Strongly Agree")
    overall_relevant = st.select_slider("It was relevant to the learning outcomes of the presentation.", options=overall_rating_options, value="Strongly Agree")
    overall_virtual = st.select_slider("It effectively used virtual teaching methods.", options=overall_rating_options, value="Strongly Agree")
    overall_objectives = st.select_slider("It enabled me to meet my personal objectives.", options=overall_rating_options, value="Strongly Agree")

    st.markdown("**This activity will assist in the improvement of my (check all that apply):**")
    improve_knowledge = st.checkbox("Knowledge")
    improve_skills = st.checkbox("Skills")
    improve_competence = st.checkbox("Competence")
    improve_performance = st.checkbox("Performance")
    improve_patient_outcomes = st.checkbox("Patient Outcomes")

    st.markdown("**Practice change**")
    practice_choices = [
        "Apply current research findings to my clinical, educational, or leadership practice.",
        "Use the EBP process to address a practice issue in my setting.",
        "Initiate or participate in a QI project to improve outcomes.",
        "Use data to measure and sustain practice improvements.",
        "Implement an innovative strategy to enhance care delivery or nursing practice.",
        "Share knowledge through presentation, publication, or mentorship.",
        "Advocate for a culture of inquiry and continuous improvement.",
    ]
    selected_practice_changes = []
    for item in practice_choices:
        if st.checkbox(item, key=f"pc_{item}"):
            selected_practice_changes.append(item)
    practice_change_other = st.text_input("Other")

    fair_balanced = st.radio("Do you feel this content was fair and balanced?", ["Yes", "No"], index=0, horizontal=True)
    commercial_support = st.radio("Did this presentation have any commercial support?", ["Yes", "No"], index=1, horizontal=True)
    commercial_bias = st.radio(
        "If yes, did the speaker demonstrate any commercial bias?",
        ["N/A", "Yes", "No"],
        index=0,
        horizontal=True,
    )
    bias_explain = st.text_input("If yes, explain")
    most_beneficial_topic = st.text_area("Which program topic was most beneficial to you?")
    topics_interest = st.text_area("What topics of interest would you like us to provide?")
    additional_comments = st.text_area("Additional Comments")

    if st.button("Submit Evaluation & Generate Certificate"):
        if any(answers[str(i)] is None for i in range(1, len(QUIZ) + 1)):
            st.error("Please answer all post-test questions.")
            st.stop()

        correct = sum(1 for i, q in enumerate(QUIZ, start=1) if answers[str(i)] == q["answer"])
        total = len(QUIZ)
        score_pct = 100 * correct / total
        passed = score_pct >= PASSING_SCORE

        if passed:
            st.success(f"Your score: {correct}/{total} ({score_pct:.0f}%). You passed.")
        else:
            st.error(f"Your score: {correct}/{total} ({score_pct:.0f}%). Passing score is {PASSING_SCORE}%.")

        cert_id = str(uuid.uuid4())

        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "conference_title": COURSE_TITLE,
            "conference_date": COURSE_DATE,
            "full_name": full_name,
            "email": email,
            "credentials": credentials,
            "profession": profession,
            "state_or_country": state_or_country,
            "pnany_member": pnany_member,
            "pnaa_member": pnaa_member,
            "pnaa_chapter": pnaa_chapter,
            "first_time_attending": first_time_attending,
            "attendance_confirmed": "Yes" if attendance else "No",

            "overall_well_organized": overall_well_organized,
            "overall_consistent_with_flyer": overall_consistent,
            "overall_relevant_to_learning_outcomes": overall_relevant,
            "overall_effective_virtual_methods": overall_virtual,
            "overall_met_personal_objectives": overall_objectives,

            "improve_knowledge": "Yes" if improve_knowledge else "No",
            "improve_skills": "Yes" if improve_skills else "No",
            "improve_competence": "Yes" if improve_competence else "No",
            "improve_performance": "Yes" if improve_performance else "No",
            "improve_patient_outcomes": "Yes" if improve_patient_outcomes else "No",

            "practice_change_selected": "; ".join(selected_practice_changes),
            "practice_change_other": practice_change_other,
            "fair_balanced": fair_balanced,
            "commercial_support": commercial_support,
            "commercial_bias": commercial_bias,
            "bias_explain": bias_explain,
            "most_beneficial_topic": most_beneficial_topic,
            "topics_interest": topics_interest,
            "additional_comments": additional_comments,

            "quiz_score": correct,
            "quiz_total": total,
            "quiz_pct": f"{score_pct:.0f}",
            "quiz_passed": "Yes" if passed else "No",
            "cert_id": cert_id,
        }

        for idx, speaker in enumerate(speakers, start=1):
            row[f"speaker_{idx}_name"] = speaker
            row[f"speaker_{idx}_effectiveness"] = speaker_ratings[f"speaker_{idx}_effectiveness"]
            row[f"speaker_{idx}_expertise"] = speaker_ratings[f"speaker_{idx}_expertise"]
            row[f"speaker_{idx}_teaching_methods"] = speaker_ratings[f"speaker_{idx}_teaching_methods"]

        for i, q in enumerate(QUIZ, start=1):
            row[f"post_test_q{i}"] = answers[str(i)]

        save_row_to_csv(os.path.join(SAVE_DIR, "submissions.csv"), row)

        try:
            save_eval_to_sheets(row)
            st.success("Saved to Google Sheets.")
        except Exception as e:
            st.warning(f"Could not save to Google Sheets: {e}")

        if not passed:
            st.info("Certificate is only generated for participants who achieve the passing score.")
            st.stop()

        pdf_bytes = make_certificate_pdf(full_name, email, score_pct, cert_id)

        cert_row = {
            "cert_id": cert_id,
            "name": full_name,
            "email": email,
            "course_title": COURSE_TITLE,
            "course_date": COURSE_DATE,
            "credit_hours": CREDIT_HOURS,
            "score_pct": f"{score_pct:.0f}",
        }
        try:
            save_cert_to_sheets(cert_row)
        except Exception as e:
            st.warning(f"Could not log certificate to Google Sheets: {e}")

        st.success("Congratulations! Your certificate is ready.")
        st.download_button(
            "Download Certificate (PDF)",
            data=pdf_bytes,
            file_name=f"Certificate_{full_name.replace(' ', '_')}.pdf",
            mime="application/pdf",
        )
