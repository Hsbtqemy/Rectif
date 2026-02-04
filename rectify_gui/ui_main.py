"""Interface graphique principale - PySide6."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import Qt, Signal, QPoint, QPointF, QTimer
from PySide6.QtGui import (
    QImage, QPixmap, QPainter, QColor, QPen, QBrush,
    QWheelEvent, QMouseEvent, QKeyEvent, QDragEnterEvent, QDropEvent,
    QShortcut, QKeySequence,
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QCheckBox, QSlider,
    QFileDialog, QTextEdit, QFrame,
    QSizePolicy,
)

from rectify_gui.image_ops import (
    auto_detect_corners, full_pipeline, get_display_image, SUPPORTED_EXTENSIONS,
)
from rectify_gui.io_meta import load_image_with_meta, save_image_with_meta, build_output_path, ImageMeta
from rectify_gui.models import QueueItem, QueueStatus
from rectify_gui.utils_geom import pts_to_screen, screen_to_pts

logger = logging.getLogger(__name__)

HANDLE_RADIUS = 8
DISPLAY_MAX_DIM = 1200

CHECKBOX_STYLE = """
    QCheckBox {
        font-weight: 600;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
    }
    QCheckBox::indicator:unchecked {
        border: 2px solid #666;
        background: #fff;
        border-radius: 3px;
    }
    QCheckBox::indicator:checked {
        border: 2px solid #2e7d32;
        background: #2e7d32;
        border-radius: 3px;
    }
    QCheckBox::indicator:hover {
        border-color: #2e7d32;
    }
