"""Host authority contract for individual physical model-provider attempts.

The contract deliberately owns identity and observability, not commercial
policy.  A host can reject, reserve, or replay a previously settled attempt
before Tactus touches a provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Protocol, TypeAlias, TypedDict, Union

JSONScalar: TypeAlias = Union[None, bool, int, float, str]
JSONValue: TypeAlias = Union[JSONScalar, List["JSONValue"], Dict[str, "JSONValue"]]


class ModelAttemptReplayPayload(TypedDict):
    """Versioned, persistence-safe result returned for host-managed replay."""

    version: Literal[1]
    kind: Literal["prediction"]
    fields: Dict[str, JSONValue]
    typed_fields: Dict[str, Literal["tool_calls"]]


@dataclass(frozen=True)
class ModelAttemptPlan:
    """The complete, immutable plan presented before a provider attempt."""

    call_id: str
    attempt_id: str
    attempt_number: int
    max_attempts: int
    provider: str
    model: str
    max_input_tokens: int
    max_output_tokens: int
    request_hash: str


@dataclass(frozen=True)
class ModelAttemptReservation:
    """The host's decision for an attempt.

    ``replay_payload`` is the JSON-compatible envelope previously supplied on
    the succeeded outcome. Tactus validates and restores it without contact.
    """

    status: Literal["approved", "rejected", "replay"]
    reservation_id: Optional[str] = None
    reason: Optional[str] = None
    replay_payload: Optional[ModelAttemptReplayPayload] = None

    @classmethod
    def approved(cls, reservation_id: str) -> "ModelAttemptReservation":
        return cls(status="approved", reservation_id=reservation_id)

    @classmethod
    def rejected(cls, reason: str) -> "ModelAttemptReservation":
        return cls(status="rejected", reason=reason)

    @classmethod
    def replay(
        cls, reservation_id: str, *, replay_payload: ModelAttemptReplayPayload
    ) -> "ModelAttemptReservation":
        return cls(status="replay", reservation_id=reservation_id, replay_payload=replay_payload)


@dataclass(frozen=True)
class ModelAttemptUsage:
    """Provider-reported usage when it is available."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None


@dataclass(frozen=True)
class ModelAttemptOutcome:
    """The immutable settlement envelope supplied after an authority decision."""

    plan: ModelAttemptPlan
    reservation_id: Optional[str]
    status: Literal["succeeded", "rejected", "replayed", "outcome_unknown"]
    usage: Optional[ModelAttemptUsage] = None
    provider_request_id: Optional[str] = None
    replay_payload: Optional[ModelAttemptReplayPayload] = None
    error: Optional[str] = None


class ModelAttemptAuthority(Protocol):
    """Optional host-side authority for model attempts."""

    def reserve(self, plan: ModelAttemptPlan) -> ModelAttemptReservation:
        """Approve, reject, or replay an attempt before provider contact."""

    def settle(self, outcome: ModelAttemptOutcome) -> None:
        """Record the terminal authority outcome for an attempt."""


class ModelAttemptRejected(RuntimeError):
    """The authority declined an attempt before any provider contact."""


class ModelAttemptOutcomeUnknown(RuntimeError):
    """Provider contact may have occurred, so automatic retry is unsafe."""
