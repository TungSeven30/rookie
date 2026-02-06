"""Static accessibility guardrails for the frontend operations UI.

These checks enforce core WCAG-oriented requirements directly from source:
- Keyboard bypass (skip link) and main landmark target
- Tab semantics on workspace toggles
- Focus-visible styles and minimum touch target sizing
- Accessible naming for critical form controls and actions
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
APP_FILE = REPO_ROOT / "frontend" / "src" / "App.tsx"
OPS_FILE = REPO_ROOT / "frontend" / "src" / "components" / "OperationsWorkspace.tsx"
CSS_FILE = REPO_ROOT / "frontend" / "src" / "index.css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_skip_link_and_main_landmark_present() -> None:
    """App should provide keyboard bypass and explicit main target."""
    content = _read(APP_FILE)
    assert 'href="#app-main"' in content
    assert 'Skip to main content' in content
    assert 'id="app-main"' in content
    assert "tabIndex={-1}" in content


def test_workspace_toggle_uses_tab_semantics() -> None:
    """Workspace switcher should expose tablist/tab semantics."""
    content = _read(APP_FILE)
    assert 'role="tablist"' in content
    assert 'role="tab"' in content
    assert "aria-selected={active}" in content


def test_focus_visible_and_touch_target_tokens_exist() -> None:
    """Buttons and inputs should support focus rings and >=44px targets."""
    css = _read(CSS_FILE)
    # Tailwind token: min-h-11 => 44px (at 4px scale)
    assert "min-h-11" in css
    assert "focus-visible:ring-2" in css
    assert "focus-visible:ring-primary-500" in css
    assert "focus-visible:outline-none" in css


def test_operations_workspace_exposes_accessible_names_for_controls() -> None:
    """Critical operations/review controls must have explicit accessible names."""
    content = _read(OPS_FILE)
    required_labels = [
        "Client name",
        "Client email",
        "Task client",
        "Task type",
        "Assigned agent",
        "Filter by status",
        "Filter by client",
        "Filter by task type",
        "Filter by agent",
        "Agent for status transition",
        "Reason for status transition",
        "Source values JSON",
        "Prepared values JSON",
        "Prior year values JSON",
        "Documented reasons JSON",
        "Injected error fields",
        "Reviewer ID",
        "Feedback tags",
        "Original content",
        "Corrected content",
        "Feedback note",
        "Save reviewer edit as implicit feedback",
        "Save explicit feedback",
    ]
    for label in required_labels:
        assert label in content


def test_feedback_result_announcements_use_live_region() -> None:
    """Feedback save result should announce changes to assistive tech."""
    content = _read(OPS_FILE)
    assert 'aria-live="polite"' in content
