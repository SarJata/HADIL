# HADIL \u2014 AI-Safe Database Query Execution Layer

HADIL is a secure, AI-driven database query layer. It allows users to query databases using natural language while enforcing strict intent verification and rule-based safety validation before any query executes.

## Architecture

User \u2192 React UI \u2192 FastAPI Backend \u2192 AI Modules \u2192 DB

## 🚀 Getting Started / Run It Yourself Guide

Follow these instructions to get the HADIL project up and running on your local machine.

### Prerequisites

Ensure you have the following installed on your system:
- **Python 3.9+** (for the FastAPI backend)
- **Node.js 18+** & **npm** (for the React/Vite frontend)
- **Git** (optional, for version control)

### 1. Clone the Repository
```bash
git clone <repository-url>
cd HADIL
```

### 2. Backend Setup (FastAPI & AI Modules)

The backend relies on Python, FastAPI, and OpenAI for the AI intelligence layer.

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   
   # On Windows:
   .\.venv\Scripts\activate
   
   # On Mac/Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   Install all required packages from `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Environment Variables:**
   Create a `.env` file in the `backend/` directory. You will need a valid OpenAI API key for the generative AI features to work.
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   DATABASE_FOLDER=./databases
   ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
   ```

5. **Run the backend server:**
   ```bash
   uvicorn main:app --reload
   ```
   The backend API will start and be available at `http://localhost:8000`. You can also view the interactive API docs at `http://localhost:8000/docs`.

### 3. Frontend Setup (React + Vite)

The frontend is a modern React application built with Vite and styled with Tailwind CSS.

1. **Open a new terminal window/tab** and navigate to the frontend directory from the project root:
   ```bash
   cd frontend
   ```

2. **Install Node.js dependencies:**
   ```bash
   npm install
   ```

3. **Set up Environment Variables:**
   Create a `.env` file in the `frontend/` directory to point to your local backend API:
   ```env
   VITE_API_URL=http://localhost:8000
   ```

4. **Start the development server:**
   ```bash
   npm run dev
   ```
   The frontend will now be running. Open `http://localhost:5173` in your browser to interact with the HADIL UI.

## Features
- **Generative AI Mock:** Converts natural language to SQL.
- **AI Verifier:** Extracts and compares intents to prevent unauthorized modifications.
- **Rule-Based Validator:** Blocks `DELETE`/`UPDATE` operations and warns about inefficient queries or missing limits.
- **React UI:** Shows the step-by-step pipeline from generation to execution.

Try searching for `Show me all users` or `Delete user` in the UI to see the validation in action!
