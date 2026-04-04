import httpx
import logging
import re
import os

from fastapi import FastAPI, BackgroundTasks, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from http import HTTPStatus
from ssl import SSLError
from anthropic import Anthropic
from dotenv import load_dotenv


from .database import *

load_dotenv()

origins = [
    "http://localhost:3000"
]

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # You can change to DEBUG or ERROR based on your needs

# Create console handler and set level to INFO
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create file handler to store logs
fh = logging.FileHandler('finder.log')
fh.setLevel(logging.DEBUG)

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
api_key = os.getenv("ANTHROPIC_API_KEY")
logger.info(f"Anthropic API Key: {'set' if api_key else 'not set'}")
ai_client = Anthropic(api_key=api_key)

@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("Shutting down HTTPX client")
    await client.aclose()

async def validate_profile_with_ai(url: str, username: str, html_snippet: str) -> bool:
    try:
        message = ai_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": f"""Analyze this web page HTML and determine if it is a real, valid profile page for the username '{username}'.

URL: {url}
Username: {username}

HTML snippet (first 2000 chars):
{html_snippet[:2000]}

Respond with ONLY 'YES' if this appears to be a genuine profile page for the given username, or 'NO' if it does not.
Consider:
- Does the page seem to be a login, error, or generic landing page?
- Does the page contain content associated with a user profile (posts, followers, bio, etc)?
- Is the username visible or referenced on the page?

