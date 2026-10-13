# Rabbit Hole — autonomous tool selection and investigation

Rabbit Hole carries out an operator-authorized task by selecting tools, checking actual job output and trying alternatives within a finite run. One initial authorization covers the permitted execution mode, exact target and budgets; it does not ask for approval on each alternative command.

## Choose an execution mode

| Mode | What the agent may execute |
|---|---|
| Selected administrator workflows | Only selected, enabled guided recipes or autonomous typed adapters. Defaults: 8 decisions, 15 minutes. |
| Installed CLI tools | Installed noninteractive executables with model-constructed literal arguments, plus applicable enabled workflows. Defaults: 64 decisions, 60 minutes. Requires a schema-3 administrator policy with `allow_installed_cli: true`. |

Workflow-only grants retain their restrictions. Schema-1/2 policies do not enable installed-tool autonomy. A review-only adapter cannot run as an autonomous workflow. **Installed CLI mode is broader:** it can invoke the underlying executable directly without using its review-only adapter. The initial mode selection authorizes that broader capability.

Commands use the existing managed-job runner, engagement working directory, and non-root Linux service account. There is no interactive stdin or embedded GUI workflow. The app does not construct a shell pipeline from command text, grant elevated privileges, or expose native model terminal tools. Executable arguments can still enable a program's own scripting, file access, child processes or network behavior; this is **not an OS or network sandbox**.

## Start a task

1. Create or select an engagement. Record permitted targets, exclusions, operator rules and applicable automation limits.
2. Select a working provider and model in **Provider & model**, then choose **Rabbit Hole**.
3. Enter the exact authorized target and choose the tool-selection mode. Workflow mode requires selecting installed administrator-enabled workflows. Installed CLI mode discovers alternatives automatically without selecting each tool.
4. Choose finite decision and time budgets within the administrator policy. Write a focused objective and confirm the one-time authorization.
5. Press **Authorize & run**. Inspect reasons, job links, exit status and saved output as the agent proceeds.
6. Use **Stop Rabbit Hole** to cancel remaining actions and terminate the active managed job.

The backend supplies a ranked shortlist before each decision. `lookup_tools` can refine or paginate discovery; documentation functions can explain unfamiliar tools. Search ranking is not proof that an executable is suitable or has the necessary permissions. See [tool discovery](TOOL-DISCOVERY.md).

## Supplemental operator instructions

While a run is active, the composer becomes **Send instruction**. Follow-ups steer the existing objective without changing targets, exclusions, privileges, elapsed time or remaining budget. Received instructions are shown as pending until applied before a model decision.

An instruction arriving during inference invalidates that proposed action; the agent replans before executing. An already-running job continues unless the operator presses Stop. Up to 64 messages of 4,000 characters are retained per run. Every accepted follow-up is included in subsequent decisions so earlier instructions are not silently discarded. Long instructions consume the selected model's context; a provider context-limit error stops the run rather than dropping instructions. The initial objective and authorization remain present.

Only messages submitted through the operator endpoint are follow-ups. Tool output, manuals, Discord messages and model text cannot update the run authorization.

## Budgets, retries and termination

Schema-3 policy supports administrator limits up to **10,000 decisions and 1,440 minutes**. The supplied installed-CLI policy example caps runs at 256 decisions and 240 minutes. Older policy schemas retain their 16-decision/30-minute ceilings. Actual run budgets cannot exceed the active policy. At most one run per operator and two per node remain active.

Every model decision consumes a step, including lookup, documentation and a discarded outdated action. Automatic shortlist generation does not consume a step. Supplemental prompts do not reset budgets. Per-job timeout, output, concurrency and disk-reserve checks also apply.

The agent receives exit status and bounded, redacted output to diagnose failures. After two failures of the same executable/argument combination, it must choose another command or finish blocked. Workflow mode similarly avoids repeating a failed workflow indefinitely. A missing executable produces an error the agent can use to select an alternative.

Runs stop when finished, blocked, out of budget, repeatedly invalid, canceled, or affected by policy/scope revocation. Executable identity and run authorization are checked again immediately before process creation. No run resumes automatically after service restart; interrupted work requires a new run authorization. Model-reported success requires at least one successful job, but still needs evidence review to establish that the objective was met.

## Execution and privacy boundaries

Installed CLI mode shares the service account's file and network access. Its stated target is not a destination firewall. Arbitrary arguments cannot be generically verified against every tool's network behavior; the operator must choose an appropriate assessment environment and permitted methods. No new sudo or root access is provided.

The selected model receives the objective, scope/notes, supplemental instructions, relevant tool metadata, workflow definitions and bounded job results. Redaction is best effort. Local run records, instructions and job output are not app-encrypted; operators sharing the Linux account can inspect them. DreadFox's separate companion privacy boundary remains unchanged.

## Administrator setup

Review and validate [the schema-3 example](../policy/adapter-policy.v3.installed-cli.example.json), then install it using trusted OS commands:

```bash
bash scripts/adapter-policy.sh validate policy/adapter-policy.v3.installed-cli.example.json
sudo install -d -o root -g root -m 0755 /etc/foxworx
sudo install -o root -g root -m 0644 policy/adapter-policy.v3.installed-cli.example.json /etc/foxworx/adapter-policy.json
```

Do not sudo-execute application scripts from the operator-writable checkout. Policy replacement revokes existing active runs; refresh permissions before starting another run. FOXWORX does not install or change the root-owned policy automatically. See [administrator policy](ADAPTER-POLICY.md).

## Backend API

Use the normal actor access and Origin/CSRF checks. Default token-free deployments use a shared local operator identity.

`POST /api/rabbit-runs` accepts:

```json
{
  "engagement_id": "<existing engagement id>",
  "objective": "Inspect the authorized local lab service and summarize evidence",
  "target": "127.0.0.1",
  "execution_mode": "installed_cli",
  "profiles": [],
  "max_steps": 64,
  "max_minutes": 60,
  "authorized": true
}
```

Omitting `execution_mode` retains workflow-only behavior and requires `profiles`. Installed CLI mode can omit profiles and use applicable administrator-enabled autonomous workflows alongside direct CLI tools.

- `GET /api/rabbit-runs?engagement_id=...`: list owned runs.
- `GET /api/rabbit-runs/{id}`: status, consumed decisions, steps and instruction revisions.
- `POST /api/rabbit-runs/{id}/messages` with `{"message":"Try a different HTTP client"}`: append an operator instruction. Ended/stopping runs reject messages with 409; invalid text returns 422; the message limit returns 429.
- `POST /api/rabbit-runs/{id}/stop` with `{}`: stop the run and its active job.

Execution records and evidence remain linked to the engagement and Investigation Graph. Ordinary Copilot proposals still require individual operator approval.
