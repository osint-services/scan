# scan
scan is an OSINT microservice that searches the [WhatsMyName](https://github.com/WebBreacher/WhatsMyName) dataset for username hits from various websites.
The service uses a database to cache search results because validating usernames is costly and time-consuming. Cached results are reused on repeat lookups, and a refresh option exists to rebuild the results.
A status endpoint is exposed so clients can poll long-running searches instead of relying on a single request timeout.

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
- GET `/scan/{username}`
    * Starts a new search if the username has not been cached yet.
    * Returns `202 Accepted` when a new background search is started.
    * Returns `102 Processing` when a search for the username is already pending or in progress.
    * Returns cached results with `200 OK` if the username has already been searched and no refresh is requested.
    * Query Parameters:
        * `refresh` (`true` or `false`, default `false`) — when set to `true`, the cache is invalidated and the username search is rebuilt.

- GET `/scan/status/{username}`
    * Returns the current status of a background search.
    * Use this endpoint to poll progress until the search reaches `completed`.

### Example response for `/scan/{username}` when cached
```json
[
  {
    "title": "GitHub",
    "uri": "https://github.com/osint-services",
    "profile_url": "https://github.com/osint-services",
    "category": "coding",
    "search_timestamp": "2024-11-02 17:01:27",
    "found_timestamp": "2024-11-02 17:01:28"
  },
  {
    "title": "Facebook",
    "uri": "https://facebook.com/osint-services",
    "profile_url": "https://facebook.com/osint-services",
    "category": "social",
    "search_timestamp": "2024-11-02 17:01:27",
    "found_timestamp": "2024-11-02 17:01:28"
  }
]
```

### Example response for `/scan/status/{username}`
```json
{
  "status": "in_progress",
  "found_sites": [
    {
      "title": "GitHub",
      "uri": "https://github.com/osint-services",
      "profile_url": "https://github.com/osint-services",
      "category": "coding",
      "search_timestamp": "2024-11-02 17:01:27",
      "found_timestamp": "2024-11-02 17:01:28"
    }
  ],
  "total_sites": 200,
  "checked_sites": 50
}
```

### Notes
- This service uses background processing and polling rather than long-lived request timeouts.
- The result validation step checks page content and common profile signals to reduce false positives from login, not-found, or generic landing pages.
- If a search fails, `GET /scan/status/{username}` will return a `failed` status and an `error` field may be included in the response.

