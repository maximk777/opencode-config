# Keys and links

- Link to a workspace entity as `[key](relative path)`. The key is authoritative; the path must point to the entity.
- `adr:NNNN` points to `docs/adr/NNNN-<slug>.md`.
- `diagram:<name>` points to `docs/diagrams/<name>.md`, or to the URL registered for it in `docs/diagrams/external.json`.
- `repo:<name>` or `repo:<name>:<path>#<operation>` names an entry of `repos.json`. Never reference code by line numbers.
- `stand:<name>` names an entry of `environments.json`; link it to `environments.json`.
- `domain:<name>` points to `domains/<name>/README.md`.
- A tracker id that matches `id_pattern` in `tracker/tracker.json` links to the issue URL built from `url`, or to `work/<ID>/record.md`.
- Never write absolute home paths such as `/Users/<name>/` or `/home/<name>/`.
- Never write a stand base URL as plain text outside `environments.json`; use its `stand:` key.
- `python3 tools/check.py` reports broken links as `key-resolve`, home paths as `home-path` and stand addresses as `stand-string`.
