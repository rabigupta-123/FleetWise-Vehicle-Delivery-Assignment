import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def validate_iso8601(value: str) -> str:
    if not value or not isinstance(value, str):
        raise ValueError("scheduled_time must be a valid ISO 8601 timestamp string")
    val = value.strip()
    try:
        normalized = val[:-1] + "+00:00" if val.endswith("Z") else val
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO 8601 timestamp: '{value}'") from exc
    return val


PHONE_REGEX = re.compile(r"^\+?[0-9\-\s\(\)]{7,30}$")


class VehicleCreate(BaseModel):
    vehicle_id: str | None = Field(default=None, max_length=50)
    registration_no: str = Field(..., min_length=1, max_length=50)
    type: str = Field(default="Van", min_length=1, max_length=50)
    capacity: int = Field(..., gt=0)
    status: Literal["available", "maintenance", "inactive"] = "available"

    @field_validator("registration_no")
    @classmethod
    def normalise_reg(cls, v: str) -> str:
        s = v.strip().upper()
        if not s:
            raise ValueError("registration_no cannot be empty")
        return s

    @field_validator("type")
    @classmethod
    def strip_type(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("type cannot be empty")
        return s

    @field_validator("vehicle_id")
    @classmethod
    def strip_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class VehicleStatusPatch(BaseModel):
    status: Literal["available", "maintenance", "inactive"]


class DriverCreate(BaseModel):
    driver_id: str | None = Field(default=None, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=7, max_length=30)
    availability_status: Literal["available", "unavailable"] = "available"

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("name cannot be empty")
        return s

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        s = v.strip()
        if not PHONE_REGEX.match(s):
            raise ValueError(f"Invalid phone number format: '{v}'")
        return s

    @field_validator("driver_id")
    @classmethod
    def strip_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class DriverStatusPatch(BaseModel):
    availability_status: Literal["available", "unavailable"]


class DeliveryCreate(BaseModel):
    delivery_id: str | None = Field(default=None, max_length=50)
    pickup: str = Field(..., min_length=1, max_length=255)
    dropoff: str = Field(..., min_length=1, max_length=255)
    scheduled_time: str = Field(..., min_length=1)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    required_capacity: int | None = Field(default=None, gt=0)
    pickup_lat: float | None = None
    pickup_lng: float | None = None
    drop_lat: float | None = None
    drop_lng: float | None = None

    @field_validator("pickup", "dropoff")
    @classmethod
    def strip_locations(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Location cannot be empty")
        return s

    @field_validator("scheduled_time")
    @classmethod
    def check_iso(cls, v: str) -> str:
        return validate_iso8601(v)

    @field_validator("delivery_id")
    @classmethod
    def strip_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class AssignRequest(BaseModel):
    vehicle_id: str = Field(..., min_length=1, max_length=50)
    driver_id: str = Field(..., min_length=1, max_length=50)
    version: int | None = None

    @field_validator("vehicle_id", "driver_id")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("ID cannot be empty")
        return s


class DeliveryStatusPatch(BaseModel):
    status: str = Field(..., min_length=1)
    reason: str | None = None
    version: int | None = None


class DriverPhonePatch(BaseModel):
    phone: str = Field(..., min_length=7, max_length=30)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        s = v.strip()
        if not PHONE_REGEX.match(s):
            raise ValueError(f"Invalid phone number format: '{v}'")
        return s


class TrackingSessionStart(BaseModel):
    driver_id: str = Field(..., min_length=1, max_length=50)
    device_id: str | None = Field(default=None, max_length=50)
    device_info: str | None = Field(default=None, max_length=255)
    consent_given: bool = Field(default=True, description="Explicit driver consent for real-time location streaming")


class TrackingConsentUpdate(BaseModel):
    consent_given: bool = Field(..., description="Whether driver has granted explicit location tracking consent")


class TrackingSessionStop(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=50)


class GPSLocationCreate(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=50)
    device_id: str | None = Field(default=None, max_length=50)
    driver_id: str | None = Field(default=None, max_length=50)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy: float = Field(..., ge=0.0)
    altitude: float | None = None
    altitude_accuracy: float | None = Field(default=None, ge=0.0)
    speed: float | None = Field(default=None, ge=0.0)
    heading: float | None = Field(default=None, ge=0.0, le=360.0)
    source: str = Field(default="device", pattern="^(device|simulated)$")
    device_timestamp: str = Field(..., min_length=1)

    @field_validator("device_timestamp")
    @classmethod
    def check_ts(cls, v: str) -> str:
        return validate_iso8601(v)


class DeviceRegisterRequest(BaseModel):
    driver_id: str = Field(..., min_length=1, max_length=50)
    nickname: str = Field(..., min_length=1, max_length=80)
    device_category: str | None = Field(default=None, max_length=50)
    model: str | None = Field(default=None, max_length=100)
    os_family: str | None = Field(default=None, max_length=50)
    os_version: str | None = Field(default=None, max_length=50)
    browser_family: str | None = Field(default=None, max_length=50)
    browser_version: str | None = Field(default=None, max_length=50)
    platform: str | None = Field(default=None, max_length=50)
    screen_res: str | None = Field(default=None, max_length=100)
    capabilities: dict | None = None
    permission_status: Literal["granted", "prompt", "denied"] = "prompt"
    client_device_token: str | None = Field(default=None, max_length=100)
    identity_confidence: str | None = Field(default="client_storage_token", max_length=50)
    detection_limitations: str | None = Field(default=None, max_length=200)

    @field_validator("nickname")
    @classmethod
    def strip_nickname(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("nickname cannot be empty")
        return s


class DeviceRenameRequest(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=80)

    @field_validator("nickname")
    @classmethod
    def strip_nickname(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("nickname cannot be empty")
        return s



class DeviceRevokeRequest(BaseModel):
    reason: str | None = Field(default="Revoked by operator", max_length=200)


class PhoneVerificationRequest(BaseModel):
    driver_id: str = Field(..., min_length=1, max_length=50)


class PhoneVerifyCodeRequest(BaseModel):
    verification_id: str = Field(..., min_length=1, max_length=50)
    code: str = Field(..., min_length=4, max_length=10)
