# WhatsMyName
WhatsMyName is an OSINT microservice that searches the [WhatsMyName](https://github.com/WebBreacher/WhatsMyName) dataset for username hits from various websites.
The service uses a database to cache searches because validating usernames is costly and time-consuming so we can cache these searches so that later lookups will 
use the results. There are ways to invalidate the cache and get fresh results if desired. The timestamps are attached to the results so a caller can decide when the
results need to be refreshed. A mechanism to check the status of the search as it processes is also in place.

## Requirements
- Python 3.9 or higher

### Tech Stack
- The REST API framework being used is [FastAPI](https://fastapi.tiangolo.com/)
- The database engine is [SQLite](https://www.sqlite.org/index.html)
- The REST client being used is [httpx](https://www.python-httpx.org/)

### Setup
1. Create Python virtual environment. `python -m venv venv`
2. Activate virtual environment. `source venv/bin/activate`
3. Install dependencies. `pip install -r requirements.txt`
4. Start server. `fastapi dev main.py` 

### Endpoints

- GET `/wmn/search/{username}` - Pass the username that you would like searched. If this is the first time the username has been searched then the search results will need to be built for the first time. Previous lookups will use the cached results until they are invalidated.

Data is returned with the format of:
```json
[{
    "name": "GitHub",
    "uri_check": "https://github.com/osint-services",
    "cat": "coding",
    "search_timestamp": "2024-11-02 17:01:27",
    "found_timestamp": "2024-11-02 17:01:28"
}, {
    "name": "Facebook",
    "uri_check": "https://facebook.com/osint-services",
    "cat": "social",
    "search_timestamp": "2024-11-02 17:01:27",
    "found_timestamp": "2024-11-02 17:01:28"
}]
```
