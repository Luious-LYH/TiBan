from __future__ import annotations

from pathlib import Path


def test_local_launcher_provisions_factory_dependencies_before_worker() -> None:
    """Keep the documented local entry point aligned with Factory's real queue path."""

    code_root = Path(__file__).resolve().parents[2]
    launcher = (code_root / "scripts" / "Start-Web-Demo.ps1").read_text(encoding="utf-8")

    assert '$env:ENDO_DEMO_QBANK_BOOTSTRAP = "false"' in launcher
    assert '$env:ENDO_DEMO_QBANK_BOOTSTRAP = "true"' not in launcher
    assert "compose up -d redis qdrant" in launcher
    assert 'Wait-HttpOk -Url "http://127.0.0.1:$qdrantPort/collections"' in launcher
    assert "Start-FactoryWorker" in launcher
    assert "dramatiq" in launcher
