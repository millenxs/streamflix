from src.analytics.views import DEFAULT_ANALYTICS_SQL


def test_analytics_views_define_dashboard_contract() -> None:
    sql = DEFAULT_ANALYTICS_SQL.read_text(encoding="utf-8")

    for view_name in (
        "vw_daily_engagement",
        "vw_content_performance",
        "vw_device_usage",
        "vw_recommendation_performance",
        "vw_user_retention_churn",
        "vw_executive_kpis",
    ):
        assert f"CREATE OR REPLACE VIEW {view_name}" in sql


def test_executive_kpis_include_active_user_windows_and_recommendation_rates() -> None:
    sql = DEFAULT_ANALYTICS_SQL.read_text(encoding="utf-8")

    assert "weekly_active_users" in sql
    assert "monthly_active_users" in sql
    assert "recommendation_ctr" in sql
    assert "recommendation_conversion_rate" in sql
    assert "recommendation_completion_rate" in sql


def test_views_use_nullif_for_safe_division() -> None:
    sql = DEFAULT_ANALYTICS_SQL.read_text(encoding="utf-8")

    assert "NULLIF" in sql
    assert "/ 0" not in sql
