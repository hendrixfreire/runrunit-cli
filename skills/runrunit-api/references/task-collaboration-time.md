# Task Collaboration and Time

Source: official Runrun.it API documentation, inventoried in August 2026.

## Comments

- `GET /tasks/:task_id/comments` — list comments on a task.
- `GET /comments/:id` — show a specific comment.
- `POST /comments` — create a new comment.
- The documentation has separate `POST /comments` examples for task and project comments.
- Task comment: `{"task_id": 1, "text": "..."}`; success is `201`.
- `PUT /comments/:id` — update a comment.
- `DELETE /comments/:id` — destroy a comment.
- `POST /comments/:id/reaction` — react to a comment.
- Before update/delete, fetch the comment and verify it belongs to the intended task.

## Checklists

Task checklist container:

- `GET /tasks/:task_id/checklist` — show task checklist.
- `POST /tasks/:task_id/checklist` — create task checklist.
- `PUT /tasks/:task_id/checklist` — update task checklist.
- `DELETE /tasks/:task_id/checklist` — destroy task checklist.

Checklist items:

- `GET /checklists/:checklist_id/items` — list items.
- `GET /checklists/:checklist_id/items/:id` — show item.
- `POST /checklists/:checklist_id/items` — create item.
- `PUT /checklists/:checklist_id/items/:id` — update item.
- `DELETE /checklists/:checklist_id/items/:id` — destroy item.

Keep task ID, checklist ID, and item ID distinct. Fetch the container before mutating an item.

## Followers

- `GET /tasks/:task_id/followers` — list followers.
- `POST /tasks/:task_id/followers` — create a task follower.
- `DELETE /tasks/:task_id/followers/:id` — remove a follower.
- Resolve user IDs with `GET /users` rather than matching free-form names.

## Evaluations

Task-level configuration:

- `POST /tasks/:task_id/evaluations` — update task evaluations.
- `DELETE /tasks/:task_id/evaluations` — destroy all evaluations for the task.

Evaluation resources:

- `GET /task_evaluations` — list all evaluations when no params are passed.
- `GET /task_evaluations` — documented filtered variant for a specific task.
- `GET /task_evaluations` — documented filtered variant for a specific evaluator.
- `POST /task_evaluations/:id/reset` — reset an evaluation.
- `DELETE /task_evaluations/:id` — destroy an evaluation.

Deleting `/tasks/:task_id/evaluations` can affect multiple records; summarize the current set and require explicit confirmation.

## Manual Work Records

- `GET /manual_work_periods` — list manual work periods.
- `GET /manual_work_periods/:id` — show one manual work period.
- `POST /manual_work_periods` — create a manual work period.
- `PUT /manual_work_periods/:id` — update a manual work period.
- `DELETE /manual_work_periods/:id` — destroy a manual work period.
- Confirmed create envelope: `manual_work_period`.
- Payload: `{"manual_work_period": {"task_id": 1, "seconds": 3600, "date_to_apply": "YYYY-MM-DD", "board_stage_id": 123, "reason_comment": "...", "team_id": 456}}`.
- Required: `seconds` (≠ 0) and `date_to_apply`.
- `board_stage_id` is optional and **not** inferred from the current stage; without it the entry has no stage in per-stage reports. Read the task's `board_stage_id` and send it.
- Anti-duplicate after timeout: `GET /manual_work_periods?task_id=&user_id=&from=&before=` and compare `date_to_apply` + `seconds` (+ `created_at`) before re-POSTing.
- The upstream stores a duration in seconds applied to one date. It does not persist start/end timestamps.
- If the user provides start/end times, derive duration exactly and preview seconds plus application date.
- Reject or split cross-midnight intervals; disclose that original timestamps will be discarded.
- Read the task and existing record before update/delete.
- Do not call this a precise interval in user-facing summaries; use **manual work record** or **apontamento manual**.

## Play/Pause Semantics

- Task-level play/pause: `POST /tasks/:id/play`, `POST /tasks/:id/pause`.
- Assignment-level play/pause: `POST /tasks/:task_id/assignments/:id/play`, `POST /tasks/:task_id/assignments/:id/pause`.
- Use assignment-level actions only after resolving the assignment ID from the task representation.
- A documented task play variant can create an assignment and play; inspect the exact payload before use.
- Play/pause are convergent: after a timeout, GET the task; re-run only if the target state was not reached.

## Verification by Operation

- Comment: list task comments and match returned comment ID/text.
- Checklist: GET the checklist and item after mutation.
- Follower: list followers and match user ID.
- Evaluation: list evaluations filtered by task and compare IDs/status.
- Manual work: GET the manual record and compare task ID, seconds, and date.
- Play/pause: GET task and inspect assignment state before deciding whether a retry is safe.
