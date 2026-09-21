# Branches and merge requests

- Never commit to the default branch. Create a branch, push it and open a merge request.
- Branch names: `repos-add-<name>`, `adr-NNNN-<slug>`, `extend-<kind>-<name>`, `work/<ID>`, `story-<domain>-<slug>`, `stage-<domain>-<stream>-<stage>` where `<stage>` is the stage being closed, for example `stage-<domain>-<stream>-decomposition`.
- Design merge requests are reviewed: map elements, stories, `stream.json`, `epic.md` and `MAP.md` text. A stage change adds to `approvals` in `stream.json` the approval mark of the stage being closed with the reviewer's name, and the stage moves one step.
- A person reviews and merges every merge request; nothing merges automatically.
- Open the merge request by `params.forge` in `.agents/kit.json`: `gitlab` pushes with `git push -u origin <branch> -o merge_request.create -o merge_request.title="<title>"`; `github` runs `git push -u origin <branch>` and then `gh pr create --fill`; `git` runs `git push -u origin <branch>`, prints the branch name and asks the person to open the request.
- Before pushing, run `git pull --rebase origin <default branch>` and resolve conflicts by `.agents/rules/file-ownership.md`.
