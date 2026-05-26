"""
Vedimy Browser-Level Feature Check
Tests every page (HTTP 200) and every API endpoint with correct routes.
Run with: python -X utf8 browser_check.py
"""
import requests, json, time, io, base64, sys
from PIL import Image
from reportlab.pdfgen import canvas as rlcanvas

BASE = "http://127.0.0.1:5000"
session = requests.Session()

PASS, FAIL, WARN = [], [], []

def check(name, ok, msg=""):
    if ok:
        print(f"  [PASS] {name}")
        PASS.append(name)
    else:
        print(f"  [FAIL] {name}  =>  {msg}")
        FAIL.append((name, msg))

def warn(name, msg=""):
    print(f"  [WARN] {name}  =>  {msg}")
    WARN.append((name, msg))

# ── helpers ─────────────────────────────────────────────────
def make_b64_image():
    img = Image.new('RGB', (100,100), color=(180,140,100))
    buf = io.BytesIO(); img.save(buf, format='JPEG')
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

def make_image_bytes():
    img = Image.new('RGB', (100,100), color=(180,140,100))
    buf = io.BytesIO(); img.save(buf, format='JPEG'); return buf.getvalue()

def make_pdf_bytes():
    buf = io.BytesIO(); c = rlcanvas.Canvas(buf)
    c.drawString(100,750,"Vedimy AI Lecture. Machine learning trains models on data.")
    c.drawString(100,730,"Deep neural networks have multiple layers of neurons.")
    c.drawString(100,710,"Model evaluation uses precision, recall and F1 score.")
    c.showPage(); c.save(); return buf.getvalue()

DUMMY_B64   = make_b64_image()
DUMMY_BYTES = make_image_bytes()
PDF_BYTES   = make_pdf_bytes()

def get_page(path, expect_text=None):
    try:
        r = session.get(BASE + path, timeout=8)
        ok = r.status_code == 200
        if ok and expect_text:
            ok = expect_text.lower() in r.text.lower()
        return ok, r.status_code
    except Exception as e:
        return False, str(e)

