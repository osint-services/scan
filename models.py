from enum import Enum

from pydantic import BaseModel, Field


class XUsernameAvailabilityReason(str, Enum):
    taken = "taken"
    available = "available"
    invalid_username = "invalid_username"


class XValidationResponse(BaseModel):
    valid: bool
    reason: XUsernameAvailabilityReason
    msg: str
    desc: str


class SiteData(BaseModel):
    title: str
    profile_uri: str
    validation_uri: str


class SiteResult(SiteData):
    is_valid_profile: bool = Field(..., description="True when the profile exists")
