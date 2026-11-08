# Happen

Happen is a lightweight, offline desktop app for organizing goals, breaking them into tabbed roadmaps and actionable steps, and tracking how much of your budget is spent or remaining.

## Features

- **Goals, Tabs, and Steps:** Organize large plans into goals, group tracks into tabs, and break each track down into individual steps with costs, notes, and deadlines.
- **Budget & Affordability Tracking:** Set your total funds once and see how much is spent on completed steps, how much remains, and which upcoming steps are currently affordable (highlighted automatically).
- **Multi-Account Local Storage:** Create password-protected local profiles stored in SQLite (`PBKDF2-HMAC-SHA256`).
- **One-Click Backups:** Export timestamped database backups directly from the settings menu.
- **Fast Ordering & Inline Editing:** Edit step titles, costs, notes, and deadlines inline, and reorder goals, tabs, or steps from the right-click context menu.

## Getting Started

### Prerequisites

- Python 3.11+

### Run from Source

```powershell
git clone https://github.com/HeniMohamedAziz/happen.git
cd happen
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Local data is stored in `%APPDATA%\Happen\happen.db` on Windows (or `~/Happen/happen.db` on Linux/macOS).

### Build a Windows Executable

```powershell
.\.venv\Scripts\pyside6-deploy.exe -f -c pysidedeploy.spec
```

The standalone executable is generated at `dist\Happen.exe`.

## License

MIT
