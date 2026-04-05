"""
Profile Validation Service
"""

import logging
from http import HTTPStatus
from ssl import SSLError

import httpx
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import ValidationError

from models import SiteData, SiteResult, XValidationResponse, XUsernameAvailabilityReason

load_dotenv()

origins = ["http://localhost:3000"]

# Set up logger
logger = logging.getLogger(__name__)
# You can change to DEBUG or ERROR based on your needs
logger.setLevel(logging.DEBUG)

# Create console handler and set level to INFO
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# Create file handler to store logs
fh = logging.FileHandler("finder.log")
fh.setLevel(logging.DEBUG)

# Create formatter and add it to the handlers
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
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
    allow_methods=["*"],
    allow_headers=["*"],
)

client = httpx.AsyncClient()


@app.on_event("shutdown")
async def shutdown() -> None:
    """
    Clean up resources on shutdown, such as closing the HTTPX client.
    """
    logger.info("Shutting down HTTPX client")
    await client.aclose()


async def confirm_profile_exists(url: str, username: str, title: str) -> bool:
    """
    For some sites, a HEAD request may return 200 OK for both existing and non-existing profiles.
    In such cases, we need to perform a GET request to confirm the existence of the profile.
    This function handles that logic, including error handling for various exceptions that may
    occur during the HTTP request.
    """
    try:
        response = await client.get(url, follow_redirects=True, timeout=15.0)
    except (
        httpx.ReadTimeout,
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadError,
        httpx.TooManyRedirects,
        ValueError,
        SSLError,
    ) as e:
        logger.warning(f"Profile validation failed for '{username}' at '{url}': {e}")
        return False
    except Exception as e:
        logger.exception(
            f"Unexpected error during profile validation for '{username}' at '{url}': {e}"
        )
        return False

    if response.status_code != HTTPStatus.OK:
        logger.debug(
            f"Profile validation GET returned {response.status_code} for {url}"
        )
        return False

    logger.info(
        f"Checking profile existence for '{username}' on {url} with title '{title}'"
    )

    # map out responses using pydantic and validate the response structure, then determine if profile exists based on the response data
    if title.lower() == "x":
        try:
            validation = XValidationResponse.parse_obj(response.json())
        except (ValidationError, ValueError) as e:
            logger.warning(
                f"Invalid validation response for '{username}' on '{url}': {e}"
            )
            return False

        # if username is not available because it's taken then profile exists
        return not validation.valid and validation.reason == XUsernameAvailabilityReason.taken

    return False


def get_site_list(username: str) -> list[SiteData]:
    """
    Returns a list of site data objects for the given username.
    """
    return [
        SiteData(
            title="X",
            profile_uri=f"https://x.com/{username}",
            validation_uri=f"https://api.x.com/i/users/username_available.json?username={username}",
        )
    ]


async def search_for_username(username: str) -> list[SiteResult]:
    """
    Searches for the given username across multiple sites by performing HEAD requests to the
    validation URIs. If a HEAD request returns 200 OK, it performs a GET request to confirm
    the existence of the profile. The function handles various exceptions that may occur during
    HTTP requests and logs relevant information throughout the process.
    """
    sites_found: list[SiteResult] = []
    sites = get_site_list(username)
    for site_data in sites:
        validation_uri = site_data.validation_uri
        try:
            response = await client.head(validation_uri, follow_redirects=True)

            if response.status_code == HTTPStatus.OK:
                is_profile = await confirm_profile_exists(
                    validation_uri, username, site_data.title
                )
                if not is_profile:
                    logger.debug(
                        f"Head-only match rejected for '{username}' on {validation_uri}"
                    )
                    continue

                site_result = SiteResult(
                    title=site_data.title,
                    profile_uri=site_data.profile_uri,
                    validation_uri=site_data.validation_uri,
                    is_valid_profile=is_profile,
                )
                sites_found.append(site_result)
                logger.debug(f"Username '{username}' found on site: {validation_uri}")
            else:
                logger.debug(f"No match for '{username}' on site: {validation_uri} \
                        (status={response.status_code})")
        except (
            httpx.ReadTimeout,
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadError,
            httpx.TooManyRedirects,
            ValueError,
            SSLError,
        ) as e:
            logger.warning(
                f"Request failed for '{username}' on site '{validation_uri}': {e}"
            )
            continue
        except Exception as e:
            logger.exception(f"Unexpected error while searching for username \
                             '{username}' on site '{validation_uri}'")
            raise e

    logger.info(
        f"Finished background search for username '{username}'. Found {len(sites_found)} matches."
    )
    return sites_found


@app.get("/scan/{username}")
async def get_username_data(username: str):
    """
    Endpoint to scan for the given username across multiple sites. It logs the incoming request and calls the search function to perform the scan, returning the results as a JSON response with a 200 OK status code.
    """
    logger.info(f"Received scan request for '{username}'")
    data = await search_for_username(username)
    return JSONResponse(status_code=status.HTTP_200_OK, content=data)
