---
name: ui-designer
description: Use when a screen spec (MAP entry, pattern name or free-form description) must become browser-viewable mockups, or mockups/manifests must be validated, regenerated or served.
---
# ui-designer

## When to use

- Turn a MAP screen spec into browser-viewable artboards.
- Iterate on mockup feedback after a user reviews the gallery.
- Regenerate or check an existing `mockups/` directory.

The skill works in any directory that has a MAP-like manifest; it assumes no other layout.

## Steps

1. Locate the project's MAP-like manifest and its `mockups/` directory. The skill works in any directory with a MAP; no other layout assumption.
2. Kit selection: read `.designer.json` next to the MAP (`kit`, `kit_version`, `tokens`); an absent file means `plain-tokens`. A per-run override from the user wins.
3. Invoke the `ui-designer` subagent with the target dir, MAP path, screen keys and optional kit override. The subagent owns rendering and validation; do not render artboards yourself.
4. After it returns: run `~/.config/opencode/bin/designer-validate <mockups> --map <MAP>` (must be green), then `~/.config/opencode/bin/designer-gallery <mockups> --map <MAP>`, then `~/.config/opencode/bin/designer-serve <mockups>` and give the user the URL.
5. Feedback loop: the user comments on the gallery; pass each comment back to the subagent as a new invocation listing the screens to change; re-run validate+gallery; serve prints a fresh URL (or reuse the running server and refresh).
6. First use in a project: `~/.config/opencode/bin/designer-kit ensure <mockups> <kit> <version>` after choosing the kit. Kits available in the machine cache: `plain-tokens`, `antd`, `tailwind-daisyui` (see `~/.config/opencode/bin/designer-kit list`).

## Verify

Command: run all three scripts by their full path and check their green markers.

- `~/.config/opencode/bin/designer-validate <mockups> --map <MAP>` exits 0 with no findings.
- `~/.config/opencode/bin/designer-gallery <mockups> --map <MAP>` writes the generated files (`index.html`, `feature/*`, `map.html`, `MOCKUPS.md`).
- `~/.config/opencode/bin/designer-serve <mockups>` prints a `designer: http://127.0.0.1:<port>/index.html` URL.

## Pitfalls

- Never reference a CDN or any http(s) URL inside artboards; vendor only.
- Never hand-edit generated files (`index.html`, `feature/*`, `map.html`, `MOCKUPS.md`); regenerate them with the gallery script.
- Kit versions are pinned in the manifest; changing a version is an explicit manifest update plus a `sync` run, never an in-place vendor edit.
- A single artboard opens via `file://`; the gallery and map view are meant for the local server.

## Templates

- templates/screen-spec.md - free-form screen spec used when no MAP row exists
- templates/designer-json.md - commented `.designer.json` example (kit, kit_version, tokens)
