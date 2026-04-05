"""
Profile Validation Service
"""

from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path
from ssl import SSLError

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
import yaml

from .config import logger
from .models import SiteData, SiteResult, XValidationResponse, XUsernameAvailabilityReason

origins = ["http://localhost:3000"]

client = httpx.AsyncClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application lifecycle")
    yield
    logger.info("Shutting down HTTPX client")
    await client.aclose()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_site_config(config_path: Path) -> list[dict]:
    if not config_path.exists():
        raise FileNotFoundError(f"Site config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    if not config or "sites" not in config:
        raise ValueError("Site config must contain a top-level 'sites' key")

    return config["sites"]

SITE_CONFIG = load_site_config(Path(__file__).resolve().parent / "sites.yaml")


def get_site_list(username: str) -> list[SiteData]:
    """
    Returns a list of site data objects for the given username by applying the configured templates.
    """
    return [
        SiteData(
            title=site["title"],
            profile_uri=site["profile_uri"].format(username=username),
            validation_uri=site["validation_uri"].format(username=username),
        )
        for site in SITE_CONFIG
    ]


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
    return data
