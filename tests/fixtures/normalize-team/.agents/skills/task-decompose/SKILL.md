---
name: task-decompose
description: Use to split a stream at the decomposition stage into stories - list scope screens without a story, create the accepted stories and close the stage through a merge request.
---
# Decompose a stream

## Steps
1. Go to the workspace root: the nearest directory, walking up from where you are, where `test -f .agents/kit.json` succeeds. Run every command below from there.
2. Ask the person for the stream as `<domain>/<stream>`, unless they already gave it. To show the choices, run `ls -d domains/*/streams/*`. Both names use lowercase letters, digits and `-` only.
3. Find the default branch: run `git symbolic-ref --short refs/remotes/origin/HEAD` and remove the `origin/` prefix; when the command fails, use `main`. Call it `<default>`. Then run, one by one:
   - `git switch <default>`
   - `GIT_TERMINAL_PROMPT=0 git pull --ff-only`
4. Read `domains/<domain>/streams/<stream>/stream.json`. When `test -f` fails on it, tell the person the stream does not exist, stop and change nothing. Take `profile`, `stage`, `scope` and `approvals`. When `stage` is not `decomposition`, tell the person the current stage, stop and change nothing. This skill works only at the decomposition stage.
5. List the uncovered keys: the keys of the stream's `scope` that no story of this stream has in its own `scope`. First run `command -v python3`.
   - When it prints a path (Python is present), run, without a pipe:
     `python3 tools/check.py --remaining; echo "exit status $?"`
     `--remaining` always exits 0, so read its exit status and output before trusting them:
     - When the exit status is not 0, or an output line starts with `check:` (such as `check: internal error` or `check: not inside a workspace`), or the output has lines but none of them starts with `stream:`, the report did not run. Tell the person what it printed and subtract by hand as below, the same as without Python.
     - Otherwise take only the output lines that start with `stream:<domain>/<stream> decomposition two_way_coverage: `. To see only them in a long output, run `python3 tools/check.py --remaining | grep "^stream:<domain>/<stream> decomposition two_way_coverage: "`; `grep` exits with status 1 when no line matches, which is not a failure here.
     Each such line has the form `stream:<domain>/<stream> decomposition two_way_coverage: <path>:<line> <detail>`. An uncovered key is reported on `domains/<domain>/streams/<stream>/stream.json:1` with the detail `scope key <key> is in no story's scope`; the key is the text between `scope key ` and ` is in no story's scope`. For example, the line
     `stream:operations/migration decomposition two_way_coverage: domains/operations/streams/migration/stream.json:1 scope key screen:operations/b is in no story's scope`
     gives the uncovered key `screen:operations/b`. Every other detail gives no uncovered key. Write these lines down for the report and do not fix them in this skill:
     - `scope must be a list of strings` on `stream.json`: the stream scope is broken, so neither this report nor the subtraction below can list the uncovered keys. Tell the person, stop and change nothing;
     - `story frontmatter does not parse: ...` or `scope must be a list of keys` on a `story.md`: that story's keys are not counted as covered, so a key it lists shows up as uncovered; tell the person before proposing a story for such a key;
     - `scope key <key> is not in the stream scope` or `scope key <key> does not exist` on a `story.md`;
     - `empty scope without an unmapped reason` on a `story.md`.
     When the report ran and no line starts with that prefix, no key is uncovered.
   - When it prints nothing (Python is missing), subtract by hand:
     1. List A: every string of the `scope` list in `stream.json`, one per line.
     2. Run `grep -Hn -e '^---$' -e '^[a-z_]*:' -e '^ *- ' domains/<domain>/streams/<stream>/stories/*/story.md`. The `-H` prints the file name even when there is one story. When it prints no line starting with a story path (the shell says `No such file or directory` or `no matches found`), the stream has no stories and list B is empty.
     3. List B: for each story file in the output, the frontmatter lies between its first two `---` lines; ignore every later line of that file, such as keys listed in the `## Scope` section. Take its `scope:` line. When it is `scope: [a, b]`, take `a` and `b`; when it is `scope: []`, take nothing; when it is `scope:` alone, take every `- <key>` line directly after it up to the next line that is not a `- ` line. Remove quotes around a key.
     4. A key of list A is uncovered when no line of list B is exactly equal to it. Compare whole keys: `screen:operations/doc` does not cover `screen:operations/docs`.

     Example. `stream.json` of `operations/migration` has `"scope": ["screen:operations/a", "screen:operations/b"]` and the stream has one story. The grep prints:
     ```
     domains/operations/streams/migration/stories/a/story.md:1:---
     domains/operations/streams/migration/stories/a/story.md:2:key: story:operations/a
     domains/operations/streams/migration/stories/a/story.md:3:type: story
     domains/operations/streams/migration/stories/a/story.md:4:wave: 1
     domains/operations/streams/migration/stories/a/story.md:5:tracker:
     domains/operations/streams/migration/stories/a/story.md:6:scope:
     domains/operations/streams/migration/stories/a/story.md:7:  - screen:operations/a
     domains/operations/streams/migration/stories/a/story.md:8:depends: []
     domains/operations/streams/migration/stories/a/story.md:9:repos: []
     domains/operations/streams/migration/stories/a/story.md:10:decisions: []
     domains/operations/streams/migration/stories/a/story.md:11:mockups: []
     domains/operations/streams/migration/stories/a/story.md:12:---
     ```
     List A is `screen:operations/a`, `screen:operations/b`; list B is `screen:operations/a`. The uncovered key is `screen:operations/b`, and step 7 proposes story `story:operations/b` for it.
