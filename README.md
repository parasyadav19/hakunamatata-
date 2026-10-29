# 🎓 Smart Attendance System - Backend

Face Recognition + Geofencing + Auto Excel Export wala attendance backend.

### 🚀 Live Repo
`https://github.com/parasyadav19/hakunamatata-.git`

### ✨ Features
- **Face Recognition** - DeepFace se student verification
- **Geofencing** - 100m radius check (College: 23.272188, 77.447813)
- **Already Registered Check** - Ek roll no. se dobara register nahi hoga
- **Time Lock** - 10:00 AM ke baad attendance closed
- **Already Marked Protection** - Ek din me ek hi baar attendance
- **Auto Excel** - Roz 10:05 AM ko Present + Absent Excel auto generate
- **GPS Fake Check** - 0,0 location pe Invalid Location error

### 🛠️ Tech Stack
- FastAPI + Uvicorn
- PostgreSQL (Neon) + psycopg
- DeepFace + TensorFlow
- Pandas + APScheduler

### ⚙️ Setup Local

```bash
# 1. Clone
git clone https://github.com/parasyadav19/hakunamatata-.git
cd hakunamatata-

# 2. Venv
python -m venv venv
venv\Scripts\activate

# 3. Install
pip install -r requirements.txt

# 4. .env file banao (ye GitHub pe nahi hai)
# .env.example ko copy karke .env banao aur apne Neon creds dalo
PGHOST=your_host
PGDATABASE=your_db
PGUSER=your_user
PGPASSWORD=your_pass
PGSSLMODE=require

# 5. Run
uvicorn main:app --reload📡 API EndpointsMethodEndpointKaamPOST/registerNaya student register (rollno, name, photo)POST/mark-attendanceFace + GPS se attendancePOST/check-distanceBina attendance ke sirf distance checkGET/export-excelAaj ki present list ExcelGET/export-absent-excelAaj ki absent list ExcelGET/attendance-summaryTotal / Present / Absent SummaryGET/Server running check🔒 Security
.env, temp/, daily_reports/, dataset/, _.jpg, _.pkl sab .gitignore me hai👨‍💻 Author
Paras Yadav - Smart Attendance Project 2026