# Finished-job deletion verification — 2026-10-11

Added **Jobs → select finished job → Delete job**, with confirmation that the saved job record and captured stdout/stderr logs are permanently removed. Failed, stopped, timed-out, output-limited and interrupted jobs are also eligible. Active jobs, workers still cleaning up, and jobs referenced by active Rabbit Hole runs are rejected.

Consumed proposals and audit entries remain; workspace files and existing exports are unchanged. Future evidence exports omit the deleted job/logs. Finished Rabbit Hole steps retain their result metadata with `job_deleted: true`, and the browser removes their output link.

- `scripts/test.sh` using the project interpreter: **279 passed, 1 skipped**, with the existing Starlette/AnyIO deprecation warning. Python compilation and shell/JavaScript syntax checks passed.
- **19 new backend tests** cover actual harmless manual-job completion/deletion, every supported finished status, active/unknown status rejection, ownership, worker cleanup, Rabbit run protection, missing logs, filesystem failure, top-level/nested/root symlinks, CSRF/Origin checks, evidence exports and approval replay prevention.
- Offline Chromium browser smoke: **PASS**, no page errors. Covers confirmation cancellation, storage-error recovery, active-job button state, failed-job eligibility, successful list/output/context reset, deletion by another tab, and mobile controls at 390px. Artifacts are in `/tmp/foxworx-job-delete-browser/`.
- Read-only code review found no material correctness or security issues.

Verification used temporary test state and browser fixtures. Existing operator jobs were not deleted during implementation.
