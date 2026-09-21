"""
Enumerations shared across the domain. These match the ENUM columns
defined in the database schema doc (Schema v0.1) exactly, so a value
here should never drift from what's allowed in the DB.
"""

from enum import Enum


class VesselClass(str, Enum):
    """The four bulk carrier classes this project covers (Schema §3.2)."""

    HANDYSIZE = "Handysize"
    SUPRAMAX = "Supramax"
    PANAMAX = "Panamax"
    CAPESIZE = "Capesize"


class PortRole(str, Enum):
    ORIGIN = "origin"
    DESTINATION = "destination"
    BOTH = "both"


class DurationType(str, Enum):
    SPOT = "spot"
    SHORT_TERM = "short_term"
    MID_TERM = "mid_term"


class AlertType(str, Enum):
    VOLATILITY = "volatility"
    CONGESTION = "congestion"
    DATA_UNAVAILABLE = "data_unavailable"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
