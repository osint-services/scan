import httpx
import logging

from fastapi import FastAPI, BackgroundTasks, status, HTTPException, WebSocket
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from http import HTTPStatus
from ssl import SSLError

from .database import *

origins = [
    "http://localhost:3000"
]

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # You can change to DEBUG or ERROR based on your needs

# Create console handler and set level to INFO
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create file handler to store logs
fh = logging.FileHandler('finder.log')
fh.setLevel(logging.INFO)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(ch)
logger.addHandler(fh)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

client = httpx.AsyncClient()

"""
Gets list of websites from WhatsMyName, this is used to search usernames
"""
def get_site_list() -> list[dict]:
    url = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
    response = httpx.get(url)

    try:
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            logger.debug("Successfully retrieved site list from WhatsMyName")
            return data['sites'] # there is a schema provided by the repository which could be used for validation here
        else:
            logger.error(f"Failed to retrieve JSON. Status code: {response.status_code}")
            raise Exception(f"Failed to retrieve JSON. Status code: {response.status_code}")
    except Exception as e:
        logger.exception(f"Failed to retrieve JSON containing list of websites from WhatsMyName dataset.\nError: {e}")
        raise Exception(f"Failed to retrieve JSON. Error: {e}")

@app.on_event("startup")
async def boot():
    cursor = conn.cursor()
    logger.info('Building database tables...')
    # Create the tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usernames_searched (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        search_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        uri_check TEXT NOT NULL,
        cat TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS username_correlations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username_id INTEGER,
        site_id INTEGER,
        found_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (username_id) REFERENCES usernames_searched(id),
        FOREIGN KEY (site_id) REFERENCES sites(id)
    );
    ''')
    conn.commit()

    logger.info('Ingesting website data...')

    try:
        sites = get_site_list()
        insert_sites(sites)
        logger.info(f"Successfully inserted {len(sites)} sites into the database.")
    except Exception as e:
        logger.error("Failed to ingest website data")
        logger.exception(e)

task_status: dict[str, dict] = {}

async def search_for_username(username: str, websocket: WebSocket) -> list:
    sites_found = []
    insert_username(username)
    logger.info(f"Started searching for username '{username}' on the sites.")

    sites = get_all_sites()
    task_status[username] = {"status": "in_progress", "found_sites" : []}
    for site_data in sites:
        uri = site_data['uri']
        try:
            response = await client.head(uri.format(account=username)) # WhatsMyName uses `account` as formatter argument)
            # if data is marked as invalid, then continue
            if 'valid' in site_data:
                if not site_data['valid']:
                    continue
                
            if response.status_code == HTTPStatus.OK:
                insert_username_correlation(username, site_data)
                sites_found.append(site_data)
                task_status[username]["found_sites"].append(site_data)
                logger.debug(f"Username '{username}' found on site: {uri}")
                message = {
                    'type': 'SEARCH_PROGRESS',
                    'username': username,
                    'sites_matched': task_status[username]['found_sites'],
                    'total_number_of_sites': len(sites)
                }
                await websocket.send_json(message)
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, ValueError, SSLError) as e:
            logger.warning(f"Error while checking site '{uri}' for username '{username}': {e}")
            continue
        except Exception as e:
            logger.exception(f"Unexpected error while searching for username '{username}' on site '{uri}'")
            task_status[username] = {"status": "failed", "error": str(e)}
            raise e

    logger.info(f"Finished searching for username '{username}'. Found {len(sites_found)} sites.")
    task_status[username]["status"] = "completed"
    return sites_found

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    while True:
        try:
            message = await websocket.receive_json()
            if message['type'] == 'CONNECTION_ESTABLISHED':
                await websocket.send_json({
                    'type': 'CONNECTION_ESTABLISHED'
                })
            elif message['type'] == 'INIT_SEARCH':
                username = message['username']
                if has_username_been_searched(username):
                    logger.info(f"Username '{username}' has been previously searched.")
                    sites = get_sites_by_username(username)
                else:
                    sites = await search_for_username(username, websocket)

                await websocket.send_json({
                    'type': 'SEARCH_COMPLETE',
                    'data': sites
                })
        except Exception as e:
            print(f'Error {e}')
            return

@app.get("/scan/{username}")
async def get_username_data(username: str, background_tasks: BackgroundTasks,  refresh: str = "false"):
    if username in task_status:
        current_task_status = task_status[username]['status']
        if current_task_status == 'in_progress' or current_task_status == 'pending':
            return JSONResponse(status_code=HTTPStatus.PROCESSING, content={'message': f'Search for {username} in progress'})
    
    refresh = refresh.lower()
    
    # if refresh has been set to true, then bypass this value even if the username was previously cached.
    if refresh == "false":
        if has_username_been_searched(username):
            logger.info(f"Username '{username}' has been previously searched.")
            sites = get_sites_by_username(username)
            return sites
    else:
        # delete search history before re-caching it
        delete_search_history(username)
    
    background_tasks.add_task(search_for_username, username)
    
    task_status[username] = {"status": "pending", "found_sites": []}
    data = { "message": f"Search for username {username} started." }
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=data)

@app.get("/scan/status/{username}")
async def get_search_status(username: str):
    if username not in task_status:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Username search task not found.")
    
    return task_status[username]