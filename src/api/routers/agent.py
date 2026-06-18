"""Stock agent API."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agent import AgentMode, StockScanner, StockTarget


router = APIRouter(prefix="/agent", tags=["Stock Agent"])


class AgentScanRequest(BaseModel):
    symbols: list[str] = Field(..., description="Targets like A:600036, HK:01347, US:AAPL")
    mode: Literal["position", "trading"] = "trading"
    days: int = Field(180, ge=80, le=800)


@router.post("/scan")
def scan_stocks(req: AgentScanRequest):
    try:
        targets = [StockTarget.parse(symbol) for symbol in req.symbols]
        result = StockScanner().scan(targets, mode=AgentMode(req.mode), days=req.days)
        return result.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
