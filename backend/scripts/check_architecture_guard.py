"""Small CI guard for the v2.0 modular-monolith boundaries."""

from __future__ import annotations

from pathlib import Path

from app.domains import DOMAIN_MANIFESTS


FORBIDDEN_APPLICATION_IMPORTS = (
    "fastapi",
    "sqlalchemy",
    "qdrant",
    "dramatiq",
    "app.adapters",
    "app.routers",
)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "app" / "application"
    violations: list[str] = []
    for source in root.rglob("*.py"):
        content = source.read_text(encoding="utf-8")
        for name in FORBIDDEN_APPLICATION_IMPORTS:
            if f"import {name}" in content or f"from {name}" in content:
                violations.append(f"{source}: forbidden import {name}")
    required_domains = {"endoscopy", "general_science"}
    missing = required_domains - set(DOMAIN_MANIFESTS)
    if missing:
        violations.append(f"missing required domain manifests: {sorted(missing)}")
    if violations:
        raise SystemExit("Architecture guard failed:\n" + "\n".join(violations))
    print(f"Architecture guard PASS: {len(list(root.rglob('*.py')))} application modules; domains={sorted(DOMAIN_MANIFESTS)}")


if __name__ == "__main__":
    main()
