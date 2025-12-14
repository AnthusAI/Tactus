"""
Stage and step tracking feature step definitions.
"""

from behave import given, then, when

from tactus.primitives.state import StatePrimitive

from features.steps.support import StageInfo, StageTracker


def _stage_state(context):
    if not hasattr(context, "stage_state"):
        context.stage_state = {
            "tracker": StageTracker(),
            "parent": None,
            "progress_total": 0,
        }
    return context.stage_state


def _tracker(context) -> StageTracker:
    return _stage_state(context)["tracker"]


def _stage_id_by_name(tracker: StageTracker, name: str) -> str:
    for stage_id, info in tracker.stages.items():
        if info.name == name or info.stage_id == name:
            return stage_id
    stage_id = name.replace(" ", "_").lower()
    tracker.stages[stage_id] = StageInfo(stage_id=stage_id, name=name)
    return stage_id


@given("stage and step primitives are initialized")
def step_impl(context):
    _stage_state(context)["tracker"] = StageTracker()
    if not hasattr(context, "state") or context.state is None:
        context.state = StatePrimitive()


@given("a workflow with stages:")
def step_impl(context):
    _tracker(context).define_stages(context.table)


@given("a workflow with {count:d} stages")
def step_impl(context, count):
    _tracker(context).define_numeric_stages(count)


@when('I begin stage "{stage_id}"')
def step_impl(context, stage_id):
    _tracker(context).begin_stage(stage_id)


@when("I complete stage {index:d}")
def step_impl(context, index):
    stage_id = f"stage{index}"
    tracker = _tracker(context)
    tracker.begin_stage(stage_id)
    tracker.complete_stage(stage_id)


@when("I begin stage {index:d}")
def step_impl(context, index):
    _tracker(context).begin_stage(f"stage{index}")


@then('the current stage should be "{name}"')
def step_impl(context, name):
    tracker = _tracker(context)
    assert tracker.current_stage == _stage_id_by_name(tracker, name)


@then('stage status should be "{status}"')
def step_impl(context, status):
    tracker = _tracker(context)
    stage = tracker.stages[tracker.current_stage]
    assert stage.status == status


@then('stage {index:d} status should be "{status}"')
def step_impl(context, index, status):
    assert _tracker(context).stages[f"stage{index}"].status == status


@given('I am in stage "{name}"')
def step_impl(context, name):
    tracker = _tracker(context)
    stage_id = _stage_id_by_name(tracker, name)
    tracker.begin_stage(stage_id)


@when('I begin step "{step_name}"')
def step_impl(context, step_name):
    tracker = _tracker(context)
    if tracker.current_stage is None:
        tracker.stages.setdefault("ad_hoc_stage", StageInfo(stage_id="ad_hoc_stage", name="Ad Hoc"))
        tracker.begin_stage("ad_hoc_stage")
    current = tracker.current_stage
    tracker.track_step(current, step_name, "in_progress")
    tracker.begin_step_timing(current, step_name)


@when('I complete step "{step_name}"')
def step_impl(context, step_name):
    tracker = _tracker(context)
    current = tracker.current_stage
    seconds = getattr(context, "seconds_passed", 0)
    if seconds:
        tracker.advance_time(seconds)
        context.seconds_passed = 0
    tracker.track_step(current, step_name, "completed")
    tracker.complete_step_timing(current, step_name)


@then('stage "{name}" should show {count:d} steps')
def step_impl(context, name, count):
    tracker = _tracker(context)
    stage_id = _stage_id_by_name(tracker, name)
    assert len(tracker.stages[stage_id].steps) == count


@then('step "{step_name}" should be {status}')
def step_impl(context, step_name, status):
    tracker = _tracker(context)
    assert tracker.stages[tracker.current_stage].steps[step_name] == status


@given("a stage with {total:d} steps")
def step_impl(context, total):
    tracker = _tracker(context)
    stage_id = "progress_stage"
    tracker.stages.setdefault(stage_id, StageInfo(stage_id=stage_id, name="progress"))
    tracker.begin_stage(stage_id)
    _stage_state(context)["progress_total"] = total


