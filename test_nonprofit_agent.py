"""Focused tests for the action decision and idempotent execution boundary."""

from types import SimpleNamespace

from nonprofit_agent import NonprofitLedger, run_nonprofit_loop


def tool_call(call_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name="send_donor_receipt",
            arguments=(
                '{"action_id":"receipt-42","donor_name":"Avery Chen",'
                '"donor_email":"avery@example.org","amount_cents":7500,'
                '"donation_date":"2026-09-25"}'
            ),
        ),
    )


class ScriptedCompletions:
    def __init__(self) -> None:
        self.responses = [
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[tool_call("call-1"), tool_call("call-2")]))]
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="Receipt sent to Avery.", tool_calls=None))]
            ),
        ]

    def create(self, **request: object) -> SimpleNamespace:
        assert request["model"] == "auto"
        return self.responses.pop(0)


def test_duplicate_receipt_tool_calls_apply_the_donation_once() -> None:
    ledger = NonprofitLedger()
    client = SimpleNamespace(chat=SimpleNamespace(completions=ScriptedCompletions()))

    result = run_nonprofit_loop(client, "Send Avery's receipt.", ledger)

    assert result["actions"] == [
        {
            "status": "receipt_sent",
            "action_id": "receipt-42",
            "recipient": "avery@example.org",
            "amount_cents": 7500,
        }
    ]
    assert ledger.execution_count["receipt-42"] == 1
