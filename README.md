# รวมแอปพลิเคชันเดสก์ท็อป (Desktop Applications Suite)

คลังโค้ด (Repository) นี้รวบรวมโปรเจกต์แอปพลิเคชันเดสก์ท็อปที่พัฒนาด้วย **Python** และ **PyQt6** ไว้ครบทั้งหมด **3 โปรเจกต์** ในที่เดียว ได้แก่:

1. 📋 **Task Manager PRO** — ระบบบริหารจัดการงานและติดตามสถานะงานแบบมืออาชีพด้วย SQLite
2. 🎬 **Media Player PRO** — โปรแกรมเล่นไฟล์เพลงและวิดีโอมัลติมีเดีย
3. 🔮 **Tarot App** — โปรแกรมเปิดไพ่ทาโรต์ทำนายดวงชะตาแบบ 3 ใบ (อดีต ปัจจุบัน อนาคต)

---

## โครงสร้างโปรเจกต์ (Project Structure)

```text
week3-ai-agent/
├── task_manager/              # ซอร์สโค้ดของ Task Manager PRO
│   ├── ui/                    # UI Components (Dashboard, Tasks, Categories, Trash, Settings, ฯลฯ)
│   ├── auth.py                # ระบบยืนยันตัวตนและการเข้ารหัสรหัสผ่าน
│   ├── database.py            # SQLite Database Operations & Schema
│   ├── database_backup.py     # ระบบสำรองและกู้คืนฐานข้อมูล (Safe Backup/Restore)
│   ├── csv_io.py              # ระบบนำเข้า-ส่งออกไฟล์ CSV (RFC 4180 + UTF-8-SIG)
│   ├── models.py              # Data Models
│   └── main.py                # จุดเริ่มต้นการรัน Task Manager PRO
│
├── media_player/              # ซอร์สโค้ดของ Media Player PRO และ Tarot App
│   ├── main.py                # จุดเริ่มต้นการรัน Media Player PRO
│   ├── tarot_main.py          # จุดเริ่มต้นการรัน Tarot App
│   └── tarot_cards/           # ข้อมูลและการ์ดไพ่ทาโรต์
│
├── tests/                     # ชุดทดสอบ Unit Tests ครอบคลุมทุกฟังก์ชัน
├── build.spec                 # PyInstaller spec สำหรับ Media Player PRO
├── tarot.spec                 # PyInstaller spec สำหรับ Tarot App
├── task_manager.spec          # PyInstaller spec สำหรับ Task Manager PRO
├── requirements.txt           # รายการแพ็กเกจ Dependencies ทั้งหมด
└── README.md                  # เอกสารแนะนำโปรเจกต์
```

---

## รายละเอียดโปรเจกต์ทั้ง 3 แอปพลิเคชัน

### 1. Task Manager PRO (`task_manager/`)
แอปพลิเคชันบริหารจัดการงานระดับมืออาชีพที่ออกแบบมาให้มีความปลอดภัย เสถียรภาพสูง และใช้งานง่าย
- **ระบบความปลอดภัยและการเข้าสู่ระบบ (Authentication)**: เข้ารหัสรหัสผ่านด้วยอัลกอริทึมมาตรฐานสากล PBKDF2-HMAC-SHA256 พร้อม Unique Salt รายบัญชี
- **หน้าสรุปข้อมูล (Dashboard)**: แสดงสถิติงานแบบเรียลไทม์ (Total, Pending, Completed, Overdue), การจำแนกตามความสำคัญ (Priority Breakdown) และตามหมวดหมู่ (Category Breakdown) รองรับทั้ง Light และ Dark Theme พร้อมคอนทราสต์ที่คมชัด สวยงาม
- **การจัดการงาน (Task Operations)**: รองรับการเพิ่ม แก้ไข ลบ ค้นหา กรองสถานะ และฟังก์ชันทำซ้ำงาน (**Duplicate Task**) ได้ทันที
- **ระบบถังขยะปลอดภัย (Trash / Recycle Bin)**: ป้องกันข้อมูลสูญหายด้วย Soft Delete (ย้ายไปถังขยะก่อน) รองรับการกู้คืนงานเดิม (Restore) หรือลบถาวร (Permanent Delete)
- **ระบบแจ้งเตือนงานเกินกำหนด (Overdue Notification)**: ตรวจจับงานที่เลยกำหนดส่งอัตโนมัติ พร้อมแบนเนอร์แจ้งเตือนและระบบ Dismiss ป้องกันการแจ้งเตือนซ้ำ
- **ระบบหมวดหมู่ (Categories)**: จัดการหมวดหมู่งานได้อย่างอิสระ มีระบบป้องกันความสัมพันธ์ข้อมูล (Cascade `SET NULL`) เมื่องานถูกลบหมวดหมู่
- **นำเข้าและส่งออกข้อมูล (CSV Export/Import)**: รองรับมาตรฐาน RFC 4180 รองรับภาษาไทยและ Unicode (UTF-8 with BOM) พร้อมระบบ Transaction Rollback ป้องกันไฟล์เสียหาย
- **สำรองและกู้คืนฐานข้อมูล (Database Backup & Restore)**: ใช้ SQLite Online Backup API ปลอดภัยขณะแอปกำลังทำงาน พร้อม Safety Snapshot อัตโนมัติก่อนกู้คืน และตรวจสอบ Schema อย่างเข้มงวด
- **ระบบธีม (Dual Themes - Light & Dark Mode)**: ปรับเปลี่ยนธีมได้ทันทีและบันทึกสถานะถาวรผ่าน `QSettings`

