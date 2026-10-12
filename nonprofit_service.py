"""HTTP entry point for the nonprofit automation loop."""

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from openai import APIConnectionError, APIStatusError
from pydantic import BaseModel, Field

from nonprofit_agent import NonprofitLedger, make_infrai_client, run_nonprofit_loop


class AutomationRequest(BaseModel):
    instruction: str = Field(min_length=1)


class AutomationResponse(BaseModel):
    summary: str
    actions: list[dict[str, Any]]


service = FastAPI(title="Nonprofit tool-calling service")
ledger = NonprofitLedger()


@service.post("/automations/run", response_model=AutomationResponse)
def run_automation(request: AutomationRequest) -> AutomationResponse:
    client = make_infrai_client(os.environ["INFRAI_API_KEY"])
    try:
        result = run_nonprofit_loop(client, request.instruction, ledger)
    except APIStatusError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=status, detail="The model request was rejected") from exc
    except APIConnectionError as exc:
        raise HTTPException(status_code=502, detail="The model service could not be reached") from exc
    return AutomationResponse.model_validate(result)
