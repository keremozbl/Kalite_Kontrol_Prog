# -*- coding: utf-8 -*-
"""
Endüstriyel Kalite Kontrol Sistemi — Konfigürasyon Modülü
===========================================================
Tüm HSV eşikleri, ROI koordinatları, Modbus ayarları,
kamera parametreleri ve uygulama meta bilgileri.

Yazar  : Kalite Kontrol Ekibi
Tarih  : 2026-04
"""

import os
from dataclasses import dataclass, field
from typing import Tuple, Dict, Optional

# ─────────────────────────── UYGULAMA META ────────────────────────────
APP_NAME = "Kalite Kontrol Sistemi"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Endüstriyel Otomasyon"

# ─────────────────────────── YOLLAR ───────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "uretim_kayitlari.db")
NOK_IMAGE_DIR = os.path.join(BASE_DIR, "nok_images")
REFERENCE_IMAGE_DIR = os.path.join(BASE_DIR, "parçalar")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# Klasörleri oluştur
for _dir in [NOK_IMAGE_DIR, LOG_DIR]:
    os.makedirs(_dir, exist_ok=True)

# ─────────────────────────── RENK PALETİ (UI) ────────────────────────
class UIColors:
    """Endüstriyel dark-mode renk paleti."""
    BACKGROUND      = "#1e1e1e"
    CARD_BG         = "#2b2b2b"
    CARD_BORDER     = "#3d3d3d"
    TEXT_PRIMARY    = "#f0f0f0"
    TEXT_SECONDARY  = "#a0a0a0"
    TEXT_MUTED      = "#6c6c6c"

    OK_GREEN        = "#2ecc71"
    OK_GREEN_DARK   = "#1a7a42"
    NOK_RED         = "#e74c3c"
    NOK_RED_DARK    = "#8b1a1a"
    ACCENT_BLUE     = "#3498db"
    ACCENT_BLUE_DARK = "#1a6ba0"
    WARNING_ORANGE  = "#f39c12"
    CRITICAL_RED    = "#c0392b"

    HEADER_BG       = "#252525"
    BUTTON_BG       = "#353535"
    BUTTON_HOVER    = "#454545"
    TABLE_ROW_ALT   = "#323232"
    TABLE_HEADER    = "#383838"
    BORDER_FOCUS    = "#3498db"

# ─────────────────────────── HSV EŞİK DEĞERLERİ ─────────────────────
@dataclass
class HSVRange:
    """HSV renk aralığı tanımı."""
    lower: Tuple[int, int, int]
    upper: Tuple[int, int, int]

class FeltThresholds:
    """
    Keçe tespit eşik değerleri.

    Beyaz keçe: Yüksek Value, düşük Saturation
    Gri keçe  : Orta Value, düşük Saturation, metalden ayrım için edge detection
    Bakır halka (keçe eksik göstergesi): Yüksek Saturation, turuncu-sarı Hue
    """

    # Beyaz keçe — parlak, düşük doygunluk
    WHITE_FELT = HSVRange(
        lower=(0, 0, 180),
        upper=(180, 60, 255)
    )

    # Gri keçe — mat, orta parlaklık
    GRAY_FELT = HSVRange(
        lower=(0, 0, 70),
        upper=(180, 55, 165)
    )

    # Bakır halka tespiti — keçe EKSİK göstergesi
    # Eğer bu renk ROI'de görülüyorsa → keçe takılmamış → NOK
    COPPER_RING = HSVRange(
        lower=(10, 120, 140),
        upper=(25, 255, 255)
    )

    # Morfolojik işlem parametreleri
    MORPH_KERNEL_SIZE = 5
    MORPH_ITERATIONS = 2

    # Minimum kontur alanı (piksel²) — gürültü filtresi
    MIN_CONTOUR_AREA_WHITE = 500
    MIN_CONTOUR_AREA_GRAY = 400
    MIN_CONTOUR_AREA_COPPER = 8000

    # Canny Edge parametreleri (gri keçe ayrımı)
    CANNY_THRESHOLD_LOW = 50
    CANNY_THRESHOLD_HIGH = 150

# ─────────────────────────── ROI BÖLGELERİ ───────────────────────────
@dataclass
class ROIRegion:
    """
    İlgi Alanı (Region of Interest) — normalize koordinatlar (0.0-1.0).
    Gerçek piksel değerleri çalışma zamanında frame boyutuna göre hesaplanır.
    """
    x_start: float
    y_start: float
    x_end: float
    y_end: float
    label: str = ""

