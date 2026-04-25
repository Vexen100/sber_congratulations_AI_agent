from __future__ import annotations

from pathlib import Path


def test_static_css_modules_exist():
    base = Path(__file__).resolve().parents[1] / "app" / "web" / "static" / "css"
    assert (base / "main.css").exists()
    assert (base / "base" / "variables.css").exists()
    assert (base / "base" / "typography.css").exists()
    assert (base / "layout" / "shell.css").exists()
    assert (base / "components" / "cards.css").exists()
    assert (base / "components" / "navigation.css").exists()
    assert (base / "components" / "buttons.css").exists()
    assert (base / "components" / "tables.css").exists()
    assert (base / "components" / "charts.css").exists()
    assert (base / "components" / "timer.css").exists()
    assert (base / "utilities" / "helpers.css").exists()
    assert (base / "utilities" / "kpi.css").exists()
    assert (base / "vibe-team-logo.svg").exists()
