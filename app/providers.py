"""
FleetWise External Provider Abstractions & Interfaces (Phase 8 & 9)

Defines clean extensible provider interfaces for:
1. IP Geolocation (approximate city-level geography, never presented as GPS sensor)
2. Telematics Hardware (CAN-bus / OBD-II / Dedicated GPS tracker ingestion)
3. SMS Gateway (Phone OTP delivery)

Privacy & Integrity Principles:
- A public IP address is NOT a GPS coordinate; precision is labeled approximate.
- No third-party provider is claimed as connected unless valid credentials exist.
- Phone number metadata is distinct from verified handset possession.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseTelematicsProvider(ABC):
    """Abstract interface for hardware telematics or fleet tracker integrations."""

    @abstractmethod
    def get_provider_name(self) -> str:
        pass

    @abstractmethod
    async def fetch_telemetry_feed(self, device_id: str) -> Optional[Dict[str, Any]]:
        pass


class BaseIPGeolocationProvider(ABC):
    """Abstract interface for IP-based approximate location lookup."""

    @abstractmethod
    def get_provider_name(self) -> str:
        pass

    @abstractmethod
    async def lookup_ip_approximate(self, ip_address: str) -> Dict[str, Any]:
        """
        Returns approximate city/region geography for an IP.
        Must explicitly label precision as 'city_approximate' and NOT 'gps'.
        """
        pass


class BaseSMSGatewayProvider(ABC):
    """Abstract interface for SMS OTP delivery."""

    @abstractmethod
    def get_provider_name(self) -> str:
        pass

    @abstractmethod
    async def send_verification_otp(self, phone_e164: str, otp_code: str) -> Dict[str, Any]:
        pass


class DevelopmentSimulationSMSGateway(BaseSMSGatewayProvider):
    """
    Default offline development gateway.
    Permits local testing and automated verification without requiring paid Twilio/AWS accounts.
    """

    def get_provider_name(self) -> str:
        return "development_simulation"

    async def send_verification_otp(self, phone_e164: str, otp_code: str) -> Dict[str, Any]:
        return {
            "success": True,
            "provider": self.get_provider_name(),
            "phone_e164": phone_e164,
            "status": "delivered_to_test_sandbox",
            "message": "Challenge active. Use test challenge code provided in verification response.",
        }


class UnconfiguredIPGeolocationProvider(BaseIPGeolocationProvider):
    """
    Default IP provider when no external MaxMind / IPInfo token is supplied.
    Truthfully reports approximate nature and avoids fabricated coordinates.
    """

    def get_provider_name(self) -> str:
        return "unconfigured_default"

    async def lookup_ip_approximate(self, ip_address: str) -> Dict[str, Any]:
        is_loopback = ip_address in ("127.0.0.1", "::1", "localhost")
        return {
            "ip": ip_address,
            "provider": self.get_provider_name(),
            "precision": "loopback_local" if is_loopback else "approximate_unconfigured",
            "country": "Local Dev" if is_loopback else "Unknown",
            "region": "Local Machine" if is_loopback else "Unknown",
            "city": "Localhost" if is_loopback else "Unknown",
            "is_gps_sensor": False,
            "note": "IP geolocation indicates network routing geography only, never physical device GPS coordinates.",
        }