class ROIConfig:
    """
    Parça üzerindeki kontrol bölgeleri.
    Koordinatlar referans fotoğraflardan analiz edilerek belirlenmiştir.

    Parça görünümü (yatay pozisyon):
    [SOL: Keçe-1 (gri)] --- [MERKEZ: Seri No] --- [SAĞ: Keçe-2 (beyaz)]
    """

    # Sol montaj deliği çevresi — Gri keçe beklenen konum
    GRAY_FELT_ROI = ROIRegion(
        x_start=0.10, y_start=0.15,
        x_end=0.42, y_end=0.75,
        label="Gri Kece"
    )

    # Sağ montaj deliği çevresi — Beyaz keçe beklenen konum
    WHITE_FELT_ROI = ROIRegion(
        x_start=0.60, y_start=0.15,
        x_end=0.92, y_end=0.75,
        label="Beyaz Kece"
    )

    # Merkez bölge — Lazer markalama / Seri numarası
    SERIAL_NUMBER_ROI = ROIRegion(
        x_start=0.30, y_start=0.10,
        x_end=0.75, y_end=0.50,
        label="Seri No"
    )

# ─────────────────────────── KAMERA AYARLARI ─────────────────────────
@dataclass
class CameraConfig:
    """Endüstriyel kamera parametreleri."""
    index: int = 0
    width: int = 1280
    height: int = 720
    fps: int = 30
    exposure: float = -6.0  # Otomatik pozlama devre dışı, düşük değer
    auto_exposure: bool = True
    warmup_frames: int = 10  # Kamera açılınca atlanacak ilk kareler

# ─────────────────────────── MODBUS AYARLARI ─────────────────────────
@dataclass
class ModbusConfig:
    """PLC Modbus haberleşme konfigürasyonu."""

    # Protokol seçimi: "tcp" veya "rtu"
    protocol: str = "tcp"
    enabled: bool = False  # PLC opsiyonel - varsayılan kapalı

    # Modbus TCP Ayarları
    tcp_host: str = "192.168.1.100"
    tcp_port: int = 502

    # Modbus RTU Ayarları
    rtu_port: str = "COM3"
    rtu_baudrate: int = 9600
    rtu_parity: str = "N"
    rtu_stopbits: int = 1
    rtu_bytesize: int = 8

    # Ortak Ayarlar
    slave_id: int = 1
    timeout: float = 1.0  # saniye
    retries: int = 3
    retry_delay: float = 0.5  # saniye

    # Register Adresleri (Holding Registers — HR)
    # IEC 61131 standardına uygun adres düzeni
    REG_TRIGGER: int = 100       # HR100: Parça Hazır sinyali (PLC → PC)  (1=Hazır, 0=Boş)
    REG_RESULT: int = 101        # HR101: Sonuç (PC → PLC)  (0=Bekle, 1=OK, 2=NOK)
    REG_HEARTBEAT: int = 102     # HR102: Heartbeat / Watchdog (PC → PLC) (artan sayaç)
    REG_SERIAL_H: int = 103      # HR103: Seri No üst word (opsiyonel)
    REG_SERIAL_L: int = 104      # HR104: Seri No alt word (opsiyonel)
    REG_ERROR_CODE: int = 105    # HR105: Hata kodu (PC → PLC) (0=Yok, 1=Kamera, 2=OCR)
    REG_PART_COUNT: int = 106    # HR106: Toplam parça sayısı (PC → PLC)

    # Polling aralığı (ms)
    poll_interval_ms: int = 50

# ─────────────────────────── OCR AYARLARI ─────────────────────────────
@dataclass
class OCRConfig:
    """Optik karakter tanıma parametreleri."""
    engine: str = "easyocr"  # "easyocr" veya "paddleocr"
    languages: list = field(default_factory=lambda: ["en"])
    confidence_threshold: float = 0.5
    # Seri numara regex — şimdilik esnek, ileride güncellenebilir
    serial_regex: str = r".+"  # Herhangi bir metin kabul et
    # Görüntü ön-işleme
    adaptive_threshold_block: int = 11
    adaptive_threshold_c: int = 2
    gaussian_blur_kernel: int = 3

# ─────────────────────────── KARAR MEKANİZMASI ──────────────────────
class DecisionCriteria:
    """
    OK/NOK karar kriterleri.

    OK  = Beyaz keçe VAR + Gri keçe VAR + Seri No okunabilir
    NOK = Herhangi bir keçe eksik VEYA bakır halka görünür VEYA seri no okunamaz
    """
    REQUIRE_WHITE_FELT: bool = True
    REQUIRE_GRAY_FELT: bool = True
    REQUIRE_SERIAL_NUMBER: bool = True
    DETECT_COPPER_RING: bool = True  # Bakır halka = keçe eksik

# ─────────────────────────── AYARLAR PANELİ ──────────────────────────
SETTINGS_PASSWORD = "1234"  # Varsayılan şifre — üretimde değiştirilmeli

# ─────────────────────────── OPENVINO ────────────────────────────────
@dataclass
class OpenVINOConfig:
    """Intel N97 iGPU optimizasyonu için OpenVINO ayarları."""
    enabled: bool = False
    device: str = "GPU"  # "CPU", "GPU", "AUTO"
    model_path: str = ""
    precision: str = "FP16"  # N97 iGPU için FP16 optimal

# ─────────────────────────── LOG AYARLARI ─────────────────────────────
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_FILE = os.path.join(LOG_DIR, "kalite_kontrol.log")
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5
