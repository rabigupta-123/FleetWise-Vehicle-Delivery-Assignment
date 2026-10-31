import math
from decimal import ROUND_HALF_UP, Decimal


def round_half_up(val: float | None, decimals: int = 1) -> float | None:
    """
    Rounds a floating point number using explicit ROUND_HALF_UP (arithmetic rounding),
    eliminating Python 3's IEEE-754 round-half-to-even bias.
    Example: 60.65 with decimals=1 rounds up to 60.7.
    """
    if val is None or not math.isfinite(val):
        return None
    d = Decimal(str(val))
    target = Decimal("10") ** -decimals if decimals > 0 else Decimal("1")
    return float(d.quantize(target, rounding=ROUND_HALF_UP))


def calculate_capacity_suitability(package_weight: float, vehicle_capacity: float) -> float:
    """
    Calculates capacity suitability score in range [0.0, 100.0].

    Formula:
    - If vehicle_capacity <= 0 or package_weight <= 0: return 0.0
    - If package_weight > vehicle_capacity (overloaded): return 0.0 (rejected)
    - If package_weight <= vehicle_capacity:
        overcapacity_ratio = (vehicle_capacity - package_weight) / vehicle_capacity
        raw_score = 100.0 - (overcapacity_ratio * 20.0)
        clamped to [0.0, 100.0]

    Mathematical Properties:
    1. Bounded: Output is strictly in [0.0, 100.0]
    2. Non-negative: Never returns negative numbers
    3. Monotonic: For a fixed package_weight, as vehicle_capacity increases beyond weight,
       the suitability score decreases monotonically from 100.0 (exact fit) down towards 80.0.
       If vehicle_capacity is less than package_weight, score drops immediately to 0.0.
    """
    if vehicle_capacity <= 0 or package_weight <= 0:
        return 0.0
    if package_weight > vehicle_capacity:
        return 0.0

    overcapacity_ratio = (vehicle_capacity - package_weight) / vehicle_capacity
    raw_score = 100.0 - (overcapacity_ratio * 20.0)
    clamped = max(0.0, min(100.0, raw_score))
    val = round_half_up(clamped, 2)
    return float(val) if val is not None else 0.0

