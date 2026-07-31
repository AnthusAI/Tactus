from __future__ import annotations

import json
from types import SimpleNamespace

import dspy
import pytest
from dspy.adapters.types.tool import ToolCalls

from tactus.dspy.agent import DSPyAgentHandle
from tactus.core import runtime as runtime_module
from tactus.protocols.model_attempt import (
    ModelAttemptOutcomeUnknown,
    ModelAttemptRejected,
    ModelAttemptReservation,
)


class _LogHandler:
    supports_streaming = False

    def log(self, _event):
        return None


class _StreamingLogHandler(_LogHandler):
    supports_streaming = True


class _Authority:
    def __init__(self, reservation: ModelAttemptReservation):
        self.reservation = reservation
        self.plans = []
        self.outcomes = []

    def reserve(self, plan):
        self.plans.append(plan)
        return self.reservation

    def settle(self, outcome):
        self.outcomes.append(outcome)


class _FailingSettlementAuthority(_Authority):
    def settle(self, outcome):
        super().settle(outcome)
        raise RuntimeError("durable settlement unavailable")


def _prediction_payload(**fields):
    return {
        "version": 1,
        "kind": "prediction",
        "fields": fields,
        "typed_fields": {},
    }


class _ReplayOnSecondReservationAuthority(_Authority):
    def __init__(self):
        super().__init__(ModelAttemptReservation.approved("reservation-1"))

    def reserve(self, plan):
        self.plans.append(plan)
        if len(self.plans) == 1:
            return ModelAttemptReservation.approved("reservation-1")
        return ModelAttemptReservation.replay(
            "reservation-1", replay_payload=_prediction_payload(response="settled replay")
        )


class _FailOnFirstChunkLog(_StreamingLogHandler):
    def log(self, event):
        if type(event).__name__ == "AgentStreamChunkEvent":
            raise RuntimeError("first chunk observer failed")


