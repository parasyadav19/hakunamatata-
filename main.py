from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import shutil, os
from db import save_student, mark_attendance_db, init_db, get_db, get_todays_attendance_for_excel
from face_engine import register_face, recognize_face
import psycopg.rows
from datetime import datetime, time, date
import math
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== CONFIG =====
COLLEGE_LAT = 23.272188
COLLEGE_LON = 77.447813
ALLOWED_RADIUS_METERS = 100
CUTOFF_TIME = time(10, 0, 0)

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def is_inside_geofence(user_lat, user_lon):
    dist = calculate_distance(user_lat, user_lon, COLLEGE_LAT, COLLEGE_LON)
    return dist <= ALLOWED_RADIUS_METERS, dist

def is_before_cutoff():
    now = datetime.now().time()
    return now <= CUTOFF_TIME, now

# ===== EXCEL FUNCTIONS =====
def create_excel_for_date(target_date):
    data = get_todays_attendance_for_excel(target_date)
    if not data:
        print(f"No attendance for {target_date}, skipping excel")
        return None
    os.makedirs("daily_reports", exist_ok=True)
    df = pd.DataFrame(data)
    file_path = f"daily_reports/attendance_{target_date}.xlsx"
    df.to_excel(file_path, index=False)
    print(f"✅ PRESENT EXCEL: {file_path} - Count: {len(data)}")
    return file_path

def create_absent_excel_for_date(target_date):
    conn = get_db()
    try:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("SELECT * FROM students ORDER BY rollno")
            all_students = cur.fetchall()
            cur.execute("SELECT rollno FROM attendance WHERE date = %s", (target_date,))
            present_rollnos = {r['rollno'] for r in cur.fetchall()}
    finally:
        conn.close()
    absent = [s for s in all_students if s['rollno'] not in present_rollnos]
    if not absent:
        print(f"All present on {target_date}, no absent excel")
        return None
    os.makedirs("daily_reports", exist_ok=True)
    df = pd.DataFrame(absent)
    file_path = f"daily_reports/absent_{target_date}.xlsx"
    df.to_excel(file_path, index=False)
    print(f"✅ ABSENT EXCEL: {file_path} - Count: {len(absent)}")
    return file_path

def auto_export_job():
    today = date.today()
    print(f"Running auto export job for {today} at {datetime.now()}")
    create_excel_for_date(today)
    create_absent_excel_for_date(today)

scheduler = BackgroundScheduler()
scheduler.add_job(auto_export_job, 'cron', hour=10, minute=5)
scheduler.start()

@app.on_event("startup")
def startup():
    init_db()

@app.post("/register")
async def register(rollno: str = Form(...), name: str = Form(...), role: str = Form(...), branch: str = Form(...), year: str = Form(...), photo: UploadFile = File(...)):
    conn = get_db()
    try:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("SELECT rollno, name FROM students WHERE rollno=%s", (rollno,))
            existing = cur.fetchone()
            if existing:
                return {"error": f"Already Registered! {rollno} ({existing['name']}) pehle se registered hai."}
    finally:
        conn.close()

    os.makedirs("temp", exist_ok=True)
    path = f"temp/{rollno}.jpg"
    with open(path, "wb") as f:
        shutil.copyfileobj(photo.file, f)
    
    is_new = save_student(rollno, name, role, branch, year)
    if not is_new:
        return {"error": f"Already Registered! {rollno} pehle se hai."}
    
    register_face(path, rollno)
    return {"rollno": rollno, "status": "Registered"}

