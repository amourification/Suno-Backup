"""
ui/theme.py — Design tokens and typography.
Single source for colors, spacing, radius, and font families.
"""

# ── Spacing (8px rhythm) ─────────────────────────────────────────────────────
SPACE_4  = 4
SPACE_8  = 8
SPACE_12 = 12
SPACE_16 = 16
SPACE_24 = 24
SPACE_32 = 32

# ── Border radius ───────────────────────────────────────────────────────────
RADIUS_SM = 4
RADIUS_MD = 6
RADIUS_LG = 8

# ── Typography ───────────────────────────────────────────────────────────────
FONT_FAMILY        = "Ubuntu"
FONT_FAMILY_MONO   = "Ubuntu Mono"
FONT_FALLBACK      = "Segoe UI"
FONT_FALLBACK_MONO = "Consolas"

FONT_TITLE_SIZE   = 15
FONT_HEADING_SIZE = 14
FONT_BODY_SIZE    = 12
FONT_LABEL_SIZE   = 11
FONT_SMALL_SIZE   = 10
FONT_MONO_SIZE    = 11

# ── Palette ──────────────────────────────────────────────────────────────────
# Main canvas: warm off-white. Sidebar: deep warm brown (high contrast flip).
# This gives immediate visual weight without gradients or gimmicks.

BG_MAIN    = "#fff8f5"   # warm near-white main canvas
BG_CARD    = "#ffffff"   # pure white — elevated
BG_PANEL   = "#fceee8"   # blush inset areas
BG_INPUT   = "#ffffff"
BG_SIDEBAR = "#2b1510"   # deep warm brown — dark sidebar

# Text on light backgrounds
TEXT_PRIMARY   = "#1c0f0b"
TEXT_SECONDARY = "#6b3a30"
TEXT_TERTIARY  = "#a06050"
TEXT_DISABLED  = "#d4b0a8"

# Text on dark sidebar
SIDEBAR_FG        = "#f0e2dc"
SIDEBAR_FG_MUTED  = "#a87060"
SIDEBAR_FG_DIM    = "#6a3f34"

# Accent — logo orange-red, used for active states, primary CTAs, focus
ACCENT        = "#e8420a"
ACCENT_HOVER  = "#c93508"
ACCENT_LIGHT  = "#fde8e0"

# Semantic
SUCCESS    = "#2d6a4f"
SUCCESS_BG = "#d8f3dc"
WARNING    = "#b45309"
WARNING_BG = "#fef3c7"
ERROR      = "#b91c1c"
ERROR_BG   = "#fee2e2"
INFO       = "#0369a1"
INFO_BG    = "#e0f2fe"

# Borders
BORDER       = "#f0d5ca"   # light-side dividers
BORDER_DARK  = "#4a2518"   # dark sidebar dividers
BORDER_FOCUS = "#e8420a"

# Log / terminal — keep intentionally dark, warm-tinted
LOG_BG      = "#140a07"
LOG_FG      = "#f0e0da"
LOG_SUCCESS = "#4ade80"
LOG_ERROR   = "#f87171"
LOG_WARN    = "#fb923c"
LOG_DIM     = "#7a4a40"

# Shadow
SHADOW_COLOR = "rgba(80,20,10,0.08)"
SHADOW_BLUR  = 8
SHADOW_Y     = 2
