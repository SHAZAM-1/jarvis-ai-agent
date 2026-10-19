# Project Mesh finding-verification lifecycle

## Trust model and meaning of a decision

Jarvis is a local, single-owner CLI application. It has no multi-user account service or operating-system identity broker. A caller-supplied name such as `owner`, `guardian`, or `verified_by`, a model-generated field, a rationale, evidence text, or a stored status is not authentication.

The local reviewer credential authenticates **possession of a passphrase** provisioned by someone at the local interactive terminal. The reviewer label is an audit label bound to that credential; it is not independently verified civil identity. The credential does not establish that a technical claim is true. A `verified` decision means the authenticated credential holder attests that they manually reviewed the cited references for the finding. Jarvis does not independently validate the claim's truth or the quality of the review.

## Provisioning and credential storage

1. Run Jarvis in an interactive terminal and issue `/reviewer-provision` once.
2. Enter an audit label and a passphrase of at least 12 characters twice. Passphrase input is hidden. Mismatched confirmations create no credential.
3. Jarvis stores a random 16-byte salt, a scrypt-derived 32-byte digest, and algorithm/version metadata in a separate `<database-stem>.reviewer.json` file beside the configured SQLite database. It never stores the plaintext passphrase.
4. The standard-library `hashlib.scrypt` scheme uses `N=16384, r=8, p=1`; verification compares digests with `hmac.compare_digest`. There is no default credential, and an existing credential is never silently overwritten.
5. File permissions are restricted to owner read/write where supported. Windows ACL behavior varies and must be checked on the host. Permissions do not protect the credential from a process running as the same OS user.

No passphrase is accepted as a CLI argument or environment variable. `/mesh-review <id> <verified|rejected>` requires an interactive terminal, asks for the passphrase without echo, then asks for a rationale and comma-separated evidence references. Non-interactive invocations fail closed. Each decision authenticates again; no long-lived authenticated session is created.

Use `/reviewer-rotate` to change the passphrase after entering the current one and confirming the new one. Use `/reviewer-revoke` to remove the credential after authenticating with the current passphrase. Revocation leaves existing findings and audit records unchanged and disables future accepted decisions. Incorrect credentials do not change finding state.

### Lost or damaged credential

There is intentionally no unauthenticated recovery command. Stop Jarvis, make a backup of the database, and use the local OS account's file-management access to move the credential file out of the way; then restart Jarvis and explicitly run `/reviewer-provision`. This is an OS-level recovery action, not an authenticated review. It does not change finding statuses or create historical accepted decisions. Anyone able to modify the credential file or application files already has local access outside the application's authentication boundary.

## Allowed transitions

- New findings default to `unverified`; model-generated status, approval, or reviewer fields are ignored.
- Only an explicitly authenticated reviewer can transition an effectively `unverified` finding to `verified` or `rejected`.
- A finding already effectively `verified` or `rejected` cannot be transitioned again through this API. A future re-review workflow would need its own explicit state machine.
- Missing, malformed, invalid, or unavailable credentials deny the request. The effective state does not change and the attempt is recorded where the finding exists.
- Existing database values such as `verified`, `approved`, unknown strings, and malformed legacy values remain untrusted unless the status matches an explicit accepted audit decision produced by the application.
- The only transition boundary is `ProjectMesh.request_finding_transition()`. Caller-supplied `actor_claim` and `actor_authenticated` values do not authorize the operation; the authenticated reviewer label comes from the credential verifier.

The rationale and evidence references are bounded, redacted, and recorded as review context—not as proof. The reviewer is responsible for determining whether the references actually support the claim.

## Audit migration and integrity

On opening an SEC-07 database, Jarvis transactionally migrates the denied-only audit schema to include the authenticated reviewer label and accepted outcomes. Existing row IDs, finding associations, timestamps, previous/requested states, actor claims, rationale, evidence references, validation scope, and denial outcomes are copied. Historical authentication flags are reset to false and reviewer identity is null; no prior denial is reclassified as accepted. The migration is idempotent and the legacy finding-status migration only adds a default-`unverified` column where absent.

New records distinguish `denied_no_authenticated_reviewer`, `denied_invalid_credential`, `accepted_verified`, and `accepted_rejected`. Accepted entries include the authenticated reviewer label, previous and requested states, decision timestamp, rationale, evidence references, validation scope, and authenticated flag. The SQLite status update and accepted audit entry are written in the same transaction.

The audit database is ordinary writable SQLite storage. It is not cryptographically signed, immutable, or tamper-proof. A person or process with direct database write access, access to modify the credential file, the same OS user's privileges, arbitrary Python execution, or the ability to alter application code can bypass or alter these controls. No protection against privileged local tampering is claimed. The audit trail records the application's decision path; it does not prove who physically used the credential, that evidence is authentic, or that the finding is true.

All Mesh findings and audit records remain untrusted evidence in model prompts, never privileged instructions. Even an accepted review does not convert repository content into system policy.
