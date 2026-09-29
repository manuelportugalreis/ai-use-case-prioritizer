"""Scoring framework for AI use cases.

Value: how much the process costs today, times the share an AI solution could realistically
take over (depends on the type of AI task).
Feasibility: is there data, is the process standardised, and how bad is a mistake?
Every assumption lives in the dictionaries below so a consultant can change them with the client.
"""
from dataclasses import dataclass

import pandas as pd

WORKING_WEEKS_PER_YEAR = 48

# Share of the process cost an AI solution could take over, by type of task (assumption).
AUTOMATION_POTENTIAL = {
    "Document extraction": 0.60,
    "Classification & routing": 0.50,
    "Q&A over documents": 0.40,
    "Drafting": 0.35,
    "Forecasting": 0.25,
}

# One-off cost to build and roll out a first version, in USD (assumption).
IMPLEMENTATION_COST = {
    "Document extraction": 25_000,
    "Classification & routing": 20_000,
    "Q&A over documents": 30_000,
    "Drafting": 10_000,
    "Forecasting": 40_000,
}

FEASIBILITY_WEIGHTS = {"data_readiness": 0.40, "standardisation": 0.35, "low_risk": 0.25}


@dataclass(frozen=True)
class Thresholds:
    impact: float = 50.0
    feasibility: float = 60.0


def annual_cost(row: pd.Series) -> float:
    labour = row["hours_per_week"] * row["people"] * row["hourly_cost"] * WORKING_WEEKS_PER_YEAR
    return labour + row["error_cost_per_month"] * 12


def feasibility_score(row: pd.Series) -> float:
    """0-100. Inputs are 1-5 ratings; risk is inverted so that low risk scores high."""
    low_risk = 6 - row["risk_if_wrong"]
    weighted = (
        FEASIBILITY_WEIGHTS["data_readiness"] * row["data_readiness"]
        + FEASIBILITY_WEIGHTS["standardisation"] * row["standardisation"]
        + FEASIBILITY_WEIGHTS["low_risk"] * low_risk
    )
    return round((weighted - 1) / 4 * 100, 1)


def quadrant(impact: float, feasibility: float, t: Thresholds) -> str:
    if impact >= t.impact and feasibility >= t.feasibility:
        return "Quick win"
    if impact >= t.impact:
        return "Strategic bet"
    if feasibility >= t.feasibility:
        return "Low-hanging fruit"
    return "Deprioritise"


def score(processes: pd.DataFrame, thresholds: Thresholds = Thresholds()) -> pd.DataFrame:
    df = processes.copy()
    unknown = set(df["ai_pattern"]) - set(AUTOMATION_POTENTIAL)
    if unknown:
        raise ValueError(f"Unknown AI pattern(s): {sorted(unknown)}")

    df["annual_cost"] = df.apply(annual_cost, axis=1)
    df["annual_value"] = df["annual_cost"] * df["ai_pattern"].map(AUTOMATION_POTENTIAL)
    df["implementation_cost"] = df["ai_pattern"].map(IMPLEMENTATION_COST)
    df["payback_months"] = (df["implementation_cost"] / (df["annual_value"] / 12)).round(1)
    df["impact_score"] = (df["annual_value"] / df["annual_value"].max() * 100).round(1)
    df["feasibility_score"] = df.apply(feasibility_score, axis=1)
    df["priority"] = [quadrant(i, f, thresholds) for i, f in zip(df["impact_score"], df["feasibility_score"])]
    df["rank_score"] = (0.6 * df["impact_score"] + 0.4 * df["feasibility_score"]).round(1)
    return df.sort_values("rank_score", ascending=False).reset_index(drop=True)


def report(scored: pd.DataFrame, company: str) -> str:
    """A short Markdown report a consultant could send after the workshop."""
    lines = [f"# AI use-case prioritisation: {company}", ""]
    total = scored["annual_value"].sum()
    wins = scored[scored["priority"] == "Quick win"]
    lines += [
        f"We assessed **{len(scored)} processes**. Together they represent an estimated "
        f"**${total:,.0f} per year** of addressable value.",
        "",
        f"**Recommended starting point ({len(wins)} quick wins):**",
        "",
    ]
    for _, r in wins.iterrows():
        lines.append(
            f"- **{r['process']}** ({r['department']}, {r['ai_pattern'].lower()}): "
            f"~${r['annual_value']:,.0f}/year, payback ~{r['payback_months']:.0f} months."
        )
    lines += ["", "| Rank | Process | Priority | Value/yr | Feasibility | Payback (months) |", "|---|---|---|---|---|---|"]
    for i, r in scored.iterrows():
        lines.append(
            f"| {i + 1} | {r['process']} | {r['priority']} | ${r['annual_value']:,.0f} | "
            f"{r['feasibility_score']:.0f}/100 | {r['payback_months']:.0f} |"
        )
    lines += ["", "_Estimates are based on the stated assumptions and must be validated with process owners._"]
    return "\n".join(lines)
