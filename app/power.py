import sys
from datetime import datetime
from typing import Any


def get_server_host_power_status() -> dict[str, Any]:
    """
    Queries real physical hardware battery and power supply directly from
    the SERVER machine operating system kernel.
    NOTE: This strictly represents the server host, NOT client/driver mobile devices.
    """
    now_str = datetime.now().strftime("%H:%M:%S")

    # 1. Windows Implementation via Win32 GetSystemPowerStatus
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", wintypes.BYTE),
                    ("BatteryFlag", wintypes.BYTE),
                    ("BatteryLifePercent", wintypes.BYTE),
                    ("SystemStatusFlag", wintypes.BYTE),
                    ("BatteryLifeTime", wintypes.DWORD),
                    ("BatteryFullLifeTime", wintypes.DWORD),
                ]

            sps = SYSTEM_POWER_STATUS()
            success = ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps))
            if success:
                ac = sps.ACLineStatus
                pct = sps.BatteryLifePercent
                rem_sec = sps.BatteryLifeTime

                if pct != 255 and pct <= 100:
                    is_charging = (ac == 1)
                    charging_text = "⚡ Charging (AC/USB)" if is_charging else "🔋 Discharging (Battery)"
                    
                    if not is_charging:
                        if rem_sec != 4294967295 and rem_sec > 0:
                            mins = round(rem_sec / 60)
                            discharging_time = f"{mins} min ({round(mins / 60, 1)} hrs)"
                        else:
                            discharging_time = "Estimating discharge rate..."
                        charging_time = "0 min (Unplugged)"
                    else:
                        discharging_time = "Operating on AC Power"
                        charging_time = "Charging to 100%" if pct < 100 else "Fully Charged (AC Connected)"

                    return {
                        "supported": True,
                        "pct": f"{pct}%",
                        "percentage_num": pct,
                        "charging": charging_text,
                        "is_charging": is_charging,
                        "chargingTime": charging_time,
                        "dischargingTime": discharging_time,
                        "battery_flag": sps.BatteryFlag,
                        "source": "Windows OS Kernel (GetSystemPowerStatus)",
                        "role": "server_host_power",
                        "label": "Server host power (Physical machine running backend)",
                        "reading_timestamp": now_str,
                    }
        except Exception:
            pass

    # 2. Cross-platform fallback via psutil if available
    try:
        import importlib
        psutil = importlib.import_module("psutil")
        if hasattr(psutil, "sensors_battery"):
            bat = psutil.sensors_battery()
            if bat is not None:
                is_charging = bool(bat.power_plugged)
                pct = round(bat.percent)
                charging_text = "⚡ Charging (AC/USB)" if is_charging else "🔋 Discharging (Battery)"
                if not is_charging and bat.secsleft > 0 and bat.secsleft != psutil.POWER_TIME_UNLIMITED:
                    discharging_time = f"{round(bat.secsleft / 60)} min"
                else:
                    discharging_time = "Operating on AC Power" if is_charging else "Unknown"

                return {
                    "supported": True,
                    "pct": f"{pct}%",
                    "percentage_num": pct,
                    "charging": charging_text,
                    "is_charging": is_charging,
                    "chargingTime": "Fully Charged" if pct == 100 else ("Charging" if is_charging else "0 min"),
                    "dischargingTime": discharging_time,
                    "source": "OS Hardware Sensors (psutil)",
                    "role": "server_host_power",
                    "label": "Server host power (Physical machine running backend)",
                    "reading_timestamp": now_str,
                }
    except Exception:
        pass

    return {
        "supported": False,
        "pct": "Unavailable",
        "percentage_num": None,
        "charging": "Unknown",
        "is_charging": False,
        "chargingTime": "Unavailable",
        "dischargingTime": "Unavailable",
        "source": "No battery sensor detected on server (Desktop / VM)",
        "role": "server_host_power",
        "label": "Server host power (Physical machine running backend)",
        "reading_timestamp": now_str,
    }

