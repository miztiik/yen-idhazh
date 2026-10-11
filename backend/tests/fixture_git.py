"""How can fixture Git target only its own repository, never an enclosing checkout?"""

from pathlib import Path


def command(repo: Path, *args: str) -> list[str]:
    root = repo.resolve()
    argv = ["git", "-c", "core.longpaths=true"]
    if (root / ".git").exists():
        return [*argv, "-C", str(root), *args]
    if (root / "HEAD").is_file() and (root / "objects").is_dir():
        return [*argv, "--git-dir", str(root), *args]
    index = 0
    while index < len(args) and args[index] == "-c":
        index += 2
    if index < len(args) and args[index] in {"init", "clone"}:
        return [*argv, "-C", str(root), *args]
    raise ValueError(f"fixture repository was not initialized: {root}")
