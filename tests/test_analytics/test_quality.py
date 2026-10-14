from src.analytics.quality import QualityCheck, QualityResult, has_blocking_failures, run_check


class CursorWithCount:
    def __init__(self, count: int) -> None:
        self.count = count
        self.executed: str | None = None

    def execute(self, statement: str) -> None:
        self.executed = statement

    def fetchone(self) -> tuple[int]:
        return (self.count,)


def test_run_check_returns_failed_row_count() -> None:
    cursor = CursorWithCount(3)
    check = QualityCheck(name="sample", description="sample check", sql="SELECT COUNT(*) FROM sample")

    result = run_check(cursor, check)

    assert result == QualityResult("sample", "sample check", "error", 3)
    assert cursor.executed == "SELECT COUNT(*) FROM sample"


def test_has_blocking_failures_only_blocks_error_failures() -> None:
    results = (
        QualityResult("warning", "warn", "warning", 10),
        QualityResult("passed", "pass", "error", 0),
    )

    assert not has_blocking_failures(results)

    blocking = (*results, QualityResult("failed", "fail", "error", 1))

    assert has_blocking_failures(blocking)
