"""Automated test suite validating design tokens and CSS architecture.

Validates:
1. Integrity and syntax of src/static/css/custom.css via tinycss2 AST.
2. Complete definition of Design System tokens in :root and .dark scopes.
3. Shadow-as-border utility conventions (zero 1px border shifts).
4. Modern 2026 CSS features (:user-valid, :has(), View Transitions API).
5. Accessibility & motion safety (@media (prefers-reduced-motion: reduce)).
"""

import re
from pathlib import Path

import tinycss2

CSS_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "static" / "css" / "custom.css"
)
OUTPUT_CSS_PATH = (
    Path(__file__).resolve().parent.parent / "src" / "static" / "css" / "output.css"
)


def _get_css_text() -> str:
    assert CSS_PATH.exists(), f"custom.css not found at {CSS_PATH}"
    return CSS_PATH.read_text(encoding="utf-8")


def test_custom_css_file_exists():
    """Verify custom.css exists on disk."""
    assert CSS_PATH.exists()
    assert CSS_PATH.stat().st_size > 0


def test_custom_css_syntax_tinycss2():
    """Verify that custom.css parses with zero syntactic error rules."""
    css_text = _get_css_text()
    rules, _ = tinycss2.parse_stylesheet_bytes(
        css_text.encode("utf-8"),
        skip_comments=False,
        skip_whitespace=False,
    )
    error_rules = [r for r in rules if r.type == "error"]
    assert len(error_rules) == 0, f"Syntactic errors found: {error_rules}"


def test_root_design_tokens():
    """Verify all mandatory design tokens exist in the :root scope."""
    css_text = _get_css_text()
    root_match = re.search(r":root\s*\{([^}]+)\}", css_text)
    assert root_match is not None, ":root token block not found in custom.css"
    root_block = root_match.group(1)

    required_root_tokens = [
        ("--color-canvas-base", "#FAF9F5"),
        ("--color-canvas-elevated", "#FFFFFF"),
        ("--color-text-primary", "#141413"),
        ("--color-text-secondary", "rgb(20, 20, 19, 0.64)"),
        ("--color-text-inverse", "#FFFFFF"),
        ("--color-accent-terracotta", "#E05236"),
        ("--color-border-faint", "rgba(0, 0, 0, 0.08)"),
        ("--color-border-strong", "#2E2E2E"),
        ("--color-focus-ring", "rgba(14, 42, 245, 0.4)"),
        ("--font-sans", "Geist Sans"),
        ("--font-mono", "Geist Mono"),
        ("--shadow-border", "var(--color-border-faint)"),
        ("--shadow-card", "var(--color-border-faint)"),
        ("--shadow-focus", "var(--color-focus-ring)"),
    ]

    for token, expected_val in required_root_tokens:
        assert token in root_block, f"Missing token {token} in :root"
        assert expected_val in root_block, f"Value mismatch for token {token}"

    # Verify Display-P3 color gamuts
    assert "--color-accent-primary" in root_block
    assert "color(display-p3" in root_block
    assert "--color-accent-hover" in root_block


def test_dark_theme_tokens():
    """Verify OLED black dark mode tokens in the .dark selector."""
    css_text = _get_css_text()
    dark_match = re.search(r"\.dark\s*\{([^}]+)\}", css_text)
    assert dark_match is not None, ".dark token block not found in custom.css"
    dark_block = dark_match.group(1)

    required_dark_tokens = [
        ("--color-canvas-base", "#000000"),
        ("--color-canvas-elevated", "#111110"),
        ("--color-text-primary", "#EDEDED"),
        ("--color-text-secondary", "rgba(237, 237, 237, 0.64)"),
        ("--color-text-inverse", "#141413"),
        ("--color-accent-terracotta", "#E05236"),
        ("--color-border-faint", "rgba(255, 255, 255, 0.08)"),
        ("--color-border-strong", "#E5E5E5"),
        ("--color-focus-ring", "rgba(14, 42, 245, 0.6)"),
    ]

    for token, expected_val in required_dark_tokens:
        assert token in dark_block, f"Missing dark token {token} in .dark"
        assert expected_val in dark_block, f"Value mismatch for dark token {token}"


def test_shadow_as_border_utilities():
    """Verify shadow-as-border utility classes exist and rely on tokens."""
    css_text = _get_css_text()
    assert ".shadow-border-subtle" in css_text
    assert "var(--shadow-border)" in css_text
    assert ".shadow-card-elevated" in css_text
    assert "var(--shadow-card)" in css_text
    assert ".shadow-focus-ring" in css_text
    assert "var(--shadow-focus)" in css_text


def test_modern_css_state_selectors():
    """Verify modern selectors (:user-valid, :user-invalid, :has())."""
    css_text = _get_css_text()
    assert ":user-valid" in css_text
    assert ":user-invalid" in css_text
    assert ":has(:focus-visible)" in css_text


def test_animations_and_view_transitions():
    """Verify terracotta snap animation and View Transitions API rules."""
    css_text = _get_css_text()
    assert "@view-transition" in css_text
    assert "::view-transition-group(root)" in css_text
    assert "@keyframes snap-terracotta-pulse" in css_text
    assert ".snap-pulse" in css_text


def test_reduced_motion_accessibility():
    """Verify prefers-reduced-motion overrides animations safely."""
    css_text = _get_css_text()
    assert "@media (prefers-reduced-motion: reduce)" in css_text
    assert "animation: none !important;" in css_text


def test_output_css_compiled_and_valid():
    """Verify output.css exists and contains built classes."""
    assert OUTPUT_CSS_PATH.exists()
    assert OUTPUT_CSS_PATH.stat().st_size > 1000