def post(path, payload, token=None):
    h = {"Content-Type":"application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    try:
        r = session.post(BASE+"/api"+path, json=payload, headers=h, timeout=12)
        return r.status_code, r.json() if r.content else {}
    except Exception as e:
        return 0, {"error": str(e)}

def patch(path, payload, token=None):
    h = {"Content-Type":"application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    try:
        r = session.patch(BASE+"/api"+path, json=payload, headers=h, timeout=10)
        return r.status_code, r.json() if r.content else {}
    except Exception as e:
        return 0, {"error": str(e)}

def put_req(path, payload, token=None):
    h = {"Content-Type":"application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    try:
        r = session.put(BASE+"/api"+path, json=payload, headers=h, timeout=10)
        return r.status_code, r.json() if r.content else {}
    except Exception as e:
        return 0, {"error": str(e)}

def get(path, token=None):
    h = {}
    if token: h["Authorization"] = f"Bearer {token}"
    try:
        r = session.get(BASE+"/api"+path, headers=h, timeout=8)
        return r.status_code, r.json() if r.content else {}
    except Exception as e:
        return 0, {"error": str(e)}

def post_files(path, files_dict, data_dict=None, token=None):
    h = {}
    if token: h["Authorization"] = f"Bearer {token}"
    try:
        r = session.post(BASE+"/api"+path, files=files_dict, data=data_dict or {}, headers=h, timeout=20)
        return r.status_code, r.json() if r.content else {}
    except Exception as e:
        return 0, {"error": str(e)}

# ─────────────────────────────────────────────────────────────
print()
print("="*62)
print("  VEDIMY BROWSER-LEVEL FEATURE CHECK")
print("="*62)

# ── SECTION 1: Frontend Pages ─────────────────────────────────
print("\n[S1] Frontend Pages (HTTP 200)")
PAGES = [
    ("/pages/index.html",             "vedimy",       "Landing Page"),
    ("/pages/login.html",             "login",        "Host Login Page"),
    ("/pages/register.html",          "register",     "Registration Page"),
    ("/pages/join.html",              "join",         "Join Room Page"),
    ("/pages/dashboard.html",         "dashboard",    "Host Dashboard"),
    ("/pages/conference.html",        "video",        "Conference Room"),
    ("/pages/exam-room.html",         "exam",         "Exam Room"),
    ("/pages/face-auth.html",         "verify",       "Face Auth Gate"),
    ("/pages/face-setup.html",        "face",         "Face Setup Page"),
    ("/pages/biometric-manager.html", "biometric",    "Biometric Manager"),
    ("/pages/guest-register.html",    "vedimy",       "Guest Registration Form"),
    ("/pages/guest-reg-manager.html", "registration", "Guest Reg Manager"),
    ("/pages/ai-teaching.html",       "ai",           "AI Teaching Studio"),
    ("/pages/learning-hub.html",      "learning",     "Learning Hub"),
    ("/pages/analytics.html",         "analytics",    "Analytics & Reports"),
    ("/pages/security-activity.html", "security",     "Security Activity"),
    ("/pages/coordinator.html",       "coordinator",  "Coordinator Panel"),
    ("/pages/storage.html",           "storage",      "Cloud Storage"),
]
for path, text, label in PAGES:
    ok, code = get_page(path, text)
    check(label, ok, f"HTTP {code}" if not ok else "")

# ── SECTION 2: Static Assets ──────────────────────────────────
print("\n[S2] CSS & JS Static Assets")
ASSETS = [
    ("/styles/globals.css",             "CSS globals"),
    ("/styles/components.css",          "CSS components"),
    ("/styles/layout.css",              "CSS layout"),
    ("/styles/chatbot.css",             "CSS chatbot"),
    ("/js/core/api.js",                 "JS api module"),
    ("/js/core/state.js",               "JS state module"),
    ("/js/components/toast.js",         "JS toast component"),
    ("/js/chatbot.js",                  "JS chatbot"),
    ("/js/pages/conference.js",         "JS conference"),
    ("/js/pages/exam-room.js",          "JS exam-room"),
    ("/js/pages/analytics.js",          "JS analytics"),
    ("/js/pages/dashboard.js",          "JS dashboard"),
]
for path, label in ASSETS:
    ok, code = get_page(path)
    check(label, ok, f"HTTP {code}" if not ok else "")

# ── SECTION 3: Authentication ─────────────────────────────────
print("\n[S3] Authentication APIs")
ts = int(time.time())
H_EMAIL = f"bcheck_host_{ts}@vedimy.io"
G_EMAIL = f"bcheck_guest_{ts}@vedimy.io"
PWD     = "BrowserCheck123!"

code, data = post("/auth/register", {"name":"BCheck Host","email":H_EMAIL,"password":PWD,"role":"host","image":DUMMY_B64})
check("Host Registration (with face image)", code == 201, data.get("error",""))

code, data = post("/auth/login", {"email":H_EMAIL,"password":PWD,"role":"host"})
check("Host Login (email+password+role)", code == 200 and "access_token" in data, data.get("error",""))
HOST_TOKEN = data.get("access_token","")

code, data = get("/auth/me", HOST_TOKEN)
check("Host Identity GET /auth/me", code == 200 and data.get("role") == "host", str(data))

code, data = post("/auth/register", {"name":"BCheck Guest","email":G_EMAIL,"password":PWD,"role":"guest","image":DUMMY_B64})
check("Guest Registration (with face image)", code == 201, data.get("error",""))

code, data = post("/auth/login", {"email":G_EMAIL,"password":PWD,"role":"guest"})
check("Guest Login (email+password+role)", code == 200 and "access_token" in data, data.get("error",""))
GUEST_TOKEN = data.get("access_token","")

code, data = post("/auth/login/face", {"email":H_EMAIL,"role":"host","image":DUMMY_B64})
check("Host Face Recognition Login", code in (200,401), data.get("error",""))  # 401 ok - dummy face won't match

# ── SECTION 4: Room Management ────────────────────────────────
print("\n[S4] Room Management APIs")

code, data = post("/rooms/create", {"title":"BCheck Room","room_type":"class","description":"Browser check"}, HOST_TOKEN)
check("Create Live Session Room", code == 201, data.get("error",""))
ROOM_ID   = data.get("id","")
ROOM_CODE = data.get("room_code","")

code, data = get(f"/rooms/{ROOM_CODE}", HOST_TOKEN)
check("Get Room by Code", code == 200 and data.get("room_code") == ROOM_CODE, str(data)[:80])

code, data = get("/rooms/my", HOST_TOKEN)
check("List My Rooms (host)", code == 200 and isinstance(data, list) and len(data) > 0, str(data)[:80])

code, data = post(f"/rooms/{ROOM_ID}/state", {"status":"active"}, HOST_TOKEN)
check("Start Room Session", code == 200, data.get("error",""))

code, data = post(f"/rooms/{ROOM_ID}/state", {"is_locked": True}, HOST_TOKEN)
check("Lock Room", code == 200, data.get("error",""))

code, data = post(f"/rooms/{ROOM_ID}/state", {"is_locked": False}, HOST_TOKEN)
check("Unlock Room", code == 200, data.get("error",""))

code, data = post(f"/rooms/{ROOM_CODE}/join", {}, GUEST_TOKEN)
check("Guest Join Room (waiting/admitted)", code in (200,202), data.get("error",""))
GUEST_STATUS = data.get("status","")

code, data = get(f"/rooms/{ROOM_ID}/waiting", HOST_TOKEN)
check("Get Waiting Room List", code == 200 and isinstance(data, list), str(data)[:80])

code, data = get(f"/rooms/{ROOM_ID}/participants/live", HOST_TOKEN)
check("Get Live Participants", code == 200, str(data)[:80])

code, data = post(f"/rooms/{ROOM_CODE}/leave", {}, GUEST_TOKEN)
check("Guest Leave Room", code == 200, data.get("error",""))

# ── SECTION 5: Guest Registration Form ───────────────────────
print("\n[S5] Guest Registration Form System")

code, data = post(f"/guest-reg/{ROOM_ID}/generate-link", {}, HOST_TOKEN)
check("Generate Guest Registration Form Link", code == 200 and "token" in data, data.get("error",""))
FORM_TOKEN = data.get("token","")

code, data = get(f"/guest-reg/{FORM_TOKEN}/form-info")
check("Guest View Form Info (public, no auth)", code == 200 and "room_title" in data, str(data)[:80])

# Submit form with face image via multipart
fd = {"guest_name":"Browser Guest","contact_number":"9876543210","address":"123 Test St"}
files = {"face_image": ("face.jpg", io.BytesIO(DUMMY_BYTES), "image/jpeg")}
r2 = session.post(f"{BASE}/api/guest-reg/{FORM_TOKEN}/submit", data=fd, files=files, timeout=15)
check("Guest Form Submission (with biometric)", r2.status_code in (200,201,422), f"HTTP {r2.status_code}")
if r2.status_code == 422:
    warn("Guest Form Submission", "Dummy face has no detectable features (expected in test)")

code, data = get(f"/guest-reg/{ROOM_ID}/active-form", HOST_TOKEN)
check("Get Active Form Token (host)", code == 200, data.get("error",""))

code, data = get(f"/guest-reg/{ROOM_ID}/submissions", HOST_TOKEN)
check("Host View All Submissions", code == 200 and isinstance(data, list), str(data)[:80])

# ── SECTION 6: Biometric Management ──────────────────────────
print("\n[S6] Biometric Management APIs")

files2 = {"images": ("face.jpg", io.BytesIO(DUMMY_BYTES), "image/jpeg")}
code2, data2 = post_files(f"/guest-face/{ROOM_ID}/upload", files2, token=HOST_TOKEN)
check("Upload Guest Biometric Profile Image", code2 == 200, data2.get("error","")[:80] if isinstance(data2, dict) else "")

code, data = get(f"/guest-face/{ROOM_ID}/profiles", HOST_TOKEN)
check("List Guest Biometric Profiles", code == 200 and isinstance(data, list), str(data)[:80])

code, data = patch(f"/guest-face/{ROOM_ID}/mode", {"biometric_mode":"required"}, HOST_TOKEN)
check("Set Biometric Mode: required (PATCH)", code == 200, data.get("error",""))

code, data = patch(f"/guest-face/{ROOM_ID}/mode", {"biometric_mode":"exam_only"}, HOST_TOKEN)
check("Set Biometric Mode: exam_only (PATCH)", code == 200, data.get("error",""))

code, data = patch(f"/guest-face/{ROOM_ID}/mode", {"biometric_mode":"disabled"}, HOST_TOKEN)
check("Set Biometric Mode: disabled (PATCH)", code == 200, data.get("error",""))

code, data = post(f"/guest-face/{ROOM_ID}/verify", {"image": DUMMY_B64}, GUEST_TOKEN)
check("Face Verify Endpoint (any result)", code in (200,422), data.get("error",""))

code, data = get(f"/guest-face/{ROOM_ID}/logs", HOST_TOKEN)
check("Biometric Verification Logs", code == 200 and isinstance(data, list), str(data)[:80])

# ── SECTION 7: AI Teaching Studio ────────────────────────────
print("\n[S7] AI Teaching Studio APIs")

TRANSCRIPT = ("Photosynthesis is the process by which green plants use sunlight to synthesize "
              "nutrients from carbon dioxide and water. This process is fundamental to life. "
              "Chlorophyll in leaves captures solar energy. The light reactions occur in thylakoids. ") * 3
code, data = post("/ai/record-lecture", {"transcript":TRANSCRIPT,"room_id":ROOM_ID,"title":"BCheck Lecture"}, HOST_TOKEN)
check("Record Lecture Transcript (POST)", code == 201 and "lecture_id" in data, data.get("error",""))
LECTURE_ID = data.get("lecture_id","")

code, data = post("/ai/summarize", {"lecture_id": LECTURE_ID}, HOST_TOKEN)
check("AI Summarize Lecture", code == 200 and "summary" in data, data.get("error",""))
AI_LECTURE_ID = data.get("ai_lecture_id","")

code, data = post("/ai/translate", {"ai_lecture_id": AI_LECTURE_ID, "target_language": "hi"}, HOST_TOKEN)
check("AI Translate Summary to Hindi", code == 200 and "translated_summary" in data, data.get("error",""))

code, data = post("/ai/generate-questions", {"lecture_id":LECTURE_ID,"count":3,"type":"mixed","difficulty":"easy"}, HOST_TOKEN)
check("AI Generate Mixed Questions (MCQ+Short)", code == 200 and "questions" in data, data.get("error",""))

code, data = get("/ai/languages")
check("AI Supported Languages List (GET)", code == 200 and "languages" in data, str(data)[:60])

code, data = get("/ai/lectures", HOST_TOKEN)
check("List AI Lectures (GET)", code == 200 and "lectures" in data, str(data)[:60])

if LECTURE_ID:
    code, data = get(f"/ai/lectures/{LECTURE_ID}/summary", HOST_TOKEN)
    check("Get Lecture Summary Detail (GET)", code == 200 and "summary" in data, str(data)[:60])

# PDF Upload
pdf_files = {"file": ("lecture.pdf", io.BytesIO(PDF_BYTES), "application/pdf")}
code2, data2 = post_files("/ai/upload-pdf", pdf_files, {"title":"BCheck PDF","room_id":ROOM_ID}, HOST_TOKEN)
check("PDF Upload & AI Text Extraction", code2 == 201 and "lecture_id" in (data2 or {}), str(data2)[:80] if not code2==201 else "")

# ── SECTION 8: Exam System ────────────────────────────────────
print("\n[S8] Exam System APIs")

code, data = post("/exams/create", {"room_id":ROOM_ID,"title":"BCheck Exam","duration_minutes":30,"instructions":"Browser check test"}, HOST_TOKEN)
check("Create Exam", code == 201 and "id" in data, data.get("error",""))
EXAM_ID = data.get("id","")

Q_LIST = [
    {"question":"What is 2+2?","type":"mcq","options":["1","2","4","8"],"answer":"4","marks":5},
    {"question":"Define photosynthesis","type":"short_answer","answer":"Plant food making","marks":10}
]
# Add questions: PUT /exams/<id>/questions
code, data = put_req(f"/exams/{EXAM_ID}/questions", {"questions": Q_LIST}, HOST_TOKEN)
check("Add Questions to Exam (PUT)", code == 200, data.get("message",data.get("error","")))

# Start exam: PUT /exams/<id>/start
code, data = put_req(f"/exams/{EXAM_ID}/start", {}, HOST_TOKEN)
check("Start Exam Session (PUT)", code == 200, data.get("error",""))

# Get exam with questions: GET /exams/<id>
code, data = get(f"/exams/{EXAM_ID}", GUEST_TOKEN)
check("Guest Fetch Exam Details+Questions", code == 200, str(data)[:60])
QUESTIONS = data.get("questions") or []
if isinstance(QUESTIONS, str):
    import json as _j
    try: QUESTIONS = _j.loads(QUESTIONS)
    except: QUESTIONS = []

# Submit: answers as dict keyed q_0, q_1 etc
answers_dict = {f"q_{i}": "4" for i in range(len(QUESTIONS))}
code, data = post(f"/exams/{EXAM_ID}/submit", {"answers": answers_dict}, GUEST_TOKEN)
check("Guest Submit Exam Answers", code in (200,201) and "score" in data, data.get("error",""))
if code in (200,201):
    print(f"         Score: {data.get('score','?')}")

code, data = get(f"/exams/{EXAM_ID}/violations", HOST_TOKEN)
check("Host View Violations Report", code == 200, str(data)[:60])

code, data = get("/exams/my-results", GUEST_TOKEN)
check("Guest View My Exam Results", code == 200, str(data)[:60])

code, data = get("/exams/upcoming", GUEST_TOKEN)
check("Guest View Upcoming Exams", code == 200, str(data)[:60])

# ── SECTION 9: Analytics ──────────────────────────────────────
print("\n[S9] Analytics & Reporting APIs")

code, data = get("/analytics/dashboard", HOST_TOKEN)
check("Analytics Dashboard Stats", code == 200 and "total_classes" in data, str(data)[:60])

code, data = get("/analytics/security-activity", HOST_TOKEN)
check("Security Activity Logs", code == 200, str(data)[:60])

code, data = get("/analytics/attendance-trend", HOST_TOKEN)
check("Attendance Trend (14 days)", code == 200, str(data)[:60])

code, data = get("/analytics/exam-scores", HOST_TOKEN)
check("Exam Scores Distribution", code == 200, str(data)[:60])

# ── SECTION 10: Chatbot & Support ────────────────────────────
print("\n[S10] AI Chatbot & Support System")

code, data = post("/chatbot/message", {"message":"How do I join a Vedimy class?"}, HOST_TOKEN)
check("AI Chatbot /chatbot/message", code == 200 and "response" in data, data.get("error",""))

# chatbot/help uses field 'issue' not 'message'
code, data = post("/chatbot/help", {"issue":"Cannot join room — I get error when clicking join button"}, HOST_TOKEN)
check("Support Ticket /chatbot/help (field=issue)", code in (200,201), data.get("error",""))

code, data = get("/chatbot/history", HOST_TOKEN)
check("Chatbot History /chatbot/history", code == 200, str(data)[:60])

# ── SECTION 11: File Storage ──────────────────────────────────
print("\n[S11] Cloud File Storage APIs")

files3 = {"file": ("test.txt", io.BytesIO(b"Browser check test file content."), "text/plain")}
code2, data2 = post_files("/files/upload", files3, token=HOST_TOKEN)
# Response has nested structure: {"file": {"id": ..., "filename": ...}}
file_obj = (data2 or {}).get("file", data2 or {})
FILE_ID = file_obj.get("id","") if isinstance(file_obj, dict) else ""
check("Upload File /files/upload", code2 == 201 and bool(FILE_ID), str(data2)[:80])

code, data = get("/files/list", HOST_TOKEN)
check("List Files /files/list", code == 200 and isinstance(data, list), str(data)[:60])

if FILE_ID:
    r3 = session.get(f"{BASE}/api/files/download/{FILE_ID}", headers={"Authorization": f"Bearer {HOST_TOKEN}"}, timeout=8)
    check("Download File /files/download/<id>", r3.status_code == 200, f"HTTP {r3.status_code}")

# ── SECTION 12: Notifications ─────────────────────────────────
print("\n[S12] Notifications & Profile APIs")

code, data = get("/notifications/", HOST_TOKEN)
check("Get Notifications List", code == 200 and isinstance(data, list), str(data)[:60])

code, data = put_req("/auth/profile/name", {"name":"Updated BCheck Host"}, HOST_TOKEN)
check("Update Profile Name (PUT /auth/profile/name)", code == 200, data.get("error",""))

# ── SECTION 13: Coordinator ───────────────────────────────────
print("\n[S13] Coordinator / Proctor APIs")

code, data = get("/coordinator/exams", HOST_TOKEN)
check("Coordinator Exam List", code == 200, str(data)[:60])

code, data = get("/coordinator/logs", HOST_TOKEN)
check("Coordinator Proctor Logs", code == 200, str(data)[:60])

if EXAM_ID:
    code, data = get(f"/coordinator/monitor/{EXAM_ID}", HOST_TOKEN)
    check("Coordinator Monitor Exam", code == 200, str(data)[:60])

# ── SECTION 14: Session Cleanup ───────────────────────────────
print("\n[S14] Session Cleanup")

code, data = put_req(f"/exams/{EXAM_ID}/end", {}, HOST_TOKEN)
check("End Exam Session (PUT)", code == 200, data.get("error",""))

code, data = post(f"/rooms/{ROOM_ID}/state", {"status":"ended"}, HOST_TOKEN)
check("End Room Session", code == 200, data.get("error",""))

# ── FINAL REPORT ──────────────────────────────────────────────
total = len(PASS) + len(FAIL)
print()
print("="*62)
print("  BROWSER CHECK FINAL REPORT")
print("="*62)
print(f"  PASSED  : {len(PASS)}/{total}")
print(f"  FAILED  : {len(FAIL)}/{total}")
print(f"  WARNINGS: {len(WARN)}")

if WARN:
    print("\n  Warnings (expected/minor):")
    for w, m in WARN:
        print(f"    [WARN] {w}: {m}")

if FAIL:
    print("\n  Failed checks:")
    for name, msg in FAIL:
        print(f"    [FAIL] {name}: {msg}")
    print()
    sys.exit(1)
else:
    print("\n  ALL CHECKS PASSED!")
    print()
