# scan

Profile validation microservice that checks whether usernames exist on social media platforms. The service validates profiles by performing HTTP requests to platform-specific endpoints and confirms existence through response validation.

## Requirements
- Python 3.9 or higher

### Tech Stack
- The REST API framework being used is [FastAPI](https://fastapi.tiangolo.com/)
- The REST client being used is [httpx](https://www.python-httpx.org/)

### Setup
1. Create Python virtual environment. `python -m venv .venv`
2. Activate virtual environment. `source .venv/bin/activate`
3. Install dependencies. `pip install -r requirements.txt`
4. Start server. `fastapi dev main.py`

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
- All requests and processing are logged to both console and `finder.log`.
- CORS is enabled for localhost:3000 frontend connections.

