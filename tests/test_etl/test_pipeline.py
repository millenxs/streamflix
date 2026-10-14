from src.etl.pipeline import (
    INSERT_FACT_RECOMMENDATIONS_SQL,
    INSERT_FACT_SESSIONS_SQL,
    INSERT_FACT_WATCH_EVENTS_SQL,
    PIPELINE_STEPS,
    PipelineResult,
    StepResult,
    run_step,
)


class RecordingCursor:
    def __init__(self, rowcount: int = 3) -> None:
        self.rowcount = rowcount
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement: str, params: dict) -> None:
        self.calls.append((statement, params))


def test_pipeline_steps_are_ordered_for_foreign_keys() -> None:
    assert [name for name, _ in PIPELINE_STEPS] == [
        "dim_device",
        "dim_location",
        "fact_recommendations",
        "fact_watch_events",
        "fact_sessions",
        "fact_user_interactions",
        "fact_recommendation_feedback",
    ]


def test_recommendation_sql_reads_recommendation_id_from_metadata() -> None:
    assert "event.metadata->>'recommendation_id'" in INSERT_FACT_RECOMMENDATIONS_SQL
    assert "event.recommendation_id" not in INSERT_FACT_RECOMMENDATIONS_SQL


def test_watch_sql_uses_playback_table_for_timing_fields() -> None:
    assert "JOIN raw_playback_events playback ON playback.event_id = event.event_id" in INSERT_FACT_WATCH_EVENTS_SQL
    assert "playback.watch_seconds" in INSERT_FACT_WATCH_EVENTS_SQL
    assert "playback.position_seconds" in INSERT_FACT_WATCH_EVENTS_SQL


def test_sessions_sql_is_single_insert_with_rollup_cte() -> None:
    assert INSERT_FACT_SESSIONS_SQL.lstrip().startswith("WITH session_rollup AS")
    assert INSERT_FACT_SESSIONS_SQL.count("INSERT INTO fact_sessions") == 1
    assert "ON CONFLICT (session_id) DO UPDATE" in INSERT_FACT_SESSIONS_SQL


def test_pipeline_result_total_ignores_negative_rowcounts() -> None:
    result = PipelineResult(
        (
            StepResult("a", 2, 0.1),
            StepResult("b", -1, 0.1),
            StepResult("c", 5, 0.1),
        )
    )

    assert result.total_rowcount == 7


def test_run_step_passes_model_version_parameter() -> None:
    cursor = RecordingCursor(rowcount=4)

    result = run_step(cursor, "fact_recommendations", "SELECT %(model_version)s", "test-model")

    assert result.name == "fact_recommendations"
    assert result.rowcount == 4
    assert cursor.calls == [("SELECT %(model_version)s", {"model_version": "test-model"})]