6. Drop from the uncovered keys every key whose story already waits for review on a story branch. A story slug can differ from the screen slug, so look at the story files on the branches, not at branch names. Run, one by one:
   1. `GIT_TERMINAL_PROMPT=0 git fetch --prune origin`
   2. `git branch -r --list 'origin/story-<domain>-*'`. Each printed line, without its leading spaces, is one story branch `<branch>`. When it prints nothing, no story waits for review; lists C and D stay empty; go to step 7.
   3. For each `<branch>`, run `git diff --name-only --diff-filter=A origin/<default>...<branch> -- 'domains/<domain>/streams/*/stories/*/story.md'`. Each printed path is a story file the branch adds. Write down the folder name before `/story.md`, the story slug, in list D.
   4. For each printed path that starts with `domains/<domain>/streams/<stream>/stories/`, run `git show <branch>:<path>` and take the keys of its frontmatter `scope` as in step 5, substep 3. Write down each key with `<branch>` in list C.
   Tell the person, for each branch with keys in list C, which keys wait for its merge, and ask whether its merge request is still open. When the person says it was closed without merging, remove that branch's keys from list C and its slugs from list D. Do not propose any key that list C still has; compare whole keys as in step 5.
7. For each remaining uncovered key `<prefix>:<element domain>/<slug>`, in `scope` order, propose one story:
   - slug: `<slug>`, the slug of the screen; key `story:<domain>/<slug>`;
   - scope: that one key;
   - wave: the `wave` of the element file (for `screen:` it is `domains/<element domain>/map/<slug>.md`), when present;
   - label and route of the element, so the person knows the screen.
   Run `ls -d domains/<domain>/streams/*/stories/<slug>`. When it prints a path, or list D from step 6 has `<slug>`, the slug is taken by another story; ask the person for another slug.
   Ask the person to accept the proposal, change its slug, wave, depends or repos, or skip it. Never invent depends or repos; ask for them. Write down each accepted story with its values.
8. Ask the person whether BFF defects exist that no screen covers. Skip the question when `test -e domains/<domain>/streams/<stream>/stories/bff-cleanup` succeeds or list D from step 6 has `bff-cleanup`. When the person reports defects, propose one story: slug `bff-cleanup`, key `story:<domain>/bff-cleanup`, `scope: []` and `unmapped: bff defects`. Run `ls -d domains/<domain>/streams/*/stories/bff-cleanup`. When it prints a path, the slug is taken by a story of another stream of this domain; ask the person for another slug. Ask for its wave, depends and repos. When the person accepts, write it down too.
9. For each accepted story, one after another, follow `.agents/skills/task-new/SKILL.md` for stream `<domain>/<stream>` with the values you wrote down, so the person is not asked again. Each story gets its own branch `story-<domain>-<slug>` and its own merge request. When `task-new` stops for a story, tell the person why and go on with the next story.
10. When step 5 found at least one uncovered key (with an open story, a new story, a skipped proposal or a stopped `task-new`), or step 9 created at least one story, stop here and report:
    - each story branch and its merge request link, or the instruction to open it;
    - every uncovered key without an open story, and the lines written down in step 5;
    - that a person reviews and merges the story merge requests, and that after the merges they run this skill again to close the stage;
    - as the last line, the last check result of `task-new`, or `check not run: python3 missing`.
