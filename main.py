# -*- coding: utf-8 -*-
"""
Endüstriyel Kalite Kontrol Sistemi — Ana Giriş Noktası
========================================================
Uygulama başlatma, logging konfigürasyonu, exception handling.
"""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Logging konfigürasyonu — dosya + konsol."""
    from config import LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT, LOG_FILE, LOG_MAX_BYTES, LOG_BACKUP_COUNT
    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    fmt = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    # Konsol
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # Dosya (rotasyonlu)
    try:
        fh = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception as e:
        print(f"Log dosyası açılamadı: {e}")


def global_exception_handler(exc_type, exc_value, exc_tb):
    """Yakalanmamış exception'ları logla."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger = logging.getLogger("main")
    logger.critical("Yakalanmamış hata!", exc_info=(exc_type, exc_value, exc_tb))


def main():
    setup_logging()
    logger = logging.getLogger("main")
    logger.info("=" * 60)
    logger.info("Kalite Kontrol Sistemi başlatılıyor...")
    logger.info("=" * 60)

    sys.excepthook = global_exception_handler

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Kiosk mode desteği
    from main_ui import MainWindow
    window = MainWindow()

    if "--kiosk" in sys.argv:
        window.showFullScreen()
        logger.info("Kiosk modu aktif")
    else:
        window.showMaximized()

    logger.info("Uygulama hazır")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
