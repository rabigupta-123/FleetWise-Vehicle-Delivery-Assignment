import re
from datetime import datetime
from typing import Literal, Optional
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
    vehicle_id: Optional[str] = Field(default=None, max_length=50)
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
    def strip_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class VehicleStatusPatch(BaseModel):
    status: Literal["available", "maintenance", "inactive"]


class DriverCreate(BaseModel):
    driver_id: Optional[str] = Field(default=None, max_length=50)
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
    def strip_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class DriverStatusPatch(BaseModel):
    availability_status: Literal["available", "unavailable"]


class DeliveryCreate(BaseModel):
    delivery_id: Optional[str] = Field(default=None, max_length=50)
    pickup: str = Field(..., min_length=1, max_length=255)
    dropoff: str = Field(..., min_length=1, max_length=255)
    scheduled_time: str = Field(..., min_length=1)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    required_capacity: Optional[int] = Field(default=None, gt=0)
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    drop_lat: Optional[float] = None
    drop_lng: Optional[float] = None

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
    def strip_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s if s else None


class AssignRequest(BaseModel):
    vehicle_id: str = Field(..., min_length=1, max_length=50)
    driver_id: str = Field(..., min_length=1, max_length=50)
    version: Optional[int] = None

    @field_validator("vehicle_id", "driver_id")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("ID cannot be empty")
        return s


class DeliveryStatusPatch(BaseModel):
    status: str = Field(..., min_length=1)
    reason: Optional[str] = None
    version: Optional[int] = None


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
    device_id: Optional[str] = Field(default=None, max_length=50)
    device_info: Optional[str] = Field(default=None, max_length=255)


class TrackingSessionStop(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=50)


class GPSLocationCreate(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=50)
    device_id: Optional[str] = Field(default=None, max_length=50)
    driver_id: Optional[str] = Field(default=None, max_length=50)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy: float = Field(..., ge=0.0)
    altitude: Optional[float] = None
    altitude_accuracy: Optional[float] = Field(default=None, ge=0.0)
    speed: Optional[float] = Field(default=None, ge=0.0)
    heading: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    device_timestamp: str = Field(..., min_length=1)

    @field_validator("device_timestamp")
    @classmethod
    def check_ts(cls, v: str) -> str:
        return validate_iso8601(v)


class DeviceRegisterRequest(BaseModel):
    driver_id: str = Field(..., min_length=1, max_length=50)
    nickname: str = Field(..., min_length=1, max_length=80)
    device_category: Optional[str] = Field(default=None, max_length=50)
    model: Optional[str] = Field(default=None, max_length=100)
    os_family: Optional[str] = Field(default=None, max_length=50)
    os_version: Optional[str] = Field(default=None, max_length=50)
    browser_family: Optional[str] = Field(default=None, max_length=50)
    browser_version: Optional[str] = Field(default=None, max_length=50)
    platform: Optional[str] = Field(default=None, max_length=50)
    screen_res: Optional[str] = Field(default=None, max_length=100)
    capabilities: Optional[dict] = None
    permission_status: Literal["granted", "prompt", "denied"] = "prompt"
    client_device_token: Optional[str] = Field(default=None, max_length=100)
    identity_confidence: Optional[str] = Field(default="client_storage_token", max_length=50)
    detection_limitations: Optional[str] = Field(default=None, max_length=200)

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
    reason: Optional[str] = Field(default="Revoked by operator", max_length=200)


class PhoneVerificationRequest(BaseModel):
    driver_id: str = Field(..., min_length=1, max_length=50)


class PhoneVerifyCodeRequest(BaseModel):
    verification_id: str = Field(..., min_length=1, max_length=50)
    code: str = Field(..., min_length=4, max_length=10)
