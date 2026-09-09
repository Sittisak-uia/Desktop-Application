# Desktop Applications Suite

A collection of Python & PyQt6 desktop applications developed for productivity and entertainment.

---

## Applications Included

### 1. Task Manager PRO (`task_manager/`)
A feature-rich desktop task and productivity management application powered by SQLite and PyQt6.
- **Authentication**: Secure password hashing with unique salts (PBKDF2-HMAC-SHA256).
- **Dashboard**: Real-time KPI summary cards, priority breakdowns, and category utilization.
- **Task Operations**: CRUD operations, priority filtering, category filtering, search, and instant task duplication.
- **Trash / Recycle Bin**: Two-stage deletion with soft-delete safeguards, item recovery, and permanent deletion.
- **Overdue Notifications**: Dynamic overdue task detection and dismissal with anti-spam safeguards.
- **Categories**: Dynamic category management with cascade `SET NULL` relational protection.
- **CSV Export & Import**: Standardized RFC 4180 CSV export/import with full Unicode/Thai text support and transactional rollback.
- **Database Backup & Restore**: Safe database backup via SQLite's native backup API (`sqlite3.Connection.backup()`), automated pre-restore safety snapshots, and strict schema validation.
- **Dual Themes**: Complete Light and Dark theme palette system persisted across restarts via `QSettings`.

### 2. Media Player PRO (`media_player/`)
A desktop audio and video player featuring playlist management, looping, playback controls, and playlist navigation.

### 3. Tarot App (`media_player/tarot_main.py`)
An interactive desktop Tarot reading application featuring the 22 Major Arcana cards with past, present, and future 3-card spread interpretations.

---

## Setup & Running Locally

### Requirements
- Python 3.10+ (tested on Python 3.13)
- PyQt6

```bash
# Create virtual environment
python -m venv .venv
& .\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run Task Manager PRO
python -m task_manager.main

# Run Media Player PRO
python media_player/main.py

# Run Tarot App
python media_player/tarot_main.py
```

---

## Running Tests

All applications include full test suites:
```bash
python -m unittest discover -s tests -v
```

---

## Building Executables (PyInstaller)

Each application has its dedicated PyInstaller specification file for standalone packaging:

```bash
# Build Task Manager PRO
pyinstaller task_manager.spec --noconfirm

# Build Media Player PRO
pyinstaller build.spec --noconfirm

# Build Tarot App
pyinstaller tarot.spec --noconfirm
```
Executables are bundled into `dist/<AppName>/`.
