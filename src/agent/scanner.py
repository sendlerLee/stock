"""
Batch stock scanner and report generation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from src.agent.providers import StockTarget
from src.agent.snapshot import SnapshotBuilder
from src.agent.stock_agent import ActionState, AgentDecision, AgentMode, AgentVerdict, StockAgent


DIMENSION_LABELS = {
    "trend": "趋势结构",
    "flow": "资金/量能",
    "fundamental": "基本面",
    "valuation": "估值/分红",
    "sector": "行业/题材",
    "catalyst": "催化剂",
}

ACTION_STATE_LABELS = {
    ActionState.BUY_NOW: "可以买入/分批建仓",
    ActionState.PROBE: "小仓试错",
    ActionState.WAIT_PULLBACK: "等待回踩",
    ActionState.WAIT_BREAKOUT: "等待突破",
    ActionState.HOLD_WATCH: "持有观察",
    ActionState.REDUCE_PROTECT: "减仓/保护",
    ActionState.AVOID: "暂不买入",
}


@dataclass
class ScanResult:
    mode: AgentMode
    decisions: list[AgentDecision]
    errors: list[str]

    @property
    def buy_candidates(self) -> list[AgentDecision]:
        return [d for d in self.decisions if d.verdict == AgentVerdict.BUY_CANDIDATE]

    @property
    def watchlist(self) -> list[AgentDecision]:
        return [d for d in self.decisions if d.verdict in {AgentVerdict.WATCH, AgentVerdict.HOLD}]

    @property
    def risk_list(self) -> list[AgentDecision]:
        return [d for d in self.decisions if d.verdict in {AgentVerdict.REDUCE, AgentVerdict.AVOID}]

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "buy_candidates": [decision_to_dict(d) for d in self.buy_candidates],
            "watchlist": [decision_to_dict(d) for d in self.watchlist],
            "risk_list": [decision_to_dict(d) for d in self.risk_list],
            "errors": self.errors,
        }


class StockScanner:
    def __init__(self, builder: Optional[SnapshotBuilder] = None, agent: Optional[StockAgent] = None):
        self.builder = builder or SnapshotBuilder()
        self.agent = agent or StockAgent()

    def scan(self, targets: list[StockTarget], mode: AgentMode = AgentMode.TRADING, days: int = 180) -> ScanResult:
        decisions = []
        errors = []
        for target in targets:
            try:
                snapshot = self.builder.build(target, days=days)
                decisions.append(self.agent.evaluate(snapshot, mode))
            except Exception as exc:
                errors.append(f"{target.market.value}:{target.symbol}: {exc}")
        decisions = sorted(decisions, key=lambda d: (d.buy_score, -d.sell_score), reverse=True)
        return ScanResult(mode=mode, decisions=decisions, errors=errors)


def decision_to_dict(decision: AgentDecision) -> dict:
    return {
        "symbol": decision.symbol,
        "name": decision.name,
        "mode": decision.mode.value,
        "verdict": decision.verdict.value,
        "action_state": decision.action_state.value,
        "status": decision_status(decision),
        "buy_score": decision.buy_score,
        "sell_score": decision.sell_score,
        "confidence": decision.confidence,
        "risks": asdict(decision.risks),
        "evidence": decision.evidence,
        "action": decision.action,
        "dimensions": [factor_to_dict(f) for f in decision.factors],
        "factors": [asdict(f) for f in decision.factors],
    }


def format_report(result: ScanResult, limit: int = 10) -> str:
    lines = [f"Stock Agent Report ({result.mode.value})"]
    lines.append("=" * 32)
    lines.extend(_format_bucket("Buy Candidates", result.buy_candidates[:limit]))
    lines.extend(_format_bucket("Watchlist", result.watchlist[:limit]))
    lines.extend(_format_bucket("Risk / Avoid", result.risk_list[:limit]))
    if result.errors:
        lines.append("")
        lines.append("Errors")
        lines.extend(f"- {err}" for err in result.errors)
    return "\n".join(lines)


def _format_bucket(title: str, decisions: list[AgentDecision]) -> list[str]:
    lines = ["", title]
    if not decisions:
        lines.append("- none")
        return lines
    for d in decisions:
        lines.append(
            f"- {d.symbol} {d.name}: 状态={decision_status(d)} "
            f"verdict={d.verdict.value} buy={d.buy_score:.1f} sell={d.sell_score:.1f} conf={d.confidence}"
        )
        lines.append(f"  dimensions: {_dimension_line(d)}")
        if d.risks.flags:
            lines.append(f"  risks: {'; '.join(d.risks.flags[:3])}")
        lines.append(f"  action: {d.action}")
    return lines


def decision_status(decision: AgentDecision) -> str:
    return ACTION_STATE_LABELS.get(decision.action_state, decision.action_state.value)


def factor_to_dict(factor) -> dict:
    return {
        "key": factor.name,
        "label": DIMENSION_LABELS.get(factor.name, factor.name),
        "score": round(factor.score, 2),
        "weight": factor.weight,
        "weighted": round(factor.weighted, 2),
        "level": factor_level(factor.score),
        "evidence": factor.evidence,
    }


def factor_level(score: float) -> str:
    if score >= 75:
        return "强"
    if score >= 55:
        return "中性偏强"
    if score >= 35:
        return "中性"
    return "弱"


def _dimension_line(decision: AgentDecision) -> str:
    parts = []
    for factor in decision.factors:
        label = DIMENSION_LABELS.get(factor.name, factor.name)
        parts.append(
            f"{label}={factor_level(factor.score)}({factor.score:.0f}/100,w={factor.weight:.0%}; {factor.evidence})"
        )
    return " | ".join(parts)
