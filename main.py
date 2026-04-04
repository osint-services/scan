import httpx
import logging
import os

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from http import HTTPStatus
from ssl import SSLError
from anthropic import Anthropic
from dotenv import load_dotenv

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

    return False

def get_site_list(username: str) -> list[dict]:
    return [
        {
            'title': 'X',
            'profile_uri': f'https://x.com/{username}',
            'validation_uri': f'https://api.x.com/i/users/username_available.json?username={username}'
        }
    ]

async def search_for_username(username: str) -> list:
    sites_found = []
    sites = get_site_list(username)
    for site_data in sites:
        validation_uri = site_data['validation_uri']
        try:
            response = await client.head(validation_uri, follow_redirects=True)

            if response.status_code == HTTPStatus.OK:
                is_profile = await confirm_profile_exists(validation_uri, username, site_data.get('title', 'Unknown'))
                if not is_profile:
                    logger.debug(f"Head-only match rejected for '{username}' on {validation_uri}")
                    continue

                site_result = site_data.copy()
                site_result["profile_uri"] = site_data['profile_uri']
                site_result["validation_uri"] = validation_uri
                site_result['is_valid_profile'] = is_profile
                sites_found.append(site_result)
                logger.debug(f"Username '{username}' found on site: {validation_uri}")
            else:
                logger.debug(f"No match for '{username}' on site: {validation_uri} (status={response.status_code})")
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.TooManyRedirects, ValueError, SSLError) as e:
            logger.warning(f"Request failed for '{username}' on site '{validation_uri}': {e}")
            continue
        except Exception as e:
            logger.exception(f"Unexpected error while searching for username '{username}' on site '{validation_uri}'")
            raise

    logger.info(f"Finished background search for username '{username}'. Found {len(sites_found)} matches.")
    return sites_found

@app.get("/scan/{username}")
async def get_username_data(username: str):
    logger.info(f"Received scan request for '{username}'")
    data = await search_for_username(username)
    return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content=data)