# -*- coding: utf-8 -*-
"""
Endüstriyel Kalite Kontrol Sistemi — Ana Arayüz (PyQt6)
=========================================================
Dark Mode, dokunmatik uyumlu, Mission Critical tasarım.
"""

import sys
import os
import cv2
import numpy as np
import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QSplitter, QDialog, QLineEdit, QFormLayout,
    QSlider, QSpinBox, QComboBox, QGroupBox, QFileDialog, QMessageBox,
    QDateEdit, QSizePolicy, QSpacerItem, QCheckBox, QStackedWidget
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, pyqtSlot, QSize, QDate, QPropertyAnimation,
    QEasingCurve, QSequentialAnimationGroup, QParallelAnimationGroup
)
from PyQt6.QtGui import (
    QImage, QPixmap, QFont, QColor, QPalette, QIcon, QPainter,
    QLinearGradient, QBrush, QPen, QFontDatabase
)

from config import UIColors, APP_NAME, APP_VERSION

logger = logging.getLogger("main_ui")

# ═══════════════════════════════════════════════════════════════════
# GLOBAL STYLESHEET
# ═══════════════════════════════════════════════════════════════════

DARK_STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {UIColors.BACKGROUND};
    color: {UIColors.TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 14px;
}}
QLabel {{
    color: {UIColors.TEXT_PRIMARY};
    background: transparent;
}}
QPushButton {{
    background-color: {UIColors.BUTTON_BG};
    color: {UIColors.TEXT_PRIMARY};
    border: 1px solid {UIColors.CARD_BORDER};
    border-radius: 8px;
    padding: 14px 24px;
    font-size: 15px;
    font-weight: bold;
    min-height: 50px;
}}
QPushButton:hover {{
    background-color: {UIColors.BUTTON_HOVER};
    border-color: {UIColors.ACCENT_BLUE};
}}
QPushButton:pressed {{
    background-color: {UIColors.ACCENT_BLUE_DARK};
    border-color: {UIColors.ACCENT_BLUE};
}}
QPushButton:disabled {{
    background-color: #2a2a2a;
    color: #555;
    border-color: #333;
}}
QPushButton#btn_start {{
    background-color: {UIColors.OK_GREEN_DARK};
    border-color: {UIColors.OK_GREEN};
    color: white;
}}
QPushButton#btn_start:hover {{
    background-color: {UIColors.OK_GREEN};
}}
QPushButton#btn_stop {{
    background-color: {UIColors.NOK_RED_DARK};
    border-color: {UIColors.NOK_RED};
    color: white;
}}
QPushButton#btn_stop:hover {{
    background-color: {UIColors.NOK_RED};
}}
QPushButton#btn_settings {{
    background-color: #2c3e50;
    border-color: {UIColors.ACCENT_BLUE};
}}
QPushButton#btn_settings:hover {{
    background-color: {UIColors.ACCENT_BLUE_DARK};
}}
QTableWidget {{
    background-color: {UIColors.CARD_BG};
    alternate-background-color: {UIColors.TABLE_ROW_ALT};
    color: {UIColors.TEXT_PRIMARY};
    border: 1px solid {UIColors.CARD_BORDER};
    border-radius: 6px;
    gridline-color: {UIColors.CARD_BORDER};
    font-size: 13px;
    selection-background-color: {UIColors.ACCENT_BLUE_DARK};
}}
QTableWidget::item {{
    padding: 6px 10px;
    border-bottom: 1px solid #333;
}}
QHeaderView::section {{
    background-color: {UIColors.TABLE_HEADER};
    color: {UIColors.TEXT_PRIMARY};
    padding: 8px 10px;
    border: none;
    border-bottom: 2px solid {UIColors.ACCENT_BLUE};
    font-weight: bold;
    font-size: 13px;
}}
QFrame#card {{
    background-color: {UIColors.CARD_BG};
    border: 1px solid {UIColors.CARD_BORDER};
    border-radius: 10px;
}}
QFrame#header_bar {{
    background-color: {UIColors.HEADER_BG};
    border-bottom: 2px solid {UIColors.ACCENT_BLUE};
    min-height: 56px;
}}
QLineEdit, QSpinBox, QComboBox, QDateEdit {{
    background-color: #333;
    color: {UIColors.TEXT_PRIMARY};
    border: 1px solid {UIColors.CARD_BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 14px;
    min-height: 36px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {UIColors.ACCENT_BLUE};
}}
QSlider::groove:horizontal {{
    height: 8px;
    background: #444;
    border-radius: 4px;
}}
QSlider::handle:horizontal {{
    background: {UIColors.ACCENT_BLUE};
    width: 20px;
    height: 20px;
    margin: -6px 0;
    border-radius: 10px;
}}
QGroupBox {{
    color: {UIColors.TEXT_PRIMARY};
    border: 1px solid {UIColors.CARD_BORDER};
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 20px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    padding: 2px 10px;
}}
QCheckBox {{
    color: {UIColors.TEXT_PRIMARY};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 20px;
    height: 20px;
}}
"""


# ═══════════════════════════════════════════════════════════════════
# CAMERA THREAD
# ═══════════════════════════════════════════════════════════════════

class CameraThread(QThread):
    """Kamera görüntüsünü arka planda okur."""
    frame_ready = pyqtSignal(np.ndarray)
    camera_error = pyqtSignal(str)

    def __init__(self, vision_engine, parent=None):
        super().__init__(parent)
        self.vision = vision_engine
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            if self.vision.kamera_durumu:
                frame = self.vision.goruntu_yakala()
                if frame is not None:
                    self.frame_ready.emit(frame)
                else:
                    self.camera_error.emit("Kare yakalanamadı")
                    self._running = False
            self.msleep(33)  # ~30fps

    def stop(self):
        self._running = False
        self.wait(2000)


# ═══════════════════════════════════════════════════════════════════
# ANALYSIS THREAD
# ═══════════════════════════════════════════════════════════════════

class AnalysisThread(QThread):
    """Görüntü analizi arka plan thread'i."""
    analysis_complete = pyqtSignal(object)  # AnalysisResult
    analysis_error = pyqtSignal(str)

    def __init__(self, vision_engine, frame, parent=None):
        super().__init__(parent)
        self.vision = vision_engine
        self.frame = frame

    def run(self):
        try:
            result = self.vision.tam_analiz(self.frame)
            self.analysis_complete.emit(result)
        except Exception as e:
            self.analysis_error.emit(str(e))


# ═══════════════════════════════════════════════════════════════════
# STATUS INDICATOR WIDGET
# ═══════════════════════════════════════════════════════════════════

class StatusIndicator(QWidget):
    """Bağlantı durum göstergesi (LED benzeri)."""
    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        self._led = QLabel()
        self._led.setFixedSize(14, 14)
        self._label = QLabel(label_text)
        self._label.setStyleSheet(f"color: {UIColors.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(self._led)
        layout.addWidget(self._label)
        self.set_status(False)

    def set_status(self, active: bool):
        color = UIColors.OK_GREEN if active else UIColors.NOK_RED
        self._led.setStyleSheet(f"""
            background-color: {color};
            border-radius: 7px;
            border: 2px solid {color}88;
        """)

    def set_warning(self):
        self._led.setStyleSheet(f"""
            background-color: {UIColors.WARNING_ORANGE};
            border-radius: 7px;
            border: 2px solid {UIColors.WARNING_ORANGE}88;
        """)


# ═══════════════════════════════════════════════════════════════════
# COUNTER CARD WIDGET
# ═══════════════════════════════════════════════════════════════════

class CounterCard(QFrame):
    """Sayaç kartı — Toplam, OK, NOK."""
    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumSize(130, 100)
        self.setStyleSheet(f"""
            QFrame#card {{
                background-color: {UIColors.CARD_BG};
                border: 1px solid {color}66;
                border-radius: 10px;
                border-top: 3px solid {color};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self._title = QLabel(title)
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(f"color: {UIColors.TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")

        self._value = QLabel("0")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setStyleSheet(f"color: {color}; font-size: 36px; font-weight: bold;")

        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def set_value(self, val: int):
        self._value.setText(str(val))


# ═══════════════════════════════════════════════════════════════════
# BIG OK/NOK RESULT PANEL
# ═══════════════════════════════════════════════════════════════════

class ResultPanel(QFrame):
    """Devasa OK / NOK sonuç göstergesi."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumSize(320, 200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Sonuç etiketi
        self._result_label = QLabel("BEKLE")
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_label.setStyleSheet(f"""
            font-size: 72px; font-weight: bold;
            color: {UIColors.TEXT_MUTED};
            padding: 20px;
        """)

        # Alt bilgiler
        self._serial_label = QLabel("Seri No: ---")
        self._serial_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._serial_label.setStyleSheet(f"color: {UIColors.TEXT_SECONDARY}; font-size: 16px;")

        self._white_label = QLabel("Beyaz Keçe: ---")
        self._white_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._white_label.setStyleSheet(f"color: {UIColors.TEXT_SECONDARY}; font-size: 14px;")

        self._gray_label = QLabel("Gri Keçe: ---")
        self._gray_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gray_label.setStyleSheet(f"color: {UIColors.TEXT_SECONDARY}; font-size: 14px;")

        self._copper_label = QLabel("")
        self._copper_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._copper_label.setStyleSheet(f"color: {UIColors.WARNING_ORANGE}; font-size: 13px;")

        self._time_label = QLabel("")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_label.setStyleSheet(f"color: {UIColors.TEXT_MUTED}; font-size: 12px;")

        layout.addStretch()
        layout.addWidget(self._result_label)
        layout.addWidget(self._serial_label)
        layout.addWidget(self._white_label)
        layout.addWidget(self._gray_label)
        layout.addWidget(self._copper_label)
        layout.addWidget(self._time_label)
        layout.addStretch()

        self.set_waiting()

    def set_waiting(self):
        self._result_label.setText("BEKLE")
        self._result_label.setStyleSheet(f"""
            font-size: 72px; font-weight: bold;
            color: {UIColors.TEXT_MUTED};
            padding: 20px;
        """)
        self.setStyleSheet(f"""
            QFrame#card {{
                background-color: {UIColors.CARD_BG};
                border: 2px solid {UIColors.CARD_BORDER};
                border-radius: 12px;
            }}
        """)

    def set_result(self, result):
        is_ok = result.durum == "OK"
        color = UIColors.OK_GREEN if is_ok else UIColors.NOK_RED
        dark = UIColors.OK_GREEN_DARK if is_ok else UIColors.NOK_RED_DARK
        text = "  O K  " if is_ok else " N O K "

        self._result_label.setText(text)
        self._result_label.setStyleSheet(f"""
            font-size: 80px; font-weight: bold;
            color: {color}; padding: 20px;
            background-color: {dark}44;
            border-radius: 16px;
        """)
        self.setStyleSheet(f"""
            QFrame#card {{
                background-color: {UIColors.CARD_BG};
                border: 3px solid {color};
                border-radius: 12px;
            }}
        """)

        self._serial_label.setText(f"Seri No: {result.seri_no or '---'}")
        wc = UIColors.OK_GREEN if result.beyaz_kece else UIColors.NOK_RED
        self._white_label.setText(f"Beyaz Keçe: {'✓ VAR' if result.beyaz_kece else '✗ YOK'}")
        self._white_label.setStyleSheet(f"color: {wc}; font-size: 14px;")
        gc = UIColors.OK_GREEN if result.gri_kece else UIColors.NOK_RED
        self._gray_label.setText(f"Gri Keçe: {'✓ VAR' if result.gri_kece else '✗ YOK'}")
        self._gray_label.setStyleSheet(f"color: {gc}; font-size: 14px;")

        if result.bakir_halka_tespit:
            self._copper_label.setText("⚠ BAKIR HALKA — KEÇE EKSİK!")
        else:
            self._copper_label.setText("")

        self._time_label.setText(f"İşlem: {result.islem_suresi_ms:.0f} ms")


# ═══════════════════════════════════════════════════════════════════
# SETTINGS DIALOG
# ═══════════════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    """Şifreli ayarlar paneli."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ Sistem Ayarları")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(DARK_STYLESHEET)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # ── Kamera ───────────────────────────────────────────────
        cam_group = QGroupBox("📷 Kamera Ayarları")
        cam_layout = QFormLayout()
        self.cam_index = QSpinBox(); self.cam_index.setRange(0, 10); self.cam_index.setValue(0)
        self.cam_width = QComboBox(); self.cam_width.addItems(["640", "1280", "1920"])
        self.cam_width.setCurrentText("1280")
        self.cam_height = QComboBox(); self.cam_height.addItems(["480", "720", "1080"])
        self.cam_height.setCurrentText("720")
        cam_layout.addRow("Kamera İndeksi:", self.cam_index)
        cam_layout.addRow("Genişlik:", self.cam_width)
        cam_layout.addRow("Yükseklik:", self.cam_height)
        cam_group.setLayout(cam_layout)

        # ── PLC ──────────────────────────────────────────────────
        plc_group = QGroupBox("🔌 PLC Haberleşme (Opsiyonel)")
        plc_layout = QFormLayout()
        self.plc_enabled = QCheckBox("PLC Haberleşme Aktif")
        self.plc_protocol = QComboBox(); self.plc_protocol.addItems(["tcp", "rtu"])
        self.plc_host = QLineEdit("192.168.1.100")
        self.plc_port = QSpinBox(); self.plc_port.setRange(1, 65535); self.plc_port.setValue(502)
        self.plc_com = QComboBox(); self.plc_com.addItems([f"COM{i}" for i in range(1, 21)])
        self.plc_baud = QComboBox(); self.plc_baud.addItems(["9600", "19200", "38400", "115200"])
        self.plc_slave = QSpinBox(); self.plc_slave.setRange(1, 247); self.plc_slave.setValue(1)
        plc_layout.addRow("", self.plc_enabled)
        plc_layout.addRow("Protokol:", self.plc_protocol)
        plc_layout.addRow("TCP Host:", self.plc_host)
        plc_layout.addRow("TCP Port:", self.plc_port)
        plc_layout.addRow("RTU Port:", self.plc_com)
        plc_layout.addRow("RTU Baud:", self.plc_baud)
        plc_layout.addRow("Slave ID:", self.plc_slave)
        plc_group.setLayout(plc_layout)

        # ── Butonlar ─────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 Kaydet")
        btn_save.setObjectName("btn_start")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)

        main_layout.addWidget(cam_group)
        main_layout.addWidget(plc_group)
        main_layout.addStretch()
        main_layout.addLayout(btn_layout)


# ═══════════════════════════════════════════════════════════════════
# CRITICAL ERROR BANNER
# ═══════════════════════════════════════════════════════════════════

class CriticalErrorBanner(QFrame):
    """Kritik hata uyarı bandı — yanıp söner."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(0)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(f"""
            color: white; font-size: 16px; font-weight: bold;
            padding: 10px;
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink)
        self._blink_state = False

    def show_error(self, message: str):
        self.setFixedHeight(48)
        self._label.setText(f"⚠ KRİTİK HATA: {message}")
        self.setStyleSheet(f"background-color: {UIColors.CRITICAL_RED};")
        self._blink_timer.start(500)

    def hide_error(self):
        self._blink_timer.stop()
        self.setFixedHeight(0)

    def _blink(self):
        self._blink_state = not self._blink_state
        color = UIColors.CRITICAL_RED if self._blink_state else "#8b0000"
        self.setStyleSheet(f"background-color: {color};")


# ═══════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """Ana pencere — Endüstriyel Kalite Kontrol Arayüzü."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1280, 720)
        self.setStyleSheet(DARK_STYLESHEET)

        # ── Modüller ─────────────────────────────────────────────
        from vision_engine import VisionEngine
        from database import DatabaseManager
        from plc_comm import PLCManager, PLCSimulator
        from config import ModbusConfig

        self.vision = VisionEngine()
        self.db = DatabaseManager()
        self.modbus_config = ModbusConfig()
        self.plc = PLCSimulator()  # Varsayılan: simülatör

        # Sayaçlar
        self._total_count = 0
        self._ok_count = 0
        self._nok_count = 0
        self._camera_thread = None
        self._analysis_thread = None
        self._current_frame = None
        self._system_running = False
        self._auto_test_active = False

        # Otomatik analiz zamanlayıcısı (PLC olmadan test için)
        self._auto_analysis_timer = QTimer(self)
        self._auto_analysis_timer.timeout.connect(self._auto_analyze)

        # UI Oluştur
        self._build_ui()
        self._load_stats()

        # Kamera önizleme zamanlayıcısı
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._update_preview)

        logger.info("Ana pencere oluşturuldu")

    # ─────────────────── UI OLUŞTURMA ────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Kritik Hata Bandı ────────────────────────────────────
        self.error_banner = CriticalErrorBanner()
        main_layout.addWidget(self.error_banner)

        # ── Üst Başlık ──────────────────────────────────────────
        header = self._build_header()
        main_layout.addWidget(header)

        # ── İçerik Alanı ─────────────────────────────────────
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 8)
        content_layout.setSpacing(8)

        # Üst bölüm: Kamera + Sonuç Paneli
        top_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Kamera görüntüsü
        camera_frame = QFrame()
        camera_frame.setObjectName("card")
        camera_layout = QVBoxLayout(camera_frame)
        camera_layout.setContentsMargins(8, 8, 8, 8)
        cam_title = QLabel("📷 CANLI GÖRÜNTÜ")
        cam_title.setStyleSheet(f"color: {UIColors.ACCENT_BLUE}; font-size: 13px; font-weight: bold;")
        self.camera_view = QLabel()
        self.camera_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_view.setMinimumSize(640, 400)
        self.camera_view.setStyleSheet(f"""
            background-color: #111;
            border: 1px solid {UIColors.CARD_BORDER};
            border-radius: 6px;
            color: {UIColors.TEXT_MUTED};
            font-size: 18px;
        """)
        self.camera_view.setText("Kamera Bağlı Değil\n\n▶ BAŞLAT butonuna basın")
        camera_layout.addWidget(cam_title)
        camera_layout.addWidget(self.camera_view, 1)

        # Sağ panel: Sonuç + Sayaçlar
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.result_panel = ResultPanel()
        right_layout.addWidget(self.result_panel, 1)

        # Sayaçlar
        counters = QWidget()
        counter_layout = QHBoxLayout(counters)
        counter_layout.setContentsMargins(0, 0, 0, 0)
        counter_layout.setSpacing(6)
        self.counter_total = CounterCard("TOPLAM", UIColors.ACCENT_BLUE)
        self.counter_ok = CounterCard("OK", UIColors.OK_GREEN)
        self.counter_nok = CounterCard("NOK", UIColors.NOK_RED)
        counter_layout.addWidget(self.counter_total)
        counter_layout.addWidget(self.counter_ok)
        counter_layout.addWidget(self.counter_nok)
        right_layout.addWidget(counters)

        top_splitter.addWidget(camera_frame)
        top_splitter.addWidget(right_panel)
        top_splitter.setSizes([700, 380])
        content_layout.addWidget(top_splitter, 1)

        # ── Alt bölüm: Log tablosu ──────────────────────────────
        log_frame = QFrame()
        log_frame.setObjectName("card")
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(8, 6, 8, 6)
        log_title = QLabel("📋 SON ÜRETİM KAYITLARI")
        log_title.setStyleSheet(f"color: {UIColors.ACCENT_BLUE}; font-size: 12px; font-weight: bold;")
        log_layout.addWidget(log_title)

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(7)
        self.log_table.setHorizontalHeaderLabels([
            "#", "Tarih-Saat", "Seri No", "Durum",
            "Beyaz Keçe", "Gri Keçe", "Hata Detayı"
        ])
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setMaximumHeight(260)

        header_view = self.log_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header_view.resizeSection(0, 50)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header_view.resizeSection(3, 80)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header_view.resizeSection(4, 100)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header_view.resizeSection(5, 100)
        header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        log_layout.addWidget(self.log_table)
        content_layout.addWidget(log_frame)

        main_layout.addWidget(content, 1)

        # ── Alt buton çubuğu ─────────────────────────────────────
        toolbar = self._build_toolbar()
        main_layout.addWidget(toolbar)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header_bar")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 8, 16, 8)

        title = QLabel(f"🔍 {APP_NAME}")
        title.setStyleSheet(f"""
            font-size: 20px; font-weight: bold;
            color: {UIColors.TEXT_PRIMARY};
        """)
        version = QLabel(f"v{APP_VERSION}")
        version.setStyleSheet(f"color: {UIColors.TEXT_MUTED}; font-size: 12px;")

        layout.addWidget(title)
        layout.addWidget(version)
        layout.addStretch()

        self.status_plc = StatusIndicator("PLC")
        self.status_cam = StatusIndicator("KAMERA")
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(f"color: {UIColors.TEXT_SECONDARY}; font-size: 13px;")

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        layout.addWidget(self.status_plc)
        layout.addWidget(self.status_cam)
        layout.addWidget(self.clock_label)
        return header

    def _build_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet(f"""
            background-color: {UIColors.HEADER_BG};
            border-top: 1px solid {UIColors.CARD_BORDER};
        """)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self.btn_start = QPushButton("▶  BAŞLAT")
        self.btn_start.setObjectName("btn_start")
        self.btn_start.clicked.connect(self.sistem_baslat)

        self.btn_stop = QPushButton("⏹  DURDUR")
        self.btn_stop.setObjectName("btn_stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.sistem_durdur)

        self.btn_manual = QPushButton("📸  MANUEL TEST")
        self.btn_manual.clicked.connect(self.manuel_test)

        self.btn_auto = QPushButton("🔁  OTO. TEST")
        self.btn_auto.setCheckable(True)
        self.btn_auto.setStyleSheet(f"""
            QPushButton {{ background-color: #2c3e50; border-color: {UIColors.WARNING_ORANGE}; }}
            QPushButton:checked {{ background-color: {UIColors.WARNING_ORANGE}; color: black; }}
            QPushButton:hover {{ background-color: #d4880f; }}
        """)
        self.btn_auto.clicked.connect(self.oto_test_toggle)

        self.btn_settings = QPushButton("⚙  AYARLAR")
        self.btn_settings.setObjectName("btn_settings")
        self.btn_settings.clicked.connect(self.ayarlar_ac)

        self.btn_report = QPushButton("📊  RAPOR")
        self.btn_report.clicked.connect(self.rapor_aktar)

        self.btn_reset = QPushButton("🔄  SIFIRLA")
        self.btn_reset.clicked.connect(self.sayaclari_sifirla)

        for btn in [self.btn_start, self.btn_stop, self.btn_manual, self.btn_auto,
                    self.btn_settings, self.btn_report, self.btn_reset]:
            btn.setMinimumHeight(54)
            btn.setMinimumWidth(120)
            layout.addWidget(btn)

        return toolbar

    # ─────────────────── SİSTEM KONTROL ──────────────────────────

    def sistem_baslat(self):
        """Sistemi başlat — kamera aç, PLC dinlemeye başla."""
        if self._system_running:
            return

        # Kamera başlat
        if not self.vision.kamera_baslat():
            self.error_banner.show_error("Kamera bağlantısı kurulamadı!")
            self.status_cam.set_status(False)
            return

        self.error_banner.hide_error()
        self.status_cam.set_status(True)

        # PLC (opsiyonel)
        if self.modbus_config.enabled:
            from plc_comm import PLCManager
            self.plc = PLCManager(self.modbus_config)
            self.plc.tetikleme_alindi.connect(self._on_trigger)
            self.plc.baglanti_durumu_degisti.connect(self._on_plc_status)
            self.plc.hata_olustu.connect(self._on_plc_error)
            self.plc.start()
        else:
            self.status_plc.set_warning()

        # Kamera önizleme
        self._camera_thread = CameraThread(self.vision)
        self._camera_thread.frame_ready.connect(self._on_frame)
        self._camera_thread.camera_error.connect(self._on_camera_error)
        self._camera_thread.start()

        self._system_running = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.result_panel.set_waiting()
        logger.info("Sistem başlatıldı")

    def sistem_durdur(self):
        """Sistemi durdur."""
        self._system_running = False
        if self._camera_thread:
            self._camera_thread.stop()
            self._camera_thread = None
        self.vision.kamera_durdur()
        self.plc.durdur()
        self.status_cam.set_status(False)
        self.status_plc.set_status(False)
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.camera_view.setText("Sistem Durduruldu")
        logger.info("Sistem durduruldu")

    def manuel_test(self):
        """Manuel tetikleme — dosyadan veya kameradan analiz."""
        if self._current_frame is not None:
            self._run_analysis(self._current_frame.copy())
        else:
            # Dosyadan yükle
            path, _ = QFileDialog.getOpenFileName(
                self, "Parça Görseli Seç", "",
                "Görseller (*.jpg *.jpeg *.png *.bmp)"
            )
            if path:
                # Unicode yol desteği (Türkçe karakter)
                data = np.fromfile(path, dtype=np.uint8)
                frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
                if frame is not None:
                    self._run_analysis(frame)

    def oto_test_toggle(self):
        """Otomatik test modunu aç/kapa — PLC olmadan sürekli analiz."""
        if self.btn_auto.isChecked():
            if not self._system_running:
                self.btn_auto.setChecked(False)
                QMessageBox.warning(self, "Uyarı", "Önce sistemi BAŞLAT butonuyla başlatın!")
                return
            self._auto_test_active = True
            self._auto_analysis_timer.start(2000)  # Her 2 saniyede bir analiz
            logger.info("Otomatik test modu AKTİF")
        else:
            self._auto_test_active = False
            self._auto_analysis_timer.stop()
            logger.info("Otomatik test modu KAPALI")

    def _auto_analyze(self):
        """Otomatik analiz — zamanlayıcı tarafından çağrılır."""
        if self._current_frame is not None and not (
            self._analysis_thread and self._analysis_thread.isRunning()
        ):
            self._run_analysis(self._current_frame.copy())

    # ─────────────────── ANALİZ ──────────────────────────────────

    def _run_analysis(self, frame):
        """Analiz thread'ini başlat."""
        if self._analysis_thread and self._analysis_thread.isRunning():
            return
        self._analysis_thread = AnalysisThread(self.vision, frame)
        self._analysis_thread.analysis_complete.connect(self._on_analysis_done)
        self._analysis_thread.analysis_error.connect(self._on_analysis_error)
        self._analysis_thread.start()

    @pyqtSlot(object)
    def _on_analysis_done(self, result):
        """Analiz tamamlandığında çağrılır."""
        # Sonuç panelini güncelle
        self.result_panel.set_result(result)

        # NOK ise görsel kaydet
        gorsel_yolu = ""
        if result.durum == "NOK" and result.annotated_frame.size > 0:
            gorsel_yolu = self.vision.nok_gorsel_kaydet(
                result.annotated_frame, result.seri_no
            )

        # Veritabanına kaydet
        self.db.kayit_ekle(
            seri_no=result.seri_no,
            durum=result.durum,
            beyaz_kece=result.beyaz_kece,
            gri_kece=result.gri_kece,
            bakir_halka_tespit=result.bakir_halka_tespit,
            hata_detayi=result.hata_detayi,
            gorsel_yolu=gorsel_yolu
        )

        # PLC'ye sonuç yaz
        self.plc.sonuc_yaz(result.durum)

        # Sayaçları güncelle
        self._total_count += 1
        if result.durum == "OK":
            self._ok_count += 1
        else:
            self._nok_count += 1
        self._update_counters()

        # Log tablosunu güncelle
        self._update_log_table()

        # Annotated frame göster
        if result.annotated_frame.size > 0:
            self._display_frame(result.annotated_frame)

    @pyqtSlot(str)
    def _on_analysis_error(self, error_msg):
        self.error_banner.show_error(f"Analiz hatası: {error_msg}")

    # ─────────────────── KAMERA CALLBACK'LERİ ────────────────────

    @pyqtSlot(np.ndarray)
    def _on_frame(self, frame):
        self._current_frame = frame
        self._display_frame(frame)

    def _display_frame(self, frame):
        """OpenCV frame'ini QLabel üzerinde göster."""
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            scaled = QPixmap.fromImage(qimg).scaled(
                self.camera_view.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.camera_view.setPixmap(scaled)
        except Exception as e:
            logger.error(f"Frame gösterim hatası: {e}")

    @pyqtSlot(str)
    def _on_camera_error(self, msg):
        self.error_banner.show_error(f"Kamera: {msg}")
        self.status_cam.set_status(False)

    def _update_preview(self):
        if self._current_frame is not None:
            self._display_frame(self._current_frame)

    # ─────────────────── PLC CALLBACK'LERİ ───────────────────────

    @pyqtSlot()
    def _on_trigger(self):
        """PLC tetikleme sinyali geldiğinde."""
        if self._current_frame is not None:
            self._run_analysis(self._current_frame.copy())

    @pyqtSlot(bool)
    def _on_plc_status(self, connected):
        self.status_plc.set_status(connected)
        if not connected:
            self.error_banner.show_error("PLC bağlantısı koptu!")

    @pyqtSlot(str)
    def _on_plc_error(self, msg):
        self.error_banner.show_error(msg)

    # ─────────────────── UI GÜNCELLEME ───────────────────────────

    def _update_counters(self):
        self.counter_total.set_value(self._total_count)
        self.counter_ok.set_value(self._ok_count)
        self.counter_nok.set_value(self._nok_count)

    def _load_stats(self):
        stats = self.db.gunluk_istatistik()
        self._total_count = stats["toplam"]
        self._ok_count = stats["ok"]
        self._nok_count = stats["nok"]
        self._update_counters()
        self._update_log_table()

    def _update_log_table(self):
        kayitlar = self.db.son_kayitlar(10)
        self.log_table.setRowCount(len(kayitlar))
        for row, k in enumerate(kayitlar):
            items = [
                str(k["id"]),
                k["tarih_saat"],
                k["seri_no"] or "---",
                k["durum"],
                "✓" if k["beyaz_kece"] else "✗",
                "✓" if k["gri_kece"] else "✗",
                k["hata_detayi"] or "-"
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 3:
                    color = QColor(UIColors.OK_GREEN) if text == "OK" else QColor(UIColors.NOK_RED)
                    item.setForeground(QBrush(color))
                    item.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
                elif col in (4, 5):
                    color = QColor(UIColors.OK_GREEN) if text == "✓" else QColor(UIColors.NOK_RED)
                    item.setForeground(QBrush(color))
                self.log_table.setItem(row, col, item)

    def _update_clock(self):
        now = datetime.now().strftime("%H:%M:%S  |  %d.%m.%Y")
        self.clock_label.setText(now)

    # ─────────────────── AYARLAR ─────────────────────────────────

    def ayarlar_ac(self):
        from config import SETTINGS_PASSWORD
        pwd, ok = self._ask_password()
        if ok and pwd == SETTINGS_PASSWORD:
            dlg = SettingsDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                logger.info("Ayarlar güncellendi")
        elif ok:
            QMessageBox.warning(self, "Hata", "Yanlış şifre!")

    def _ask_password(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("🔒 Şifre")
        dlg.setStyleSheet(DARK_STYLESHEET)
        dlg.setFixedSize(350, 160)
        layout = QVBoxLayout(dlg)
        lbl = QLabel("Ayarlar menüsü şifresi:")
        entry = QLineEdit()
        entry.setEchoMode(QLineEdit.EchoMode.Password)
        entry.setPlaceholderText("Şifre giriniz...")
        btn = QPushButton("Giriş")
        btn.setObjectName("btn_start")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(lbl)
        layout.addWidget(entry)
        layout.addWidget(btn)
        result = dlg.exec()
        return entry.text(), result == QDialog.DialogCode.Accepted

    # ─────────────────── RAPOR ───────────────────────────────────

    def rapor_aktar(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Rapor Kaydet", f"uretim_raporu_{datetime.now():%Y%m%d}.xlsx",
            "Excel (*.xlsx)"
        )
        if path:
            try:
                self.db.excel_aktar(path)
                QMessageBox.information(self, "Başarılı", f"Rapor kaydedildi:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Rapor hatası:\n{e}")

    def sayaclari_sifirla(self):
        reply = QMessageBox.question(
            self, "Onay", "Tüm sayaçlar sıfırlanacak. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._total_count = 0
            self._ok_count = 0
            self._nok_count = 0
            self._update_counters()
            self.result_panel.set_waiting()

    # ─────────────────── KAPANIŞ ─────────────────────────────────

    def closeEvent(self, event):
        self.sistem_durdur()
        self.vision.cleanup()
        logger.info("Uygulama kapatıldı")
        event.accept()
