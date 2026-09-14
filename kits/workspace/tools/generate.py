#!/usr/bin/env python3
"""Regenerate adapters, the repository table, the alias index, map tables and breakdowns of a workspace."""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path  # noqa: E402

from wslib import common, gen_adapters, gen_maps, gen_tables  # noqa: E402


def render_all(root):
    out = {}
    out.update(gen_adapters.render(root))
    out.update(gen_tables.render(root))
    out.update(gen_maps.render(root))
    return out


def _owned_dir_of(rel):
    """Return the owned dir containing rel, or None when rel lies outside every owned dir."""
    for owned in gen_adapters.OWNED_DIRS:
        if rel == owned or rel.startswith(owned + "/"):
            return owned
    return None


def _unlink_symlinked_dirs(root, owned, rel_dir):
    """Unlink symlinks among the components of rel_dir from the owned dir down; return True when one was removed."""
    # A symlinked output directory would make writes land in the sources; replace it with a real directory.
    # Components above the owned dir (for example .claude or a symlinked .agents) are never touched.
    current = root / owned
    parts = Path(rel_dir).relative_to(owned).parts
    changed = False
    for part in (None,) + parts:
        if part is not None:
            current = current / part
        if current.is_symlink():
            current.unlink()
            changed = True
    return changed


def _delete_stale(root, rendered):
    changed = []
    for owned in gen_adapters.OWNED_DIRS:
        base = root / owned
        if base.is_symlink():
            base.unlink()
            changed.append(owned)
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(str(base)):
            for name in list(dirnames):
                path = Path(dirpath, name)
                if path.is_symlink():
                    path.unlink()
                    dirnames.remove(name)
                    changed.append(path.relative_to(root).as_posix())
            for name in filenames:
                path = Path(dirpath, name)
                rel = path.relative_to(root).as_posix()
                if rel not in rendered or path.is_symlink():
                    path.unlink()
                    if rel not in rendered:
                        changed.append(rel)
    return changed


def _remove_empty_dirs(root):
    for owned in gen_adapters.OWNED_DIRS:
        base = root / owned
        if not base.is_dir():
            continue
        for dirpath, _, _ in os.walk(str(base), topdown=False):
            path = Path(dirpath)
            if path != base and not any(path.iterdir()):
                path.rmdir()


def write_all(root):
    """Write rendered files, delete unrendered files in owned dirs, return changed paths."""
    root = Path(root)
    rendered = render_all(root)
    changed = _delete_stale(root, rendered)
    for rel, data in rendered.items():
        path = root / rel
        owned = _owned_dir_of(rel)
        replaced = False
        if owned is not None:
            replaced = _unlink_symlinked_dirs(root, owned, str(Path(rel).parent))
        if (owned is not None or rel == "CLAUDE.md") and path.is_symlink():
            path.unlink()
            replaced = True
        if owned is not None and path.is_dir():
            # A skill path that changed from folder to file; its files were already deleted and counted as stale.
            shutil.rmtree(str(path))
        if not replaced and path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        changed.append(rel)
    _remove_empty_dirs(root)
    return changed


def main():
    root = common.find_root(Path.cwd())
    if root is None:
        print("generate: not inside a workspace (no .agents/kit.json)", file=sys.stderr)
        return 2
    changed = write_all(root)
    print(f"generated: {len(changed)} files changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
