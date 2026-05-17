# Vedimy

Vedimy is a Flask-based learning and examination platform with authentication, rooms, exams, proctoring, analytics, guest registration, file handling, chatbot support, and a static frontend served by the backend.

## Project Structure

```text
.
├── app.py                  # Root launcher for the backend app
├── backend/                # Flask API, models, services, sockets, migrations
│   ├── app.py
│   ├── config.py
│   ├── requirements.txt
│   ├── models/
│   ├── routes/
│   └── services/
└── frontend/               # HTML, CSS, and JavaScript frontend
    ├── pages/
    ├── styles/
    └── js/
```

## Requirements

- Python 3.11 or newer
- pip

## Setup

Create and activate a virtual environment:

```powershell
python -m venv backend\venv
backend\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r backend\requirements.txt
```

## Environment Variables

Use environment variables for secrets and deployment-specific settings. Do not commit real keys or passwords.

Common variables:

```text
SECRET_KEY=change-me
JWT_SECRET_KEY=change-me
DATABASE_URL=sqlite:///vedimy.db
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=noreply@vedimy.com
FACE_ENCRYPTION_KEY=32-character-encryption-key
PORT=5000
```

## Run Locally

From the repository root:

```powershell
python app.py
```

Open:

```text
http://localhost:5000
```

Health check:

```text
http://localhost:5000/api/health
```

## Notes

- Local virtual environments, databases, logs, caches, and generated reports/screenshots are ignored by Git.
- For production, set strong `SECRET_KEY`, `JWT_SECRET_KEY`, and `FACE_ENCRYPTION_KEY` values through the host environment.
