"""
ui/components.py — Reusable styled Qt components.
"""

from PySide6.QtWidgets import QPushButton, QFrame, QLabel, QLineEdit, QCheckBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from .theme import (
    RADIUS_SM, RADIUS_MD,
    FONT_FAMILY, FONT_BODY_SIZE, FONT_LABEL_SIZE, FONT_SMALL_SIZE, FONT_HEADING_SIZE,
    BG_CARD, BG_PANEL, BG_INPUT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_DISABLED,
    SIDEBAR_FG, SIDEBAR_FG_MUTED, SIDEBAR_FG_DIM,
    ACCENT, ACCENT_HOVER,
    BORDER, BORDER_DARK, BORDER_FOCUS,
)


def _font(family: str, size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    return QFont(family, size, weight)


# ── Divider (light surface) ───────────────────────────────────────────────────

class Divider(QFrame):
    def __init__(self, parent=None, dark: bool = False):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        color = BORDER_DARK if dark else BORDER
        self.setStyleSheet(f"background-color: {color}; border: none;")


# ── SectionHeader ─────────────────────────────────────────────────────────────

class SectionHeader(QLabel):
    """Muted uppercase section label."""
    def __init__(self, text: str, parent=None, dark: bool = False):
        super().__init__(text.upper(), parent)
        self.setFont(_font(FONT_FAMILY, FONT_SMALL_SIZE, QFont.Weight.Medium))
        color = SIDEBAR_FG_DIM if dark else TEXT_TERTIARY
        self.setStyleSheet(f"color: {color}; letter-spacing: 0.5px; background: transparent; border: none;")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


# ── StyledInput ───────────────────────────────────────────────────────────────

class StyledInput(QLineEdit):
    def __init__(self, parent=None, placeholder: str = ""):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFont(_font(FONT_FAMILY, FONT_LABEL_SIZE))
        self.setMinimumHeight(30)
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {BG_INPUT};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_MD}px;
                padding: 0 10px;
                selection-background-color: {ACCENT};
            }}
            QLineEdit:focus {{ border-color: {BORDER_FOCUS}; }}
            QLineEdit:disabled {{ background-color: {BG_PANEL}; color: {TEXT_DISABLED}; }}
        """)


# ── SidebarInput — input that lives on the dark sidebar ──────────────────────

class SidebarInput(QLineEdit):
    def __init__(self, parent=None, placeholder: str = ""):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFont(_font(FONT_FAMILY, FONT_LABEL_SIZE))
        self.setMinimumHeight(30)
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: #3d1e15;
                color: {SIDEBAR_FG};
                border: 1px solid {BORDER_DARK};
                border-radius: {RADIUS_MD}px;
                padding: 0 10px;
                selection-background-color: {ACCENT};
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
            QLineEdit::placeholder {{ color: {SIDEBAR_FG_DIM}; }}
        """)


# ── ModernButton ──────────────────────────────────────────────────────────────

class ModernButton(QPushButton):
    """Solid button. 6px radius, no gradients."""
    def __init__(self, text: str, parent=None, *, primary: bool = False,
                 destructive: bool = False, sidebar: bool = False):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(_font(FONT_FAMILY, FONT_BODY_SIZE))
        self.setMinimumHeight(30)
        self.setMinimumWidth(72)
        self._primary = primary
        self._destructive = destructive
        self._sidebar = sidebar
        self._update_style()

    def _update_style(self):
        if self._destructive:
            bg, bg_h, fg = "#7f1d1d", "#991b1b", "#fca5a5"
        elif self._primary:
            bg, bg_h, fg = ACCENT, ACCENT_HOVER, "#ffffff"
        elif self._sidebar:
            bg, bg_h, fg = "#3d1e15", "#4f2a1e", SIDEBAR_FG
        else:
            bg, bg_h, fg = "#f0ddd6", "#e5cfc8", TEXT_PRIMARY

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: none;
                border-radius: {RADIUS_MD}px;
                padding: 0 14px;
            }}
            QPushButton:hover {{ background-color: {bg_h}; }}
            QPushButton:pressed {{ background-color: {bg}; }}
            QPushButton:disabled {{ background-color: #f0e4e0; color: {TEXT_DISABLED}; }}
        """)


# ── StyledCheckBox ────────────────────────────────────────────────────────────

class StyledCheckBox(QCheckBox):
    def __init__(self, text: str, parent=None, dark: bool = False):
        super().__init__(text, parent)
        self.setFont(_font(FONT_FAMILY, FONT_BODY_SIZE))
        fg = SIDEBAR_FG if dark else TEXT_SECONDARY
        bg_ind = "#3d1e15" if dark else BG_INPUT
        border = BORDER_DARK if dark else BORDER
        self.setStyleSheet(f"""
            QCheckBox {{ color: {fg}; spacing: 6px; background: transparent; }}
            QCheckBox::indicator {{
                width: 14px; height: 14px;
                border: 1px solid {border};
                border-radius: 3px;
                background-color: {bg_ind};
            }}
            QCheckBox::indicator:checked {{
                background-color: {ACCENT};
                border-color: {ACCENT};
            }}
            QCheckBox:disabled {{ color: {TEXT_DISABLED}; }}
        """)


# ── BadgeLabel ────────────────────────────────────────────────────────────────

class BadgeLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFont(_font(FONT_FAMILY, FONT_SMALL_SIZE))
        self.setStyleSheet(f"""
            QLabel {{
                background-color: #3d1e15;
                color: {SIDEBAR_FG_MUTED};
                border-radius: {RADIUS_SM}px;
                padding: 1px 6px;
            }}
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
