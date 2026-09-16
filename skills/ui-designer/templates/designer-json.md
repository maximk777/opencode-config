# .designer.json

Lives next to the MAP (or in the project root). Selects the style kit for every render in the
project. An absent file, or missing fields, means kit `plain-tokens`; a per-run override from the
user wins over both.

```json
{
  "kit": "plain-tokens",
  "kit_version": "1.0.0",
  "tokens": {
    "color-primary": "#1a73e8",
    "color-surface": "#ffffff",
    "font-family": "Inter, system-ui, sans-serif",
    "radius": "8px"
  }
}
```

Fields:

- `kit` - kit name as printed by `~/.config/opencode/bin/designer-kit list`; known kits:
  `plain-tokens`, `antd`, `tailwind-daisyui`.
- `kit_version` - exact pinned version; versions are pre-installed in the machine cache, never
  downloaded at render time.
- `tokens` - optional palette overrides the kit cheat-sheet describes how to apply; omit the field
  to use the kit defaults. Tokens are design decisions: change them once, here, not per artboard.

After changing `kit` or `kit_version`, keep the vendor copies in sync with the manifest pins by
running `~/.config/opencode/bin/designer-kit sync <mockups>`.
