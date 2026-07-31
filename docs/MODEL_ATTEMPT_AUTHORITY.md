# Model-attempt authority contract

`ModelAttemptAuthority` is the supported host hook for authorizing, recording,
and durably replaying each physical model-provider attempt made by a Tactus
Agent. It is optional and policy-neutral: Tactus defines the attempt boundary
and immutable envelopes, while the host owns persistence and authorization
policy.

The public types live in `tactus.protocols.model_attempt` and are re-exported
from `tactus.protocols`.

## Required agent bounds

When a runtime has a `model_attempt_authority`, every participating Agent must
have all of the following:

- an exact `provider/model` identifier;
- a positive `max_input_tokens`;
- a positive `max_tokens` output bound; and
- a positive `model_attempt_max_attempts` (the legacy `max_attempts` spelling is
  also accepted by runtime configuration).

The host passes the authority to `TactusRuntime`:

```python
from tactus.core.runtime import TactusRuntime

runtime = TactusRuntime(
    procedure_id="durable-procedure",
    storage_backend=storage,
    model_attempt_authority=authority,
)
```

The corresponding Agent configuration remains host/application configuration:

```lua
worker = Agent {
  model = "openai/gpt-4o-mini",
  max_input_tokens = 12000,
  max_tokens = 800,
  model_attempt_max_attempts = 3,
}
```

Tactus fails closed before provider contact if an exact model, bound, durable
execution identity, or measurable physical request is unavailable.

## Lifecycle

For each physical attempt, Tactus performs this sequence:

1. Build the exact Raw provider request once.
2. Canonicalize and hash that request.
3. Count its physical input tokens and reject an overflow.
4. Construct an immutable `ModelAttemptPlan`.
5. Call `authority.reserve(plan)` before provider contact.
6. Reject, replay, or make exactly the approved contact.
7. Call `authority.settle(outcome)` with the terminal evidence.

The built request used for hashing and token measurement is also the request
used for contact. Its canonical payload includes the complete messages (and
therefore the rendered system prompt and conversation), tools, `tool_choice`,
and relevant serialized provider request options. A change to any of these
changes `request_hash`.

Input enforcement uses LiteLLM's model-aware token counter over that physical
payload, including tools and tool choice. An overflow is rejected before
`reserve()`, and an unsupported/unmeasurable module is rejected before both
reservation and contact. The authority path does not estimate from an earlier
prompt-context object.

## Plans and replay-stable identity

`ModelAttemptPlan` contains:

- `call_id`: opaque identity for one logical model call;
- `attempt_id`: `call_id` plus the one-based physical attempt number;
- `attempt_number` and `max_attempts`;
- exact `provider` and resolved `model`;
- `max_input_tokens` and `max_output_tokens`; and
- `request_hash` for this attempt's exact provider request.

The `call_id` is derived from replay-stable procedure ID, run ID, checkpoint
position, stable Agent name, the first exact request hash, and the optional
configured `model_attempt_call_id` namespace. It does not use an in-memory turn
counter or process-local ordinal. A configured ID is a namespace, not the full
identity, so reusing a static value across checkpoint positions does not create
a collision.

The first request establishes the logical call. Later repair/tool-follow-up
attempts retain its `call_id`, while every attempt carries its own
`request_hash`. Re-executing the same logical call produces the same
`call_id`/`attempt_id` and reaches the authority again; Tactus does not suppress
it with process-local "seen" state. The host is therefore the authority for
deciding whether the attempt is new or replayable.

## Reservation decisions

`reserve(plan)` returns one `ModelAttemptReservation`:

- `approved(reservation_id)`: the host durably reserved this exact attempt and
  Tactus may contact the provider;
- `rejected(reason)`: Tactus records a `rejected` outcome and makes no contact;
  or
- `replay(reservation_id, replay_payload=...)`: Tactus validates and restores a
  previously settled result and makes no contact.

Invalid, missing, corrupt, or type-mismatched replay payloads fail closed before
provider contact. A replay decision is terminal; it is not an instruction to
fall through to a new request if restoration fails.

## Outcomes

`settle(outcome)` receives the original plan, reservation ID, and one status:

- `succeeded`: provider completion is known. The outcome includes provider
  usage when available, provider request ID when available, and a versioned
  JSON replay payload.
- `replayed`: a valid persisted payload was restored without provider contact.
- `rejected`: the authority declined the attempt before contact.
- `outcome_unknown`: contact began but a safe terminal success could not be
  established or durably represented.

Examples of `outcome_unknown` include ambiguous provider/stream failures,
empty streams, post-contact observer failures, a provider result that cannot be
encoded as a supported replay payload, and failure while settling success.
Once contact begins, these failures are non-retryable inside Tactus because a
second automatic contact could duplicate a billable request. Tactus makes a
best-effort conservative `outcome_unknown` settlement even if the first
settlement attempt failed.

## Versioned replay payload

`ModelAttemptReplayPayload` version 1 is a plain JSON-compatible mapping:

```json
{
  "version": 1,
  "kind": "prediction",
  "fields": {
    "response": "completed"
  },
  "typed_fields": {}
}
```

It is safe to pass directly to `json.dumps(..., allow_nan=False)`. Tactus builds
it from the actual DSPy `Prediction`, not from a text-only projection. Version
1 preserves JSON fields and explicitly marks supported typed fields such as
DSPy `ToolCalls`, allowing a fresh Agent to restore the internal result shape
required by streaming, non-streaming, and downstream tool processing.

Hosts must store the envelope unchanged and return it through
`ModelAttemptReservation.replay`. Hosts must not synthesize private DSPy
objects or downgrade the envelope to response text.

## Retry boundaries

Authority mode disables lower-level LiteLLM/broker retries by forwarding
`num_retries=0`. `ModelAttemptRejected` and `ModelAttemptOutcomeUnknown` are
terminal to the Agent retry loop. Streaming fallback cannot turn an unknown
attempt into a non-streaming second contact.

This does not hide legitimate multiple physical attempts: each follow-up or
repair attempt receives its own plan and reservation, remains within
`model_attempt_max_attempts`, and is visible to the host before contact.

## Host responsibilities

The host must:

- implement durable, idempotent lookup by `attempt_id`;
- atomically persist an approval/reservation before returning `approved`;
- associate persisted outcomes with the exact plan and `request_hash`;
- persist succeeded usage, provider request ID, and replay payload unchanged;
- return `replay` only for the matching settled attempt;
- treat `outcome_unknown` as spent/ambiguous until externally reconciled;
- make authorization, quota, pricing, and reconciliation decisions outside
  Tactus; and
- keep `reserve()` and `settle()` behavior safe when the same envelope is
  delivered more than once.

Tactus does not provide host pricing policy, a persistence backend for this
contract, provider-side reconciliation, or permission to retry an ambiguous
attempt.

## Release and deployment order

Release Tactus with this supported contract first. Host applications must then
pin that released Tactus version before enabling their authority integration.
Production hosts must not monkeypatch Tactus, depend on an unreleased local
path, or copy private Agent methods to obtain this behavior.
