# Supporting Resources for Task Administration

Use these routes to resolve IDs and validate destinations before mutating a task. Paths are relative to `https://runrun.it/api/v1.0`.

## Projects

- `GET /projects` — list projects.
- `GET /projects/:id` — show a project.
- `GET /projects/:id/related_users` — list users related to a project.
- `GET /projects/filters` — list project filters.
- `GET /projects/filters/:id` — show a project filter.
- `POST /projects/` — create a project.
- `PUT /projects/:id` — documented variants deliver or reopen a project; inspect payload before use.
- `POST /projects/:id/move` — documented variants move to another client, project group, or project subgroup.
- `POST /projects/:id/share` — share project.
- `POST /projects/:id/unshare` — unshare project.
- `POST /projects/:id/clone` — clone project.
- `POST /projects/:id/change_board_stage` — change project board stage.
- `PUT /projects/:project_id/description` — update project description.
- Project administration is outside the default task-only scope; use writes only when explicitly requested.

## Boards and Stages

- `GET /boards` — list boards.
- `GET /boards/:id` — show a board.
- `GET /boards/:board_id/stages` — list all non-deleted stages, including empty ones.
- `GET /boards/:board_id/stages/:id` — show a stage.
- `POST /boards/:board_id/stages` — create a stage.
- `PUT /boards/:board_id/stages/:id` — update a stage.
- `DELETE /boards/:board_id/stages/:id` — destroy a stage.
- `POST /boards/:board_id/stages/:id/move` — move stage between group positions.
- `POST /boards/:board_id/stages/:id/update_use_latency_time` — toggle latency-time use.
- `POST /boards/:board_id/stages/:id/update_use_scrum_points` — toggle scrum-points use.
- For task movement, list stages for the known board and select by exact ID.

## Users

- `GET /users` — list users.
- `GET /users/:user_id` — get user by ID.
- There is no `GET /users/me` (`me` as id → `404`). Current user: `GET /users?me_first=true&limit=1`; the first item owns the `User-Token`.
- `POST /users` and `PUT /users/:id` exist but are account administration, not task administration.
- Use individual `User-Token` values so actions preserve authorship and permissions.

## User Relationships

- `GET /users/:user_id/demanders` — list demanders.
- `GET /users/:user_id/partners` — list partners.
- Mutations exist for adding, replacing, and deleting demanders/partners; they are out of default task scope.

## Teams

- `GET /teams` — list teams.
- `GET /teams/:id` — show a team.
- `POST /teams`, `PUT /teams/:id`, `DELETE /teams/:id` — team administration.
- `POST /teams/:id/add_member` — add member.
- `POST /teams/:id/remove_member` — remove member.
- Team writes are not prerequisites for ordinary task assignment; resolve user/assignment IDs first.

## Task Types

- `GET /task_types` — list task types.
- `GET /task_types/:id` — show task type.
- `POST /task_types` — create task type.
- `PUT /task_types/:id` — update task type.
- Use read routes to resolve `type_id`; do not create a type merely because a task-create payload needs one.

## Tags

- `GET /tags` — query tags.
- Generic task update has a documented variant for adding tags without setting color.
- `task.tags_data` replaces the whole collection; `[]` removes all. Read → modify → resend.
- New tags are created when referenced by name.
- Resolve existing tags before update; do not assume case-insensitive uniqueness.

## Clients and Project Hierarchy

- `GET /clients` and `GET /clients/:id` — resolve client IDs for project context.
- Client mutations and monthly-budget routes exist but are outside task administration.
- Project groups, project subgroups, and project templates have dedicated resources in the official reference; load their exact endpoint sections before account-structure mutations.

## Task Templates and Workflows

- Task templates have CRUD-like resources plus checklist and workflow support.
- Generic `/workflows` routes are overloaded for task and task-template workflows.
- A confirmed task-template query is `GET /workflows?task_template_id=:id`.
- A confirmed task-template create body contains `task_template_id` and `workflow`.
- A confirmed task-template delete body contains `task_template_id`.
- Do not apply task-template examples to live-task workflows without checking the exact documented section.

## Lookup Procedure

1. Start from the task (`GET /tasks/:id`) or bounded task collection.
2. Extract existing board, stage, project, assignment, and type IDs.
3. Query the smallest supporting collection needed.
4. Match by stable ID; names are display data and may be duplicated.
5. Fetch the chosen destination resource by ID when a show route exists.
6. Only then construct the task mutation.
