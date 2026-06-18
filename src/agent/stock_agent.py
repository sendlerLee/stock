"""
Stock agent scoring layer.

The agent turns normalized market, technical, fundamental, and flow inputs into
an explainable buy/watch/sell/avoid verdict. It is deliberately pure Python so
data fetchers can evolve independently from the decision logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AgentMode(str, Enum):
    """Decision style for scoring."""

    POSITION = "position"  # mid-term allocation / income / value
    TRADING = "trading"    # short-term trend / catalyst / flow


class AgentVerdict(str, Enum):
    BUY_CANDIDATE = "buy_candidate"
    WATCH = "watch"
    HOLD = "hold"
    REDUCE = "reduce"
    AVOID = "avoid"


class ActionState(str, Enum):
    """User-facing execution state.

    This is more granular than ``AgentVerdict``. Verdicts keep compatibility
    for buckets, while action states say what to actually do next.
    """

    BUY_NOW = "buy_now"
    PROBE = "probe"
    WAIT_PULLBACK = "wait_pullback"
    WAIT_BREAKOUT = "wait_breakout"
    HOLD_WATCH = "hold_watch"
    REDUCE_PROTECT = "reduce_protect"
    AVOID = "avoid"


@dataclass(frozen=True)
class FactorScore:
    name: str
    score: float
    weight: float
    evidence: str

    @property
    def weighted(self) -> float:
        return self.score * self.weight


@dataclass
class RiskProfile:
    score: float = 0.0
    flags: list[str] = field(default_factory=list)


@dataclass
class StockSnapshot:
    symbol: str
    name: str = ""
    market: str = ""
    price: Optional[float] = None
    change_pct: Optional[float] = None
    turnover_pct: Optional[float] = None
    amount: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    dividend_yield: Optional[float] = None
    roe: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None
    rsi14: Optional[float] = None
    volume_ratio: Optional[float] = None
    flow_5d: Optional[float] = None
    flow_20d: Optional[float] = None
    flow_60d: Optional[float] = None
    sector_change_pct: Optional[float] = None
    catalyst_score: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentDecision:
    symbol: str
    name: str
    mode: AgentMode
    verdict: AgentVerdict
    buy_score: float
    sell_score: float
    confidence: str
    factors: list[FactorScore]
    risks: RiskProfile
    evidence: list[str]
    action: str
    action_state: ActionState


class StockAgent:
    """Explainable stock selection agent."""

    def evaluate(self, snapshot: StockSnapshot, mode: AgentMode = AgentMode.TRADING) -> AgentDecision:
        factors = self._score_factors(snapshot, mode)
        risks = self._score_risks(snapshot, mode)
        gross_buy_score = sum(f.weighted for f in factors)
        buy_score = round(gross_buy_score - risks.score, 2)
        sell_score = round(self._sell_score(snapshot, risks), 2)
        verdict = self._verdict(gross_buy_score, buy_score, sell_score, risks, mode)
        action_state = self._action_state(snapshot, factors, verdict, buy_score, sell_score, risks, mode)
        confidence = self._confidence(snapshot, factors, risks)
        evidence = self._evidence(snapshot, factors, risks)
        action = self._action_text(action_state, mode)
        return AgentDecision(
            symbol=snapshot.symbol,
            name=snapshot.name,
            mode=mode,
            verdict=verdict,
            buy_score=buy_score,
            sell_score=sell_score,
            confidence=confidence,
            factors=factors,
            risks=risks,
            evidence=evidence,
            action=action,
            action_state=action_state,
        )

    def rank(self, snapshots: list[StockSnapshot], mode: AgentMode = AgentMode.TRADING) -> list[AgentDecision]:
        decisions = [self.evaluate(snapshot, mode) for snapshot in snapshots]
        return sorted(decisions, key=lambda item: (item.buy_score, -item.sell_score), reverse=True)

    def _score_factors(self, s: StockSnapshot, mode: AgentMode) -> list[FactorScore]:
        if mode == AgentMode.POSITION:
            weights = {
                "trend": 0.15,
                "flow": 0.15,
                "fundamental": 0.25,
                "valuation": 0.25,
                "sector": 0.10,
                "catalyst": 0.10,
            }
        else:
            weights = {
                "trend": 0.30,
                "flow": 0.25,
                "fundamental": 0.10,
                "valuation": 0.10,
                "sector": 0.15,
                "catalyst": 0.10,
            }

        return [
            FactorScore("trend", self._trend_score(s), weights["trend"], self._trend_evidence(s)),
            FactorScore("flow", self._flow_score(s), weights["flow"], self._flow_evidence(s)),
            FactorScore("fundamental", self._fundamental_score(s), weights["fundamental"], self._fundamental_evidence(s)),
            FactorScore("valuation", self._valuation_score(s, mode), weights["valuation"], self._valuation_evidence(s)),
            FactorScore("sector", self._sector_score(s), weights["sector"], self._sector_evidence(s)),
            FactorScore("catalyst", self._catalyst_score(s), weights["catalyst"], self._catalyst_evidence(s)),
        ]

    def _trend_score(self, s: StockSnapshot) -> float:
        score = 0.0
        if s.price and s.ma20:
            score += 35 if s.price > s.ma20 else 5
        if s.price and s.ma60:
            score += 35 if s.price > s.ma60 else 5
        if s.ma20 and s.ma60:
            score += 20 if s.ma20 > s.ma60 else 0
        if s.rsi14 is not None:
            if 45 <= s.rsi14 <= 68:
                score += 10
            elif 68 < s.rsi14 <= 78:
                score += 5
            elif s.rsi14 > 85:
                score -= 15
        return clamp(score)

    def _flow_score(self, s: StockSnapshot) -> float:
        if s.flow_5d is None and s.flow_20d is None and s.flow_60d is None:
            score = 45.0
            if s.volume_ratio is not None:
                if 1.2 <= s.volume_ratio <= 3.0:
                    score += 10
                elif s.volume_ratio > 5:
                    score -= 10
            return clamp(score)
        score = 40 if is_positive(s.flow_5d) else 0
        score += 35 if is_positive(s.flow_20d) else 0
        score += 15 if is_positive(s.flow_60d) else 0
        if s.volume_ratio is not None:
            if 1.2 <= s.volume_ratio <= 3.0:
                score += 10
            elif s.volume_ratio > 5:
                score -= 10
        return clamp(score)

    def _fundamental_score(self, s: StockSnapshot) -> float:
        score = 0.0
        if s.roe is not None:
            if s.roe >= 15:
                score += 35
            elif s.roe >= 8:
                score += 25
            elif s.roe >= 3:
                score += 10
        if s.profit_growth is not None:
            if s.profit_growth >= 20:
                score += 30
            elif s.profit_growth >= 5:
                score += 20
            elif s.profit_growth >= 0:
                score += 10
            else:
                score -= 15
        if s.revenue_growth is not None:
            if s.revenue_growth >= 15:
                score += 25
            elif s.revenue_growth >= 3:
                score += 15
            elif s.revenue_growth < 0:
                score -= 10
        if s.dividend_yield is not None and s.dividend_yield >= 4:
            score += 10
        return clamp(score)

    def _valuation_score(self, s: StockSnapshot, mode: AgentMode) -> float:
        score = 0.0
        if s.pe_ttm is not None:
            if 0 < s.pe_ttm <= 12:
                score += 40
            elif s.pe_ttm <= 25:
                score += 28
            elif s.pe_ttm <= 50:
                score += 12
            elif mode == AgentMode.TRADING and s.pe_ttm <= 120:
                score += 5
            else:
                score -= 20
        if s.pb is not None:
            if 0 < s.pb <= 1:
                score += 30
            elif s.pb <= 3:
                score += 18
            elif s.pb <= 8:
                score += 5
            else:
                score -= 15
        if s.dividend_yield is not None:
            if s.dividend_yield >= 6:
                score += 30
            elif s.dividend_yield >= 3:
                score += 18
        return clamp(score)

    def _sector_score(self, s: StockSnapshot) -> float:
        if s.sector_change_pct is None:
            return 50.0 if s.tags else 35.0
        if s.sector_change_pct >= 3:
            return 90.0
        if s.sector_change_pct >= 1:
            return 70.0
        if s.sector_change_pct >= -1:
            return 45.0
        return 20.0

    def _catalyst_score(self, s: StockSnapshot) -> float:
        if s.catalyst_score is not None:
            return clamp(s.catalyst_score)
        score = 0.0
        tag_text = " ".join(s.tags + s.notes)
        hot_words = ("AI", "半导体", "存储", "国产替代", "高股息", "分红", "回购", "涨价", "订单")
        score += 12 * sum(1 for word in hot_words if word in tag_text)
        return clamp(score)

    def _score_risks(self, s: StockSnapshot, mode: AgentMode) -> RiskProfile:
        risk = RiskProfile()
        if s.pe_ttm is not None and s.pe_ttm > 120:
            risk.score += 15 if mode == AgentMode.TRADING else 25
            risk.flags.append(f"PE TTM very high: {s.pe_ttm:.1f}")
        if s.pb is not None and s.pb > 8:
            risk.score += 12 if mode == AgentMode.TRADING else 18
            risk.flags.append(f"PB very high: {s.pb:.1f}")
        if s.rsi14 is not None and s.rsi14 > 80:
            risk.score += 10
            risk.flags.append(f"RSI overheated: {s.rsi14:.1f}")
        if s.change_pct is not None and s.change_pct > 9:
            risk.score += 8
            risk.flags.append(f"one-day surge: {s.change_pct:.1f}%")
        if is_negative(s.flow_20d) and is_negative(s.flow_60d):
            risk.score += 12
            risk.flags.append("medium-term capital flow is negative")
        if s.amount is not None and s.amount <= 0:
            risk.score += 20
            risk.flags.append("missing or zero turnover")
        return risk

    def _sell_score(self, s: StockSnapshot, risks: RiskProfile) -> float:
        score = risks.score
        if s.price and s.ma20 and s.price < s.ma20:
            score += 20
        if s.price and s.ma60 and s.price < s.ma60:
            score += 25
        if is_negative(s.flow_5d):
            score += 15
        if is_negative(s.flow_20d):
            score += 20
        if s.profit_growth is not None and s.profit_growth < -10:
            score += 20
        return clamp(score)

    def _verdict(
        self,
        gross_buy_score: float,
        buy_score: float,
        sell_score: float,
        risks: RiskProfile,
        mode: AgentMode,
    ) -> AgentVerdict:
        reduce_threshold = 70 if mode == AgentMode.POSITION else 65
        if sell_score >= reduce_threshold:
            return AgentVerdict.REDUCE
        if buy_score >= 70 and sell_score < 45:
            if mode == AgentMode.TRADING and not self._has_trading_confirmation(gross_buy_score):
                return AgentVerdict.WATCH
            return AgentVerdict.BUY_CANDIDATE
        if mode == AgentMode.TRADING and gross_buy_score >= 70 and sell_score < 50:
            return AgentVerdict.WATCH
        if buy_score >= 55:
            return AgentVerdict.WATCH
        if mode == AgentMode.POSITION and buy_score >= 35 and sell_score < reduce_threshold and risks.score < 35:
            return AgentVerdict.WATCH
        if sell_score >= 45 or risks.score >= 35:
            return AgentVerdict.AVOID
        return AgentVerdict.HOLD if mode == AgentMode.POSITION else AgentVerdict.WATCH

    def _has_trading_confirmation(self, gross_buy_score: float) -> bool:
        # Trading candidates must be driven by momentum/flow/sector, not only by valuation.
        return gross_buy_score >= 85

    def _confidence(self, s: StockSnapshot, factors: list[FactorScore], risks: RiskProfile) -> str:
        populated = sum(
            value is not None
            for value in (
                s.price,
                s.ma20,
                s.ma60,
                s.rsi14,
                s.flow_5d,
                s.flow_20d,
                s.pe_ttm,
                s.pb,
                s.roe,
            )
        )
        if populated >= 8 and risks.score < 25:
            return "A"
        if populated >= 6:
            return "B"
        return "C"

    def _evidence(self, s: StockSnapshot, factors: list[FactorScore], risks: RiskProfile) -> list[str]:
        lines = [factor.evidence for factor in factors if factor.evidence]
        lines.extend(risks.flags)
        lines.extend(s.notes[:3])
        return lines

    def _action_state(
        self,
        s: StockSnapshot,
        factors: list[FactorScore],
        verdict: AgentVerdict,
        buy_score: float,
        sell_score: float,
        risks: RiskProfile,
        mode: AgentMode,
    ) -> ActionState:
        factor_map = {factor.name: factor.score for factor in factors}
        trend = factor_map.get("trend", 0.0)
        flow = factor_map.get("flow", 0.0)
        valuation = factor_map.get("valuation", 0.0)
        sector = factor_map.get("sector", 0.0)
        catalyst = factor_map.get("catalyst", 0.0)
        flow_unknown = s.flow_5d is None and s.flow_20d is None and s.flow_60d is None
        below_ma20 = bool(s.price and s.ma20 and s.price < s.ma20)
        extended = bool(s.price and s.ma20 and s.price > s.ma20 * 1.12)
        overheated = bool(s.rsi14 is not None and s.rsi14 >= 70)
        very_risky = risks.score >= 35 or sell_score >= (55 if mode == AgentMode.TRADING else 60)

        if verdict == AgentVerdict.REDUCE:
            return ActionState.REDUCE_PROTECT
        if verdict == AgentVerdict.AVOID and not (mode == AgentMode.TRADING and trend >= 90 and sector >= 80 and sell_score < 50):
            return ActionState.AVOID

        if mode == AgentMode.TRADING:
            if trend >= 85 and sector >= 70 and buy_score >= 38 and sell_score < 35 and not overheated:
                return ActionState.BUY_NOW if flow >= 55 else ActionState.PROBE
            if trend >= 80 and sector >= 60 and sell_score < 45:
                return ActionState.WAIT_PULLBACK if (extended or overheated or flow_unknown) else ActionState.PROBE
            if below_ma20 and sector >= 60:
                return ActionState.WAIT_BREAKOUT
            if trend >= 75 and buy_score >= 32 and sell_score < 45:
                return ActionState.PROBE
            return ActionState.HOLD_WATCH if not very_risky else ActionState.AVOID

        if mode == AgentMode.POSITION:
            if trend >= 75 and valuation >= 45 and buy_score >= 45 and sell_score < 35 and risks.score < 25:
                return ActionState.BUY_NOW
            if trend >= 70 and buy_score >= 30 and sell_score < 45 and risks.score < 35:
                return ActionState.PROBE
            if below_ma20 and valuation >= 55 and sell_score < 55:
                return ActionState.WAIT_BREAKOUT
            if trend >= 80 and buy_score >= 25 and risks.score < 35:
                return ActionState.WAIT_PULLBACK if extended else ActionState.PROBE
            return ActionState.HOLD_WATCH if not very_risky else ActionState.AVOID

        return ActionState.HOLD_WATCH

    def _action_text(self, action_state: ActionState, mode: AgentMode) -> str:
        if action_state == ActionState.BUY_NOW:
            return "Actionable for staged entry under portfolio limits; use predefined stop discipline."
        if action_state == ActionState.PROBE:
            return "Actionable as a small probe position; add only after price/flow confirmation."
        if action_state == ActionState.WAIT_PULLBACK:
            return "Wait for pullback or consolidation before entry; avoid chasing an extended move."
        if action_state == ActionState.WAIT_BREAKOUT:
            return "Wait for a breakout or reclaim of the key moving average before entry."
        if action_state == ActionState.REDUCE_PROTECT:
            return "Reduce or protect existing position; new entries need a fresh setup."
        if action_state == ActionState.AVOID:
            return "Avoid new buys under current evidence."
        return "Hold existing position if it still fits portfolio risk limits."

    def _trend_evidence(self, s: StockSnapshot) -> str:
        return f"trend: price={fmt(s.price)}, ma20={fmt(s.ma20)}, ma60={fmt(s.ma60)}, rsi14={fmt(s.rsi14)}"

    def _flow_evidence(self, s: StockSnapshot) -> str:
        status = "unconfirmed" if s.flow_5d is None and s.flow_20d is None and s.flow_60d is None else "available"
        return f"flow: status={status}, 5d={fmt(s.flow_5d)}, 20d={fmt(s.flow_20d)}, 60d={fmt(s.flow_60d)}, vol_ratio={fmt(s.volume_ratio)}"

    def _fundamental_evidence(self, s: StockSnapshot) -> str:
        return f"fundamental: roe={fmt(s.roe)}, revenue_growth={fmt(s.revenue_growth)}, profit_growth={fmt(s.profit_growth)}"

    def _valuation_evidence(self, s: StockSnapshot) -> str:
        return f"valuation: pe_ttm={fmt(s.pe_ttm)}, pb={fmt(s.pb)}, dividend_yield={fmt(s.dividend_yield)}"

    def _sector_evidence(self, s: StockSnapshot) -> str:
        tags = ", ".join(s.tags[:5]) if s.tags else "-"
        return f"sector: change={fmt(s.sector_change_pct)}%, tags={tags}"

    def _catalyst_evidence(self, s: StockSnapshot) -> str:
        return f"catalyst: score={fmt(s.catalyst_score)}, notes={'; '.join(s.notes[:2]) if s.notes else '-'}"


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


def is_positive(value: Optional[float]) -> bool:
    return value is not None and value > 0


def is_negative(value: Optional[float]) -> bool:
    return value is not None and value < 0


def fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)
