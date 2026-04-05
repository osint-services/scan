# profile-checker

Profile validation microservice called `profile-checker` that checks whether usernames exist on social media platforms. The service validates profiles by performing HTTP requests to platform-specific endpoints and confirms existence through response validation.

## Requirements
- Python 3.9 or higher

### Tech Stack
- The REST API framework being used is [FastAPI](https://fastapi.tiangolo.com/)
- The REST client being used is [httpx](https://www.python-httpx.org/)

### Setup
1. Create Python virtual environment. `python -m venv .venv`
2. Activate virtual environment. `source .venv/bin/activate`
3. Install dependencies. `pip install -r requirements.txt`
4. Create a `.env` file with `LOG_LEVEL` and `LOG_FILE` as needed.
5. Start server. `fastapi dev main.py`

### Configuration
- `config.py` initializes logging and reads environment variables.
- `.env` supports:
  - `LOG_LEVEL` — log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
  - `LOG_FILE` — path to the log output file
- Site verification templates are stored in `sites.yaml`.

### Endpoints
- GET `/scan/{username}`
    * Validates whether the given username exists on supported platforms.
    * Returns `200 OK` with results containing found profiles.
    * Performs HEAD requests to platform validation endpoints and follows up with GET requests to confirm profile existence.

### Example response for `/scan/{username}`
```json
[
  {
    "title": "X",
    "profile_uri": "https://x.com/osint-services",
    "validation_uri": "https://api.x.com/i/users/username_available.json?username=osint-services",
    "is_valid_profile": true
  }
]
```

### Notes
- Profile validation checks page responses and validation endpoints to confirm actual profile existence and reduce false positives.
- The service currently supports X (Twitter) profile validation.
- Logging is configured in `config.py` and writes to both console and the file specified by `LOG_FILE`.
- Supported site templates are defined in `sites.yaml`, making it easy to add or update platform endpoints without changing application logic.
- `LOG_LEVEL` and `LOG_FILE` can be configured via `.env`.
- The project root already includes `__init__.py`, so the package can be imported if needed, but script execution does not require additional `__init__.py` files.
- CORS is enabled for localhost:3000 frontend connections.

