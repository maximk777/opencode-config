# Branches and merge requests

- Never commit to the default branch. Create a branch, push it and open a merge request.
- Branch names: `repos-add-<name>`, `adr-NNNN-<slug>`, `extend-<kind>-<name>`, `work/<ID>`.
- A person reviews and merges every merge request; nothing merges automatically.
- Open the merge request by `params.forge` in `.agents/kit.json`: `gitlab` pushes with `git push -u origin <branch> -o merge_request.create -o merge_request.title="<title>"`; `github` runs `git push -u origin <branch>` and then `gh pr create --fill`; `git` runs `git push -u origin <branch>`, prints the branch name and asks the person to open the request.
- Before pushing, run `git pull --rebase origin <default branch>` and resolve conflicts by `.agents/rules/file-ownership.md`.
