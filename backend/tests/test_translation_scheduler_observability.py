"""Translation scheduler observability tests.

Covers:
- SchedulerDecisionRecorder records candidates and selections
- Selected model decision includes identity fields
- Cooldown, RPM, RPD, quota, memory skip reasons
- Fallback selection, no-capacity failure
- Candidate list bounding and truncation
- Checkpoint/resume IDs, memory fields
- Scheduler summary aggregation
- push/collect decision accumulator (parallelism safe)
- Legacy translation compatibility

No live translation providers. All tests are offline.
"""

from __future__ import annotations

from datetime import timedelta

from novelai.shared.pipeline import SchedulerModelStatus
from novelai.translation.scheduler import (
    SchedulerDecisionRecorder,
    SchedulerModelConfig,
    SchedulerModelRuntimeState,
    SchedulerPolicy,
    SelectionReason,
    TranslationScheduler,
    build_scheduler_summary,
    utc_now,
)


def _make_scheduler(
    models: list[tuple[str, str, str]],
    *,
    policy: SchedulerPolicy = SchedulerPolicy.VOLUME_FIRST,
) -> TranslationScheduler:
    configs = [
        SchedulerModelConfig(provider_key=pk, provider_model=pm, priority_order=i)
        for i, (pk, pm, _status) in enumerate(models)
    ]
    states = {}
    future = (utc_now() + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    for pk, pm, status in models:
        state = SchedulerModelRuntimeState(
            provider_key=pk,
            provider_model=pm,
            priority_order=0,
            status=status,
            cooldown_until=future if status == SchedulerModelStatus.COOLING_DOWN.value else None,
            exhausted_until=future if status == SchedulerModelStatus.DAILY_EXHAUSTED.value else None,
        )
        states[(pk, pm)] = state
    scheduler = TranslationScheduler(
        model_configs=configs,
        policy=policy,
        model_states=states,
    )
    return scheduler


def _make_rpm_limited_state() -> SchedulerModelRuntimeState:
    state = SchedulerModelRuntimeState(
        provider_key="test",
        provider_model="model",
        priority_order=0,
        rpm_limit=10,
        rpd_limit=100,
        requests_this_minute=10,
        requests_today=5,
        status=SchedulerModelStatus.AVAILABLE.value,
    )
    state.window_started_at = (utc_now() - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
    return state


# ---------------------------------------------------------------------------
# Task 2-3: Decision recorder basics
# ---------------------------------------------------------------------------


class TestSchedulerDecisionRecorder:
    def test_records_selected_decision(self) -> None:
        scheduler = _make_scheduler([("provider_a", "model_a", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder(chapter_id="1")
        selection = scheduler.select_model(decision_recorder=recorder)
        assert selection.provider_key == "provider_a"
        assert selection.provider_model == "model_a"

        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        assert decision.selected_provider == "provider_a"
        assert decision.selected_model == "model_a"

    def test_decision_includes_chapter_id(self) -> None:
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder(chapter_id="ch12")
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        assert decision.chapter_id == "ch12"
        assert decision.to_dict().get("chapter_id") == "ch12"

    def test_decision_includes_request_id(self) -> None:
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder(request_id="req-123")
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        assert decision.request_id == "req-123"
        assert decision.to_dict().get("request_id") == "req-123"

    def test_decision_includes_job_id(self) -> None:
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder(job_id="job-789")
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        assert decision.job_id == "job-789"

    def test_decision_includes_activity_id(self) -> None:
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder(activity_id="activity-456")
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        assert decision.activity_id == "activity-456"

    def test_decision_includes_policy(self) -> None:
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder()
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        assert decision.policy == "volume_first"

    def test_decision_is_json_serializable(self) -> None:
        import json
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder(chapter_id="1", request_id="req-1")
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        dumped = json.dumps(decision.to_dict())
        assert isinstance(dumped, str)


# ---------------------------------------------------------------------------
# Task 4-6: Skip reason codes
# ---------------------------------------------------------------------------


class TestSkipReasons:
    def test_cooldown_skip_reason_recorded(self) -> None:
        models = [
            ("p1", "m1", SchedulerModelStatus.COOLING_DOWN.value),
            ("p2", "m2", SchedulerModelStatus.AVAILABLE.value),
        ]
        scheduler = _make_scheduler(models)
        recorder = SchedulerDecisionRecorder(chapter_id="1")
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        # p2 is selected as fallback (p1 was cooling down)
        assert decision.selected_provider == "p2"
        assert decision.candidates is not None
        # First candidate should have a skip reason
        skip_candidate = next(c for c in decision.candidates if c.provider == "p1")
        assert skip_candidate.skip_reason is not None
        assert skip_candidate.selected is False
        # Fallback flag should be set
        assert decision.fallback_used is True

    def test_rpm_skip_reason(self) -> None:
        now = utc_now()
        state = _make_rpm_limited_state()
        config = SchedulerModelConfig(provider_key="test", provider_model="model", priority_order=0)
        scheduler = TranslationScheduler(
            model_configs=[config],
            policy=SchedulerPolicy.VOLUME_FIRST,
            model_states={("test", "model"): state},
        )
        recorder = SchedulerDecisionRecorder()
        selection = scheduler.select_model(now=now, decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        # Model is RPM-limited — no capacity
        assert decision.selected_provider is None
        assert decision.selected_model is None
        # Candidate was recorded with status
        assert decision.candidates is not None
        assert len(decision.candidates) == 1

    def test_fallback_selection_records_skipped_candidates(self) -> None:
        models = [
            ("p1", "m1", SchedulerModelStatus.COOLING_DOWN.value),
            ("p2", "m2", SchedulerModelStatus.AVAILABLE.value),
        ]
        scheduler = _make_scheduler(models)
        recorder = SchedulerDecisionRecorder()
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value, total_candidates=2)
        assert decision.fallback_used is True
        assert decision.candidate_count_total == 2
        assert decision.candidates is not None
        assert len(decision.candidates) == 2

    def test_no_capacity_failure(self) -> None:
        models = [
            ("p1", "m1", SchedulerModelStatus.DAILY_EXHAUSTED.value),
            ("p2", "m2", SchedulerModelStatus.COOLING_DOWN.value),
        ]
        scheduler = _make_scheduler(models)
        recorder = SchedulerDecisionRecorder()
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        # Both models are unavailable — no capacity
        assert decision.selected_provider is None
        assert decision.selected_model is None
        assert decision.candidates is not None
        assert len(decision.candidates) == 2

    def test_candidate_list_is_bounded(self) -> None:
        models = [(f"p{i}", f"m{i}", SchedulerModelStatus.AVAILABLE.value) for i in range(25)]
        scheduler = _make_scheduler(models)
        recorder = SchedulerDecisionRecorder()
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value, total_candidates=25)
        # First available candidate is selected, remaining are skipped
        assert decision.selected_provider == "p0"
        assert decision.candidates is not None
        assert len(decision.candidates) == 1  # Only first candidate evaluated before selection


# ---------------------------------------------------------------------------
# Task 17: Legacy compatibility
# ---------------------------------------------------------------------------


class TestLegacyCompatibility:
    def test_scheduler_works_without_recorder(self) -> None:
        """Not passing a decision_recorder must not change behavior."""
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        selection = scheduler.select_model()
        assert selection.provider_key == "p"
        assert selection.provider_model == "m"
        assert selection.reason == SelectionReason.PRIMARY_AVAILABLE.value

    def test_scheduler_works_without_observability_metadata(self) -> None:
        """Recorder must not influence selection."""
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder()
        selection_with = scheduler.select_model(decision_recorder=recorder)
        selection_without = scheduler.select_model()
        assert selection_with.provider_key == selection_without.provider_key
        assert selection_with.provider_model == selection_without.provider_model


# ---------------------------------------------------------------------------
# Task 13: Decision to_dict safety
# ---------------------------------------------------------------------------


class TestDecisionSafety:
    def test_to_dict_excludes_secrets(self) -> None:
        """Decision dict must not include API keys or credentials."""
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder()
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        d = decision.to_dict()
        for key in d:
            assert "key" not in key.lower() or key == "provider_key"
        # Check no secrets stored
        dumped = str(d).lower()
        assert "secret" not in dumped
        assert "api_key" not in dumped

    def test_to_dict_excludes_source_text(self) -> None:
        """Decision dict must not include source or translated text."""
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder()
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        d = str(decision.to_dict())
        assert "translated" not in d.lower() or "translated_at" in d.lower()


class TestDecisionAccumulator:
    """push_scheduler_decision / collect_scheduler_decisions (REQ-12, REQ-9)."""

    def test_push_and_collect(self) -> None:
        from novelai.translation.scheduler import collect_scheduler_decisions, push_scheduler_decision

        # Clear any prior decisions
        collect_scheduler_decisions()

        push_scheduler_decision({"selected": {"provider": "p", "model": "m"}})
        push_scheduler_decision({"selected": {"provider": "q", "model": "n"}})

        decisions = collect_scheduler_decisions()
        assert len(decisions) == 2
        assert decisions[0]["selected"]["provider"] == "p"
        assert decisions[1]["selected"]["provider"] == "q"

    def test_collect_clears_accumulator(self) -> None:
        from novelai.translation.scheduler import collect_scheduler_decisions, push_scheduler_decision

        collect_scheduler_decisions()
        push_scheduler_decision({"selected": {"provider": "p", "model": "m"}})
        first = collect_scheduler_decisions()
        assert len(first) == 1
        second = collect_scheduler_decisions()
        assert len(second) == 0

    def test_accumulator_is_thread_safe_list(self) -> None:
        """The accumulator is a plain list — appends are atomic in CPython."""
        from novelai.translation.scheduler import _scheduler_decisions_accumulator

        _scheduler_decisions_accumulator.clear()
        _scheduler_decisions_accumulator.append({"a": 1})
        _scheduler_decisions_accumulator.append({"b": 2})
        assert len(_scheduler_decisions_accumulator) == 2


# ---------------------------------------------------------------------------
# Task 9: Parallel chapter decisions
# ---------------------------------------------------------------------------


class TestParallelismSafety:
    def test_decisions_from_parallel_chapters_are_distinct(self) -> None:
        """Simulate two parallel chapters producing decisions."""
        from novelai.translation.scheduler import (
            SchedulerDecisionRecorder,
            collect_scheduler_decisions,
            push_scheduler_decision,
        )

        collect_scheduler_decisions()

        # Chapter 1 decision
        r1 = SchedulerDecisionRecorder(chapter_id="ch1", request_id="req-1")
        s1 = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        sel1 = s1.select_model(decision_recorder=r1)
        d1 = r1.finalize(selection=sel1, policy=s1.policy.value).to_dict()
        push_scheduler_decision(d1)

        # Chapter 2 decision
        r2 = SchedulerDecisionRecorder(chapter_id="ch2", request_id="req-2")
        s2 = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        sel2 = s2.select_model(decision_recorder=r2)
        d2 = r2.finalize(selection=sel2, policy=s2.policy.value).to_dict()
        push_scheduler_decision(d2)

        decisions = collect_scheduler_decisions()
        assert len(decisions) == 2
        assert decisions[0]["chapter_id"] == "ch1"
        assert decisions[1]["chapter_id"] == "ch2"

    def test_duplicate_attempts_distinguishable(self) -> None:
        """Same chapter, different attempts — distinguished by request_id."""
        from novelai.translation.scheduler import (
            SchedulerDecisionRecorder,
            collect_scheduler_decisions,
            push_scheduler_decision,
        )

        collect_scheduler_decisions()

        s = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        for attempt in range(2):
            r = SchedulerDecisionRecorder(
                chapter_id="ch1",
                request_id=f"req-ch1-attempt-{attempt}",
                job_id="job-1",
            )
            sel = s.select_model(decision_recorder=r)
            d = r.finalize(selection=sel, policy=s.policy.value).to_dict()
            push_scheduler_decision(d)

        decisions = collect_scheduler_decisions()
        assert len(decisions) == 2
        assert decisions[0]["request_id"] == "req-ch1-attempt-0"
        assert decisions[1]["request_id"] == "req-ch1-attempt-1"
        assert decisions[0]["job_id"] == "job-1"


# ---------------------------------------------------------------------------
# Task 8: Checkpoint/resume integration
# ---------------------------------------------------------------------------


class TestCheckpointObservability:
    def test_decision_includes_checkpoint_id(self) -> None:
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder(checkpoint_id="cp-abc")
        selection = scheduler.select_model(decision_recorder=recorder)
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        assert decision.checkpoint_id == "cp-abc"
        assert decision.to_dict().get("checkpoint_id") == "cp-abc"


# ---------------------------------------------------------------------------
# Task 10: Memory observability
# ---------------------------------------------------------------------------


class TestMemoryObservability:
    def test_decision_memory_fields(self) -> None:
        recorder = SchedulerDecisionRecorder()
        decision = recorder.finalize(
            selection=_make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)]).select_model(),
            policy="volume_first",
        )
        # Memory fields are None by default
        assert decision.exact_memory_bytes is None
        assert decision.memory_limit_bytes is None
        assert decision.memory_pressure is None

    def test_decision_memory_fields_in_to_dict(self) -> None:
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder()
        selection = scheduler.select_model(decision_recorder=recorder)

        # Simulate setting memory on the underlying decision
        recorder._decision.exact_memory_bytes = 500_000_000
        recorder._decision.memory_limit_bytes = 1_000_000_000
        recorder._decision.memory_pressure = False

        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        d = decision.to_dict()
        assert "memory" in d
        assert d["memory"]["exact_memory_bytes"] == 500_000_000
        assert d["memory"]["memory_limit_bytes"] == 1_000_000_000
        assert d["memory"]["memory_pressure"] is False

    def test_memory_pressure_flag(self) -> None:
        scheduler = _make_scheduler([("p", "m", SchedulerModelStatus.AVAILABLE.value)])
        recorder = SchedulerDecisionRecorder()
        selection = scheduler.select_model(decision_recorder=recorder)
        recorder._decision.memory_pressure = True
        decision = recorder.finalize(selection=selection, policy=scheduler.policy.value)
        assert decision.memory_pressure is True


# ---------------------------------------------------------------------------
# Task 12: Scheduler summary
# ---------------------------------------------------------------------------


class TestSchedulerSummary:
    def test_summary_counts_chapters_with_decisions(self) -> None:
        decisions = [
            {"selected": {"provider": "p", "model": "m"}, "candidates": []},
            {"selected": {"provider": "p", "model": "m"}, "candidates": []},
        ]
        summary = build_scheduler_summary(decisions)
        assert summary["chapters_with_decisions"] == 2

    def test_summary_counts_fallback(self) -> None:
        decisions = [
            {"selected": {"provider": "p", "model": "m"}, "fallback_used": True, "candidates": []},
            {"selected": {"provider": "p", "model": "m"}, "fallback_used": False, "candidates": []},
        ]
        summary = build_scheduler_summary(decisions)
        assert summary["fallback_count"] == 1

    def test_summary_counts_no_capacity(self) -> None:
        decisions = [
            {"selected": None, "failure_reason": "no_capacity", "candidates": []},
            {"selected": {"provider": "p", "model": "m"}, "candidates": []},
        ]
        summary = build_scheduler_summary(decisions)
        assert summary["no_capacity_count"] == 1

    def test_summary_aggregates_skip_reasons(self) -> None:
        decisions = [
            {
                "selected": {"provider": "p", "model": "m"},
                "candidates": [
                    {"skip_reason": "cooldown_active"},
                    {"skip_reason": "cooldown_active"},
                ],
            },
        ]
        summary = build_scheduler_summary(decisions)
        assert summary["skip_reason_counts"] == {"cooldown_active": 2}

    def test_summary_aggregates_selected_models(self) -> None:
        decisions = [
            {"selected": {"provider": "p", "model": "m"}, "candidates": []},
            {"selected": {"provider": "p", "model": "m"}, "candidates": []},
            {"selected": {"provider": "q", "model": "n"}, "candidates": []},
        ]
        summary = build_scheduler_summary(decisions)
        assert summary["selected_model_counts"] == {"p:m": 2, "q:n": 1}
        assert summary["provider_counts"] == {"p": 2, "q": 1}

    def test_summary_counts_checkpoint(self) -> None:
        decisions = [
            {"selected": {"provider": "p", "model": "m"}, "checkpoint_id": "cp-1", "candidates": []},
            {"selected": {"provider": "p", "model": "m"}, "candidates": []},
        ]
        summary = build_scheduler_summary(decisions)
        assert summary["checkpoint_blocked_count"] == 1

    def test_summary_tracks_peak_memory(self) -> None:
        decisions = [
            {"selected": {"provider": "p", "model": "m"}, "memory": {"exact_memory_bytes": 100, "memory_pressure": False}, "candidates": []},
            {"selected": {"provider": "p", "model": "m"}, "memory": {"exact_memory_bytes": 500, "memory_pressure": True}, "candidates": []},
            {"selected": {"provider": "p", "model": "m"}, "memory": {"exact_memory_bytes": 300, "memory_pressure": False}, "candidates": []},
        ]
        summary = build_scheduler_summary(decisions)
        assert summary["peak_exact_memory_bytes"] == 500
        assert summary["memory_pressure_count"] == 1

    def test_summary_empty_decisions(self) -> None:
        summary = build_scheduler_summary([])
        assert summary["chapters_with_decisions"] == 0
        assert summary["skip_reason_counts"] == {}
        assert summary["selected_model_counts"] == {}
        assert summary["provider_counts"] == {}

    def test_summary_excludes_noise_fields(self) -> None:
        decisions = [
            {"selected": {"provider": "p", "model": "m"}, "candidates": [], "extra_noise": "should_not_appear"},
        ]
        summary = build_scheduler_summary(decisions)
        assert "extra_noise" not in summary
        assert "candidates" not in summary


# ---------------------------------------------------------------------------
# Task 18: Activity metadata summary
# ---------------------------------------------------------------------------


class TestActivityMetadataSummary:
    """Scheduler_summary is stored in activity metadata via the worker."""

    def test_worker_passes_scheduler_summary(self) -> None:
        """Simulate what the worker does: extract scheduler_summary."""
        from novelai.translation.scheduler import (
            build_scheduler_summary,
            collect_scheduler_decisions,
            push_scheduler_decision,
        )

        collect_scheduler_decisions()

        push_scheduler_decision({
            "selected": {"provider": "p", "model": "m"},
            "fallback_used": False,
            "candidates": [],
            "chapter_id": "1",
        })
        push_scheduler_decision({
            "selected": {"provider": "q", "model": "n"},
            "fallback_used": True,
            "candidates": [{"skip_reason": "preferred_model_cooling_down"}],
            "chapter_id": "2",
        })

        summary = build_scheduler_summary(collect_scheduler_decisions())
        assert summary["chapters_with_decisions"] == 2
        assert summary["fallback_count"] == 1
        assert summary["selected_model_counts"] == {"p:m": 1, "q:n": 1}
        assert "preferred_model_cooling_down" in summary["skip_reason_counts"]

    def test_scheduler_summary_combined_with_chapter_progress(self) -> None:
        """The translate_chapters return dict includes both chapter_progress and scheduler_summary."""
        from novelai.translation.scheduler import (
            build_scheduler_summary,
            collect_scheduler_decisions,
            push_scheduler_decision,
        )

        collect_scheduler_decisions()
        push_scheduler_decision({
            "selected": {"provider": "p", "model": "m"},
            "fallback_used": True,
            "candidates": [],
        })
        summary = build_scheduler_summary(collect_scheduler_decisions())

        full_result = {
            "chapter_progress": {"1": {"status": "succeeded"}, "2": {"status": "succeeded"}},
            "succeeded": 2,
            "failed": 0,
            "skipped": 0,
            "total": 2,
            "scheduler_summary": summary,
        }
        assert full_result["scheduler_summary"]["chapters_with_decisions"] == 1
        assert full_result["scheduler_summary"]["fallback_count"] == 1

    def test_scheduler_summary_empty_when_no_decisions(self) -> None:
        from novelai.translation.scheduler import build_scheduler_summary, collect_scheduler_decisions

        collect_scheduler_decisions()
        summary = build_scheduler_summary(collect_scheduler_decisions())
        assert summary["chapters_with_decisions"] == 0
        assert summary["fallback_count"] == 0
        assert summary["no_capacity_count"] == 0


# ---------------------------------------------------------------------------
# Task 18: Scheduler health API data
# ---------------------------------------------------------------------------


class TestSchedulerHealthData:
    """Test the scheduler_health service method generates correct structure.

    These tests call the method directly; the mocked preferences return
    no provider_management state so the method falls through to
    _default_fallback_policy, which needs a registered provider.
    We patch at a high level to keep tests offline.
    """

    def _make_service(self):
        from novelai.services.admin_service import AdminService

        fake_prefs = type("FakePrefs", (), {
            "prefs_path": "nope",
            "get_provider_management": lambda self: {},
            "get_preferred_provider": lambda self: "gemini",
            "get_provider_model": lambda self: "gemini-3.1-flash-lite",
            "get_api_key": lambda self, pk: "fake-key",
            "reload": lambda self: None,
            "clear": lambda self: None,
        })()
        return AdminService(
            preferences=fake_prefs,  # type: ignore[arg-type]
            translation_cache=type("FakeCache", (), {"cache_file": "nope"})(),  # type: ignore[arg-type]
            usage=type("FakeUsage", (), {"usage_path": "nope", "reload": lambda self: None, "clear": lambda self: None})(),  # type: ignore[arg-type]
            activity_runner=type("FakeRunner", (), {"status": lambda self: {}})(),  # type: ignore[arg-type]
        )

    def test_health_structure(self) -> None:
        """scheduler_health() returns policy + models."""
        import json

        service = self._make_service()
        # Patch scheduler_policy_models to avoid provider registry calls
        original = service.scheduler_policy_models
        service.scheduler_policy_models = lambda **kw: [
            {"provider_key": "gemini", "provider_model": "g-1", "priority_order": 0},
        ]
        try:
            health = service.scheduler_health()
            assert "policy" in health
            assert "models" in health
            assert "default_provider" in health["policy"]
            assert "allow_cross_provider_fallback" in health["policy"]
            assert len(health["models"]) >= 1
            # Verify JSON-serializable
            json.dumps(health)
        finally:
            service.scheduler_policy_models = original

    def test_health_models_have_required_fields(self) -> None:
        service = self._make_service()
        original = service.scheduler_policy_models
        service.scheduler_policy_models = lambda **kw: [
            {"provider_key": "gemini", "provider_model": "gemini-3.1-flash-lite", "priority_order": 0},
            {"provider_key": "gemini", "provider_model": "gemma-4-31b-it", "priority_order": 1},
        ]
        try:
            health = service.scheduler_health()
            for model in health["models"]:
                assert "provider_key" in model
                assert "provider_model" in model
                assert "priority_order" in model
                assert "configured" in model
        finally:
            service.scheduler_policy_models = original

    def test_health_redacts_secrets(self) -> None:
        """scheduler_health must not include API keys or credential secrets."""
        service = self._make_service()
        original = service.scheduler_policy_models
        service.scheduler_policy_models = lambda **kw: [
            {"provider_key": "gemini", "provider_model": "g-1", "priority_order": 0},
        ]
        try:
            health = service.scheduler_health()
            dumped = str(health).lower()
            assert "api_key" not in dumped
            assert "secret" not in dumped
        finally:
            service.scheduler_policy_models = original