### 2. Media Player PRO (`media_player/`)
โปรแกรมเล่นไฟล์มัลติมีเดียเดสก์ท็อปสำหรับเล่นไฟล์เสียงและวิดีโอ
- เล่น หยุด ชั่วคราว และปรับระดับเสียงได้อย่างราบรื่น
- จัดการ Playlist เพิ่ม ลบ และเลือกเล่นเพลง/วิดีโอในคิว
- รองรับโหมดเล่นวนซ้ำ (Loop) และการควบคุมแทร็ก

### 3. Tarot App (`media_player/tarot_main.py`)
แอปพลิเคชันทำนายดวงชะตาด้วยไพ่ทาโรต์แบบอินเทอร์แอคทีฟ
- สำรับไพ่ Major Arcana ครบทั้ง 22 ใบ พร้อมภาพประกอบที่สวยงาม
- ทำนายดวงแบบ 3 ใบ (อดีต - ปัจจุบัน - อนาคต)
- ให้คำทำนาย ความหมายของไพ่ และการแปลผลในรูปแบบที่เข้าใจง่าย

---

## ข้อกำหนดของระบบ (Prerequisites)

- **Python 3.10 ขึ้นไป** (แนะนำและทดสอบบน Python 3.13)
- ระบบปฏิบัติการ: Windows 10/11, macOS, หรือ Linux
- แพ็กเกจหลัก: **PyQt6** (ติดตั้งผ่าน `requirements.txt`)

---

## วิธีการติดตั้งและเริ่มใช้งาน (Installation & Setup)

1. **สร้างและเปิดใช้งาน Virtual Environment**:
   ```powershell
   # บน Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **ติดตั้ง Dependencies ทั้งหมด**:
   ```bash
   pip install -r requirements.txt
   ```

3. **วิธีเปิดใช้งานแต่ละแอปพลิเคชัน**:

   - **เปิด Task Manager PRO**:
     ```bash
     python -m task_manager.main
     ```
     *(บัญชีผู้ใช้เริ่มต้น: Username: `admin` / Password: `admin123`)*

   - **เปิด Media Player PRO**:
     ```bash
     python media_player/main.py
     ```

   - **เปิด Tarot App**:
     ```bash
     python media_player/tarot_main.py
     ```

---

## การทดสอบระบบ (Automated Tests)

มีชุดทดสอบครอบคลุมฟังก์ชันการทำงานของระบบ:

```bash
# รันชุดทดสอบทั้งหมดในคลังโค้ด
python -m unittest discover -s tests -v

# รันเฉพาะชุดทดสอบของ Dashboard ใน Task Manager PRO
python -m unittest tests.test_dashboard -v
```

---

## การแปลงเป็นไฟล์โปรแกรม (.exe) ด้วย PyInstaller

โปรเจกต์นี้มีไฟล์สเปก `.spec` แยกอิสระสำหรับแต่ละแอปพลิเคชัน สามารถคอมไพล์เป็นโปรแกรมใช้งานแบบไม่ต้องติดตั้ง Python ได้ทันที:

```powershell
# 1. Build Task Manager PRO -> dist/TaskManagerPRO/
pyinstaller task_manager.spec --noconfirm

# 2. Build Media Player PRO -> dist/MediaPlayerPRO/
pyinstaller build.spec --noconfirm

# 3. Build Tarot App -> dist/TarotApp/
pyinstaller tarot.spec --noconfirm
```
