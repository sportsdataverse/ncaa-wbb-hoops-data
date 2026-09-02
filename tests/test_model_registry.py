"""models/REGISTRY.md carries one row per published RAPM estimand and names
its gates. Pure-file parser (ops/ scripts are not importable packages);
bites per-row: delete a tag's row and this fails. WBB-specific: the
UNGATED_SEASONS carve-out must be stated on the league-wide row.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "models" / "REGISTRY.md"

TAGS = ["ncaa_wbb_rapm", "ncaa_wbb_rapm_within_team"]
LEAGUE_GATE_TOKENS = [
    "usable-possession",
    "intercept era band",
    "Torvik",
    "0.89",
    "UNGATED_SEASONS",
    "SE gate",
    "0.92, 0.98",
]


def _rows() -> list[str]:
    text = REGISTRY.read_text(encoding="utf-8")
    return [ln for ln in text.splitlines() if ln.startswith("|") and "---" not in ln]


def test_registry_exists():
    assert REGISTRY.is_file(), "models/REGISTRY.md is missing"


def test_each_estimand_has_a_row():
    rows = _rows()
    for tag in TAGS:
        assert any(f"`{tag}`" in r for r in rows), f"no registry row for {tag}"


def test_league_row_names_its_gates_and_carveout():
    row = next(r for r in _rows() if "`ncaa_wbb_rapm`" in r)
    missing = [t for t in LEAGUE_GATE_TOKENS if t not in row]
    assert not missing, f"league-wide row missing gate tokens: {missing}"


def test_estimands_not_conflated():
    rows = [r for r in _rows() if "rapm" in r]
    assert len(rows) >= 2
    assert all("estimand" in r for r in rows)