class _RecordingLM:
    kwargs = {}

    def __init__(self):
        self.calls = []
        self.history = []

    def __call__(self, *, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        return ["ok"]


class _PersistingAuthority(_Authority):
    def __init__(self):
        super().__init__(ModelAttemptReservation.approved("reservation-1"))
        self.serialized_replay_payload = None

    def settle(self, outcome):
        super().settle(outcome)
        if outcome.status == "succeeded":
            self.serialized_replay_payload = json.dumps(
                outcome.replay_payload, sort_keys=True, allow_nan=False
            )


class _StableExecutionContext:
    def __init__(self, *, procedure_id="procedure-1", run_id="run-1", position=7):
        self.procedure_id = procedure_id
        self.current_run_id = run_id
        self._position = position

    def next_position(self):
        return self._position


def _bounded_provider(callback):
    def provider(**kwargs):
        return callback(**kwargs)

    provider.build_provider_request = lambda **kwargs: {
        "messages": [
            {"role": "system", "content": kwargs.get("system_prompt", "")},
            {"role": "user", "content": kwargs.get("user_message", "")},
        ],
        "kwargs": {},
    }
    return provider


class _LuaGlobals:
    def __init__(self):
        self.values = {}

    def __call__(self):
        return self.values


class _LuaSandbox:
    def __init__(self):
        self.lua = SimpleNamespace(globals=_LuaGlobals())


def _agent(authority, *, attempts=1, execution_context=None, call_id=None, name="gate"):
    if execution_context is None:
        execution_context = _StableExecutionContext()
    agent = DSPyAgentHandle(
        name=name,
        system_prompt="Use the supplied evidence.",
        model="openai/gpt-4o-mini-2024-07-18",
        max_tokens=32,
        max_input_tokens=128,
        model_attempt_max_attempts=attempts,
        model_attempt_authority=authority,
        execution_context=execution_context,
        model_attempt_call_id=call_id,
        log_handler=_LogHandler(),
        module="Raw",
    )
    return agent


def test_authority_receives_exact_plan_and_real_usage_before_provider_call():
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority)
    calls = []

    def provider(**_kwargs):
        calls.append("provider")
        return dspy.Prediction(response="approved")

    agent._module = SimpleNamespace(module=_bounded_provider(provider))
    lm = SimpleNamespace(
        history=[
            {
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "total_tokens": 18,
                    "prompt_tokens_details": {"cached_tokens": 3},
                },
                "response": SimpleNamespace(id="provider-response-1"),
            }
        ]
    )
    with dspy.context(lm=lm):
        result = agent._turn_without_streaming(
            {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
        )

    assert result.output == "approved"
    assert calls == ["provider"]
    assert len(authority.plans) == 1
    plan = authority.plans[0]
    assert plan.provider == "openai"
    assert plan.model == "gpt-4o-mini-2024-07-18"
    assert plan.max_input_tokens == 128
    assert plan.max_output_tokens == 32
    assert plan.max_attempts == 1
    assert plan.request_hash
    assert plan.attempt_id == f"{plan.call_id}:1"
    assert authority.outcomes[0].status == "succeeded"
    assert authority.outcomes[0].provider_request_id == "provider-response-1"
    assert authority.outcomes[0].usage.input_tokens == 11
    assert authority.outcomes[0].usage.output_tokens == 7
    assert authority.outcomes[0].usage.cached_tokens == 3


def test_authority_rejection_makes_zero_provider_calls():
    authority = _Authority(ModelAttemptReservation.rejected("budget exhausted"))
    agent = _agent(authority)
    calls = []
    agent._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: calls.append("provider") or dspy.Prediction(response="never")
        )
    )

    with pytest.raises(ModelAttemptRejected, match="budget exhausted"):
        agent._turn_without_streaming(
            {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
        )

    assert calls == []
    assert authority.outcomes[0].status == "rejected"


def test_authority_replay_returns_settled_result_without_provider_contact():
    authority = _Authority(
        ModelAttemptReservation.replay(
            "reservation-1", replay_payload=_prediction_payload(response="settled")
        )
    )
    agent = _agent(authority)
    calls = []
    agent._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: calls.append("provider") or dspy.Prediction(response="never")
        )
    )

    result = agent._turn_without_streaming(
        {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
    )

    assert result.output == "settled"
    assert calls == []
    assert authority.outcomes[0].status == "replayed"


def test_post_contact_failure_is_unknown_and_not_retried():
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority, attempts=3)
    calls = []

    def provider(**_kwargs):
        calls.append("provider")
        raise RuntimeError("connection reset after send")

    agent._module = SimpleNamespace(module=_bounded_provider(provider))

    with pytest.raises(ModelAttemptOutcomeUnknown, match="connection reset after send"):
        agent._turn_with_retries(
            {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
        )

    assert calls == ["provider"]
    assert authority.outcomes[0].status == "outcome_unknown"


def test_empty_stream_outcome_unknown_does_not_fall_back_to_a_second_provider_call(monkeypatch):
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority, attempts=3, execution_context=_StableExecutionContext())
    agent.log_handler = _StreamingLogHandler()
    contacts = []

    def provider(**_kwargs):
        contacts.append("provider")
        return dspy.Prediction(response="fallback must not run")

    def empty_streamify(_module):
        def stream(**_kwargs):
            async def values():
                if False:  # pragma: no cover - marks this as an async iterator
                    yield None

            return values()

        return stream

    agent._module = SimpleNamespace(module=_bounded_provider(provider))
    monkeypatch.setattr(dspy, "streamify", empty_streamify)

    with pytest.raises(ModelAttemptOutcomeUnknown, match="Streaming produced no result"):
        agent._turn_with_retries(
            {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
        )

    assert contacts == []
    assert [outcome.status for outcome in authority.outcomes] == ["outcome_unknown"]


def test_settlement_failure_after_provider_success_is_unknown_and_not_retried():
    authority = _FailingSettlementAuthority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority, attempts=3, execution_context=_StableExecutionContext())
    contacts = []

    def provider(**_kwargs):
        contacts.append("provider")
        return dspy.Prediction(response="provider completed")

    agent._module = SimpleNamespace(module=_bounded_provider(provider))

    with pytest.raises(ModelAttemptOutcomeUnknown, match="durable settlement unavailable"):
        agent._turn_with_retries(
            {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
        )

    assert contacts == ["provider"]
    assert [outcome.status for outcome in authority.outcomes] == ["succeeded", "outcome_unknown"]


def test_authority_call_identity_uses_replay_stable_scope_not_turn_count():
    first_authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    replayed_authority = _Authority(ModelAttemptReservation.approved("reservation-2"))
    scope = _StableExecutionContext()
    first = _agent(first_authority, execution_context=scope)
    replayed = _agent(replayed_authority, execution_context=scope)
    first._module = SimpleNamespace(module=_bounded_provider(lambda **_kwargs: None))
    replayed._module = SimpleNamespace(module=_bounded_provider(lambda **_kwargs: None))
    first._turn_count = 1
    replayed._turn_count = 99

    first._reserve_model_attempt(
        {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
    )
    replayed._reserve_model_attempt(
        {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
    )

    assert first_authority.plans[0].call_id == replayed_authority.plans[0].call_id


def test_configured_call_id_is_scoped_to_replay_stable_position_to_avoid_turn_collisions():
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    first = _agent(
        authority,
        execution_context=_StableExecutionContext(position=7),
        call_id="configured-call",
    )
    second = _agent(
        authority,
        execution_context=_StableExecutionContext(position=8),
        call_id="configured-call",
    )
    first._module = SimpleNamespace(module=_bounded_provider(lambda **_kwargs: None))
    second._module = SimpleNamespace(module=_bounded_provider(lambda **_kwargs: None))

    first._reserve_model_attempt(
        {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
    )
    second._reserve_model_attempt(
        {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
    )

    assert authority.plans[0].call_id != authority.plans[1].call_id


def test_reusable_handle_same_logical_call_reaches_authority_for_host_replay():
    authority = _ReplayOnSecondReservationAuthority()
    agent = _agent(authority)
    contacts = []
    agent._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: contacts.append("provider")
            or dspy.Prediction(response="provider result")
        )
    )
    prompt = {"system_prompt": "system", "history": [], "user_message": "hi"}

    first = agent._run_provider_attempt({}, prompt, lambda: agent._module.module(**prompt))
    replayed = agent._run_provider_attempt({}, prompt, lambda: agent._module.module(**prompt))

    assert first.response == "provider result"
    assert replayed.response == "settled replay"
    assert contacts == ["provider"]
    assert len(authority.plans) == 2
    assert authority.plans[0].call_id == authority.plans[1].call_id
    assert [outcome.status for outcome in authority.outcomes] == ["succeeded", "replayed"]


def test_distinct_agents_at_same_checkpoint_have_distinct_logical_call_ids():
    first_authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    second_authority = _Authority(ModelAttemptReservation.approved("reservation-2"))
    scope = _StableExecutionContext()
    first = _agent(first_authority, execution_context=scope, name="researcher")
    second = _agent(second_authority, execution_context=scope, name="reviewer")
    first._module = SimpleNamespace(module=_bounded_provider(lambda **_kwargs: None))
    second._module = SimpleNamespace(module=_bounded_provider(lambda **_kwargs: None))
    prompt = {"system_prompt": "system", "history": [], "user_message": "hi"}

    first._reserve_model_attempt({}, prompt)
    second._reserve_model_attempt({}, prompt)

    assert first_authority.plans[0].call_id != second_authority.plans[0].call_id


def test_request_hash_covers_exact_provider_tool_choice():
    class _Tool:
        def format_as_litellm_function_call(self):
            return {
                "type": "function",
                "function": {"name": "lookup", "description": "Lookup", "parameters": {}},
            }

    first_authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    second_authority = _Authority(ModelAttemptReservation.approved("reservation-2"))
    first = _agent(first_authority)
    second = _agent(second_authority)
    first.tools = [_Tool()]
    second.tools = [_Tool()]
    first.tool_choice = "auto"
    second.tool_choice = "required"
    prompt = {
        "system_prompt": "system",
        "history": [],
        "user_message": "hi",
        "tools": [_Tool()],
    }

    first._reserve_model_attempt({}, prompt)
    second._reserve_model_attempt({}, prompt)

    assert first_authority.plans[0].request_hash != second_authority.plans[0].request_hash


def test_exact_provider_request_is_built_once_and_reused_for_contact():
    class _CountingProvider:
        def __init__(self):
            self.builds = 0
            self.contacted_with = []

        def build_provider_request(self, **kwargs):
            self.builds += 1
            return {
                "messages": [{"role": "user", "content": kwargs["user_message"]}],
                "kwargs": {"tool_choice": "required"},
            }

        def __call__(self, **kwargs):
            self.contacted_with.append(kwargs["_tactus_provider_request"])
            return dspy.Prediction(response="ok")

    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority)
    provider = _CountingProvider()
    agent._module = SimpleNamespace(module=provider)
    prompt = {"system_prompt": "system", "history": [], "user_message": "hi"}

    result = agent._run_provider_attempt({}, prompt, lambda: provider(**prompt))

    assert result.response == "ok"
    assert provider.builds == 1
    assert provider.contacted_with == [
        {
            "messages": [{"role": "user", "content": "hi"}],
            "kwargs": {"tool_choice": "required"},
        }
    ]


def test_real_raw_module_dispatches_the_prepared_exact_request():
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority)
    lm = _RecordingLM()
    prompt = {"system_prompt": "system", "history": [], "user_message": "hi"}

    with dspy.context(lm=lm):
        result = agent._run_provider_attempt({}, prompt, lambda: agent._module.module(**prompt))

    assert result.response == "ok"
    assert lm.calls == [
        {
            "messages": [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "hi"},
            ],
            "kwargs": {"max_tokens": 32},
        }
    ]


