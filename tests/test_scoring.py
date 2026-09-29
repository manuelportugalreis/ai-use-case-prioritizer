import pandas as pd
import pytest

from prioritizer.scoring import Thresholds, annual_cost, feasibility_score, quadrant, report, score

ROW = pd.Series({
    "hours_per_week": 10, "people": 2, "hourly_cost": 50, "error_cost_per_month": 100,
    "data_readiness": 5, "standardisation": 5, "risk_if_wrong": 1,
})


def test_annual_cost():
    assert annual_cost(ROW) == 10 * 2 * 50 * 48 + 1200


def test_feasibility_bounds():
    assert feasibility_score(ROW) == 100
    worst = ROW.copy()
    worst[["data_readiness", "standardisation", "risk_if_wrong"]] = [1, 1, 5]
    assert feasibility_score(worst) == 0


def test_quadrants():
    t = Thresholds(impact=50, feasibility=60)
    assert quadrant(80, 80, t) == "Quick win"
    assert quadrant(80, 20, t) == "Strategic bet"
    assert quadrant(20, 80, t) == "Low-hanging fruit"
    assert quadrant(20, 20, t) == "Deprioritise"


def test_sample_scores_and_report():
    scored = score(pd.read_csv("data/sample_processes.csv"))
    assert scored["impact_score"].max() == 100
    assert scored["rank_score"].is_monotonic_decreasing
    assert "Quick win" in set(scored["priority"])
    assert "# AI use-case prioritisation: Test Co" in report(scored, "Test Co")


def test_unknown_pattern_raises():
    df = pd.read_csv("data/sample_processes.csv").head(1)
    df.loc[0, "ai_pattern"] = "Magic"
    with pytest.raises(ValueError):
        score(df)
