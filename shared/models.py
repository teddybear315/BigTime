"""
Shared data models for the BigTime application.
Used by both server and client components.
"""

import uuid
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from typing import Any, Dict, Optional


class SyncState(Enum):
    """Sync states for offline-first operation"""
    SYNCED = "synced"
    PENDING = "pending"
    FAILED = "failed"

    @classmethod
    def is_valid_transition(cls, from_state: str, to_state: str) -> bool:
        """Check if state transition is valid"""
        if from_state == to_state:
            return True

        # Valid transitions:
        # PENDING -> SYNCED (successful sync)
        # PENDING -> FAILED (sync failed)
        # FAILED -> PENDING (retry)
        # SYNCED -> PENDING (data changed, needs re-sync)
        # Any state -> FAILED (can fail from any state)

        valid_transitions = {
            cls.PENDING.value: [cls.SYNCED.value, cls.FAILED.value],
            cls.FAILED.value: [cls.PENDING.value],
            cls.SYNCED.value: [cls.PENDING.value, cls.FAILED.value]
        }

        return to_state in valid_transitions.get(from_state, [])


class PayPeriod(Enum):
    """Employee pay periods"""
    HOURLY = "hourly"
    MONTHLY = "monthly"


@dataclass
class Employee:
    """Employee model with all fields needed for time tracking operations"""
    id: Optional[int] = None
    name: str = ""
    badge: str = ""
    phone_number: Optional[int] = None
    pin: str = ""
    department: str = ""
    date_of_birth: Optional[date] = None
    hire_date: Optional[date] = None
    deactivated: bool = False
    ssn: Optional[int] = None
    period: str = PayPeriod.HOURLY.value
    rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization"""
        data = asdict(self)
        # Convert date objects to strings (handle both date objects and strings)
        if self.date_of_birth:
            if isinstance(self.date_of_birth, date):
                data['date_of_birth'] = self.date_of_birth.isoformat()
            else:
                data['date_of_birth'] = self.date_of_birth  # Already a string
        if self.hire_date:
            if isinstance(self.hire_date, date):
                data['hire_date'] = self.hire_date.isoformat()
            else:
                data['hire_date'] = self.hire_date  # Already a string
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Employee':
        """Create Employee from dictionary (API response)"""
        # Convert string dates back to date objects
        if 'date_of_birth' in data and data['date_of_birth']:
            data['date_of_birth'] = date.fromisoformat(data['date_of_birth'])
        if 'hire_date' in data and data['hire_date']:
            data['hire_date'] = date.fromisoformat(data['hire_date'])
        return cls(**data)


@dataclass
class TimeLog:
    """Time log entry with sync metadata"""
    id: Optional[int] = None
    client_id: Optional[str] = None  # Client-generated UUID for idempotency
    remote_id: Optional[int] = None  # Server-assigned ID
    badge: str = ""
    clock_in: Optional[str] = None  # ISO format timestamp
    clock_out: Optional[str] = None  # ISO format timestamp
    device_id: Optional[str] = None
    device_ts: Optional[str] = None  # Device timestamp for debugging
    sync_state: str = SyncState.PENDING.value
    sync_error: Optional[str] = None  # Error message for failed sync operations
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        """Generate client_id if not provided"""
        if not self.client_id:
            self.client_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TimeLog':
        """Create TimeLog from dictionary (API response)"""
        return cls(**data)


@dataclass
class SyncStatus:
    """Status information for sync operations"""
    is_online: bool = False
    is_syncing: bool = False
    last_sync: Optional[str] = None  # ISO timestamp
    pending_count: int = 0  # Total pending items (logs + other)
    pending_logs: int = 0
    failed_logs: int = 0
    server_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# API Request/Response Models
@dataclass
class CreateLogRequest:
    """API request to create a new time log"""
    client_id: str
    badge: str
    clock_in: str  # ISO timestamp
    device_id: Optional[str] = None
    device_ts: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UpdateLogRequest:
    """API request to update an existing time log"""
    client_id: str
    clock_out: Optional[str] = None  # ISO timestamp
    device_id: Optional[str] = None
    device_ts: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ApiResponse:
    """Standard API response wrapper"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Configuration models
@dataclass
class ServerConfig:
    """Server configuration with validation"""
    server_url: str = ""
    device_id: str = ""
    api_key: str = ""
    sync_interval: int = 30  # seconds
    timeout: int = 10  # seconds

    def __post_init__(self) -> None:
        """Validate configuration after initialization"""
        # Validate server URL format if provided
        if self.server_url:
            if not self.server_url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid server URL: must start with http:// or https://")

        # Validate sync interval range
        if not (5 <= self.sync_interval <= 3600):
            raise ValueError(f"Sync interval must be between 5 and 3600 seconds, got {self.sync_interval}")

        # Validate timeout range
        if not (1 <= self.timeout <= 120):
            raise ValueError(f"Timeout must be between 1 and 120 seconds, got {self.timeout}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServerConfig':
        """Create from dictionary"""
        return cls(**data)
