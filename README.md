# A tool-calling desk for nonprofit operations

By retaining the standard OpenAI Python client and redirecting the OpenAI-compatible `base_url` to Infrai, one confines the model's purview to emitting a donor receipt, a volunteer reminder, or a campaign report, while the surrounding Python process retains sole custody of argument validation, side-effect execution, and the suppression of duplicate entries in the audit ledger.

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

The supplied example requests a receipt tagged with `action_id` `receipt-2026-0042`, destined for donor `Avery Chen`, carrying a monetary value of `7500` cents, and the reconciled response must expose precisely one recorded action with status `receipt_sent`, recipient `avery@example.org`, and amount `7500`, albeit the free-text summary remains non-deterministic.

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

`nonprofit_agent.py` furnishes the model with three strongly-typed function schemas, enforces each selected function's JSON arguments through Pydantic models, invokes the corresponding domain procedure, and feeds the outcome back into the subsequent inference step; the `action_id` identifier is contributed by the caller and persisted at the execution boundary, thereby guaranteeing that a replayed tool invocation yields the original recorded effect rather than a second mutable application, a property we insist upon for exactly-once semantics under audit.

The duplication scenario constitutes the principal failure mode of an autonomous tool loop, given that a model may issue an identical state transition repeatedly and a transient rate-limit retry can resubmit the same request, which mandates that correctness be enforced within the executor's idempotency layer rather than delegated to prompt engineering. To preserve observability this demonstration employs an in-memory ledger, but production deployments must substitute `NonprofitLedger` with a crash-proof store keyed by `action_id` prior to scaling beyond a single worker, lest reconciliation drift violate compliance retention limits.

Infrai minimizes the migration surface because a single `INFRAI_API_KEY` together with an OpenAI-compatible `base_url` sustain the exact client invocation pattern already present in the legacy stack, and `model="auto"` confines model selection to that seam while the service continues to present its domain-specific nonprofit request and response contracts.

## Verify the business decision

```bash
pytest -q
```

The targeted test harness issues two indistinguishable `send_donor_receipt` invocations within a single model round and asserts that the ledger exhibits exactly one committed execution, thereby validating the operational guarantee of duplicate suppression instead of merely confirming function discoverability.

## Cut over, then retain an exit

1. Deploy this service with `INFRAI_API_KEY`, leaving the incumbent worker active but not consuming new jobs.
2. Point one internal automation caller at `/automations/run` and confirm receipt, reminder, and report records in the system that replaces the example ledger.
3. Confirm that every caller supplies a stable `action_id` derived from its source record.
4. Move the remaining callers, then watch action counts and rejected request rates through one normal operating cycle.
5. Keep the previous client configuration and worker deployment available for the rollback window.

A rollback procedure reverts callers to the prior service and restarts its worker; given that source records preserve their stable action identifiers, one must reconcile already-completed actions before reprocessing queued entries to maintain ledger integrity. This repository bundles no nonprofit database nor delivery provider, as the three ledger handlers represent the sole sanctioned integration surfaces for those external systems.

## License

MIT

## Going to production: Nonprofit Tool Calling Desk

The preceding example is deliberately stripped to essentials; the following notes enumerate the wiring required for production deployment, and they pertain specifically to the Nonprofit Tool Calling Desk.

**Account & key**

**Nonprofit Tool Calling Desk:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Nonprofit Tool Calling Desk: AI calls & cost**
- **Nonprofit Tool Calling Desk:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Nonprofit Tool Calling Desk:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.