"""


class ImageViewerWidget(QWidget):
    """Widget d'affichage d'image avec zoom, pan et poignées déplaçables."""

    corners_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 250)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._image_bgr: Optional[NDArray[np.uint8]] = None
        self._pixmap: Optional[QPixmap] = None
        self._corners: Optional[NDArray[np.float32]] = None
        self._scale = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._dragging_handle: Optional[int] = None
        self._panning = False
        self._pan_start = QPoint()
        self._auto_failed = False

    def set_image(
        self,
        img_bgr: NDArray[np.uint8],
        corners: Optional[NDArray[np.float32]] = None,
        auto_failed: bool = False,
        show_corners: bool = True,
        preserve_zoom: bool = False,
    ) -> None:
        self._image_bgr = img_bgr
        self._auto_failed = auto_failed
        display = get_display_image(img_bgr, DISPLAY_MAX_DIM)
        h, w = display.shape[:2]
        same_size = (
            preserve_zoom and self._pixmap is not None
            and self._pixmap.width() == w and self._pixmap.height() == h
        )
        bytes_per_line = w * 3
        qimg = QImage(display.data, w, h, bytes_per_line, QImage.Format.Format_RGB888).rgbSwapped()
        self._pixmap = QPixmap.fromImage(qimg)

        if corners is not None and show_corners:
            scale_display = max(display.shape[:2]) / max(img_bgr.shape[:2])
            self._corners = corners * scale_display
        elif show_corners:
            h_d, w_d = display.shape[:2]
            self._corners = np.array([[0, 0], [w_d - 1, 0], [w_d - 1, h_d - 1], [0, h_d - 1]], dtype=np.float32)
        else:
            self._corners = None

        if not same_size:
            self._fit_to_view()
        self.update()

    def get_corners_in_original_scale(self) -> Optional[NDArray[np.float32]]:
        if self._corners is None or self._image_bgr is None:
            return None
        scale_display = max(get_display_image(self._image_bgr, DISPLAY_MAX_DIM).shape[:2]) / max(self._image_bgr.shape[:2])
        return self._corners / scale_display

    def _fit_to_view(self) -> None:
        if self._pixmap is None:
            return
        pw, ph = self._pixmap.width(), self._pixmap.height()
        w, h = self.width(), self.height()
        scale = min(w / pw, h / ph, 2.0)
        self._scale = scale
        self._offset_x = (w - pw * scale) / 2
        self._offset_y = (h - ph * scale) / 2

    def zoom_in(self) -> None:
        if self._pixmap is None:
            return
        self._apply_zoom(1.25, self.width() / 2, self.height() / 2)

    def zoom_out(self) -> None:
        if self._pixmap is None:
            return
        self._apply_zoom(0.8, self.width() / 2, self.height() / 2)

    def zoom_fit(self) -> None:
        self._fit_to_view()
        self.update()

    def _apply_zoom(self, factor: float, anchor_x: float, anchor_y: float) -> None:
        old_scale = self._scale
        new_scale = max(0.2, min(5.0, old_scale * factor))
        if abs(new_scale - old_scale) < 0.01:
            return
        self._offset_x = anchor_x - (anchor_x - self._offset_x) * (new_scale / old_scale)
        self._offset_y = anchor_y - (anchor_y - self._offset_y) * (new_scale / old_scale)
        self._scale = new_scale
        self.update()

    def _hit_handle(self, pos: QPointF) -> Optional[int]:
        if self._corners is None:
            return None
        screen_pts = pts_to_screen(self._corners, self._scale, self._offset_x, self._offset_y)
        for i in range(4):
            sx, sy = screen_pts[i, 0], screen_pts[i, 1]
            if (pos.x() - sx) ** 2 + (pos.y() - sy) ** 2 <= HANDLE_RADIUS**2:
                return i
        return None

    def paintEvent(self, event: object) -> None:
        super().paintEvent(event)
        if self._pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(int(self._offset_x), int(self._offset_y),
            int(self._pixmap.width() * self._scale), int(self._pixmap.height() * self._scale), self._pixmap)
        if self._corners is not None:
            screen_pts = pts_to_screen(self._corners, self._scale, self._offset_x, self._offset_y)
            pen = QPen(QColor(0, 200, 0), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            for i in range(4):
                j = (i + 1) % 4
                painter.drawLine(int(screen_pts[i, 0]), int(screen_pts[i, 1]), int(screen_pts[j, 0]), int(screen_pts[j, 1]))
            brush = QBrush(QColor(255, 100, 100))
            painter.setBrush(brush)
            painter.setPen(QPen(QColor(200, 50, 50), 2))
            for i in range(4):
                x, y = screen_pts[i, 0], screen_pts[i, 1]
                painter.drawEllipse(int(x - HANDLE_RADIUS), int(y - HANDLE_RADIUS), HANDLE_RADIUS * 2, HANDLE_RADIUS * 2)
        if self._auto_failed:
            painter.setPen(QColor(255, 0, 0))
            painter.drawText(20, 30, "Auto-détection échouée - Ajustez manuellement")

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap is None:
            return
        pos = event.position()
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._apply_zoom(factor, pos.x(), pos.y())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_handle(pos)
            if hit is not None:
                self._dragging_handle = hit
            else:
                self._panning = True
                self._pan_start = event.pos()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        if self._dragging_handle is not None:
            new_pt = screen_to_pts(np.array([[pos.x(), pos.y()]], dtype=np.float32), self._scale, self._offset_x, self._offset_y)
            self._corners[self._dragging_handle] = new_pt[0]
            self.corners_changed.emit()
            self.update()
        elif self._panning:
            delta = event.pos() - self._pan_start
            self._offset_x += delta.x()
            self._offset_y += delta.y()
            self._pan_start = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._dragging_handle = None
            self._panning = False

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        if self._pixmap is not None and not self._panning:
            self._fit_to_view()


class MainWindow(QMainWindow):
    def __init__(self, input_dir: Path, output_dir: Path, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._input_dir = input_dir
        self._output_dir = output_dir
        self._queue: list[QueueItem] = []
        self._current_index = -1
        self._current_meta: Optional[ImageMeta] = None
        self._suffix = "_rectified"
        self._preview_debounce = QTimer(self)
        self._preview_debounce.setSingleShot(True)
        self._preview_debounce.timeout.connect(self._update_preview)

        self._setup_ui()
        self._connect_signals()
        self._log("Application démarrée. input=%s, output=%s", input_dir, output_dir)

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Queue
        queue_panel = QFrame()
        queue_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        queue_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        queue_layout = QVBoxLayout(queue_panel)
        queue_layout.setSpacing(3)
        queue_layout.addWidget(QLabel("File d'attente"))
        self._queue_list = QListWidget()
        self._queue_list.setMinimumWidth(170)
        self._queue_list.currentRowChanged.connect(self._on_queue_selection)
        queue_layout.addWidget(self._queue_list)
        for txt, fn in [
            ("Ajouter fichiers…", self._add_files),
            ("Ajouter dossier input…", self._add_input_folder),
            ("Remplir depuis input/", self._fill_from_input),
            ("Retirer la sélection", self._remove_selected),
            ("Vider la liste d'attente", self._clear_queue),
        ]:
            b = QPushButton(txt)
            b.clicked.connect(fn)
            queue_layout.addWidget(b)
        splitter.addWidget(queue_panel)

        # Centre : split view Original / Preview
        center_widget = QWidget()
        center_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        center_layout = QVBoxLayout(center_widget)
        center_layout.setSpacing(3)

        center_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panneau Original (gauche) - encadré
        original_frame = QFrame()
        original_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        original_frame.setStyleSheet(
            "QFrame { "
            "border: 1px solid #cfcfcf; "
            "border-radius: 6px; "
            "background: #ffffff; "
            "padding: 6px; "
            "}"
        )
        original_layout = QVBoxLayout(original_frame)
        original_layout.setContentsMargins(6, 6, 6, 6)
        original_layout.setSpacing(4)
        lbl_original = QLabel("Original")
        lbl_original.setStyleSheet("font-weight: bold; font-size: 11px; color: #333; padding: 2px 0;")
        original_layout.addWidget(lbl_original)
        self._viewer = ImageViewerWidget()
        self._viewer.corners_changed.connect(self._schedule_preview_update)
        original_layout.addWidget(self._viewer, 1)
        center_splitter.addWidget(original_frame)

        # Panneau Preview (droite) - encadré
        preview_frame = QFrame()
        preview_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        preview_frame.setStyleSheet(
            "QFrame { "
            "border: 1px solid #cfcfcf; "
            "border-radius: 6px; "
            "background: #ffffff; "
            "padding: 6px; "
            "}"
        )
        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(6, 6, 6, 6)
        preview_layout.setSpacing(4)
        lbl_preview = QLabel("Preview")
        lbl_preview.setStyleSheet("font-weight: bold; font-size: 11px; color: #333; padding: 2px 0;")
        preview_layout.addWidget(lbl_preview)
        self._preview_viewer = ImageViewerWidget()
        preview_layout.addWidget(self._preview_viewer, 1)
        center_splitter.addWidget(preview_frame)

        center_splitter.setSizes([500, 500])
        center_splitter.setStretchFactor(0, 1)
        center_splitter.setStretchFactor(1, 1)
        center_splitter.setHandleWidth(8)
        center_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #c0c0c0;
                width: 8px;
                margin: 0 2px;
            }
            QSplitter::handle:hover {
                background-color: #4a90d9;
            }
        """)
        center_layout.addWidget(center_splitter, 1)
        self._lbl_effects_active = QLabel()
        self._lbl_effects_active.setStyleSheet("color: #666; font-size: 10px;")

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addWidget(self._lbl_effects_active)
        btn_layout.addStretch()
        # Groupe Zoom
        for lbl, shortcut, fn in [
            ("Zoom −", "Ctrl+-", self._zoom_out),
            ("Ajuster", "Ctrl+0", self._zoom_fit),
            ("Zoom +", "Ctrl++", self._zoom_in),
        ]:
            b = QPushButton(lbl)
            b.clicked.connect(fn)
            if shortcut:
                b.setShortcut(shortcut)
            btn_layout.addWidget(b)
        btn_layout.addStretch()
        # Groupe Correction
        for lbl, shortcut, fn in [
            ("Auto", "A", self._run_auto),
            ("Reset", "R", self._run_reset),
        ]:
            b = QPushButton(lbl)
            b.clicked.connect(fn)
            if shortcut:
                b.setShortcut(shortcut)
            btn_layout.addWidget(b)
        btn_layout.addStretch()
        # Groupe Navigation
        for lbl, shortcut, fn in [
            ("Précédent", "Left", self._go_prev),
            ("Suivant", "Right", self._go_next),
            ("Passer", None, self._skip_current),
        ]:
            b = QPushButton(lbl)
            b.clicked.connect(fn)
            if shortcut:
                b.setShortcut(shortcut)
            btn_layout.addWidget(b)
        btn_layout.addStretch()
        # Bouton primaire Valider & Enregistrer
        self._btn_validate = QPushButton("Valider && Enregistrer")
        self._btn_validate.setMinimumWidth(260)
        self._btn_validate.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._btn_validate.setShortcut(Qt.Key.Key_Return)
        self._btn_validate.clicked.connect(self._validate_and_save)
        self._btn_validate.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
            QPushButton:pressed {
                background-color: #0d3d12;
            }
        """)
        btn_layout.addWidget(self._btn_validate)
        center_layout.addLayout(btn_layout)
        splitter.addWidget(center_widget)

        # Options - blocs avec titre dans la box, barre en dessous, slider sur ligne à part, info en bas
        options_panel = QFrame()
        options_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        options_panel.setMinimumWidth(230)
        options_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        options_panel.setStyleSheet("QFrame { margin: 0; padding: 0; }")
        options_layout = QVBoxLayout(options_panel)
        options_layout.setSpacing(14)
        options_layout.setContentsMargins(4, 4, 4, 4)

        options_layout.addSpacing(8)
        lbl_options_title = QLabel("Options de retouche")
        lbl_options_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_options_title.setStyleSheet("font-weight: bold; font-size: 12px;")
        options_layout.addWidget(lbl_options_title)
        options_layout.addSpacing(8)
        sep_options = QFrame()
        sep_options.setFrameShape(QFrame.Shape.HLine)
        sep_options.setFrameShadow(QFrame.Shadow.Sunken)
        sep_options.setFixedHeight(2)
        options_layout.addWidget(sep_options)
        options_layout.addSpacing(8)

        EFFECT_BOX_HEIGHT = 98
        SLIDER_STYLE = """
            QSlider::groove:horizontal { border: 1px solid #999; background: #ddd; height: 4px; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #4a90d9; border-radius: 2px; }
            QSlider::handle:horizontal { background: #4a90d9; width: 10px; margin: -3px 0; border-radius: 5px; }
        """

        def _make_effect_box(title: str, tooltip: str) -> tuple[QFrame, QVBoxLayout]:
            """Titre, barre en dessous, puis Activer, slider sur sa ligne, repères, info."""
            box = QFrame()
            box.setFrameStyle(QFrame.Shape.StyledPanel)
            box.setStyleSheet(
                "QFrame { "
                "background-color: #f6f6f6; "
                "border: 1px solid #ddd; "
                "border-radius: 4px; "
                "}"
            )
            box.setFixedHeight(EFFECT_BOX_HEIGHT)
            box.setToolTip(tooltip)
            lay = QVBoxLayout(box)
            lay.setContentsMargins(8, 8, 8, 8)
            lay.setSpacing(6)
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #000;")
            lay.addWidget(lbl_title)
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet("QFrame { border: none; background: #ddd; }")
            lay.addWidget(sep)
            lay.addSpacing(6)
            return box, lay

        # Denoise
        grp, lay = _make_effect_box("Réduction du bruit (NLM)", "Réduit le bruit/grain (scans, faible lumière).")
        self._chk_denoise = QCheckBox("Activer")
        self._chk_denoise.setStyleSheet(CHECKBOX_STYLE)
        self._chk_denoise.setChecked(False)
        self._chk_denoise.toggled.connect(self._on_options_changed)
        lay.addWidget(self._chk_denoise)
        self._slider_denoise = QSlider(Qt.Orientation.Horizontal)
        self._slider_denoise.setFixedHeight(24)
        self._slider_denoise.setStyleSheet(SLIDER_STYLE)
        self._slider_denoise.setRange(5, 25)
        self._slider_denoise.setValue(15)
        self._slider_denoise.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider_denoise.setTickInterval(5)
        self._slider_denoise.valueChanged.connect(lambda v: (self._lbl_denoise.setText(f"Intensité (5–25) : {v}"), self._chk_denoise.setChecked(True), self._on_options_changed()))
        lay.addWidget(self._slider_denoise)
        self._lbl_denoise = QLabel("Intensité (5–25) : 15")
        self._lbl_denoise.setStyleSheet("color: #555; font-size: 10px;")
        lay.addWidget(self._lbl_denoise)
        options_layout.addWidget(grp)

        # CLAHE
        grp, lay = _make_effect_box("Contraste (CLAHE)", "Renforce le contraste local (documents ternes).")
        self._chk_clahe = QCheckBox("Activer")
        self._chk_clahe.setStyleSheet(CHECKBOX_STYLE)
        self._chk_clahe.setChecked(False)
        self._chk_clahe.toggled.connect(self._on_options_changed)
        lay.addWidget(self._chk_clahe)
        self._slider_clahe = QSlider(Qt.Orientation.Horizontal)
        self._slider_clahe.setFixedHeight(24)
        self._slider_clahe.setStyleSheet(SLIDER_STYLE)
        self._slider_clahe.setRange(10, 60)
        self._slider_clahe.setValue(30)
        self._slider_clahe.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider_clahe.setTickInterval(10)
        self._slider_clahe.valueChanged.connect(lambda v: (self._lbl_clahe.setText(f"Limite (1.0–6.0) : {v/10:.1f}"), self._chk_clahe.setChecked(True), self._on_options_changed()))
        lay.addWidget(self._slider_clahe)
        self._lbl_clahe = QLabel("Limite (1.0–6.0) : 3.0")
        self._lbl_clahe.setStyleSheet("color: #555; font-size: 10px;")
        lay.addWidget(self._lbl_clahe)
        options_layout.addWidget(grp)

        # Sharpen
        grp, lay = _make_effect_box("Accentuation (Unsharp Mask)", "Rend les contours plus nets (texte, détails).")
        self._chk_sharpen = QCheckBox("Activer")
        self._chk_sharpen.setStyleSheet(CHECKBOX_STYLE)
        self._chk_sharpen.setChecked(False)
        self._chk_sharpen.toggled.connect(self._on_options_changed)
        lay.addWidget(self._chk_sharpen)
        self._slider_sharpen = QSlider(Qt.Orientation.Horizontal)
        self._slider_sharpen.setFixedHeight(24)
        self._slider_sharpen.setStyleSheet(SLIDER_STYLE)
        self._slider_sharpen.setRange(10, 30)
        self._slider_sharpen.setValue(18)
        self._slider_sharpen.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider_sharpen.setTickInterval(5)
        self._slider_sharpen.valueChanged.connect(lambda v: (self._lbl_sharpen.setText(f"Intensité (0–3) : {v/10:.1f}"), self._chk_sharpen.setChecked(True), self._on_options_changed()))
        lay.addWidget(self._slider_sharpen)
        self._lbl_sharpen = QLabel("Intensité (0–3) : 1.8")
        self._lbl_sharpen.setStyleSheet("color: #555; font-size: 10px;")
        lay.addWidget(self._lbl_sharpen)
        options_layout.addWidget(grp)

        # Taille
        grp, lay = _make_effect_box("Limite de taille", "Évite les sorties trop grandes ou trop petites.")
        self._chk_clamp = QCheckBox("Activer")
        self._chk_clamp.setStyleSheet(CHECKBOX_STYLE)
        self._chk_clamp.setChecked(True)
        self._chk_clamp.toggled.connect(self._on_options_changed)
        lay.addWidget(self._chk_clamp)
        self._slider_max_scale = QSlider(Qt.Orientation.Horizontal)
        self._slider_max_scale.setFixedHeight(24)
        self._slider_max_scale.setStyleSheet(SLIDER_STYLE)
        self._slider_max_scale.setRange(100, 200)
        self._slider_max_scale.setValue(125)
        self._slider_max_scale.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider_max_scale.setTickInterval(25)
        self._slider_max_scale.valueChanged.connect(lambda v: (self._lbl_max_scale.setText(f"Facteur max (1.0–2.0) : {v/100:.2f}"), self._chk_clamp.setChecked(True), self._on_options_changed()))
        lay.addWidget(self._slider_max_scale)
        self._lbl_max_scale = QLabel("Facteur max (1.0–2.0) : 1.25")
        self._lbl_max_scale.setStyleSheet("color: #555; font-size: 10px;")
        lay.addWidget(self._lbl_max_scale)
        options_layout.addWidget(grp)
        options_layout.addStretch()
        splitter.addWidget(options_panel)

        splitter.setSizes([200, 860, 240])
        splitter.setHandleWidth(10)
        splitter.setStretchFactor(1, 1)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #b0b0b0;
                width: 10px;
                margin: 0 2px;
            }
            QSplitter::handle:hover {
                background-color: #4a90d9;
            }
        """)
        layout.addWidget(splitter, 1)

        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setMaximumHeight(70)
        layout.addWidget(QLabel("Console"))
        layout.addWidget(self._log_edit, 0)

        QShortcut(Qt.Key.Key_Delete, self, self._remove_selected)
        QShortcut(QKeySequence("Ctrl++"), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_fit)
        QShortcut(QKeySequence("A"), self, self._run_auto)
        QShortcut(QKeySequence("R"), self, self._run_reset)
        QShortcut(Qt.Key.Key_Return, self, self._validate_and_save)
        QShortcut(Qt.Key.Key_Left, self, self._go_prev)
        QShortcut(Qt.Key.Key_Right, self, self._go_next)

    def _connect_signals(self) -> None:
        self._queue_list.setAcceptDrops(True)
        self._queue_list.dragEnterEvent = self._queue_drag_enter
        self._queue_list.dropEvent = self._queue_drop

    def _queue_drag_enter(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def _queue_drop(self, e: QDropEvent) -> None:
        paths = [Path(u.toLocalFile()) for u in e.mimeData().urls()
                 if Path(u.toLocalFile()).is_file() and Path(u.toLocalFile()).suffix.lower() in SUPPORTED_EXTENSIONS]
        if paths:
            self._add_paths_to_queue(paths)
        e.acceptProposedAction()

    def _log(self, msg: str, *args: object) -> None:
        text = msg % args if args else msg
        logger.info(text)
        self._log_edit.append(text)
        self._log_edit.verticalScrollBar().setValue(self._log_edit.verticalScrollBar().maximum())

    def _schedule_preview_update(self) -> None:
        """Déclenche la mise à jour du preview avec debounce (200 ms)."""
        self._preview_debounce.stop()
        self._preview_debounce.start(200)

    def _zoom_in(self) -> None:
        self._viewer.zoom_in()
        self._preview_viewer.zoom_in()

    def _zoom_out(self) -> None:
        self._viewer.zoom_out()
        self._preview_viewer.zoom_out()

    def _zoom_fit(self) -> None:
        self._viewer.zoom_fit()
        self._preview_viewer.zoom_fit()

    def _on_options_changed(self) -> None:
        self._schedule_preview_update()

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Ajouter des images", str(self._input_dir), "Images (*.jpg *.jpeg *.png *.tiff *.tif);;Tous (*.*)")
        if paths:
            self._add_paths_to_queue([Path(p) for p in paths])

    def _add_input_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier", str(self._input_dir))
        if folder:
            self._scan_and_add_folder(Path(folder))

    def _fill_from_input(self) -> None:
        self._scan_and_add_folder(self._input_dir)

    def _scan_and_add_folder(self, p: Path) -> None:
        files = []
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(p.glob(f"*{ext}"))
        files.sort()
        if files:
            self._add_paths_to_queue(files)
            self._log("Ajouté %d images depuis %s", len(files), p)
        else:
            self._log("Aucune image trouvée dans %s", p)

    def _add_paths_to_queue(self, paths: list[Path]) -> None:
        added = 0
        for p in paths:
            if not any(q.path == p for q in self._queue):
                self._queue.append(QueueItem(path=p))
                added += 1
        self._refresh_queue_list()
        if added and self._current_index < 0 and self._queue:
            self._current_index = 0
            self._load_current_image()
        if added:
            self._log("Ajouté %d fichier(s)", added)

    def _remove_selected(self) -> None:
        row = self._queue_list.currentRow()
        if 0 <= row < len(self._queue):
            self._queue.pop(row)
            self._refresh_queue_list()
            self._current_index = min(self._current_index, len(self._queue) - 1)
            if self._current_index >= 0:
                self._load_current_image()
            else:
                self._viewer.set_image(np.zeros((100, 100, 3), dtype=np.uint8), show_corners=False)
                self._preview_viewer.set_image(np.zeros((100, 100, 3), dtype=np.uint8), show_corners=False)

    def _clear_queue(self) -> None:
        self._queue.clear()
        self._current_index = -1
        self._refresh_queue_list()
        self._viewer.set_image(np.zeros((100, 100, 3), dtype=np.uint8), show_corners=False)
        self._preview_viewer.set_image(np.zeros((100, 100, 3), dtype=np.uint8), show_corners=False)
        self._log("Queue vidée")

    def _refresh_queue_list(self) -> None:
        self._queue_list.clear()
        for item in self._queue:
            lw = QListWidgetItem(f"{item.filename} [{item.status.value}]" + (f" - {item.error_message}" if item.error_message else ""))
            if item.status == QueueStatus.DONE:
                lw.setForeground(QColor(0, 128, 0))
            elif item.status == QueueStatus.ERROR:
                lw.setForeground(QColor(200, 0, 0))
            self._queue_list.addItem(lw)
        if 0 <= self._current_index < len(self._queue):
            self._queue_list.setCurrentRow(self._current_index)

    def _on_queue_selection(self, row: int) -> None:
        if 0 <= row < len(self._queue):
            self._current_index = row
            self._load_current_image()

    def _load_current_image(self) -> None:
        if self._current_index < 0 or self._current_index >= len(self._queue):
            return
        item = self._queue[self._current_index]
        try:
            img_bgr, meta = load_image_with_meta(item.path)
            self._current_meta = meta
            corners, success = auto_detect_corners(img_bgr)
            self._viewer.set_image(img_bgr, corners, auto_failed=not success)
            self._update_preview()
            self._log("Auto-détection %s pour %s", "OK" if success else "échouée", item.filename)
        except Exception as e:
            logger.exception("Erreur chargement %s", item.path)
            item.status = QueueStatus.ERROR
            item.error_message = str(e)
            self._log("Erreur: %s - %s", item.filename, e)
            self._refresh_queue_list()
            self._go_next()

    def _run_auto(self) -> None:
        if 0 <= self._current_index < len(self._queue):
            try:
                img_bgr, meta = load_image_with_meta(self._queue[self._current_index].path)
                self._current_meta = meta
                corners, success = auto_detect_corners(img_bgr)
                self._viewer.set_image(img_bgr, corners, auto_failed=not success)
                self._update_preview()
            except Exception as e:
                self._log("Erreur auto: %s", e)

    def _run_reset(self) -> None:
        self._run_auto()

    def _update_preview(self) -> None:
        if self._current_index < 0 or self._current_index >= len(self._queue):
            return
        item = self._queue[self._current_index]
        try:
            img_bgr, _ = load_image_with_meta(item.path)
            corners = self._viewer.get_corners_in_original_scale()
            if corners is None:
                return
            result = full_pipeline(
                img_bgr, corners,
                denoise=self._chk_denoise.isChecked(), denoise_strength=float(self._slider_denoise.value()),
                clahe=self._chk_clahe.isChecked(), clahe_clip=self._slider_clahe.value() / 10.0,
                sharpen=self._chk_sharpen.isChecked(), sharpen_amount=self._slider_sharpen.value() / 10.0,
                clamp_enabled=self._chk_clamp.isChecked(), ref_max_dim=max(img_bgr.shape[:2]),
                max_scale_factor=self._slider_max_scale.value() / 100.0, min_scale_factor=0.75,
            )
            self._preview_viewer.set_image(result, show_corners=False, preserve_zoom=True)
            effects = [n for n, c in [("Denoise", self._chk_denoise), ("CLAHE", self._chk_clahe), ("Sharpen", self._chk_sharpen)] if c.isChecked()]
            self._lbl_effects_active.setText("Effets : " + ", ".join(effects) if effects else "Aucun effet")
        except Exception as e:
            self._log("Erreur preview: %s", e)

    def _validate_and_save(self) -> None:
        if self._current_index < 0 or self._current_index >= len(self._queue):
            return
        item = self._queue[self._current_index]
        if self._current_meta is None:
            try:
                _, self._current_meta = load_image_with_meta(item.path)
            except Exception as e:
                self._log("Erreur: %s", e)
                return
        try:
            img_bgr, _ = load_image_with_meta(item.path)
            corners = self._viewer.get_corners_in_original_scale()
            if corners is None:
                return
            result = full_pipeline(
                img_bgr, corners,
                denoise=self._chk_denoise.isChecked(), denoise_strength=float(self._slider_denoise.value()),
                clahe=self._chk_clahe.isChecked(), clahe_clip=self._slider_clahe.value() / 10.0,
                sharpen=self._chk_sharpen.isChecked(), sharpen_amount=self._slider_sharpen.value() / 10.0,
                clamp_enabled=self._chk_clamp.isChecked(), ref_max_dim=max(img_bgr.shape[:2]),
                max_scale_factor=self._slider_max_scale.value() / 100.0, min_scale_factor=0.75,
            )
            out_path = build_output_path(item.path, self._output_dir, self._suffix)
            save_image_with_meta(out_path, result, self._current_meta, quality=95, suffix="")
            item.status = QueueStatus.DONE
            self._log("Enregistré: %s", out_path.name)
            self._go_next()
        except Exception as e:
            logger.exception("Erreur sauvegarde")
            item.status = QueueStatus.ERROR
            item.error_message = str(e)
            self._log("Erreur: %s", e)
            self._refresh_queue_list()

    def _skip_current(self) -> None:
        self._go_next()

    def _go_prev(self) -> None:
        if self._queue:
            self._current_index = (self._current_index - 1) % len(self._queue)
            self._load_current_image()
            self._queue_list.setCurrentRow(self._current_index)

    def _go_next(self) -> None:
        if self._queue:
            self._current_index = (self._current_index + 1) % len(self._queue)
            self._load_current_image()
            self._queue_list.setCurrentRow(self._current_index)