def test_succeeded_settlement_exposes_json_serializable_replay_payload():
    authority = _PersistingAuthority()
    agent = _agent(authority)
    agent._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: dspy.Prediction(
                response="approved", metadata={"citations": ["source-1"]}
            )
        )
    )
    prompt = {"system_prompt": "system", "history": [], "user_message": "hi"}

    agent._run_provider_attempt({}, prompt, lambda: agent._module.module(**prompt))

    payload = json.loads(authority.serialized_replay_payload)
    assert payload == {
        "fields": {
            "metadata": {"citations": ["source-1"]},
            "response": "approved",
        },
        "kind": "prediction",
        "typed_fields": {},
        "version": 1,
    }


def test_fresh_agent_restores_serialized_nonstreaming_replay_without_contact():
    persisting = _PersistingAuthority()
    first = _agent(persisting)
    contacts = []
    first._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: contacts.append("provider")
            or dspy.Prediction(
                response="approved",
                metadata={"rank": 1},
                tool_calls=ToolCalls.from_dict_list(
                    [{"name": "lookup", "args": {"query": "evidence"}}]
                ),
            )
        )
    )
    prompt = {"system_prompt": "system", "history": [], "user_message": "hi"}
    first_result = first._run_provider_attempt({}, prompt, lambda: first._module.module(**prompt))
    persisted = json.loads(persisting.serialized_replay_payload)
    replaying = _Authority(
        ModelAttemptReservation.replay("reservation-1", replay_payload=persisted)
    )
    fresh = _agent(replaying)
    fresh._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: contacts.append("unexpected") or dspy.Prediction(response="never")
        )
    )

    replayed_result = fresh._run_provider_attempt(
        {}, prompt, lambda: fresh._module.module(**prompt)
    )

    assert first_result.toDict() == replayed_result.toDict()
    assert isinstance(replayed_result.tool_calls, ToolCalls)
    assert replayed_result.tool_calls.tool_calls[0].name == "lookup"
    assert contacts == ["provider"]
    assert replaying.outcomes[0].status == "replayed"
    assert persisting.outcomes[0].plan.request_hash == replaying.plans[0].request_hash


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 99, "kind": "prediction", "fields": {}, "typed_fields": {}},
        {"version": 1, "kind": "wrong", "fields": {}, "typed_fields": {}},
        {"version": 1, "kind": "prediction", "fields": [], "typed_fields": {}},
        {
            "version": 1,
            "kind": "prediction",
            "fields": {"tool_calls": []},
            "typed_fields": {"tool_calls": "tool_calls"},
        },
        None,
        dspy.Prediction(response="not persistence safe"),
    ],
)
def test_corrupted_or_type_mismatched_replay_fails_closed_without_contact(payload):
    authority = _Authority(ModelAttemptReservation.replay("reservation-1", replay_payload=payload))
    agent = _agent(authority, attempts=3)
    contacts = []
    agent._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: contacts.append("provider") or dspy.Prediction(response="never")
        )
    )

    with pytest.raises(ModelAttemptRejected, match="replay payload"):
        agent._turn_with_retries(
            {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
        )

    assert contacts == []


def test_unserializable_provider_success_is_unknown_and_not_retried():
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority, attempts=3)
    contacts = []
    agent._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: contacts.append("provider") or dspy.Prediction(response=object())
        )
    )

    with pytest.raises(ModelAttemptOutcomeUnknown, match="replay payload"):
        agent._turn_with_retries(
            {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
        )

    assert contacts == ["provider"]
    assert [outcome.status for outcome in authority.outcomes] == ["outcome_unknown"]


def test_fresh_agent_restores_serialized_streaming_replay_without_contact(monkeypatch):
    persisting = _PersistingAuthority()
    first = _agent(persisting)
    first.log_handler = _StreamingLogHandler()
    contacts = []

    def streamify(_module):
        def stream(**_kwargs):
            async def values():
                contacts.append("provider")
                yield "approved"
                yield dspy.Prediction(response="approved", metadata={"mode": "stream"})

            return values()

        return stream

    first._module = SimpleNamespace(
        module=_bounded_provider(lambda **_kwargs: dspy.Prediction(response="unused"))
    )
    monkeypatch.setattr(dspy, "streamify", streamify)
    prompt = {"system_prompt": "system", "history": [], "user_message": "hi"}
    first_result = first._turn_with_retries({}, prompt)
    persisted = json.loads(persisting.serialized_replay_payload)

    replaying = _Authority(
        ModelAttemptReservation.replay("reservation-1", replay_payload=persisted)
    )
    fresh = _agent(replaying)
    fresh.log_handler = _StreamingLogHandler()
    fresh._module = SimpleNamespace(
        module=_bounded_provider(lambda **_kwargs: dspy.Prediction(response="never"))
    )
    replayed_result = fresh._turn_with_retries({}, prompt)

    assert (
        first_result.output
        == replayed_result.output
        == {
            "metadata": {"mode": "stream"},
            "response": "approved",
        }
    )
    assert contacts == ["provider"]
    assert replaying.outcomes[0].status == "replayed"


def test_first_stream_chunk_observer_failure_is_unknown_and_not_retried(monkeypatch):
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority, attempts=3)
    agent.log_handler = _FailOnFirstChunkLog()
    contacts = []

    def streamify(_module):
        def stream(**_kwargs):
            async def values():
                contacts.append("provider")
                yield "hello"
                yield dspy.Prediction(response="completed")

            return values()

        return stream

    agent._module = SimpleNamespace(
        module=_bounded_provider(lambda **_kwargs: dspy.Prediction(response="unused"))
    )
    monkeypatch.setattr(dspy, "streamify", streamify)

    with pytest.raises(ModelAttemptOutcomeUnknown, match="first chunk observer failed"):
        agent._turn_with_retries(
            {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
        )

    assert contacts == ["provider"]
    assert authority.outcomes[-1].status == "outcome_unknown"


def test_input_overflow_blocks_before_reservation_or_provider_contact():
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority, execution_context=_StableExecutionContext())
    agent.max_input_tokens = 1
    contacts = []

    with pytest.raises(ModelAttemptRejected, match="max_input_tokens"):
        agent._run_provider_attempt(
            {},
            {"system_prompt": "system", "history": [], "user_message": "this is too large"},
            lambda: contacts.append("provider") or dspy.Prediction(response="never"),
        )

    assert authority.plans == []
    assert contacts == []


