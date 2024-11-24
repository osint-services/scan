# Find Username Service

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
