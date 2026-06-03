# 🔬 Nexus Demo API

A demonstration microservice used to showcase the **Project Nexus AI Code Quality & Automated Remediation Pipeline**.

This repository contains intentional code quality issues that trigger the pipeline's automated detection and remediation capabilities.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python -m src.app

# Run tests
pytest tests/ -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check and service info |
| `GET` | `/api/users` | List users (supports `?q=` search) |
| `POST` | `/api/users` | Register a new user |
| `POST` | `/api/auth/login` | Authenticate and get token |
| `POST` | `/api/auth/validate` | Validate an existing token |
| `GET` | `/api/activity` | Recent audit log entries |

## Project Structure

```
src/
├── app.py        # Flask application and route definitions
├── auth.py       # Token generation, validation, permissions
├── database.py   # SQLite data access layer
├── config.py     # Environment-aware configuration
└── utils.py      # Utility functions (sanitization, validation)
tests/
├── test_app.py       # Endpoint integration tests
├── test_auth.py      # Authentication unit tests
└── test_database.py  # Database operation tests
static/
└── index.html    # Service status dashboard
```

## Architecture

- **Runtime:** Python 3.9+ / Flask 3.x
- **Database:** SQLite (file-based, auto-initialized)
- **Auth:** Base64-encoded JSON tokens with expiry
- **Testing:** pytest with unittest-style test classes

## CI/CD Pipeline

This repository is monitored by the **Project Nexus Pipeline** which:

1. **Scans** code with CodeQL for security vulnerabilities
2. **Builds** and runs the test suite
3. **Remediates** failures automatically using AI-generated patches
4. **Opens PRs** with fixes for human review

## License

MIT
