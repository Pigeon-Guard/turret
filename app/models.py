"""Data models for the turret application."""
from dataclasses import dataclass, asdict


@dataclass
class SharedState:
    """Shared state for turret control."""
    mode: str = "manual"
    owner: str = "none"
    owner_since: float = 0.0
    owner_last_seen: float = 0.0
    pan_target: float = 0.0
    tilt_target: float = 0.0
    pan_angle: float = 0.0
    tilt_angle: float = 0.0
    trigger_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
