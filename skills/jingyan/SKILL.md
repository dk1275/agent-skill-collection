---
name: jingyan
description: "Build and operate a local cross-project experience loop: extract candidate lessons, promote and version evidence-complete methods under the library's approval policy, retrieve them before tasks, and record post-task retrospectives. Use for AI experience transfer, reusable-method libraries, cross-project learning, or when a project should inherit verified practices; do not mutate source projects."
---

# Jingyan｜经验传承

Use the shared local tool to turn project evidence into reusable methods without letting an agent silently rewrite long-term rules.

## Fixed boundaries

- Source projects are read-only unless the user separately asks to change them.
- Extraction creates `pending` candidates only. Never represent a candidate as an established method.
- Follow the library's recorded approval policy. `manual` requires a per-item user decision. `bootstrap_auto` is a durable blanket authorization declared by the user; under it, approve evidence-complete candidates without asking item by item, using `BOOTSTRAP_AUTHORIZED` and preserving the audit trail.
- Task preparation retrieves only `approved` methods and must preserve each method's applicability, exclusions, evidence, version, and verification checklist.
- Each `inject` creates an open task record. The matching `retro --injection-id` is required to close it; run `closure --project` before reporting an important task complete.
- A retrospective may propose new candidates. In `bootstrap_auto`, promote only lessons that include concrete applicability, exclusions, risk, and verification; incomplete lessons remain pending.
- Do not store secrets, tokens, cookies, real OpenIDs, or unnecessary personal data. The tool rejects common credential patterns; still review inputs before writing.
- Do not use agreement among agents as evidence. Prefer observed results, project records, tests, deployment checks, and user acceptance.

## Data location

Default library root:

`<your-experience-library>`

Override it with `--root` only when the user names another library. The canonical executable is `scripts/experience_tool.py` in this skill.

## Workflow

1. Read the target project's product map and handoff, limited to files relevant to the task.
2. Before work, run `inject` with the task, project, and project type. Save its `INJECTION_ID`; use the returned methods as constraints or checks, not as replacements for current project evidence.
3. Before reporting completion, record the outcome with `retro --injection-id <ID>`. State what was actually verified and what remains unverified.
4. When adding a lesson, provide concrete applicability, exclusions, risk, and verification. Otherwise it remains pending rather than becoming a formal method.
5. Review extracted candidates and use `candidate update` to replace any placeholder boundary. Approval always refuses incomplete applicability or exclusion fields.
6. Read `policy show`. In `manual`, present candidates to the user. In `bootstrap_auto`, promote all evidence-complete pending candidates without interrupting the user; preserve the user's blanket authorization in each decision record.
7. For a method change, create a candidate with `--method-id`. Approval archives the previous version and increments the patch version.
8. Run `closure --project <project>` after the retrospective. An open injection is an unfinished task record; do not report completion until it is closed. Use `verify` after changes and cross-project tests.

## Common commands

```bash
python3 scripts/experience_tool.py --root <library> status
python3 scripts/experience_tool.py --root <library> policy show
python3 scripts/experience_tool.py --root <library> policy set --approval-mode bootstrap_auto --authorized-by user --reason <reason> --confirm USER_AUTHORIZED
python3 scripts/experience_tool.py --root <library> extract --source-file <one-markdown-file> --source-project <project> --source-ref <safe-reference>
python3 scripts/experience_tool.py --root <library> candidate add --source-project <project> --title <title> --rule <rule> --applies-to <scope> --not-for <exclusions> --evidence <evidence> --risk <risk> --verification <check> --tags <comma-separated>
python3 scripts/experience_tool.py --root <library> candidate list --status pending
python3 scripts/experience_tool.py --root <library> candidate update <candidate-id> --not-for <exclusions> --verification <check>
python3 scripts/experience_tool.py --root <library> approve <candidate-id> --approved-by user --decision-note <note> --confirm USER_APPROVED
python3 scripts/experience_tool.py --root <library> approve-all --approved-by <actor> --decision-note <note> --confirm BOOTSTRAP_AUTHORIZED
python3 scripts/experience_tool.py --root <library> inject --project <project> --project-type <type> --task <task> --query <keywords> --limit 5
python3 scripts/experience_tool.py --root <library> retro --project <project> --task <task> --result success|partial|failure --outcome <observed-result> --injection-id <injection-id> --used-method <method-id>
python3 scripts/experience_tool.py --root <library> closure --project <project>
python3 scripts/experience_tool.py --root <library> verify
```

When extracting from prose, inspect the generated candidates before presenting them. The extractor is intentionally conservative and heuristic; it does not decide whether a statement is true or broadly applicable.

