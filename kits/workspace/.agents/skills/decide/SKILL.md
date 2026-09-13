---
name: decide
description: Use to record an architecture decision as an ADR in docs/adr through a merge request.
---
# Record a decision

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there.
2. Ask the person for:
   - `title`: one line;
   - context: what forces the decision;
   - decision: what we do;
   - rejected alternatives, each with the reason it was rejected;
   - consequences: what changes after the decision;
   - affected keys, such as `repo:payments-worker` or `domain:payments`;
   - the ADR this decision replaces, such as `adr:0001`, or none.
   Every affected key must exist, see `.agents/rules/keys-and-links.md`: a `repo:` name is in `repos.json`, a `domain:` directory is in `domains/`, and so on. Drop or correct, together with the person, every key that does not exist. Never invent content the person did not give.
3. Find the workspace default branch: run `git symbolic-ref --short refs/remotes/origin/HEAD` and remove the `origin/` prefix; when the command fails, use `main`. Call it `<default>`. Then run, one by one:
   - `git switch <default>`
   - `git pull --ff-only`
4. Choose the number `NNNN` and the slug, then create the branch. Do this after the pull, so the number is taken from the fresh default branch.
   - Run `ls docs/adr/ | grep -E '^[0-9]{4}-.*\.md$' | tail -1 | cut -c1-4`. It prints the highest number, for example `0002`.
   - When it prints nothing, `NNNN` is `0001`. Otherwise run `printf '%04d\n' "$(expr <highest> + 1)"`, for example `printf '%04d\n' "$(expr 0002 + 1)"` prints `0003`.
   - Slug: the title in lowercase, every run of characters other than `a-z` and `0-9` replaced by one `-`, and `-` removed from both ends. Run `printf '%s' "<title>" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'`. For `Use Kafka for payment events` it prints `use-kafka-for-payment-events`.
   - When the slug command prints nothing (the title has no Latin letters or digits, for example a Russian title), ask the person for a short English slug made only of `a-z`, `0-9` and `-`, such as `use-kafka`. Use it as `<slug>`.
   - Run `git switch -c adr-NNNN-<slug>`.
5. Run `cp .agents/templates/adr.md docs/adr/NNNN-<slug>.md` and edit the new file:
   - `key: adr:NNNN`;
   - `title: <title>`;
   - `status: proposed`;
   - `date:` the output of `date +%F`;
   - `affects:` the keys as an inline list, for example `affects: [repo:payments-worker, domain:payments]`, or `affects: []`;
   - the heading `# ADR-NNNN: <title>`;
   - replace the placeholder text of `## Context`, `## Decision` and `## Consequences` with the person's words, and add one table row `| <option> | <reason> |` per rejected alternative under `## Alternatives`.
   Example frontmatter and heading:
   ```
   ---
   key: adr:0003
   title: Use Kafka for payment events
   status: proposed
   date: 2026-09-13
   affects: [repo:payments-worker, domain:payments]
   ---
   # ADR-0003: Use Kafka for payment events
   ```
   When the decision replaces an older ADR, open that older file in `docs/adr/` and change its `status:` line to `status: superseded`. This change goes into the same merge request as the new ADR.
6. If `command -v python3` succeeds, run `python3 tools/generate.py`. Otherwise apply `## Recipe: index`.
7. Run the check. First run `command -v python3`.
   - When it succeeds (Python is present): run `python3 tools/check.py`. Fix findings only in the files this skill changed: `docs/adr/NNNN-<slug>.md`, `.agents/index.json`, and the older ADR when you marked it `superseded`. Run it again. Stop running it when no finding names any of these files. If findings in other files remain, do not fix them; list them in the report.
   - When it fails (Python is missing): do not run the check. Remember the line `check not run: python3 missing` for the report.
8. Commit: run `git add docs/adr/NNNN-<slug>.md .agents/index.json`. When you marked an older ADR `superseded` in step 5, also run `git add docs/adr/<older file>.md`, so it is in the same commit. Then run `git commit -m "docs(adr): propose NNNN <slug>"`.
9. Run `git pull --rebase origin <default>`. Then follow `## Conflicts and renumbering`.
10. Push and open the merge request by `.agents/rules/merge-requests.md`, with title `ADR-NNNN: <title>` and branch `adr-NNNN-<slug>`.
11. Report to the person:
    - the file `docs/adr/NNNN-<slug>.md`;
    - the branch `adr-NNNN-<slug>`;
    - the merge request link, or the instruction to open it;
    - the remaining check findings in other files, when there are any;
    - as the last line, the check result, or `check not run: python3 missing`.

## Recipe: index
`.agents/index.json` lists all `adr:` entries first, in number order, then all `diagram:` entries. To add your ADR:

1. Build the line `  "adr:NNNN": "docs/adr/NNNN-<slug>.md"`: two spaces, then the entry.
2. Insert it directly after the last line that starts with `  "adr:`. When there is no such line, insert it as the first entry, directly after the line `{`. When the whole file is the single line `{}`, replace that line with three lines: `{`, your entry line, `}`, as in Example 1.
3. When an entry line comes before your line, make sure that entry line ends with `,`; add the comma when it is missing.
4. When an entry line comes after your line, end your line with `,`. When your line is the last entry, it has no comma.
5. Keep two-space indentation and no trailing spaces. The file ends with `}` and a newline.

Example 1. The index is empty:

```
{}
```

After adding `0001-use-kafka`:

```
{
  "adr:0001": "docs/adr/0001-use-kafka.md"
}
```

Example 2. Before, with one ADR and one diagram:

