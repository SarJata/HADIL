# HADIL \u2014 AI-Safe Database Query Execution Layer

HADIL is a secure, AI-driven database query layer. It allows users to query databases using natural language while enforcing strict intent verification and rule-based safety validation before any query executes.

## Architecture

User \u2192 React UI \u2192 FastAPI Backend \u2192 AI Modules \u2192 DB

## Setup

### 1. Backend (FastAPI)

1. Open a terminal and navigate to `backend/`:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .\\.venv\\Scripts\\activate
   # Mac/Linux:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install fastapi uvicorn pydantic
   ```
4. Run the server:
   ```bash
   uvicorn main:app --reload
   ```
The backend will be available at `http://localhost:8000`.

### 2. Frontend (React + Vite)

1. Open another terminal and navigate to `frontend/`:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```
The frontend will be available at `http://localhost:5173`.

## Features
- **Generative AI Mock:** Converts natural language to SQL.
- **AI Verifier:** Extracts and compares intents to prevent unauthorized modifications.
- **Rule-Based Validator:** Blocks `DELETE`/`UPDATE` operations and warns about inefficient queries or missing limits.
- **React UI:** Shows the step-by-step pipeline from generation to execution.

Try searching for `Show me all users` or `Delete user` in the UI to see the validation in action!