Respond with exactly 'YES' or 'NO'."""
                }
            ]
        )
        
        # Extract text from the first TextBlock in the response
        response_text = ""
        for block in message.content:
            if hasattr(block, "text"):
                response_text = block.text.strip().upper() # type: ignore
                break
        
        is_valid = response_text == "YES"
        logger.debug(f"AI validation for {url}: {response_text}")
        return is_valid
    except Exception as e:
        logger.warning(f"AI validation failed for {url}: {e}")
        return False

async def confirm_profile_exists(url: str, username: str, title: str) -> bool:
    try:
        response = await client.get(url, follow_redirects=True, timeout=15.0)
    except (httpx.ReadTimeout, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.TooManyRedirects, ValueError, SSLError) as e:
        logger.warning(f"Profile validation failed for '{username}' at '{url}': {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error during profile validation for '{username}' at '{url}'")
        return False

    if response.status_code != HTTPStatus.OK:
        logger.debug(f"Profile validation GET returned {response.status_code} for {url}")
        return False

    
    # X returns an object that has a valid marker on it, if it's not valid 
    logger.info(f"Checking profile existence for '{username}' on {url} with title '{title}'")
    if title.lower() == 'x':
        username_available = response.json().get('valid')
        reason = response.json().get('reason', 'No reason provided').lower()
        return not username_available and reason == 'taken' # if username not available because it's taken then profile exists, if it's not available because it's invalid then profile doesn't exist

    final_url = str(response.url).lower()
    deny_url_tokens = ["login", "signin", "sign-in", "sign_up", "register", "auth", "account", "signup"]
    if any(token in final_url for token in deny_url_tokens):
        logger.debug(f"Profile validation ignored redirect/login URL for {url}: {final_url}")
        return False

    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type and "text" not in content_type:
        logger.debug(f"Profile validation skipped non-HTML content for {url}: {content_type}")
        return False

    body = response.text.lower()
    deny_body_patterns = [
        "log in", "login", "sign in", "sign up", "register", "create account",
        "not found", "page not found", "404", "410", "private", "forbidden", "access denied",
        "account does not exist", "user not found", "profile does not exist", "this account is not available",
        "there isn\'t anything here", "page isn\'t available", "this page isn\'t available", "this blog doesn\'t exist.",
        "member not found", "couldn\'t find", "profile unavailable", "does not exist",
    ]

    # Garmin has a specific blank page for non-existent profiles that doesn't include typical error phrases, so we can add a specific check for that
    if '<html class="signed-out">' in body and "garmin" in final_url:
        logger.debug(f"Profile validation denied Garmin profile {url} due to signed-out blank page")
        return False

    if any(pattern in body for pattern in deny_body_patterns):
        logger.debug(f"Profile validation denied {url} due to body content")
        return False

    title_match = re.search(r"<title[^>]*>(.*?)<\/title>", response.text, re.IGNORECASE | re.DOTALL)
    page_title = title_match.group(1).strip().lower() if title_match else ""

    og_type_match = re.search(r"<meta[^>]+property=[\"']og:type[\"'][^>]+content=[\"']([^\"']+)[\"']", response.text, re.IGNORECASE)
    if og_type_match and "profile" in og_type_match.group(1).lower():
        logger.debug(f"Profile validation accepted {url} due to og:type profile")
        return True

    username_lower = username.lower()
    username_in_title = username_lower in page_title
    username_in_url = username_lower in final_url
    username_in_body = username_lower in body

    profile_markers = [
        "followers", "following", "posts", "timeline", "about", "bio", "overview", "activity",
        "repositories", "repos", "projects", "connections", "friends", "photos", "videos",
        "likes", "stories", "publications", "recent posts", "reviews", "blogs", "posts", "tweets"
    ]
    marker_count = sum(1 for marker in profile_markers if marker in body or marker in page_title)

    if username_in_title:
        logger.debug(f"Profile validation accepted {url} because username appears in title")
        return True

    if username_in_body and marker_count >= 1:
        logger.debug(f"Profile validation accepted {url} because username and profile markers were found")
        return True

    if username_in_url and marker_count >= 1:
        logger.debug(f"Profile validation accepted {url} because URL and profile markers were found")
        return True

    logger.debug(f"Profile heuristics inconclusive for {url}, escalating to AI validation")
    is_profile = await validate_profile_with_ai(url, username, response.text)
    return is_profile

"""
Gets list of websites from WhatsMyName, this is used to search usernames
"""
def get_site_list() -> list[dict]:
    url = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"
    response = httpx.get(url, timeout=20.0)

    try:
        if response.status_code == HTTPStatus.OK:
            data = response.json()
            logger.debug("Successfully retrieved site list from WhatsMyName")
            return data['sites']
        logger.error(f"Failed to retrieve JSON. Status code: {response.status_code}")
        raise Exception(f"Failed to retrieve JSON. Status code: {response.status_code}")
    except Exception as e:
        logger.exception("Failed to retrieve WhatsMyName dataset")
        raise

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

async def search_for_username(username: str) -> list:
    sites_found = []
    insert_username(username)
    logger.info(f"Starting background search for username '{username}'")

    sites = get_all_sites()
    task_status[username] = {
        "status": "in_progress",
        "found_sites": [],
        "total_sites": len(sites),
        "checked_sites": 0,
    }

    for site_data in sites:
        uri = site_data['uri']
        try:
            response = await client.head(uri.format(account=username), follow_redirects=True)
            task_status[username]["checked_sites"] += 1

            if 'valid' in site_data and not site_data['valid']:
                logger.debug(f"Skipping invalid site entry for '{username}': {uri}")
                continue

            if response.status_code == HTTPStatus.OK:
                profile_url = uri.format(account=username)
                is_profile = await confirm_profile_exists(profile_url, username, site_data.get('title'))
                if not is_profile:
                    logger.debug(f"Head-only match rejected for '{username}' on {profile_url}")
                    continue

                insert_username_correlation(username, site_data)
                site_result = site_data.copy()
                site_result["profile_url"] = profile_url
                site_result["uri"] = profile_url
                sites_found.append(site_result)
                task_status[username]["found_sites"].append(site_result)
                logger.debug(f"Username '{username}' found on site: {uri}")
            else:
                logger.debug(f"No match for '{username}' on site: {uri} (status={response.status_code})")
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.TooManyRedirects, ValueError, SSLError) as e:
            logger.warning(f"Request failed for '{username}' on site '{uri}': {e}")
            continue
        except Exception as e:
            logger.exception(f"Unexpected error while searching for username '{username}' on site '{uri}'")
            task_status[username] = {
                "status": "failed",
                "error": str(e),
                "found_sites": task_status[username].get("found_sites", []),
                "checked_sites": task_status[username].get("checked_sites", 0),
                "total_sites": task_status[username].get("total_sites", len(sites)),
            }
            raise

    logger.info(f"Finished background search for username '{username}'. Found {len(sites_found)} matches.")
    task_status[username]["status"] = "completed"
    return sites_found

@app.get("/scan/{username}")
async def get_username_data(username: str, background_tasks: BackgroundTasks, refresh: str = "false"):
    logger.info(f"Received scan request for '{username}' with refresh={refresh}")

    if username in task_status:
        current_task_status = task_status[username]["status"]
        if current_task_status in {"in_progress", "pending"}:
            logger.info(f"Search already in progress for '{username}'")
            return JSONResponse(
                status_code=HTTPStatus.PROCESSING,
                content={"message": f"Search for {username} in progress", "status": current_task_status},
            )

    refresh = refresh.lower()

    if refresh == "false" and has_username_been_searched(username):
        logger.info(f"Returning cached search results for '{username}'")
        sites = get_sites_by_username(username)
        return sites

    if refresh != "false":
        logger.info(f"Invalidating cache for '{username}' and starting a fresh search")
        delete_search_history(username)

    background_tasks.add_task(search_for_username, username)
    task_status[username] = {"status": "pending", "found_sites": [], "total_sites": 0, "checked_sites": 0}
    logger.info(f"Scheduled background search task for '{username}'")

    data = {"message": f"Search for username {username} started."}
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=data)

@app.get("/scan/status/{username}")
async def get_search_status(username: str):
    if username not in task_status:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Username search task not found.")

    return task_status[username]