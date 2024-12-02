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
    * A new search is initiated if no previous search has been cached. When a search is started a 202 ACCEPTED HTTP status code will be returned to indicate the beginning of the processing.
    * When the processing of a username has begun, subsequent accesses to the endpoint will result in a 102 PROCESSING HTTP status code which means the search is still being executed, this can sometimes take a long time given the size of the dataset and the fact that an HTTP request has to be made for each site.
    * You can use the `/wmn/status/{username}` endpoint to retrieve the status of the search at any given time.
    * Cached searches will return the results with a 200 OK HTTP status code.

    * Query Parameters
        * refresh (boolean): this can be either `true` or `false`. Defaults to `false`. It determines if a request should ignore the cache and build new search results for a given username. This can be useful if cached results are too old.

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

- GET `/wmn/status/{username}` - Get the search status of the given username.

Data is returned with the format of:
```json
{
    "status": "in_progress",
    "sites_found": [{
        "name": "GitHub",
        "uri_check": "https://github.com/osint-services",
        "cat": "coding",
        "search_timestamp": "2024-11-02 17:01:27",
        "found_timestamp": "2024-11-02 17:01:28"
    }]
}
```

