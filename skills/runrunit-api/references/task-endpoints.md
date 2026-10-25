# Task Endpoints

Source: official Runrun.it API documentation, task-related routes inventoried in August 2026. Paths below are relative to `https://runrun.it/api/v1.0`.

## Core CRUD

- `GET /tasks` — query tasks; collection pagination applies.
- `GET /tasks/:id` — show one task.
- `GET /tasks/:id/subtasks` — show task subtasks.
- `POST /tasks` — create a task; documented success `201`.
- `PUT /tasks/:id` — update a task; documented variants cover title, desired start date, desired date, tags, points, and custom fields.
- `DELETE /tasks/:id` — destroy a task; documented success `204`.
- `GET /tasks/:id/form_answers` — answers to the form that created the task.
- `GET /tasks/:id/fields` — list fields from the task's board.
- `GET /tasks/:task_id/fields/:field_id/value` — show a field value.

## Create and Update Contract

- The update examples use a `task` envelope.
- Confirmed update subjects: title, desired start date, desired date, tags, points, custom fields.
- Create (official answer, supersedes the contradictory tables): only `title` is truly required. Send `board_id`, `type_id` and, if the account requires projects, `project_id` explicitly for deterministic results.
- Recommended minimal payload: `{"task": {"title": "...", "board_id": 123, "type_id": 456, "project_id": 789}}`.
- Optional on create: `board_stage_id` (must belong to the board), `description` (HTML), `custom_fields` `{"<field_id>": value}`, `parent_task_id` (subtask).
- After a create timeout: stamp an own id (tag, custom field or `source`) and search for it before recreating.
- Clear dates by sending the key with `null` (`{"task": {"desired_start_date": null, "desired_date": null}}`); omit the key to leave it unchanged.
- Tags: `task.tags_data` replaces the whole collection (`[]` removes all). Read → modify → resend; serialize concurrent writers per task.
- Do not silently translate names into IDs; resolve board/project/type/user identifiers first.
- Description of an existing task never goes through `PUT /tasks/:id`; use the description resource below.

## Description

- `GET /tasks/:task_id/description` — show task description.
- `PUT /tasks/:task_id/description` — body `{"task_description": {"description": "<p>...</p>"}}`.
- Webhooks distinguish `task:update` from `task:description:update`.

## State and Work Actions

- `POST /tasks/:id/play` — play a task.
- `POST /tasks/:id/play` — a documented variant creates an assignment and plays the task.
- `POST /tasks/:id/pause` — pause a task.
- `POST /tasks/:id/deliver` — deliver a task.
- `POST /tasks/:id/reopen` — reopen a task.
- `POST /tasks/:id/reposition` — reposition a task.
- `POST /tasks/:id/reestimate` — reestimate using an `assingee_id` parameter as spelled in the documentation title; inspect the endpoint section before use.
- `POST /tasks/:id/mark_as_urgent` — mark urgent.
- `POST /tasks/:id/unmark_as_urgent` — remove urgency.
- `POST /tasks/:id/move_to_top` — move to top.
- Transitions (move / deliver / play / pause) are convergent: after a timeout, read the task and decide; re-running to the same final state is safe.

## Classification and Placement

- `POST /tasks/:id/change_board` — change board.
- `POST /tasks/:id/change_project` — change project.
- `POST /tasks/:id/change_type` — change task type.
- `POST /tasks/:id/move_to_next_stage` — move to next stage.
- `POST /tasks/:id/move` — move to another stage.
- `POST /tasks/:id/move` — documented variant accepts position.
- Read the task and destination stage before moving; preview both IDs and expected state.

## Sharing and Assignments

- `POST /tasks/:id/share` — share task.
- `POST /tasks/:id/unshare` — unshare task.
- `POST /tasks/:id/create_assignments` — create assignments for another user.
- `DELETE /tasks/:task_id/assignments/:id` — `:id` is the assignment id (string), not the user id. Optional query `destroy_worked_time`. Success `204`.
- Assignment-level actions:
  - `POST /tasks/:task_id/assignments/:id/play`
  - `POST /tasks/:task_id/assignments/:id/pause`
  - `POST /tasks/:task_id/assignments/:id/deliver`
  - `POST /tasks/:task_id/assignments/:id/reopen`
  - `POST /tasks/:task_id/assignments/:id/reposition`
  - `POST /tasks/:task_id/assignments/:id/reestimate`
- Distinguish task ID, user ID, and assignment ID; never substitute one for another.

## Workflow

- `POST /tasks/:id/complete_workflow_step` — complete current workflow step.
- `POST /tasks/:id/undo_workflow_step` — undo workflow step.
- Generic workflow resources also exist under `/workflows`; they include task and task-template workflow variants. Inspect the exact documented section before using because identical paths have multiple workable types.

## Cloning

- `POST /tasks/clone` — clone a task.
- Treat cloning as a write that may fan out relationships; inspect the new task representation after creation.

## Task Relationships

- `GET /tasks/:task_id/descendants` — list descendants.
- `POST /tasks/:task_id/descendants` — add a descendant.
- `DELETE /tasks/:task_id/descendants/:id` — remove a descendant relationship.
- `GET /tasks/:task_id/prerequisites` — list prerequisites.
- `POST /tasks/:task_id/prerequisites` — add a prerequisite.
- `DELETE /tasks/:task_id/prerequisites/:id` — remove a prerequisite relationship.
- Relationship deletion does not necessarily delete the related task; verify the target representation afterward.

## Estimates and Documents

- `GET /tasks/:task_id/estimates` — list task estimates.
- `POST /tasks/:task_id/estimates` — create an estimate.
- `GET /tasks/:task_id/documents` — list uploaded documents.
- Upload is 3 steps:
  1. `POST /documents?task_id=:uid` with `{"document": {"data_file_name", "data_file_size", "warning_duplicate": true}}` → response carries POST Policy `fields`. The current official example uses Oracle Cloud Storage; prefer a returned upload URL or the configured current destination. Do not infer the endpoint solely from a bucket name.
  2. Multipart POST to the object storage with those fields + the file, without Runrun.it authentication headers. The CLI uses the current official Oracle destination as fallback; see `cli.md`.
  3. `POST /documents/:id/mark_as_uploaded` — without it the file does not list or download. Read the document and download it to compare SHA-256 with the uploaded bytes.
- Upload contract refreshed 23/10/2026 against https://github.com/Runrunit/api_examples/blob/main/upload_file_to_task.py .
- `GET /documents/:id`, `DELETE /documents/:id`.

## Filters

- `GET /tasks/filters` — list task filters.
- `GET /tasks/filters/:id` — show one task filter.
- `DELETE /tasks/filters/:id` — destroy a task filter.
- Filter deletion is destructive account configuration, not task deletion.

## Mutation Checklist

1. `GET /tasks/:id` and capture title, board/stage, project, assignees, dates, urgent state, and workflow state.
2. Resolve every destination/reference ID through supporting collection routes.
3. Preview the exact method, path, ID, and JSON keys.
4. Confirm state-changing or destructive operations.
5. Execute once; on timeout, reconcile (GET and compare) before any retry.
6. GET the task again and compare the intended fields/state.