```
{
  "adr:0001": "docs/adr/0001-use-kafka.md",
  "diagram:payments": "docs/diagrams/payments.md"
}
```

After adding `0002-split-ledger`:

```
{
  "adr:0001": "docs/adr/0001-use-kafka.md",
  "adr:0002": "docs/adr/0002-split-ledger.md",
  "diagram:payments": "docs/diagrams/payments.md"
}
```

## Conflicts and renumbering
Do not run `python3 tools/check.py` in steps 1-4: while your number collides, check reports a duplicate number on the other ADR. Step 5 runs it after renumbering.

1. List all conflicted files: `git diff --name-only --diff-filter=U`. When it prints nothing, go to step 4.
2. First check the whole list for any file other than `.agents/index.json`. If there is one:
   - Run `git rebase --abort`.
   - For each such file, show the person both versions, each under its label: `Your branch:` with `git diff <default>...adr-NNNN-<slug> -- <file>`, and `Default branch:` with `git show origin/<default>:<file>`.
   - Stop and wait for the person. Do not touch `.agents/index.json`.
3. Only when `.agents/index.json` is the sole conflicted file:
   - Run `git checkout --ours -- .agents/index.json`. During a rebase `--ours` is the default branch version.
   - Rebuild the index: if `command -v python3` succeeds, run `python3 tools/generate.py`. Otherwise apply `## Recipe: index`, but when the file already has a line starting with `  "adr:NNNN"` for another file, add nothing: step 4 adds your entry under a new number.
   - Run `git add .agents/index.json`.
   - Run `GIT_EDITOR=true git rebase --continue`. When it stops on conflicts again, go back to step 1.
4. After a successful rebase, run `ls docs/adr/NNNN-*`. When it shows only your file, go to step 5. When it shows another file with your number, renumber your ADR:
   - Choose the next free number `MMMM` with only the first two bullets of step 4 of `## Steps`: the `ls docs/adr/ | ... | cut -c1-4` command, then the `printf '%04d\n'` command. Keep your slug. Do not create or switch branches: stay on `adr-NNNN-<slug>`.
   - Run `git mv docs/adr/NNNN-<slug>.md docs/adr/MMMM-<slug>.md`.
   - In that file change `key: adr:NNNN` to `key: adr:MMMM` and the heading to `# ADR-MMMM: <title>`.
   - Run `git grep -n "adr:NNNN"`. Change to `adr:MMMM` only the references you added in this branch; `git diff origin/<default>...HEAD` shows them. Leave the references to the other ADR as they are.
   - Update the index: if `command -v python3` succeeds, run `python3 tools/generate.py`. Otherwise delete the line `  "adr:NNNN": "docs/adr/NNNN-<slug>.md"` with your slug when it is present, fix the comma of the line before it, and add `  "adr:MMMM": "docs/adr/MMMM-<slug>.md"` by `## Recipe: index`.
   - Run `git add -A docs/adr .agents/index.json` and every file where you changed a reference, then `git commit -m "docs(adr): renumber <slug> to MMMM"`.
   - From here on use `MMMM` instead of `NNNN` in the file name, the title and the report. The branch keeps its name.
5. Run the check, only now, after step 4. First run `command -v python3`.
   - When it succeeds (Python is present): run `python3 tools/check.py`. Fix findings only in the files this skill changed: your ADR file, `.agents/index.json`, the older ADR when you marked it `superseded`, and every file where you changed a reference in step 4. Run it again. Stop running it when no finding names any of these files. If findings in other files remain, do not fix them; list them in the report.
   - When you fixed a file, run `git add <file>` for each fixed file, then `git commit --amend --no-edit`.
   - When it fails (Python is missing): do not run the check. Remember the line `check not run: python3 missing` for the report.

## Accepting an ADR
Acceptance usually happens later, in a new session. `adr-NNNN-<slug>` below is the branch of the merge request; after renumbering it keeps the old number, while the file has the new one. In steps 7 and 8 use the number of the file: after step 3, `ls docs/adr/*-<slug>.md` shows it. Run every command from the workspace root (step 1 of `## Steps`).

1. Run `git fetch origin`.
2. Run `git switch adr-NNNN-<slug>`.
3. Run `git pull --ff-only`.
4. After review, in the same merge request and before merging, edit the ADR frontmatter:
   - change `status: proposed` to `status: accepted`;
   - add the line `approved: {by: <reviewer name>, date: YYYY-MM-DD}` with the review date from `date +%F`.
   `check` rejects an ADR with `status: accepted` that has no `approved` mark, so never set one without the other.
5. A replaced ADR gets `status: superseded` in the merge request of the new ADR that replaces it, never in a separate one: step 5 of `## Steps` edits the older file and step 8 adds it to the same commit.
6. Run the check. First run `command -v python3`.
   - When it succeeds (Python is present): run `python3 tools/check.py`. Fix findings only in your ADR file, the file this section changed. Run it again. Stop running it when no finding names that file. If findings in other files remain, do not fix them; list them to the person.
   - When it fails (Python is missing): do not run the check. Tell the person `check not run: python3 missing`.
7. Run `git add docs/adr/NNNN-<slug>.md`.
8. Run `git commit -m "docs(adr): accept NNNN <slug>"`.
9. Run `git push origin adr-NNNN-<slug>`.

## Without Python
1. In step 6, and in `## Conflicts and renumbering`, apply `## Recipe: index` instead of `python3 tools/generate.py`.
2. Skip `python3 tools/generate.py` and `python3 tools/check.py` everywhere.
3. End the report with the line:

check not run: python3 missing
