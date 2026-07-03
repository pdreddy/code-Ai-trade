from pathlib import Path

FORBIDDEN_LEGACY_MARKERS = tuple(
    "".join(parts)
    for parts in (
        ("K", "OC"),
        ("K", "oc"),
        ("ko", "c3"),
        ("ko", "c-quant"),
        ("K", "OC3"),
        ("K", "OC S2"),
        ("K", "OC Season"),
        ("ko", "c_s2"),
        ("ko", "c2"),
    )
)
SKIPPED_PARTS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "__pycache__",
}


def test_repository_does_not_contain_legacy_project_branding() -> None:
    offenders: list[str] = []
    for path in Path(".").rglob("*"):
        if not path.is_file() or any(part in SKIPPED_PARTS for part in path.parts):
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        for marker in FORBIDDEN_LEGACY_MARKERS:
            if marker in text:
                offenders.append(f"{path}:{marker}")
    assert offenders == []