def test_unmeasurable_provider_request_fails_closed_before_contact():
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority, execution_context=_StableExecutionContext())
    contacts = []
    agent._module = SimpleNamespace(
        module=lambda **_kwargs: contacts.append("provider") or dspy.Prediction(response="never")
    )

    with pytest.raises(ModelAttemptRejected, match="cannot be bounded"):
        agent._run_provider_attempt(
            {},
            {"system_prompt": "system", "history": [], "user_message": "hi"},
            lambda: contacts.append("provider") or dspy.Prediction(response="never"),
        )

    assert authority.plans == []
    assert contacts == []


def test_authority_enforced_attempt_bound_blocks_the_next_physical_call():
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority, attempts=1)
    calls = []
    agent._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: calls.append("provider") or dspy.Prediction(response="ok")
        )
    )
    prompt = {"system_prompt": "system", "history": [], "user_message": "hi"}
    outer_scope = agent._begin_model_attempt_turn()
    try:
        agent._run_provider_attempt({}, prompt, lambda: agent._module.module(**prompt))
        with pytest.raises(ModelAttemptRejected, match="maximum was exhausted"):
            agent._run_provider_attempt({}, prompt, lambda: agent._module.module(**prompt))
    finally:
        agent._end_model_attempt_turn(outer_scope)

    assert calls == ["provider"]


