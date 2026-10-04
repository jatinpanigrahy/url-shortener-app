"""Empirical Adversarial Contrast & WCAG Verification Suite for docs/design_system_2.md.

Challenger 2 (Round 2 - Contrast & WCAG Challenger):
1. Mathematical relative luminance & contrast ratio calculation oracle (W3C WCAG 2.1).
2. Verification of interactive control borders (--raw-border-control) vs canvas (>= 3.0:1).
3. Verification of dark accent text (#6B8BFF) vs canvas/card (>= 4.5:1).
4. Verification of form error text (#DC2626 / #F87171) vs canvas (>= 4.5:1).
5. Verification of muted text in light and dark modes (>= 4.5:1).
6. Verification of dark Primary Action button text (#141413) on #4D74FF (>= 4.5:1).
7. Table reconciliation: verify all 25 color pairings in Section 2.2 Table against calculated values.
8. Verification of touch targets (>= 44px) across tokens and CSS.
9. Verification of prefers-reduced-motion rules.
"""

from pathlib import Path

import pytest

DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "design_system_2.md"


def rel_luminance(r: int, g: int, b: int) -> float:
    """Calculate exact W3C WCAG 2.1 relative luminance for sRGB color."""
    def channel_linear(val: int) -> float:
        c = val / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_lin = channel_linear(r)
    g_lin = channel_linear(g)
    b_lin = channel_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def contrast_ratio(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Calculate WCAG 2.1 contrast ratio between two sRGB colors."""
    l1 = rel_luminance(*c1)
    l2 = rel_luminance(*c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Parse hex string to RGB tuple."""
    hex_clean = hex_str.strip().lstrip("#")
    return (
        int(hex_clean[0:2], 16),
        int(hex_clean[2:4], 16),
        int(hex_clean[4:6], 16),
    )


def composite_alpha(fg: tuple[int, int, int], bg: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    """Alpha composite foreground over background in standard 8-bit sRGB."""
    return tuple(round(alpha * fg[i] + (1.0 - alpha) * bg[i]) for i in range(3))


@pytest.fixture(scope="module")
def doc_text() -> str:
    if DOC_PATH.exists():
        return DOC_PATH.read_text(encoding="utf-8")
    return ""


# ==============================================================================
# 1. INTERACTIVE CONTROL BORDERS (--raw-border-control vs Canvas >= 3.0:1)
# ==============================================================================

def test_control_border_light_mode():
    border_control = hex_to_rgb("#8E8D88")
    canvas_base = hex_to_rgb("#FAF9F5")
    canvas_elevated = hex_to_rgb("#FFFFFF")

    cr_base = contrast_ratio(border_control, canvas_base)
    cr_elevated = contrast_ratio(border_control, canvas_elevated)

    assert cr_base >= 3.0, f"Light control border on canvas base failed: {cr_base:.2f}:1"
    assert round(cr_base, 2) == 3.16
    assert cr_elevated >= 3.0, f"Light control border on elevated failed: {cr_elevated:.2f}:1"
    assert round(cr_elevated, 2) == 3.33


def test_control_border_dark_mode():
    border_control_dark = hex_to_rgb("#686764")
    dark_canvas_elevated = hex_to_rgb("#1C1C1A")
    dark_canvas_base = hex_to_rgb("#141413")

    cr_elevated = contrast_ratio(border_control_dark, dark_canvas_elevated)
    cr_base = contrast_ratio(border_control_dark, dark_canvas_base)

    assert cr_elevated >= 3.0, f"Dark control border on elevated failed: {cr_elevated:.2f}:1"
    assert round(cr_elevated, 2) == 3.02
    assert cr_base >= 3.0, f"Dark control border on base failed: {cr_base:.2f}:1"
    assert round(cr_base, 2) == 3.26


# ==============================================================================
# 2. DARK ACCENT TEXT (#6B8BFF vs Canvas/Card >= 4.5:1)
# ==============================================================================

def test_dark_accent_text_contrast():
    accent_text_dark = hex_to_rgb("#6B8BFF")
    dark_canvas_elevated = hex_to_rgb("#1C1C1A")
    dark_canvas_base = hex_to_rgb("#141413")
    dark_canvas_sunken = hex_to_rgb("#0C0C0B")

    cr_elevated = contrast_ratio(accent_text_dark, dark_canvas_elevated)
    cr_base = contrast_ratio(accent_text_dark, dark_canvas_base)
    cr_sunken = contrast_ratio(accent_text_dark, dark_canvas_sunken)

    assert cr_elevated >= 4.5, f"#6B8BFF on dark card failed: {cr_elevated:.2f}:1"
    assert round(cr_elevated, 2) == 5.50
    assert cr_base >= 4.5, f"#6B8BFF on dark base failed: {cr_base:.2f}:1"
    assert round(cr_base, 2) == 5.94
    assert cr_sunken >= 4.5, f"#6B8BFF on dark sunken failed: {cr_sunken:.2f}:1"
    assert round(cr_sunken, 2) == 6.30


# ==============================================================================
# 3. FORM ERROR TEXT (#DC2626 / #F87171 vs Canvas >= 4.5:1)
# ==============================================================================

def test_form_error_text_light_mode():
    error_text_light = hex_to_rgb("#DC2626")
    canvas_elevated = hex_to_rgb("#FFFFFF")
    canvas_base = hex_to_rgb("#FAF9F5")

    cr_elevated = contrast_ratio(error_text_light, canvas_elevated)
    cr_base = contrast_ratio(error_text_light, canvas_base)

    assert cr_elevated >= 4.5, f"#DC2626 on white card failed: {cr_elevated:.2f}:1"
    assert round(cr_elevated, 2) == 4.83
    assert cr_base >= 4.5, f"#DC2626 on cream canvas failed: {cr_base:.2f}:1"
    assert round(cr_base, 2) == 4.58


def test_form_error_text_dark_mode():
    error_text_dark = hex_to_rgb("#F87171")
    dark_canvas_elevated = hex_to_rgb("#1C1C1A")
    dark_canvas_base = hex_to_rgb("#141413")

    cr_elevated = contrast_ratio(error_text_dark, dark_canvas_elevated)
    cr_base = contrast_ratio(error_text_dark, dark_canvas_base)

    assert cr_elevated >= 4.5, f"#F87171 on dark card failed: {cr_elevated:.2f}:1"
    assert round(cr_elevated, 2) == 6.17
    assert cr_base >= 4.5, f"#F87171 on dark base failed: {cr_base:.2f}:1"
    assert round(cr_base, 2) == 6.66


# ==============================================================================
# 4. MUTED TEXT IN LIGHT AND DARK MODE (>= 4.5:1)
# ==============================================================================

def test_muted_text_light_mode():
    text_primary = hex_to_rgb("#141413")
    canvas_base = hex_to_rgb("#FAF9F5")
    canvas_elevated = hex_to_rgb("#FFFFFF")

    # 60% opacity composited
    composited_base = composite_alpha(text_primary, canvas_base, 0.60)
    composited_elevated = composite_alpha(text_primary, canvas_elevated, 0.60)

    cr_base = contrast_ratio(composited_base, canvas_base)
    cr_elevated = contrast_ratio(composited_elevated, canvas_elevated)

    assert cr_base >= 4.5, f"Light muted text on canvas base failed: {cr_base:.2f}:1"
    assert round(cr_base, 2) == 4.72
    assert cr_elevated >= 4.5, f"Light muted text on elevated failed: {cr_elevated:.2f}:1"
    assert round(cr_elevated, 2) == 4.82


def test_muted_text_dark_mode():
    text_dark_primary = hex_to_rgb("#EDEDEC")
    dark_canvas_elevated = hex_to_rgb("#1C1C1A")
    dark_canvas_base = hex_to_rgb("#141413")

    # 50% opacity composited
    composited_elevated = composite_alpha(text_dark_primary, dark_canvas_elevated, 0.50)
    composited_base = composite_alpha(text_dark_primary, dark_canvas_base, 0.50)

    cr_elevated = contrast_ratio(composited_elevated, dark_canvas_elevated)
    cr_base = contrast_ratio(composited_base, dark_canvas_base)

    assert cr_elevated >= 4.5, f"Dark muted text on elevated failed: {cr_elevated:.2f}:1"
    assert round(cr_elevated, 2) == 4.56
    assert cr_base >= 4.5, f"Dark muted text on base failed: {cr_base:.2f}:1"
    assert round(cr_base, 2) == 4.67


# ==============================================================================
# 5. DARK PRIMARY ACTION BUTTON TEXT ON #4D74FF (>= 4.5:1)
# ==============================================================================

def test_dark_primary_button_text():
    button_bg = hex_to_rgb("#4D74FF")
    dark_ink_text = hex_to_rgb("#141413")
    white_text = hex_to_rgb("#FFFFFF")

    cr_dark_ink = contrast_ratio(dark_ink_text, button_bg)
    cr_white = contrast_ratio(white_text, button_bg)

    # Dark ink text passes
    assert cr_dark_ink >= 4.5, f"Dark ink on #4D74FF failed: {cr_dark_ink:.2f}:1"
    assert round(cr_dark_ink, 2) == 4.62

    # White text fails WCAG AA (confirming adversarial failure mode)
    assert cr_white < 4.5, f"White text unexpectedly passed: {cr_white:.2f}:1"
    assert round(cr_white, 2) == 3.99

    # Test hover state
    hover_bg = hex_to_rgb("#7090FF")
    cr_hover = contrast_ratio(dark_ink_text, hover_bg)
    assert cr_hover >= 4.5, f"Dark ink on hover #7090FF failed: {cr_hover:.2f}:1"
    assert round(cr_hover, 2) == 6.25


# ==============================================================================
# 6. TABLE RECONCILIATION: VERIFY ALL 25 ROWS IN SECTION 2.2 TABLE
# ==============================================================================

def test_section_2_2_table_all_25_pairs():
    expected_pairs = [
        ("Text Primary (Light)", hex_to_rgb("#141413"), hex_to_rgb("#FAF9F5"), 17.50),
        ("Text Primary (Light)", hex_to_rgb("#141413"), hex_to_rgb("#FFFFFF"), 18.43),
        ("Text Secondary (Light)", composite_alpha(hex_to_rgb("#141413"), hex_to_rgb("#FAF9F5"), 0.64), hex_to_rgb("#FAF9F5"), 5.44),
        ("Text Muted (Light, 12px Caption)", composite_alpha(hex_to_rgb("#141413"), hex_to_rgb("#FAF9F5"), 0.60), hex_to_rgb("#FAF9F5"), 4.72),
        ("Text Primary (Dark)", hex_to_rgb("#EDEDEC"), hex_to_rgb("#141413"), 15.74),
        ("Text Primary (Dark)", hex_to_rgb("#EDEDEC"), hex_to_rgb("#1C1C1A"), 14.57),
        ("Text Secondary (Dark)", composite_alpha(hex_to_rgb("#EDEDEC"), hex_to_rgb("#141413"), 0.64), hex_to_rgb("#141413"), 6.96),
        ("Text Muted (Dark, 12px Caption)", composite_alpha(hex_to_rgb("#EDEDEC"), hex_to_rgb("#1C1C1A"), 0.50), hex_to_rgb("#1C1C1A"), 4.56),
        ("Accent Primary (Light)", hex_to_rgb("#0E2AF5"), hex_to_rgb("#FAF9F5"), 7.47),
        ("Button Text Inverse (Light)", hex_to_rgb("#FFFFFF"), hex_to_rgb("#0E2AF5"), 7.87),
        ("Accent Primary Fill (Dark UI)", hex_to_rgb("#4D74FF"), hex_to_rgb("#1C1C1A"), 4.27),
        ("Accent Text Tint (Dark)", hex_to_rgb("#6B8BFF"), hex_to_rgb("#1C1C1A"), 5.50),
        ("Accent Text Tint (Dark)", hex_to_rgb("#6B8BFF"), hex_to_rgb("#141413"), 5.94),
        ("Button Text Inverse (Dark)", hex_to_rgb("#141413"), hex_to_rgb("#4D74FF"), 4.62),
        ("Button Text Hover (Dark)", hex_to_rgb("#141413"), hex_to_rgb("#7090FF"), 6.25),
        ("Decorative Border (Light)", composite_alpha(hex_to_rgb("#141413"), hex_to_rgb("#FAF9F5"), 0.14), hex_to_rgb("#FAF9F5"), 1.34),
        ("Decorative Border (Dark)", composite_alpha((255, 255, 255), hex_to_rgb("#141413"), 0.18), hex_to_rgb("#141413"), 1.72),
        ("Interactive Control Border (Light)", hex_to_rgb("#8E8D88"), hex_to_rgb("#FAF9F5"), 3.16),
        ("Interactive Control Border (Dark)", hex_to_rgb("#686764"), hex_to_rgb("#1C1C1A"), 3.02),
        ("Error Message Text (Light)", hex_to_rgb("#DC2626"), hex_to_rgb("#FFFFFF"), 4.83),
        ("Error Message Text (Dark)", hex_to_rgb("#F87171"), hex_to_rgb("#1C1C1A"), 6.17),
        ("Focus Indicator (Light)", hex_to_rgb("#0E2AF5"), hex_to_rgb("#FFFFFF"), 7.87),
        ("Focus Indicator (Dark)", hex_to_rgb("#4D74FF"), hex_to_rgb("#1C1C1A"), 4.27),
        ("Terracotta Pulse (Light)", hex_to_rgb("#D96B43"), hex_to_rgb("#FAF9F5"), 3.25),
        ("Terracotta Pulse (Dark)", hex_to_rgb("#E07A5F"), hex_to_rgb("#1C1C1A"), 5.79),
    ]

    for name, c1, c2, claimed in expected_pairs:
        cr = contrast_ratio(c1, c2)
        diff = abs(cr - claimed)
        assert diff <= 0.015, f"{name}: calculated {cr:.4f}:1 diverges from claimed {claimed}:1"


# ==============================================================================
# 7. TOUCH TARGETS (>= 44px)
# ==============================================================================

def test_touch_target_declarations(doc_text: str):
    if not doc_text:
        pytest.skip("docs/design_system_2.md not present")
    assert "--target-touch-min: 44px;" in doc_text
    assert ".touch-target {" in doc_text
    assert "min-height: var(--target-touch-min, 44px);" in doc_text
    assert "min-width: var(--target-touch-min, 44px);" in doc_text
    assert "'touch': 'var(--target-touch-min, 44px)'" in doc_text


# ==============================================================================
# 8. PREFERS-REDUCED-MOTION SPECIFICATIONS
# ==============================================================================

def test_reduced_motion_specifications(doc_text: str):
    css_path = Path(__file__).resolve().parent.parent / "src" / "static" / "css" / "custom.css"
    if css_path.exists():
        css_text = css_path.read_text(encoding="utf-8")
        assert "@media (prefers-reduced-motion: reduce)" in css_text
        assert "animation: none !important;" in css_text
    elif doc_text:
        assert "@media (prefers-reduced-motion: reduce)" in doc_text
        assert "animation-duration: 0.01ms !important;" in doc_text
        assert "transition-duration: 0.01ms !important;" in doc_text
        assert "scroll-behavior: auto !important;" in doc_text
        assert ".feed-item-new {" in doc_text
        assert "animation: none !important;" in doc_text
    else:
        pytest.skip("Neither custom.css nor doc present")


# ==============================================================================
# 9. UI CONTRAST TOKENS A11Y STANDARDS (custom.css & token palette)
# ==============================================================================

def test_ui_contrast_tokens_meet_a11y_standards():
    """Verify that UI contrast tokens strictly satisfy WCAG AA contrast standards."""
    # Light theme tokens
    light_canvas_base = hex_to_rgb("#FAF9F5")
    light_canvas_elevated = hex_to_rgb("#FFFFFF")
    light_text_primary = hex_to_rgb("#141413")
    light_text_sec = composite_alpha(light_text_primary, light_canvas_base, 0.64)
    light_border_control = hex_to_rgb("#8E8D88")
    light_accent_primary = hex_to_rgb("#0E2AF5")

    # Dark theme tokens
    dark_canvas_base = hex_to_rgb("#000000")
    dark_canvas_elevated = hex_to_rgb("#111110")
    dark_text_primary = hex_to_rgb("#EDEDED")
    dark_text_sec = composite_alpha(dark_text_primary, dark_canvas_elevated, 0.64)
    dark_border_control = hex_to_rgb("#686764")
    dark_accent_terracotta = hex_to_rgb("#E05236")

    # High-contrast body text validation (WCAG AA >= 4.5:1)
    assert contrast_ratio(light_text_primary, light_canvas_base) >= 4.5
    assert contrast_ratio(light_text_primary, light_canvas_elevated) >= 4.5
    assert contrast_ratio(light_text_sec, light_canvas_base) >= 4.5
    assert contrast_ratio(light_accent_primary, light_canvas_base) >= 4.5

    assert contrast_ratio(dark_text_primary, dark_canvas_base) >= 4.5
    assert contrast_ratio(dark_text_primary, dark_canvas_elevated) >= 4.5
    assert contrast_ratio(dark_text_sec, dark_canvas_elevated) >= 4.5
    assert contrast_ratio(dark_accent_terracotta, dark_canvas_elevated) >= 4.5

    # Interactive UI control border contrast (WCAG non-text contrast >= 3.0:1)
    assert contrast_ratio(light_border_control, light_canvas_base) >= 3.0
    assert contrast_ratio(dark_border_control, dark_canvas_elevated) >= 3.0
