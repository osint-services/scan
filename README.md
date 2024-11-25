# WhatsMyName
A FastAPI-based project that searches for usernames across various websites using the WhatsMyName dataset. The project includes a SQLite-backed database to track search history, site data, and correlations.

## Requirements
- Python 3.9 or higher

### Dependencies
- FastAPI
- httpx
- SQLite

### Setup
1. Create Python virtual environment. `python -m venv venv`
2. Activate virtual environment. `source venv/bin/activate`
3. Install dependencies. `pip install -r requirements.txt`
4. Start server. `fastapi dev main.py` 

### Endpoints

- GET `/{username}` - Pass the username that you would like searched. If this is the first time the username has been searched then the search results will need to be built for the first time. Previous lookups will use the cached results until they are invalidated.

Data is returned with the format of:
```json
[{
    "name": "GitHub",
    "uri_check": "https://github.com/osint-services",
    "cat": "coding"
}, {
    "name": "Facebook",
    "uri_check": "https://facebook.com/osint-services",
    "cat": "social"
}]
```