11. Otherwise every story is merged. Verify nothing is uncovered: you are on the updated `<default>` from step 3 and step 5 found no uncovered key. When step 5 wrote down any other `two_way_coverage` line, tell the person, stop and change nothing; the stage cannot close while the gate fails.
12. Ask the person who approves closing the decomposition stage: the name of the reviewer who will merge the stage change. Wait for a name. Never use your own name and never guess one. With no name, stop and change nothing. Run `date +%Y-%m-%d` for `<date>`.
13. Run `git switch -c stage-<domain>-<stream>-decomposition`.
14. Edit `domains/<domain>/streams/<stream>/stream.json`, as `## Stage change` describes:
    - replace `"stage": "decomposition"` with `"stage": "ready"`;
    - append the mark `{"stage": "decomposition", "by": "<reviewer>", "date": "<date>"}` as the last element of `approvals`. Keep the layout of the marks already there. When the marks are written one key per line, as in the example below, write the new mark the same way: `{` and `}` with 4 spaces, each key line with 6 spaces, keys in the order `stage`, `by`, `date`, a comma after the `stage` and `by` lines. Add a comma after the `}` of the previous last mark.
    - Inside the JSON string write `"` as `\"` and `\` as `\\`.
    - Change nothing else in the file.

    Example. `stream.json` before:
    ```json
    {
      "key": "stream:operations/migration",
      "profile": "ui-migration",
      "stage": "decomposition",
      "scope": [
        "screen:operations/a",
        "screen:operations/b"
      ],
      "approvals": [
        {
          "stage": "goal",
          "by": "Anna Petrova",
          "date": "2026-09-01"
        },
        {
          "stage": "map",
          "by": "Anna Petrova",
          "date": "2026-09-08"
        }
      ]
    }
    ```
    After closing the stage with reviewer `Ivan Sokolov` on `2026-09-14`:
    ```json
    {
      "key": "stream:operations/migration",
      "profile": "ui-migration",
      "stage": "ready",
      "scope": [
        "screen:operations/a",
        "screen:operations/b"
      ],
      "approvals": [
        {
          "stage": "goal",
          "by": "Anna Petrova",
          "date": "2026-09-01"
        },
        {
          "stage": "map",
          "by": "Anna Petrova",
          "date": "2026-09-08"
        },
        {
          "stage": "decomposition",
          "by": "Ivan Sokolov",
          "date": "2026-09-14"
        }
      ]
    }
    ```
15. Run the check. First run `command -v python3`.
    - When it prints a path: run `python3 tools/check.py`. Look at the findings with the rule `stage-gate` (such as `domains/<domain>/streams/<stream>/stream.json:1 stage-gate decomposition two_way_coverage: scope key <key> is in no story's scope`). A finding belongs to this stream when its path starts with `domains/<domain>/streams/<stream>/`, or its path is `domains/<domain>/MAP.md` or the element file of a scope key in this stream's `scope`.
      - When a `stage-gate` finding belongs to this stream, a gate of a closed stage fails: show the finding to the person and stop; change nothing more and do not commit. Tell the person that your edit of `domains/<domain>/streams/<stream>/stream.json` is uncommitted on branch `stage-<domain>-<stream>-decomposition`, and ask whether to keep it or discard it with `git checkout -- domains/<domain>/streams/<stream>/stream.json`. Wait for the answer.
      - `stage-gate` findings of other streams: do not fix them and do not stop; list them for the person in the report and go on.
      - Never remove a scope key or an approval mark to silence a finding. Fix only findings whose path is `domains/<domain>/streams/<stream>/stream.json` (the file this step changed) and run the check again; stop running it when no finding names that path. Findings in other files: do not fix them; list them in the report.
    - When it prints nothing: do not run the check. Remember the line `check not run: python3 missing` for the report.
16. Commit: run `git add domains/<domain>/streams/<stream>/stream.json`, then `git commit -m "docs(stream): close decomposition of <domain>/<stream>"`.
17. Run `GIT_TERMINAL_PROMPT=0 git pull --rebase origin <default>`. When it reports a conflict, `stream.json` is a shared hand-written file:
    - Run `git rebase --abort`.
    - Show the person both versions with these labels: "default branch": the output of `git show origin/<default>:domains/<domain>/streams/<stream>/stream.json`; "your branch": the output of `git show stage-<domain>-<stream>-decomposition:domains/<domain>/streams/<stream>/stream.json`.
    - Stop and wait for the person.

    After the rebase has finished, run step 15 again. When it leaves findings in `stream.json`, do not amend and do not push; list them for the person and wait. When it made you fix `stream.json`, run `git add domains/<domain>/streams/<stream>/stream.json`, then `git commit --amend --no-edit`.
18. Push and open the merge request by `.agents/rules/merge-requests.md`, with branch `stage-<domain>-<stream>-decomposition` and title `Close decomposition of stream:<domain>/<stream>`. Use `GIT_TERMINAL_PROMPT=0` before `git push`.
19. Report to the person:
    - the branch `stage-<domain>-<stream>-decomposition`;
    - the merge request link, or the instruction to open it;
    - the approval mark you added, and that the stage becomes `ready` only when a person merges the merge request;
    - as the last line, the check result, or `check not run: python3 missing`.

## Stage change
- A stage moves one step at a time. This skill moves a stream only from `decomposition` to `ready`; it never skips a stage and never changes another stage.
- The stage change is its own merge request on branch `stage-<domain>-<stream>-decomposition`. It changes only `stream.json`: the `stage` value and one new approval mark for the stage being closed, `decomposition`.
- The mark names the reviewer the person gave in step 12. Add it only after the person names that reviewer.
- A person reviews and merges the merge request. Nothing merges automatically, and this skill never merges. Until the merge, the default branch keeps stage `decomposition`.
- `python3 tools/check.py` requires, for every closed stage, its gates and its approval mark. After the merge, `decomposition` is closed, so every scope key needs a story and the mark must stay.
- When the scope grows later, `extend` returns the stream to `map` and removes the later marks; this skill does not do that.

## Without Python
1. In step 5, subtract by hand instead of running `python3 tools/check.py --remaining`.
2. Skip `python3 tools/check.py` everywhere, and follow the `## Without Python` section of `.agents/skills/task-new/SKILL.md` for each story.
3. End the report with the line:

check not run: python3 missing
