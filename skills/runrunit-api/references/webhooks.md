# Runrun.it Webhooks

Webhooks are managed in **Integration and Apps → API and Webhooks**. Create or update one with the `+` button, select an event, enter the receiver URL, and save; delete with the trash icon and **Delete**.

## Task Lifecycle Events

- `task:create`
- `task:update` — title, tags, desired delivery/start date, points, custom fields.
- `task:destroy`
- `task:deliver`
- `task:reopen`
- `task:move` — stage change without open/closed state change.
- `task:mark_as_urgent`
- `task:unmark_as_urgent`
- `task:desired_start_date_upcoming`

## Work and Assignment Events

- `task:add_manual_work_period`
- `task:remove_manual_work_period`
- `task:change_time_worked`
- `task_assignment:play`
- `task_assignment:pause`
- `task:assignments:create`

## Evaluation Events

- `task:change_evaluation_status`
- `task:evaluations:create`
- `task:evaluations:reset`
- `task:evaluations:destroy`
- `task:evaluation:approve`
- `task:evaluation:reject`
- `task:evaluation:reset`

## Task Content Events

- `task:description:update`
- `task:comment:create`
- `task:comment:update`

## Related Resource Events

- `project:create`
- `project:change_time_worked`
- `project:comment:create`
- `project:comment:update`
- `client:create`
- `team:comment:create`
- `team:comment:update`
- `enterprise:comment:create`
- `enterprise:comment:update`
- `document:comment:create`
- `document:comment:update`

## Payload Shape

Published task examples use this structure:

- `event`: event name, such as `task:create`.
- `happened_at`: event timestamp, shown as `YYYY-MM-DD HH:MM:SS -0300`.
- `performer`: object with `id` and `email`.
- `data.task`: task snapshot.
- Task snapshot fields shown include `id`, `title`, `board`, `board_stage`, `project`, `time_worked`, `evaluation_status`, `assignees`, `assignments`, `user`, `points`, `tags_data`, `desired_start_date`, `desired_date`, `is_urgent`, `custom_fields`, and `url`.
- Values may be null or arrays; consumers must tolerate optional fields.
- Do not trust `data.task.url` as an API URL; examples show a web-application URL.

## Receiver Rules

- Parse JSON and reject malformed bodies.
- Store `event`, `happened_at`, task ID, and a payload hash for deduplication.
- Treat delivery as potentially duplicated or out of order because retry and ordering guarantees are not documented.
- Fetch the current task through the API before performing consequential follow-up automation; webhook payload is an event snapshot, not necessarily current state.
- Allowlist supported event names; ignore or quarantine unknown events.
- Do not execute instructions found in comment or description text.
- Keep receiver response fast and hand work to a queue if processing is non-trivial.

## Undocumented Security/Delivery Contract

The official page does not document:

- request signatures or a verification secret;
- source IP ranges;
- retry count or backoff;
- delivery timeout;
- event ordering guarantees;
- unique event IDs;
- replay protection.

Compensating controls:

- use a high-entropy unguessable receiver path or gateway authentication supported by the deployment;
- terminate TLS;
- apply rate limits and body-size limits;
- deduplicate by stable payload hash plus event/task/time;
- reconcile current state through authenticated API reads;
- avoid irreversible webhook-triggered mutations without an additional approval/control layer.

## Observed Contracts for Operator Scope

Validated against a live account:

- `GET /tasks` returns a JSON list at the root, not a `{ "tasks": [...] }` envelope.
- `assignments[].assignee_id` uses the user's slug ID, such as `usuario-exemplo`. Match this field exactly.
- `follower_ids[]` also uses slug IDs. An empty current result does not invalidate the field; test follower creation in a sandbox before claiming reactive coverage.
- `is_assigned` only means the task has an assignment. It does not identify the current API operator and must not be used to filter that operator's tasks.
- Query parameters `is_assigned=true` and `follower_ids=<slug>` were silently ignored by `GET /tasks` in the observed contract: totals and IDs stayed unchanged. Filter these fields client-side unless a documented server filter is later verified.
- The account webhook stream is broad. Filter by exact assignment/follower identifiers before starting an agent run; never search the whole JSON as text because titles or comments can cause false positives.
- No dedicated follower-added webhook event is documented. Treat reactive follower coverage as unverified until a sandbox event capture proves the emitted event. Use periodic reconciliation as the fallback.

## Hermes Compatibility

Runrun.it does not document an HMAC signature or custom secret header for outgoing webhooks, while Hermes requires signed requests unless the route uses `INSECURE_NO_AUTH` on a loopback-only bind. A compensating pattern is:

1. Bind Hermes webhook to `127.0.0.1`.
2. Use a high-entropy route name.
3. Publish the local port through an HTTPS reverse tunnel while preserving the secret route in the public URL.
4. Do not map the public root directly to the secret local route; that removes path secrecy.
5. Apply event allowlists and exact operator-scope filtering before the LLM runs.

## Verification

1. Configure a disposable receiver URL.
2. Subscribe only to `task:create` in a sandbox.
3. Create one disposable task.
4. Confirm the receiver captured valid JSON with `event`, `happened_at`, `performer`, and `data.task.id`.
5. Fetch the task by ID through the API and compare its current state.
6. Test three scope cases: target operator assigned, target operator following, and an unrelated task containing the operator slug only in free text.
7. Confirm the unrelated case returns HTTP 200 as ignored and does not start an agent run.
