# Codex Ticket Generator

## Setup

```powershell
cd F:\PythonAiProjects\Tickets\Codex
.\CodexCode\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open: `http://127.0.0.1:5000`

## What it does

- Supports up to 5 adults and 3 children (max 8 visitors total).
- Takes per-visitor fields: Visitor Name, Age, Gender.
- Auto-fills:
  - Booked at: current datetime (IST)
  - Date: current date
- Age rules:
  - Age < 15 => Child
  - Age >= 15 => Adult
- ASI Fee per visitor:
  - Adult => Rs. 35
  - Child => Rs. 0
- Generates downloadable PDF:
  - 1 visitor => 1 page
  - 8 visitors => 8 pages
- Keeps original template design and overlays only requested fields.
