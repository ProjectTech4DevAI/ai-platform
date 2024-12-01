# T4D AI Service

This is a FastAPI application for the T4D AI Service.

## Prerequisites

- Python 3.10+
- PostgreSQL
- `pip` (Python package installer)

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/ProjectTech4DevAI/ai-platform.git
cd https://github.com/ProjectTech4DevAI/ai-platform.git
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create the environment from the template

```bash
cp .env.example .env
```

### 5. Set Up Pre-commit Hooks

Install pre-commit and set up the hooks

```bash
pre-commit install
pre-commit run --all-files
```

### 6. Run the application

```bash
python main.py
```

## API Documentation

FastAPI automatically generates interactive API documentation. You can access it at:

- Swagger UI: http://127.0.0.1:7050/api/docs
- ReDoc: http://127.0.0.1:7050/api/redoc