def test_validation_retry_after_settled_success_reserves_a_second_attempt():
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority, attempts=2)
    agent.retry_enabled = True
    agent.retry_attempts = 2
    contacts = []
    validations = []
    agent._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: contacts.append("provider") or dspy.Prediction(response="approved")
        )
    )

    def validate(_result):
        validations.append("validated")
        if len(validations) == 1:
            raise ValueError("response needs repair")

    agent._validate_output = validate

    result = agent._turn_with_retries(
        {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
    )

    assert result.output == "approved"
    assert contacts == ["provider", "provider"]
    assert [plan.attempt_number for plan in authority.plans] == [1, 2]
    assert [outcome.status for outcome in authority.outcomes] == ["succeeded", "succeeded"]


def test_validation_retry_respects_the_physical_attempt_bound_before_contact():
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    agent = _agent(authority, attempts=1)
    agent.retry_enabled = True
    agent.retry_attempts = 2
    contacts = []
    agent._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: contacts.append("provider") or dspy.Prediction(response="approved")
        )
    )
    agent._validate_output = lambda _result: (_ for _ in ()).throw(
        ValueError("response needs repair")
    )

    with pytest.raises(ModelAttemptRejected, match="maximum was exhausted"):
        agent._turn_with_retries(
            {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
        )

    assert contacts == ["provider"]
    assert [plan.attempt_number for plan in authority.plans] == [1]
    assert [outcome.status for outcome in authority.outcomes] == ["succeeded"]


@pytest.mark.parametrize(
    "reservation",
    [
        ModelAttemptReservation(status="unsupported"),
        ModelAttemptReservation(status="approved", reservation_id=""),
        ModelAttemptReservation(status="replay", reservation_id=""),
        ModelAttemptReservation(status="replay", reservation_id="reservation-1"),
        ModelAttemptReservation(status="replay", reservation_id="reservation-1", replay_payload={}),
    ],
)
def test_malformed_authority_reservations_fail_closed_without_provider_contact(reservation):
    authority = _Authority(reservation)
    agent = _agent(authority)
    contacts = []
    agent._module = SimpleNamespace(
        module=_bounded_provider(
            lambda **_kwargs: contacts.append("provider") or dspy.Prediction(response="never")
        )
    )

    with pytest.raises(ModelAttemptRejected, match="reservation|replay payload"):
        agent._turn_with_retries(
            {}, {"system_prompt": "system", "history": [], "user_message": "hi"}
        )

    assert contacts == []


@pytest.mark.asyncio
async def test_runtime_threads_authority_and_attempt_bounds_to_agents(monkeypatch):
    authority = _Authority(ModelAttemptReservation.approved("reservation-1"))
    runtime = runtime_module.TactusRuntime(
        procedure_id="procedure-1",
        hitl_handler=object(),
        model_attempt_authority=authority,
    )
    runtime.lua_sandbox = _LuaSandbox()
    runtime.toolset_registry = {}
    runtime.config = {}
    runtime.registry = SimpleNamespace(
        agents={
            "gate": {
                "system_prompt": "system",
                "provider": "openai",
                "model": "gpt-4o-mini-2024-07-18",
                "max_tokens": 32,
                "max_input_tokens": 128,
                "model_attempt_max_attempts": 2,
            }
        }
    )
    runtime.agents = {}
    captured = {}

    async def no_dependencies():
        return None

    def create_agent(_name, config, **kwargs):
        captured["config"] = config
        captured["kwargs"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(runtime, "_initialize_dependencies", no_dependencies)
    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", create_agent)

    await runtime._setup_agents(context={})

    assert captured["kwargs"]["model_attempt_authority"] is authority
    assert captured["config"]["max_input_tokens"] == 128
    assert captured["config"]["model_attempt_max_attempts"] == 2
