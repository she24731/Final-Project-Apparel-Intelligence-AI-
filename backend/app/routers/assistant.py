from __future__ import annotations

from fastapi import APIRouter

from app.schemas.assistant import AssistantTurnRequest, AssistantTurnResponse
from app.services.assistant_turn import run_assistant_turn

router = APIRouter(tags=["assistant"])


@router.post("/assistant/turn", response_model=AssistantTurnResponse)
async def assistant_turn(body: AssistantTurnRequest) -> AssistantTurnResponse:
    return await run_assistant_turn(body.message, body.context)
