# Resume Match App

## Overview
A simple full-stack application that accepts a resume and job description, scores the resume for fit, and returns a fit decision.

## Backend

Install dependencies:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the backend:

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend

Install dependencies:

```bash
cd frontend
npm install
```

Run the frontend:

```bash
npm run dev
```

Open the provided Vite URL in the browser.

## Usage

1. Paste the job description into the Job Description field.
2. Paste the resume text into the Resume field.
3. Click **Score Resume**.

The app displays whether the resume is a fit, shows a score, and lists matched keywords.

You can also upload plain text or document files for the job description and resume. PDF and DOCX uploads are supported on the backend.
