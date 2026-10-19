# Project Mesh finding-verification lifecycle

## Trust model discovered

Jarvis is a local, single-owner CLI application. The current application has no login, authenticated reviewer identity, session identity, or reviewer credential. A string such as `owner`, `guardian`, or `verified_by` supplied by a caller or model is not proof of identity. The configured local model is not an independent reviewer, and model-generated evidence is not independent verification.

## Implemented lifecycle

- **`unverified`** is the only effective finding trust state.
- Finding creation ignores model-supplied status, approval, and reviewer fields. New rows are explicitly written as `unverified` when the schema supports the column.
- A stored legacy value such as `verified`, `approved`, an unknown string, or a malformed value is not accepted as a trust decision. Serialized context reports effective `status: unverified` and preserves the raw database value separately as `stored_status_untrusted`.
- Requests to move a finding to `verified` or `rejected` go through `ProjectMesh.request_finding_transition()`. The method validates the ID, requested state, rationale, and evidence references, then records a denial and raises `PermissionError` because the application cannot authenticate a reviewer. It never changes the finding state.
- A denied attempt is an audit record of a request, not an accepted decision. Its `actor_claim` is caller-supplied and `actor_authenticated` is always false.
- The audit entry records the finding ID, timestamp, previous effective state, requested state, untrusted actor claim, rationale, evidence references, validation scope, and `denied_no_authenticated_reviewer` outcome.

No `verified` or `rejected` transition is currently authorized. This is deliberate: a real authenticated reviewer mechanism must exist before the application can claim such a decision. A future implementation may add a verified/rejected state only alongside authentication, authorization, evidence validation rules, and a corresponding audit test suite.

## Persistence and compatibility

Initialization adds `mesh_finding_verification_audit` with `CREATE TABLE IF NOT EXISTS`. It does not rewrite or delete findings/events and does not backfill actors, timestamps, evidence, or audit history. Existing findings remain intact. Old stored statuses are preserved as raw data but are never promoted into effective trust. Legacy finding tables without a `status` column remain writable through the old insert shape and are serialized as effectively unverified.

## Integrity limits

The audit table is ordinary SQLite storage in the same writable application database. The code prevents the normal finding-creation API from recording a successful transition, but it cannot resist a local process or person with direct database write access, arbitrary Python execution, or the ability to modify the application code/database. There is no cryptographic signature, append-only external log, immutable storage, or authenticated human identity. An audit row proves only that the database currently contains a recorded request; it does not prove who submitted it or that the finding is true.

All Mesh records and audit text remain untrusted evidence in prompt construction. The presence of a status, rationale, or evidence reference is never privileged policy or proof.
