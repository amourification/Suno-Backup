"""
ui/main_window.py — Main window layout. UI only; no business logic.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QFileDialog, QSplitter, QFrame,
    QListWidget, QListWidgetItem, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QPixmap, QIcon, QColor, QTextCursor

from .theme import (
    SPACE_4, SPACE_8, SPACE_12, SPACE_16, SPACE_24,
    FONT_FAMILY, FONT_FAMILY_MONO,
    FONT_TITLE_SIZE, FONT_HEADING_SIZE, FONT_BODY_SIZE,
    FONT_LABEL_SIZE, FONT_SMALL_SIZE, FONT_MONO_SIZE,
    BG_MAIN, BG_CARD, BG_PANEL, BG_SIDEBAR, BG_INPUT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_DISABLED,
    SIDEBAR_FG, SIDEBAR_FG_MUTED, SIDEBAR_FG_DIM,
    ACCENT, ACCENT_LIGHT,
    BORDER, BORDER_DARK, BORDER_FOCUS,
    LOG_BG, LOG_FG,
    RADIUS_MD, RADIUS_LG, RADIUS_SM,
    SUCCESS, ERROR, WARNING, INFO,
)
from .components import (
    SectionHeader, StyledInput, SidebarInput,
    ModernButton, StyledCheckBox, BadgeLabel, Divider,
)


def _font(family: str, size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    return QFont(family, size, weight)


class MainWindow(QMainWindow):
    """Main application window. Builds UI only; caller wires logic."""

    def __init__(self, default_output_dir: str, icon_path: Path | None = None):
        super().__init__()
        self.setWindowTitle("Suno Backup")
        self.setMinimumSize(820, 560)
        self.resize(1080, 720)
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG_MAIN}; }}")

        self._icon_path = icon_path
        self._default_output_dir = default_output_dir

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_body(root)
        self._build_statusbar(root)
        self._set_app_icon()

    def _set_app_icon(self):
        if self._icon_path and self._icon_path.exists():
            try:
                self.setWindowIcon(QIcon(str(self._icon_path)))
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # Body: horizontal splitter → dark sidebar | main content
    # ─────────────────────────────────────────────────────────────────────────

    def _build_body(self, parent: QVBoxLayout):
        h_split = QSplitter(Qt.Orientation.Horizontal)
        h_split.setHandleWidth(1)
        h_split.setStyleSheet(f"QSplitter::handle {{ background-color: {BORDER_DARK}; }}")

        self._build_sidebar(h_split)
        self._build_main(h_split)

        h_split.setSizes([220, 860])
        h_split.setStretchFactor(0, 0)
        h_split.setStretchFactor(1, 1)
        parent.addWidget(h_split, 1)

    # ─────────────────────────────────────────────────────────────────────────
    # Dark sidebar
    # ─────────────────────────────────────────────────────────────────────────

    def _build_sidebar(self, parent: QSplitter):
        outer = QWidget()
        outer.setMinimumWidth(180)
        outer.setMaximumWidth(300)
        outer.setStyleSheet(f"QWidget {{ background-color: {BG_SIDEBAR}; }}")

        # Wrap contents in a scroll area so it survives small heights
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background-color: {BG_SIDEBAR}; border: none; }}
            QScrollBar:vertical {{
                background: {BG_SIDEBAR}; width: 4px; border-radius: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: #4a2518; border-radius: 2px;
            }}
        """)

        inner = QWidget()
        inner.setStyleSheet(f"QWidget {{ background-color: {BG_SIDEBAR}; border: none; }}")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(SPACE_16, SPACE_16, SPACE_16, SPACE_16)
        layout.setSpacing(SPACE_8)

        # ── App identity ──────────────────────────────────────────────────────
        id_row = QHBoxLayout()
        id_row.setSpacing(SPACE_8)
        self._header_icon_label = QLabel()
        self._header_icon_label.setFixedSize(28, 28)
        self._header_icon_label.setScaledContents(True)
        if self._icon_path and self._icon_path.exists():
            pix = QPixmap(str(self._icon_path))
            if not pix.isNull():
                self._header_icon_label.setPixmap(
                    pix.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation))
            else:
                self._header_icon_label.setVisible(False)
        else:
            self._header_icon_label.setVisible(False)
        id_row.addWidget(self._header_icon_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel("Suno Backup")
        title.setFont(_font(FONT_FAMILY, FONT_TITLE_SIZE, QFont.Weight.Medium))
        title.setStyleSheet(f"color: {SIDEBAR_FG}; background: transparent; border: none;")
        title_col.addWidget(title)
        self._vault_status = QLabel("Vault —")
        self._vault_status.setFont(_font(FONT_FAMILY, FONT_SMALL_SIZE))
        self._vault_status.setStyleSheet(f"color: {SIDEBAR_FG_DIM}; background: transparent; border: none;")
        title_col.addWidget(self._vault_status)
        id_row.addLayout(title_col)
        id_row.addStretch()
        badge = BadgeLabel("v2.0")
        id_row.addWidget(badge)
        layout.addLayout(id_row)

        layout.addSpacing(SPACE_12)
        layout.addWidget(Divider(dark=True))
        layout.addSpacing(SPACE_12)

        # ── Output folder ─────────────────────────────────────────────────────
        layout.addWidget(SectionHeader("Output folder", dark=True))
        layout.addSpacing(SPACE_4)
        out_row = QHBoxLayout()
        out_row.setSpacing(SPACE_4)
        self.output_path_edit = SidebarInput(placeholder="Path to suno_library")
        self.output_path_edit.setText(self._default_output_dir)
        out_row.addWidget(self.output_path_edit)
        browse_btn = ModernButton("…", sidebar=True)
        browse_btn.setFixedWidth(30)
        browse_btn.setMinimumWidth(30)
        out_row.addWidget(browse_btn)
        layout.addLayout(out_row)
        browse_btn.clicked.connect(self._on_browse_output)

        layout.addSpacing(SPACE_12)
        layout.addWidget(Divider(dark=True))
        layout.addSpacing(SPACE_12)

        # ── Download formats ──────────────────────────────────────────────────
        layout.addWidget(SectionHeader("Download", dark=True))
        layout.addSpacing(SPACE_4)
        self.check_mp3   = StyledCheckBox("MP3 audio",     dark=True); self.check_mp3.setChecked(True)
        self.check_wav   = StyledCheckBox("WAV audio",     dark=True); self.check_wav.setChecked(True)
        self.check_video = StyledCheckBox("Video (WEBM)",  dark=True); self.check_video.setChecked(True)
        self.check_art   = StyledCheckBox("Cover art",     dark=True); self.check_art.setChecked(True)
        self.check_json  = StyledCheckBox("Metadata JSON", dark=True); self.check_json.setChecked(True)
        for cb in (self.check_mp3, self.check_wav, self.check_video, self.check_art, self.check_json):
            layout.addWidget(cb)

        layout.addSpacing(SPACE_12)
        layout.addWidget(Divider(dark=True))
        layout.addSpacing(SPACE_12)

        # ── WAV delay ─────────────────────────────────────────────────────────
        layout.addWidget(SectionHeader("WAV delay (s)", dark=True))
        layout.addSpacing(SPACE_4)
        delay_row = QHBoxLayout()
        delay_row.setSpacing(SPACE_8)
        self.delay_min_edit = SidebarInput()
        self.delay_min_edit.setPlaceholderText("min")
        self.delay_min_edit.setFixedWidth(48)
        self.delay_min_edit.setText("4")
        delay_row.addWidget(self.delay_min_edit)
        sep = QLabel("–")
        sep.setStyleSheet(f"color: {SIDEBAR_FG_DIM}; background: transparent; border: none;")
        delay_row.addWidget(sep)
        self.delay_max_edit = SidebarInput()
        self.delay_max_edit.setPlaceholderText("max")
        self.delay_max_edit.setFixedWidth(48)
        self.delay_max_edit.setText("8")
        delay_row.addWidget(self.delay_max_edit)
        delay_row.addStretch()
        layout.addLayout(delay_row)

        layout.addStretch()
        layout.addWidget(Divider(dark=True))
        layout.addSpacing(SPACE_8)

        # ── Action buttons ────────────────────────────────────────────────────
        self.scan_btn        = ModernButton("Scan Library",  primary=True)
        self.start_btn       = ModernButton("Start Backup",  primary=True)
        self.stop_btn        = ModernButton("Stop",          sidebar=True)
        self.stop_btn.setEnabled(False)
        self.clear_vault_btn = ModernButton("Clear Vault",   destructive=True)

        for btn in (self.scan_btn, self.start_btn, self.stop_btn, self.clear_vault_btn):
            layout.addWidget(btn)

        scroll.setWidget(inner)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll)
        parent.addWidget(outer)

    # ─────────────────────────────────────────────────────────────────────────
    # Main content area
    # ─────────────────────────────────────────────────────────────────────────

    def _build_main(self, parent: QSplitter):
        main = QWidget()
        main.setStyleSheet(f"QWidget {{ background-color: {BG_MAIN}; border: none; }}")

        # Vertical splitter: top (progress + song list) | bottom (log)
        v_split = QSplitter(Qt.Orientation.Vertical)
        v_split.setHandleWidth(4)
        v_split.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {BORDER};
                border-top: 1px solid {BORDER};
            }}
            QSplitter::handle:hover {{
                background-color: {ACCENT};
            }}
        """)

        # ── Top pane ──────────────────────────────────────────────────────────
        top_pane = QWidget()
        top_pane.setStyleSheet(f"QWidget {{ background-color: {BG_MAIN}; border: none; }}")
        top_layout = QVBoxLayout(top_pane)
        top_layout.setContentsMargins(SPACE_24, SPACE_16, SPACE_24, SPACE_8)
        top_layout.setSpacing(SPACE_12)

        self._build_progress_card(top_layout)

        # Song list header
        song_header = QHBoxLayout()
        song_lbl = QLabel("Songs to download")
        song_lbl.setFont(_font(FONT_FAMILY, FONT_LABEL_SIZE, QFont.Weight.Medium))
        song_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        song_header.addWidget(song_lbl)
        song_header.addStretch()
        self.select_all_btn  = ModernButton("All")
        self.select_all_btn.setMinimumWidth(44)
        self.select_none_btn = ModernButton("None")
        self.select_none_btn.setMinimumWidth(44)
        song_header.addWidget(self.select_all_btn)
        song_header.addWidget(self.select_none_btn)
        top_layout.addLayout(song_header)

        self.song_tree = QTreeWidget()
        self.song_tree.setHeaderLabels(["Title", "ID"])
        self.song_tree.header().setStretchLastSection(False)
        self.song_tree.header().setSectionResizeMode(0, self.song_tree.header().ResizeMode.Stretch)
        self.song_tree.header().setSectionResizeMode(1, self.song_tree.header().ResizeMode.Fixed)
        self.song_tree.setColumnWidth(1, 220)
        self.song_tree.setAlternatingRowColors(False)
        self.song_tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.song_tree.setFont(_font(FONT_FAMILY, FONT_LABEL_SIZE))
        self.song_tree.setRootIsDecorated(False)
        self.song_tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.song_tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {BG_CARD};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_MD}px;
                outline: none;
            }}
            QTreeWidget::item {{ padding: 4px 8px; border: none; }}
            QTreeWidget::item:selected {{ background-color: {ACCENT_LIGHT}; color: {TEXT_PRIMARY}; }}
            QTreeWidget::item:hover {{ background-color: #fdf0eb; }}
            QHeaderView::section {{
                background-color: {BG_PANEL};
                color: {TEXT_TERTIARY};
                border: none;
                border-bottom: 1px solid {BORDER};
                padding: 4px 8px;
                font-size: {FONT_SMALL_SIZE}pt;
            }}
        """)
        top_layout.addWidget(self.song_tree, 1)

        v_split.addWidget(top_pane)

        # ── Bottom pane: log ──────────────────────────────────────────────────
        log_pane = QWidget()
        log_pane.setStyleSheet(f"QWidget {{ background-color: {BG_MAIN}; border: none; }}")
        log_layout = QVBoxLayout(log_pane)
        log_layout.setContentsMargins(SPACE_24, SPACE_8, SPACE_24, SPACE_12)
        log_layout.setSpacing(SPACE_8)

        log_header = QHBoxLayout()
        log_lbl = QLabel("Activity log")
        log_lbl.setFont(_font(FONT_FAMILY, FONT_LABEL_SIZE, QFont.Weight.Medium))
        log_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        log_header.addWidget(log_lbl)
        log_header.addStretch()
        self.copy_log_btn  = ModernButton("Copy")
        self.clear_log_btn = ModernButton("Clear")
        log_header.addWidget(self.copy_log_btn)
        log_header.addWidget(self.clear_log_btn)
        log_layout.addLayout(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.log_text.setFont(_font(FONT_FAMILY_MONO, FONT_MONO_SIZE))
        self.log_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {LOG_BG};
                color: {LOG_FG};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_MD}px;
                padding: 10px;
                selection-background-color: #4a2018;
            }}
            QScrollBar:vertical {{
                background: #1e0e0a; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: #5a2e22; border-radius: 3px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        log_layout.addWidget(self.log_text, 1)

        v_split.addWidget(log_pane)
        v_split.setSizes([420, 280])
        v_split.setStretchFactor(0, 1)
        v_split.setStretchFactor(1, 1)

        outer_layout = QVBoxLayout(main)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(v_split)
        parent.addWidget(main)

    # ─────────────────────────────────────────────────────────────────────────
    # Progress card
    # ─────────────────────────────────────────────────────────────────────────

    def _build_progress_card(self, parent: QVBoxLayout):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_CARD};
                border: 1px solid {BORDER};
                border-radius: {RADIUS_LG}px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(SPACE_16, SPACE_12, SPACE_16, SPACE_12)
        card_layout.setSpacing(SPACE_8)

        # Top row: big percentage + songs label
        top_row = QHBoxLayout()
        self.prog_pct = QLabel("—")
        self.prog_pct.setFont(_font(FONT_FAMILY, FONT_HEADING_SIZE, QFont.Weight.Bold))
        self.prog_pct.setStyleSheet(f"color: {ACCENT}; background: transparent; border: none;")
        top_row.addWidget(self.prog_pct)
        top_row.addSpacing(SPACE_8)
        self.prog_label = QLabel("Songs: —")
        self.prog_label.setFont(_font(FONT_FAMILY, FONT_SMALL_SIZE))
        self.prog_label.setStyleSheet(f"color: {TEXT_TERTIARY}; background: transparent; border: none;")
        self.prog_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self.prog_label)
        top_row.addStretch()

        # Current track
        self.current_track_label = QLabel("—")
        self.current_track_label.setFont(_font(FONT_FAMILY, FONT_HEADING_SIZE, QFont.Weight.Medium))
        self.current_track_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; background: transparent; border: none;")
        self.current_track_label.setWordWrap(False)
        self.current_track_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(self.current_track_label, 1)
        card_layout.addLayout(top_row)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: {BG_PANEL}; border-radius: 3px; border: none; }}
            QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 3px; }}
        """)
        card_layout.addWidget(self.progress_bar)

        # Phase pipeline
        phase_names = ["Metadata", "Cover", "MP3", "Video", "WAV", "Embed"]
        self.phase_labels = []
        phase_row = QHBoxLayout()
        phase_row.setSpacing(SPACE_4)
        for i, name in enumerate(phase_names):
            lb = QLabel(name)
            lb.setFont(_font(FONT_FAMILY, FONT_SMALL_SIZE))
            lb.setStyleSheet(f"color: {TEXT_DISABLED}; background: transparent; border: none;")
            self.phase_labels.append(lb)
            phase_row.addWidget(lb)
            if i < len(phase_names) - 1:
                dot = QLabel("›")
                dot.setStyleSheet(f"color: {TEXT_DISABLED}; background: transparent; border: none;")
                phase_row.addWidget(dot)
        phase_row.addStretch()
        card_layout.addLayout(phase_row)

        # Format stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(SPACE_24)
        self.stat_labels = {}
        self.stat_fail_labels = {}
        self.format_bars = {}
        for key, label in [("mp3", "MP3"), ("wav", "WAV"), ("video", "Video"), ("art", "Art")]:
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(label)
            lbl.setFont(_font(FONT_FAMILY, FONT_SMALL_SIZE))
            lbl.setStyleSheet(f"color: {TEXT_TERTIARY}; background: transparent; border: none;")
            col.addWidget(lbl)

            cnt_row = QHBoxLayout()
            cnt_row.setSpacing(SPACE_4)
            num = QLabel("0")
            num.setFont(_font(FONT_FAMILY, FONT_BODY_SIZE, QFont.Weight.Medium))
            num.setStyleSheet(f"color: {SUCCESS}; background: transparent; border: none;")
            self.stat_labels[key] = num
            cnt_row.addWidget(num)
            fail = QLabel("")
            fail.setFont(_font(FONT_FAMILY, FONT_SMALL_SIZE))
            fail.setStyleSheet(f"color: {ERROR}; background: transparent; border: none;")
            self.stat_fail_labels[key] = fail
            cnt_row.addWidget(fail)
            cnt_row.addStretch()
            col.addLayout(cnt_row)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFixedHeight(3)
            bar.setTextVisible(False)
            bar.setStyleSheet(f"""
                QProgressBar {{ background-color: {BG_PANEL}; border-radius: 1px; border: none; }}
                QProgressBar::chunk {{ background-color: {SUCCESS}; border-radius: 1px; }}
            """)
            self.format_bars[key] = bar
            col.addWidget(bar)
            stats_row.addLayout(col)
        stats_row.addStretch()
        card_layout.addLayout(stats_row)

        parent.addWidget(card)

    # ─────────────────────────────────────────────────────────────────────────
    # Status bar
    # ─────────────────────────────────────────────────────────────────────────

    def _build_statusbar(self, parent: QVBoxLayout):
        bar = QWidget()
        bar.setFixedHeight(28)
        bar.setStyleSheet(f"""
            QWidget {{
                background-color: {BG_SIDEBAR};
                border-top: 1px solid {BORDER_DARK};
            }}
        """)
        h = QHBoxLayout(bar)
        h.setContentsMargins(SPACE_16, 0, SPACE_16, 0)

        self.status_label = QLabel("Ready")
        self.status_label.setFont(_font(FONT_FAMILY, FONT_SMALL_SIZE))
        self.status_label.setStyleSheet(
            f"color: {SIDEBAR_FG_DIM}; background: transparent; border: none;")
        h.addWidget(self.status_label)
        h.addStretch()

        ver = QLabel("Suno Backup v2.0")
        ver.setFont(_font(FONT_FAMILY, FONT_SMALL_SIZE))
        ver.setStyleSheet(f"color: {SIDEBAR_FG_DIM}; background: transparent; border: none;")
        h.addWidget(ver)

        parent.addWidget(bar)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Output folder", self.output_path_edit.text())
        if path:
            self.output_path_edit.setText(path)

    # ── Controller interface ──────────────────────────────────────────────────

    def get_output_dir(self) -> str:
        return self.output_path_edit.text().strip() or self._default_output_dir

    def set_output_dir(self, path: str):
        self.output_path_edit.setText(path)

    def get_download_flags(self):
        return {
            "download_mp3":   self.check_mp3.isChecked(),
            "download_wav":   self.check_wav.isChecked(),
            "download_video": self.check_video.isChecked(),
            "download_art":   self.check_art.isChecked(),
            "download_json":  self.check_json.isChecked(),
        }

    def set_download_flags(self, flags: dict):
        self.check_mp3.setChecked(flags.get("download_mp3", True))
        self.check_wav.setChecked(flags.get("download_wav", True))
        self.check_video.setChecked(flags.get("download_video", True))
        self.check_art.setChecked(flags.get("download_art", True))
        self.check_json.setChecked(flags.get("download_json", True))

    def get_wav_delay(self) -> tuple[float, float]:
        try:
            mn = float(self.delay_min_edit.text() or 4)
        except ValueError:
            mn = 4.0
        try:
            mx = float(self.delay_max_edit.text() or 8)
        except ValueError:
            mx = 8.0
        return (mn, mx)

    def set_wav_delay(self, min_val: float, max_val: float):
        self.delay_min_edit.setText(str(int(min_val)) if min_val == int(min_val) else str(min_val))
        self.delay_max_edit.setText(str(int(max_val)) if max_val == int(max_val) else str(max_val))

    def set_vault_status(self, text: str, color: str | None = None):
        self._vault_status.setText(text)
        style = f"color: {color};" if color else f"color: {SIDEBAR_FG_DIM};"
        self._vault_status.setStyleSheet(f"{style} background: transparent; border: none;")

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_progress(self, current: int, total: int, pct: int | None = None):
        self.prog_label.setText(f"Songs: {current} / {total}" if total else "Songs: —")
        if pct is not None:
            self.progress_bar.setValue(pct)
            self.prog_pct.setText(f"{pct}%")

    def set_current_track(self, title: str | None):
        if not title:
            self.current_track_label.setText("—")
            self.set_phase_step(-1)
            return
        short = (title[:50] + "…") if len(title) > 50 else title
        self.current_track_label.setText(short)

    def set_phase_step(self, step: int):
        for i, lb in enumerate(self.phase_labels):
            if step < 0:
                lb.setStyleSheet(f"color: {TEXT_DISABLED}; background: transparent; border: none;")
            elif i < step:
                lb.setStyleSheet(f"color: {SUCCESS}; background: transparent; border: none;")
            elif i == step:
                lb.setStyleSheet(
                    f"color: {ACCENT}; font-weight: bold; background: transparent; border: none;")
            else:
                lb.setStyleSheet(f"color: {TEXT_DISABLED}; background: transparent; border: none;")

    def set_stat(self, key: str, value):
        if key in self.stat_labels:
            self.stat_labels[key].setText(str(value) if value else "0")

    def set_stat_fail(self, key: str, fail_count: int):
        if key in self.stat_fail_labels:
            lb = self.stat_fail_labels[key]
            if fail_count and fail_count > 0:
                lb.setText(f"  {fail_count} ✗")
                lb.setVisible(True)
            else:
                lb.setText("")
                lb.setVisible(False)

    def set_format_progress(self, key: str, value: int):
        if key in self.format_bars:
            self.format_bars[key].setValue(min(100, max(0, value)))

    def log_append(self, text: str, color: str | None = None):
        if color:
            self.log_text.append(f'<span style="color:{color}">{text}</span>')
        else:
            self.log_text.append(text)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()

    def log_clear(self):
        self.log_text.clear()

    def log_plain_text(self) -> str:
        return self.log_text.toPlainText()

    def set_running(self, running: bool):
        self.scan_btn.setEnabled(not running)
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def song_tree_clear(self):
        self.song_tree.clear()

    def song_tree_add(self, song_id: str, title: str):
        item = QTreeWidgetItem([title[:80], song_id])
        item.setData(0, Qt.ItemDataRole.UserRole, song_id)
        self.song_tree.addTopLevelItem(item)

    def get_selected_song_ids(self) -> list[str]:
        return [item.text(1) for item in self.song_tree.selectedItems()]

    def select_all_songs(self):
        self.song_tree.selectAll()

    def select_none_songs(self):
        self.song_tree.clearSelection()

    def song_tree_count(self) -> int:
        return self.song_tree.topLevelItemCount()

    # Compatibility stubs for older controller calls
    def add_activity_event(self, message: str, kind: str = "info"):
        color_map = {"success": SUCCESS, "error": ERROR, "warning": WARNING, "info": INFO}
        self.log_append(message, color_map.get(kind))

    def set_show_log_visible(self, visible: bool):
        pass  # log is always visible now
