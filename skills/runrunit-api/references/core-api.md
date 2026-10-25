# Core Runrun.it API Contract

Source: official Runrun.it API documentation, inventoried in August 2026; rate-limit, ETag, null-clearing and retry rules updated in October 2026 from official answers by the Runrun.it team (these win over older notes).

## Connection

- Base URL: `https://runrun.it/api/v1.0`.
- Send `App-Key: <app_key>` on every request.
- Send `User-Token: <user_token>` on every request.
- Send `Content-Type: application/json` for JSON bodies.
- `App-Key` identifies the account and cannot be changed through the GUI.
- `User-Token` is unique per user and determines the acting identity.
- Invalid credentials return HTTP `401 Unauthorized`.
- Access is a premium feature on eligible paid accounts.
- Credential UI: **Integration and Apps → API and Webhooks → Open**.
- If the feature is absent, check plan eligibility or contact `help@runrun.it`.

## Data Format

- Responses are valid JSON, except successful no-content responses (`204`).
- Requests should use JSON; many actions also accept form encoding, but JSON is canonical here.
- Dates use ISO 8601.
- In query strings, URL-encode special characters; notably encode timezone `+` rather than sending it literally.
- Do not log or print `App-Key` or `User-Token`.

## Rate Limit

- Maximum: 100 requests per minute **per source IP** (not per App-Key; extra keys do not raise the ceiling).
- Exceeded limit: HTTP `429`.
- `RateLimit-Limit`: configured request limit.
- `RateLimit-Remaining`: requests remaining in the current window.
- `RateLimit-Reset`: date when the limit is restored.
- The documentation instructs waiting one minute before new requests after exhaustion.
- Excessive use can lead to revocation of the offending `App-Key`.
- Retry GET requests only after the reset; never blindly retry mutations because there is no idempotency key.

## Staying Under the Limit

- Cache boards, stages, task types, projects, users and tags with a TTL of minutes.
- Use `ETag` / `If-None-Match` on reads (`--if-none-match` in the script; `304` = cached copy is still valid).
- Filter and paginate `GET /tasks` on the server instead of pulling everything and filtering locally.
- The official MCP (`/mcp`, OAuth) is a conversational-assistant surface; never use it to bypass the REST rate limit.

## Timeouts and Reconciliation

- POSTs have no idempotency key. After a timeout, GET and compare before resending.
- Task create: stamp an own identifier (tag, custom field or `source`) and search for it before recreating.
- Manual work: see `task-collaboration-time.md` for the duplicate check.
- Transitions (move / deliver / play / pause) are convergent: read state, then re-run only if the final state was not reached.

## Pagination

- `page`: page number, starting at 1; an out-of-range value defaults to 1.
- `limit`: items per page; default and maximum are 100.
- `offset`: starting point for retrieval.
- `X-Item-Range`: `items {first_position}-{last_position}/{total}`.
- `Link`: navigation relations `self`, `prev`, `next`, `last`.
- `X-Item-Without-View-Permission`: optional count hidden by permissions.
- Start without pagination parameters or with an explicit bounded `limit`.
- Follow the URL attached to `rel="next"` until absent.
- Accept a next link only when it resolves to HTTPS on host `runrun.it`.
- Bound total pages and total items to avoid accidental full-account extraction.
- Pagination follows the principles of RFC 7233 and RFC 5988.

## Response Handling

- `200`: successful read or update with representation.
- `201`: successful creation with representation.
- `204`: successful operation with no body.
- `401`: credentials are missing or incorrect.
- `429`: rate limit reached; inspect `RateLimit-*` headers.
- Other status codes are not covered by a complete published error taxonomy.
- Sanitize vendor error bodies before presenting them; they may reveal account context.

## Safety Rules

- Read the target resource before changing it.
- Resolve IDs through documented collection routes; do not infer IDs from names.
- Preview method, route, entity ID, and changed fields before writes.
- Require explicit confirmation for delete, deliver, reopen, move, assignment changes, and time-entry mutation.
- After a write, GET the resource again when a readable representation exists.
- No optimistic-concurrency contract for writes (`If-Match`); `ETag` is for read caching only. Serialize writers per task (critical for tags).
- Clear dates by sending the key with `null`; omitting the key leaves the value unchanged.
- Do not assume a missing response body means failure when the documented status is `204`.

## Known Documentation Gaps

- No complete error schema or taxonomy.
- No idempotency key (confirmed): reconcile after timeouts.
- No optimistic-concurrency mechanism for writes.
- No complete endpoint-permission matrix.
- Some parameter tables conflict with examples.
- Plan eligibility prose and pricing presentation can differ; the account UI is the practical entitlement check.
