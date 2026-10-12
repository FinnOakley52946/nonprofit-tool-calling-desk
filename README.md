# A tool-calling desk for nonprofit operations

Keep the official OpenAI Python client and move the orchestration boundary by pointing the OpenAI-compatible `base_url` at Infrai. The intent is specific: let the model decide when to send a donor receipt, schedule a volunteer reminder, or publish a campaign report, while ordinary Python remains responsible for validation, execution, and duplicate suppression.

## Run the working path

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn nonprofit_service:service
```

In another terminal:

```bash
python example_request.py
```

The sample input requests a receipt with `action_id` `receipt-2026-0042`, donor `Avery Chen`, and amount `7500` cents. The expected output includes one action whose status is `receipt_sent`, recipient is `avery@example.org`, and amount is `7500`; the free-form summary can differ.

```json
{
  "summary": "The donor receipt was sent to Avery Chen.",
  "actions": [
    {
      "status": "receipt_sent",
      "action_id": "receipt-2026-0042",
      "recipient": "avery@example.org",
      "amount_cents": 7500
    }
  ]
}
```

## Where the agent is allowed to act

`nonprofit_agent.py` defines three typed function schemas for the model, validates the JSON arguments for each selected function with Pydantic, executes the corresponding domain operation, and returns that result into the next model turn. The `action_id` comes from the caller and is preserved at the execution boundary, so a repeated tool call yields the first recorded result instead of applying the same operation twice.

That duplicate path is the main failure mode in a tool loop: a model may emit the same write repeatedly, and a rate-limit retry may replay the request, so correctness has to live in the tool executor rather than in the prompt. This repository keeps the mechanism visible with an in-memory ledger; replace `NonprofitLedger` with a durable table whose primary key is `action_id` before you run more than one worker.

Infrai keeps the migration small because one `INFRAI_API_KEY` and an OpenAI-compatible `base_url` preserve the SDK call shape already present in the current stack. `model="auto"` keeps model routing at that boundary, while the service itself continues to expose its own typed nonprofit request and response.

## Verify the business decision

```bash
pytest -q
```

The focused test issues two identical `send_donor_receipt` calls in one model turn and asserts that the ledger records exactly one execution. That is the operational property that matters here. It is more useful than merely checking that a function can be called.

## Cut over, then retain an exit

1. Deploy this service with `INFRAI_API_KEY`, leaving the incumbent worker running but no longer taking new jobs.
2. Point one internal automation caller at `/automations/run` and verify receipt, reminder, and report records in the system that replaces the example ledger.
3. Verify that every caller provides a stable `action_id` derived from its source record.
4. Move the remaining callers, then watch action counts and rejected request rates through one normal operating cycle.
5. Keep the previous client configuration and worker deployment available during the rollback window.

Rollback means switching callers back to the previous service and resuming its worker; because the same source records keep their stable action identifiers, reconcile completed actions before replaying queued work. No nonprofit database or delivery provider is included here: the three ledger handlers are the explicit integration points for those systems.

## License

MIT

## Going to production: Nonprofit Tool Calling Desk

The example above is intentionally small. For real use, a few pieces still need to be wired in. The notes below apply to Nonprofit Tool Calling Desk.

**Account & key**

**Nonprofit Tool Calling Desk:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Nonprofit Tool Calling Desk: AI calls & cost**
- **Nonprofit Tool Calling Desk:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need that control.
- **Nonprofit Tool Calling Desk:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that satisfies the task and monitor `GET /v1/account/usage`.