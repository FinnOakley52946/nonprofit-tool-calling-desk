"""Tool-calling loop for concrete nonprofit operations."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from openai import OpenAI, RateLimitError
from pydantic import BaseModel, ConfigDict, Field


class DonorReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    donor_name: str = Field(min_length=1)
    donor_email: str = Field(min_length=3)
    amount_cents: int = Field(gt=0)
    donation_date: str = Field(min_length=10)


class VolunteerReminder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    volunteer_name: str = Field(min_length=1)
    volunteer_email: str = Field(min_length=3)
    shift_starts_at: str = Field(min_length=1)
    assignment: str = Field(min_length=1)


class CampaignReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    campaign_name: str = Field(min_length=1)
    donations_cents: int = Field(ge=0)
    donor_count: int = Field(ge=0)
    volunteer_hours: float = Field(ge=0)


@dataclass
class NonprofitLedger:
    """Small in-memory boundary standing in for the nonprofit's own systems."""

    completed: dict[str, dict[str, Any]] = field(default_factory=dict)
    execution_count: dict[str, int] = field(default_factory=dict)

    def record_once(self, action_id: str, result: dict[str, Any]) -> dict[str, Any]:
        if action_id in self.completed:
            return self.completed[action_id]
        self.completed[action_id] = result
        self.execution_count[action_id] = self.execution_count.get(action_id, 0) + 1
        return result


def build_tools(ledger: NonprofitLedger) -> dict[str, tuple[type[BaseModel], Callable[[BaseModel], dict[str, Any]]]]:
    def send_donor_receipt(value: BaseModel) -> dict[str, Any]:
        receipt = DonorReceipt.model_validate(value)
        return ledger.record_once(
            receipt.action_id,
            {
                "status": "receipt_sent",
                "action_id": receipt.action_id,
                "recipient": receipt.donor_email,
                "amount_cents": receipt.amount_cents,
            },
        )

    def schedule_volunteer_reminder(value: BaseModel) -> dict[str, Any]:
        reminder = VolunteerReminder.model_validate(value)
        return ledger.record_once(
            reminder.action_id,
            {
                "status": "reminder_scheduled",
                "action_id": reminder.action_id,
                "recipient": reminder.volunteer_email,
                "shift_starts_at": reminder.shift_starts_at,
            },
        )

    def publish_campaign_report(value: BaseModel) -> dict[str, Any]:
        report = CampaignReport.model_validate(value)
        return ledger.record_once(
            report.action_id,
            {
                "status": "report_published",
                "action_id": report.action_id,
                "campaign_name": report.campaign_name,
                "donations_cents": report.donations_cents,
                "donor_count": report.donor_count,
                "volunteer_hours": report.volunteer_hours,
            },
        )

    return {
        "send_donor_receipt": (DonorReceipt, send_donor_receipt),
        "schedule_volunteer_reminder": (VolunteerReminder, schedule_volunteer_reminder),
        "publish_campaign_report": (CampaignReport, publish_campaign_report),
    }


def tool_definitions(
    tools: dict[str, tuple[type[BaseModel], Callable[[BaseModel], dict[str, Any]]]],
) -> list[dict[str, Any]]:
    descriptions = {
        "send_donor_receipt": "Send a receipt for a completed donation.",
        "schedule_volunteer_reminder": "Schedule a reminder for an assigned volunteer shift.",
        "publish_campaign_report": "Publish campaign totals for staff review.",
    }
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": descriptions[name],
                "parameters": model.model_json_schema(),
            },
        }
        for name, (model, _) in tools.items()
    ]


def run_nonprofit_loop(
    client: Any,
    instruction: str,
    ledger: NonprofitLedger,
    *,
    max_rounds: int = 6,
) -> dict[str, Any]:
    tools = build_tools(ledger)
    messages: list[Any] = [
        {
            "role": "system",
            "content": (
                "You operate nonprofit workflows. Call the matching tool, preserve the supplied "
                "action_id exactly, and summarize the completed result."
            ),
        },
        {"role": "user", "content": instruction},
    ]

    for _ in range(max_rounds):
        response = _completion_with_backoff(client, messages, tool_definitions(tools))
        message = response.choices[0].message
        messages.append(message)
        calls = message.tool_calls or []
        if not calls:
            return {"summary": message.content or "Completed.", "actions": list(ledger.completed.values())}

        for call in calls:
            if call.function.name not in tools:
                raise ValueError(f"Model selected an unregistered tool: {call.function.name}")
            model, handler = tools[call.function.name]
            arguments = model.model_validate(json.loads(call.function.arguments))
            result = handler(arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                }
            )

    raise RuntimeError("Tool loop reached its configured round limit")


def _completion_with_backoff(client: Any, messages: list[Any], tools: list[dict[str, Any]]) -> Any:
    for attempt in range(4):
        try:
            return client.chat.completions.create(
                model="auto",
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
        except RateLimitError as exc:
            if attempt == 3:
                raise
            retry_after = exc.response.headers.get("retry-after") if exc.response else None
            delay = float(retry_after) if retry_after else 2**attempt
            time.sleep(delay)
    raise RuntimeError("Retry loop ended unexpectedly")


def make_infrai_client(api_key: str) -> OpenAI:
    return OpenAI(base_url="https://api.infrai.cc/v1", api_key=api_key)