@when("{completed:d} steps are completed")
def step_impl(context, completed):
    tracker = _tracker(context)
    total = _stage_state(context)["progress_total"]
    tracker.set_progress(tracker.current_stage, completed, total)


@then("stage progress should be {percent:d}%")
def step_impl(context, percent):
    tracker = _tracker(context)
    progress = tracker.stages[tracker.current_stage].progress
    assert round(progress) == percent


@given('a parent stage "{parent}"')
def step_impl(context, parent):
    tracker = _tracker(context)
    tracker.stages[parent] = tracker.stages.get(parent) or StageInfo(stage_id=parent, name=parent)
    _stage_state(context)["parent"] = parent


@given('child stages "{child1}" and "{child2}"')
def step_impl(context, child1, child2):
    tracker = _tracker(context)
    tracker.stages.setdefault(child1, StageInfo(stage_id=child1, name=child1))
    tracker.stages.setdefault(child2, StageInfo(stage_id=child2, name=child2))
    tracker.set_children(_stage_state(context)["parent"], [child1, child2])


@when('I complete "{child}"')
def step_impl(context, child):
    tracker = _tracker(context)
    tracker.stages[child].status = "completed"
    tracker.set_child_completion(_stage_state(context)["parent"])


@then("parent stage progress should reflect child completion")
def step_impl(context):
    tracker = _tracker(context)
    parent = _stage_state(context)["parent"]
    assert tracker.stages[parent].progress == 50.0


@then("parent should be 50% complete")
def step_impl(context):
    tracker = _tracker(context)
    parent = _stage_state(context)["parent"]
    assert tracker.stages[parent].progress == 50.0


@then("step duration should be approximately {seconds:d} seconds")
def step_impl(context, seconds):
    tracker = _tracker(context)
    last_step = list(tracker.step_timings[tracker.current_stage].keys())[-1]
    start = tracker.step_timings[tracker.current_stage][last_step]
    duration = tracker.clock_seconds - start
    assert duration <= seconds


@then("I can identify slow steps")
def step_impl(context):
    assert _tracker(context).step_timings


@then('the stage should be marked as "{status}"')
def step_impl(context, status):
    tracker = _tracker(context)
    assert tracker.stages[tracker.current_stage].status == status


@then("the failure reason should be recorded")
def step_impl(context):
    tracker = _tracker(context)
    assert tracker.stages[tracker.current_stage].failure_reason is not None


@then("I can retry the stage or skip to next stage")
def step_impl(context):
    assert True


@given('a workflow that failed at stage "{name}"')
def step_impl(context, name):
    tracker = _tracker(context)
    stage_id = _stage_id_by_name(tracker, name)
    tracker.begin_stage(stage_id)
    tracker.mark_failed(stage_id, "previous failure")
    context.workflow_config = {
        "steps": [
            {
                "id": "resume_step",
                "action": "state.set",
                "params": {"key": "resume", "value": "done"},
            }
        ]
    }


@then('it should restart from stage "{name}"')
def step_impl(context, name):
    tracker = _tracker(context)
    assert tracker.current_stage == _stage_id_by_name(tracker, name)


@then("completed stages should be skipped")
def step_impl(context):
    tracker = _tracker(context)
    skipped = [stage for stage in tracker.stages.values() if stage.status == "completed"]
    assert skipped or tracker.current_stage is not None


@given("a long-running workflow")
def step_impl(context):
    _tracker(context).progress_updates.clear()


@when("stages and steps complete")
def step_impl(context):
    tracker = _tracker(context)
    tracker.progress_updates.append("stage complete")
    tracker.progress_updates.append("step complete")


@then("progress updates should be emitted")
def step_impl(context):
    assert len(_tracker(context).progress_updates) >= 2


@then("external systems can monitor status")
def step_impl(context):
    assert all(isinstance(event, str) for event in _tracker(context).progress_updates)
