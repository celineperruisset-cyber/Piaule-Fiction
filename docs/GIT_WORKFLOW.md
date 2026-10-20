# Git and GitHub workflow

This document defines how Piaule Fiction changes are reviewed, recorded, and published. The goal is to keep the project history understandable, reproducible, and free of secrets or personal data.

## Repository model

- `main` contains the current stable project state.
- Short-lived branches isolate one coherent change from `main`.
- `origin` is the local name of the private GitHub repository.
- A pull request explains and reviews a branch before it is merged into `main`.

## Daily workflow

1. Start from an up-to-date `main` branch.
2. Create a short-lived branch named after the change.
3. Modify one coherent part of the project.
4. Review `git status` and `git diff` before staging anything.
5. Check that no secret, credential, personal document, or real applicant data is included.
6. Stage only the intended files with `git add`.
7. Create one explicit commit describing the result.
8. Push the branch and open a pull request.
9. Merge only after the change and its evidence have been reviewed.

## Commit message convention

Commit messages use the form:

```text
type: short description of the result
```

| Type | Use |
|---|---|
| `feat` | Add or extend product behavior. |
| `fix` | Correct faulty behavior. |
| `docs` | Change documentation only. |
| `test` | Add or correct automated tests or evaluation cases. |
| `chore` | Maintain tooling, configuration, or repository structure. |

Examples:

```text
feat: add listing risk signals
fix: block unsupported document sharing
docs: explain candidate consent safeguards
test: add incomplete candidate dossier cases
chore: configure Python linting
```

## Review checklist

Before every commit or pull request, verify that:

- the changed files match the stated objective;
- the code or documentation can be explained;
- relevant tests have been run;
- `.env`, API keys, passwords, tokens, and private keys are absent;
- all candidate dossiers and documents are synthetic;
- product rules are separated from legal or platform-specific constraints;
- any consequential AI recommendation remains subject to meaningful human review.

## Local and remote actions

- `git add` selects changes for the next commit; it does not upload them.
- `git commit` records a local snapshot; it does not upload it.
- `git push` sends local commits to GitHub.
- `git fetch` downloads remote history without changing working files.
- `git pull` fetches and then integrates remote changes.

Commit messages are proposed and explained before they are created. At the end of each work session, the repository status, diff, tests, documentation, and secret exposure are reviewed before pushing.