@app.post("/mark-attendance")
async def mark_attendance(file: UploadFile = File(...), latitude: float = Form(...), longitude: float = Form(...)):
    if latitude == 0 or longitude == 0:
        return {"status": "Invalid Location", "message": "GPS nahi mila, Location ON karo aur Allow karo"}

    before_cutoff, curr_t = is_before_cutoff()
    if not before_cutoff:
        return {"status": "Closed", "message": f"Attendance closed after 10 AM. Time: {curr_t.strftime('%H:%M:%S')}"}
    
    inside, distance = is_inside_geofence(latitude, longitude)
    print(f"CHECK -> User: {latitude},{longitude} | Dist: {int(distance)}m")
    
    if not inside:
        return {"status": "Out of Range", "message": f"College se bahar ho! Distance: {int(distance)}m. {ALLOWED_RADIUS_METERS}m ke andar aao.", "distance": int(distance)}

    os.makedirs("temp", exist_ok=True)
    path = "temp/check.jpg"
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    result = recognize_face(path)
    if not result:
        return {"error": "Face not recognized - Please register first"}
    
    rollno = result
    conn = get_db()
    try:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("SELECT * FROM students WHERE rollno=%s", (rollno,))
            student = cur.fetchone()
    finally:
        conn.close()

    if not student:
        return {"error": "Student not in DB"}

    success = mark_attendance_db(rollno, latitude, longitude, distance)
    if not success:
        return {"status": "Already Marked", "rollno": rollno, "name": student['name'], "branch": student['branch'], "message": "Already Marked for Today"}

    return {"status": "Present", "rollno": rollno, "name": student['name'], "branch": student['branch'], "role": student['role'], "distance": f"{int(distance)}m inside campus", "time": str(curr_t)}

@app.post("/check-distance")
async def check_distance(latitude: float = Form(...), longitude: float = Form(...)):
    dist = calculate_distance(latitude, longitude, COLLEGE_LAT, COLLEGE_LON)
    return {
        "your_lat": latitude,
        "your_lon": longitude,
        "college_lat": COLLEGE_LAT,
        "college_lon": COLLEGE_LON,
        "distance_meters": int(dist),
        "inside": dist <= ALLOWED_RADIUS_METERS
    }

@app.get("/export-excel")
def export_excel():
    today = date.today()
    file_path = create_excel_for_date(today)
    if not file_path or not os.path.exists(file_path):
        return {"message": f"Aaj {today} ko koi attendance nahi"}
    return FileResponse(file_path, filename=f"attendance_{today}.xlsx")

@app.get("/export-excel/{date_str}")
def export_excel_by_date(date_str: str):
    try:
        target = datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        return {"error": "Date format YYYY-MM-DD me bhejo"}
    file_path = create_excel_for_date(target)
    if not file_path:
        return {"message": f"{target} ko koi attendance nahi"}
    return FileResponse(file_path, filename=f"attendance_{target}.xlsx")

@app.get("/absent-list")
def absent_list():
    today = date.today()
    conn = get_db()
    try:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("SELECT * FROM students ORDER BY rollno")
            all_students = cur.fetchall()
            cur.execute("SELECT rollno FROM attendance WHERE date = %s", (today,))
            present_rollnos = {r['rollno'] for r in cur.fetchall()}
    finally:
        conn.close()
    absent = [s for s in all_students if s['rollno'] not in present_rollnos]
    return {
        "date": str(today),
        "total": len(all_students),
        "present": len(present_rollnos),
        "absent": len(absent),
        "absent_list": absent
    }

@app.get("/export-absent-excel")
def export_absent_excel():
    today = date.today()
    file_path = create_absent_excel_for_date(today)
    if not file_path:
        return {"message": f"Aaj {today} sab present hain! Koi absent nahi"}
    return FileResponse(file_path, filename=f"absent_{today}.xlsx")

@app.get("/attendance-summary")
def summary():
    today = date.today()
    present_data = get_todays_attendance_for_excel(today)
    abs_data = absent_list()
    return {
        "date": str(today),
        "total_students": abs_data['total'],
        "present": abs_data['present'],
        "absent": abs_data['absent'],
        "present_list": present_data,
        "absent_list": abs_data['absent_list']
    }

@app.get("/")
def root():
    return {"msg": "Smart Attendance Running", "cutoff": "10:00 AM", "auto_excel": "10:05 AM Present + Absent"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)