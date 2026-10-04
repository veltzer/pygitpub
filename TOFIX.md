# TOFIX

Findings from a code scan on 2026-10-04.

## High

- `src/pygitpub/main.py:211-212` - `cleanup` deletes every workflow run whose `head_branch != "master"`, regardless of state. In any repo whose default branch is not `master` (e.g. `main`, or any collaborator/org repo selected via `--affiliation`) this wipes the entire run history, and it also deletes in-progress runs (`run.conclusion is None`) on feature branches. Compare against `repo.default_branch` and skip runs that are still running.
- `src/pygitpub/main.py:79-131,197-267` - the mutating endpoints `fix_metadata` (edits description and replaces topics), `homepage_fix` (edits homepage) and `cleanup` (deletes runs, deployments, releases) ignore `ConfigAlgo.dryrun`; only `clone_all` honours it (`main.py:388`). Make every mutating endpoint print-only when `--dryrun` is set.

## Medium

- `src/pygitpub/main.py:117` - `homepage_fix` sets the Pages homepage to `https://{username}.github.io/{repo.name}/` for every repo, which is wrong for the user-site repo `veltzer.github.io` itself (it yields `https://veltzer.github.io/veltzer.github.io/`; that repo's homepage is supposed to be `https://veltzer.org`). Special-case the `<username>.github.io` repo.
- `src/pygitpub/main.py:117,125` - homepages are built from `ConfigGithub.username` instead of `repo.owner.login`, so with `--affiliation=collaborator,organization_member` other owners' repos get pointed at the user's own account. Use `repo.owner.login` (and then `ConfigGithub.username`, required by every endpoint, `configs.py:19`, becomes unnecessary).
- `src/pygitpub/main.py:424` - `workflows_run` dispatches on hardcoded `ref="master"`; use `repo.default_branch`.
- `src/pygitpub/main.py:291-296` - `runs_show_running` filters on `run.conclusion is None` and then prints the conclusion, so the output column is always `None`; it also includes queued/waiting runs. Filter and print on `run.status` (`in_progress`, `queued`).
- `src/pygitpub/main.py:392-401` - `clone_all` sends `git clone` stdout and stderr to `/dev/null`, so when a clone fails the user only gets a bare `CalledProcessError` with no git error message. Keep stderr (or capture it and include it in the error).
- `src/pygitpub/main.py:46` - `github.Github(login_or_token=...)` is deprecated in the locked PyGithub 2.10 (scheduled for removal in v3); use `github.Github(auth=github.Auth.Token(apikey))`.
- `rsconstruct.toml:60` - sphinx `dep_inputs = ["src/pygitpub/*.py"]` does not cover the `src/pygitpub/utils/` subpackage, and `sphinx/pygitpub.utils.rst` documents it, so edits there do not rebuild the docs. Add `"src/pygitpub/utils/*.py"`.

## Low

- `src/pygitpub/main.py:368` - `clone_all` has the same description as `pull_all` ("Pull all projects from github"); it should say "Clone".
- `src/pygitpub/utils/misc.py:11,15` - `get_logger` and `get_number_of_files` are not used anywhere in the package (`get_number_of_files` only by its test); remove them. Lines 21-23 are stray blank lines.
- `src/pygitpub/main.py:198,250`, `tests/unit_tests/test_logic.py:91` - stale `# pylint: disable=...` pragmas; the repo lints with ruff, not pylint.
- `src/pygitpub/main.py:348,381-387` - commented-out code (`"--tags"`, debug prints); delete.
- `scripts/pygitpub_create.sh:9` - stale snippet: hardcoded placeholder user `'your_github_username'`, basic-auth password prompt (no longer accepted by GitHub), and `repo_name` interpolated raw into JSON. Delete it (the functionality is `gh repo create`) or move it into pygitpub as an endpoint.
- `scripts/pygitpub_rename_main_to_master.sh:6-9` - renames whatever branch is checked out and leaves the essential steps commented out; delete or finish it.
- `src/pygitpub/configs.py:17` - typo "Paramters".
- `doc/NOTES.txt` - a leftover Python docstring about auth options that no longer matches the code (only token auth is used); delete.
