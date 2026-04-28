# -*- coding: utf-8 -*-
"""
Endüstriyel Kalite Kontrol Sistemi — Görüntü İşleme Motoru
=============================================================
OpenCV tabanlı keçe varlık kontrolü ve OCR seri numarası okuma.

Pipeline:
  Tetikleme → Kare Yakalama → ROI Kesme →
  ├─ Beyaz Keçe: HSV Filter → Morphology → Contour → Min Area
  ├─ Gri Keçe : HSV Filter + Edge Detection → Contour → Min Area
  ├─ Bakır Halka: HSV Filter → Contour → Keçe Eksik Tespiti
  └─ Seri No  : Grayscale → Adaptive Threshold → OCR → Validate
  → Karar (OK/NOK)
"""

import os
import cv2
import numpy as np
import logging
import re
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger("vision_engine")


@dataclass
class AnalysisResult:
    """Tek bir parça analizi sonucu."""
    durum: str = "NOK"              # "OK" veya "NOK"
    beyaz_kece: bool = False         # Beyaz keçe var mı
    gri_kece: bool = False           # Gri keçe var mı
    bakir_halka_tespit: bool = False  # Bakır halka görüldü mü (keçe eksik)
    seri_no: str = ""                # Okunan seri numarası
    seri_no_guven: float = 0.0       # OCR güven skoru
    hata_detayi: str = ""            # Hata açıklaması
    islem_suresi_ms: float = 0.0     # İşlem süresi (ms)
    annotated_frame: np.ndarray = None  # İşaretlenmiş görüntü

    def __post_init__(self):
        if self.annotated_frame is None:
            self.annotated_frame = np.array([])


class VisionEngine:
    """
    Görüntü işleme motoru.
    Keçe tespiti, bakır halka tespiti ve OCR işlemlerini yürütür.
    """

    def __init__(self):
        from config import (
            FeltThresholds, ROIConfig, OCRConfig,
            CameraConfig, DecisionCriteria, OpenVINOConfig, NOK_IMAGE_DIR
        )
        self.thresholds = FeltThresholds()
        self.roi_config = ROIConfig()
        self.ocr_config = OCRConfig()
        self.camera_config = CameraConfig()
        self.criteria = DecisionCriteria()
        self.openvino_config = OpenVINOConfig()
        self.nok_image_dir = NOK_IMAGE_DIR

        self._camera: Optional[cv2.VideoCapture] = None
        self._ocr_reader = None
        self._ocr_initialized = False
        self._ocr_init_failed = False
        self._camera_open = False

        # OpenVINO placeholder
        self._openvino_model = None

        logger.info("Vision Engine başlatıldı")

    # ─────────────────── KAMERA YÖNETİMİ ────────────────────────────

    def kamera_baslat(self, index: int = None) -> bool:
        """
        Kamerayı başlat ve yapılandır.

        Args:
            index: Kamera indeksi (None ise config'den alınır)

        Returns:
            True ise başarılı
        """
        idx = index if index is not None else self.camera_config.index
        try:
            self._camera = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not self._camera.isOpened():
                # DirectShow başarısız olursa varsayılan backend dene
                self._camera = cv2.VideoCapture(idx)

            if not self._camera.isOpened():
                logger.error(f"Kamera açılamadı (index={idx})")
                self._camera_open = False
                return False

            # Parametre ayarla
            self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.camera_config.width)
            self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.camera_config.height)
            self._camera.set(cv2.CAP_PROP_FPS, self.camera_config.fps)

            if not self.camera_config.auto_exposure:
                self._camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual
                self._camera.set(cv2.CAP_PROP_EXPOSURE, self.camera_config.exposure)

            # Ilk kareleri at (warm-up)
            for _ in range(self.camera_config.warmup_frames):
                self._camera.read()

            self._camera_open = True
            actual_w = int(self._camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logger.info(f"Kamera başlatıldı: index={idx}, {actual_w}x{actual_h}")
            return True

        except Exception as e:
            logger.error(f"Kamera başlatma hatası: {e}")
            self._camera_open = False
            return False

    def kamera_durdur(self):
        """Kamerayı kapat."""
        if self._camera and self._camera.isOpened():
            self._camera.release()
        self._camera_open = False
        logger.info("Kamera durduruldu")

    @property
    def kamera_durumu(self) -> bool:
        """Kamera açık ve çalışıyor mu?"""
        return self._camera_open and self._camera is not None and self._camera.isOpened()

    def goruntu_yakala(self) -> Optional[np.ndarray]:
        """Kameradan tek kare yakala."""
        if not self.kamera_durumu:
            logger.warning("Kamera çalışmıyor — görüntü yakalanamadı")
            return None
        ret, frame = self._camera.read()
        if not ret or frame is None:
            logger.error("Kare yakalanamadı")
            self._camera_open = False
            return None
        return frame

    # ─────────────────── OCR BAŞLATMA ────────────────────────────────

    def _init_ocr(self):
        """OCR motorunu tembel yükleme ile başlat."""
        if self._ocr_initialized:
            return
        if self._ocr_init_failed:
            return  # Daha önce başarısız olduysa tekrar deneme

        try:
            if self.ocr_config.engine == "easyocr":
                import easyocr
                self._ocr_reader = easyocr.Reader(
                    self.ocr_config.languages,
                    gpu=False  # N97 — CPU modunda (OpenVINO ile GPU opsiyonel)
                )
                logger.info("EasyOCR başlatıldı")
            elif self.ocr_config.engine == "paddleocr":
                from paddleocr import PaddleOCR
                self._ocr_reader = PaddleOCR(
                    use_angle_cls=True,
                    lang="en",
                    use_gpu=False,
                    show_log=False
                )
                logger.info("PaddleOCR başlatıldı")
            self._ocr_initialized = True
        except Exception as e:
            logger.warning(f"OCR yüklenemedi (analiz OCR olmadan devam edecek): {e}")
            self._ocr_initialized = False
            self._ocr_init_failed = True

    # ─────────────────── ROI YARDIMCI ────────────────────────────────

    def _roi_kes(self, frame: np.ndarray, roi) -> np.ndarray:
        """ROI bölgesini normalize koordinatlardan kırp."""
        h, w = frame.shape[:2]
        x1 = int(roi.x_start * w)
        y1 = int(roi.y_start * h)
        x2 = int(roi.x_end * w)
        y2 = int(roi.y_end * h)
        return frame[y1:y2, x1:x2].copy()

    def _roi_coords(self, frame: np.ndarray, roi) -> Tuple[int, int, int, int]:
        """ROI'nin piksel koordinatlarını döndür."""
        h, w = frame.shape[:2]
        return (
            int(roi.x_start * w), int(roi.y_start * h),
            int(roi.x_end * w), int(roi.y_end * h)
        )

    # ─────────────────── BEYAZ KEÇE TESPİTİ ─────────────────────────

    def beyaz_kece_kontrol(self, frame: np.ndarray) -> Tuple[bool, np.ndarray]:
        """
        Beyaz keçe varlığını kontrol et.
        HSV filtreleme + morfolojik işlemler + kontur analizi.

        Returns:
            (keçe_var_mı, maskelenmis_görüntü)
        """
        roi = self._roi_kes(frame, self.roi_config.WHITE_FELT_ROI)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # HSV maskeleme
        lower = np.array(self.thresholds.WHITE_FELT.lower)
        upper = np.array(self.thresholds.WHITE_FELT.upper)
        mask = cv2.inRange(hsv, lower, upper)

        # Morfolojik temizlik
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (self.thresholds.MORPH_KERNEL_SIZE, self.thresholds.MORPH_KERNEL_SIZE)
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel,
                                iterations=self.thresholds.MORPH_ITERATIONS)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        # Kontur analizi
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_contours = [
            c for c in contours
            if cv2.contourArea(c) >= self.thresholds.MIN_CONTOUR_AREA_WHITE
        ]

        found = len(valid_contours) > 0
        logger.info(
            f"Beyaz keçe: {'BULUNDU' if found else 'BULUNAMADI'} "
            f"({len(valid_contours)} geçerli kontur)"
        )
        return found, mask

    # ─────────────────── GRİ KEÇE TESPİTİ ───────────────────────────

    def gri_kece_kontrol(self, frame: np.ndarray) -> Tuple[bool, np.ndarray]:
        """
        Gri keçe varlığını kontrol et.
        HSV filtreleme + Canny Edge Detection + kontur analizi.
        Metalik yüzeyden ayrım için ek edge-based kontrol.

        Returns:
            (keçe_var_mı, maskelenmis_görüntü)
        """
        roi = self._roi_kes(frame, self.roi_config.GRAY_FELT_ROI)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # HSV maskeleme
        lower = np.array(self.thresholds.GRAY_FELT.lower)
        upper = np.array(self.thresholds.GRAY_FELT.upper)
        hsv_mask = cv2.inRange(hsv, lower, upper)

        # Canny Edge — keçe kenarlarını tespit et
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(
            blurred,
            self.thresholds.CANNY_THRESHOLD_LOW,
            self.thresholds.CANNY_THRESHOLD_HIGH
        )

        # Edge mask ile HSV mask'i birleştir
        # Keçe bölgesi: HSV uyuyor + belirgin kenar yapısı
        edge_dilated = cv2.dilate(edges, None, iterations=2)
        combined_mask = cv2.bitwise_and(hsv_mask, edge_dilated)

        # Ek olarak sadece HSV mask ile de kontrol (kenar zayıfsa)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (self.thresholds.MORPH_KERNEL_SIZE, self.thresholds.MORPH_KERNEL_SIZE)
        )
        hsv_cleaned = cv2.morphologyEx(hsv_mask, cv2.MORPH_CLOSE, kernel,
                                        iterations=self.thresholds.MORPH_ITERATIONS)
        hsv_cleaned = cv2.morphologyEx(hsv_cleaned, cv2.MORPH_OPEN, kernel, iterations=1)

        # Her iki yöntemle de kontrol
        contours_combined, _ = cv2.findContours(
            combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        contours_hsv, _ = cv2.findContours(
            hsv_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        valid_combined = [
            c for c in contours_combined
            if cv2.contourArea(c) >= self.thresholds.MIN_CONTOUR_AREA_GRAY
        ]
        valid_hsv = [
            c for c in contours_hsv
            if cv2.contourArea(c) >= self.thresholds.MIN_CONTOUR_AREA_GRAY
        ]

        found = len(valid_combined) > 0 or len(valid_hsv) > 0
        logger.info(
            f"Gri keçe: {'BULUNDU' if found else 'BULUNAMADI'} "
            f"(combined: {len(valid_combined)}, hsv: {len(valid_hsv)} kontur)"
        )
        return found, hsv_cleaned

    # ─────────────────── BAKIR HALKA TESPİTİ (KEÇE EKSİK) ──────────

    def bakir_halka_kontrol(self, frame: np.ndarray, roi_type: str = "gray") -> Tuple[bool, np.ndarray]:
        """
        Bakır halka tespiti — keçe takılmamış göstergesi.
        Eğer montaj deliği çevresinde bakır/turuncu renk görülüyorsa
        bu alandaki keçe eksiktir.

        Args:
            roi_type: "gray" veya "white" — hangi ROI'de bakılacak

        Returns:
            (bakır_halka_var_mı, maskelenmis_görüntü)
        """
        if roi_type == "white":
            roi_region = self.roi_config.WHITE_FELT_ROI
        else:
            roi_region = self.roi_config.GRAY_FELT_ROI

        roi = self._roi_kes(frame, roi_region)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Bakır/turuncu renk aralığı
        lower = np.array(self.thresholds.COPPER_RING.lower)
        upper = np.array(self.thresholds.COPPER_RING.upper)
        mask = cv2.inRange(hsv, lower, upper)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid = [
            c for c in contours
            if cv2.contourArea(c) >= self.thresholds.MIN_CONTOUR_AREA_COPPER
        ]

        found = len(valid) > 0
        if found:
            logger.warning(
                f"⚠ BAKIR HALKA TESPİT EDİLDİ ({roi_type} ROI) — Keçe eksik!"
            )
        return found, mask

    # ─────────────────── SERİ NUMARA OKUMA (OCR) ─────────────────────

    def seri_no_oku(self, frame: np.ndarray) -> Tuple[str, float]:
        """
        Lazer markalama alanından seri numarasını oku.

        İşlem adımları:
        1. ROI kırpma
        2. Gri tonlama
        3. Parlama giderme (adaptive threshold)
        4. Gauss bulanıklaştırma
        5. OCR motoru çalıştır
        6. Regex doğrulama

        Returns:
            (seri_numara, güven_skoru)
        """
        self._init_ocr()
        if not self._ocr_initialized:
            logger.error("OCR motoru hazır değil")
            return "", 0.0

        roi = self._roi_kes(frame, self.roi_config.SERIAL_NUMBER_ROI)

        # Ön-işleme
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # CLAHE — kontrast artırma (parlama ve gölge dengeleme)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Gauss bulanıklaştırma
        blurred = cv2.GaussianBlur(
            enhanced,
            (self.ocr_config.gaussian_blur_kernel, self.ocr_config.gaussian_blur_kernel),
            0
        )

        # Adaptive threshold — parlama giderme
        thresh = cv2.adaptiveThreshold(
            blurred, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            self.ocr_config.adaptive_threshold_block,
            self.ocr_config.adaptive_threshold_c
        )

        # OCR çalıştır
        try:
            if self.ocr_config.engine == "easyocr":
                results = self._ocr_reader.readtext(thresh)
                if results:
                    # En yüksek güvenli sonucu al
                    best = max(results, key=lambda x: x[2])
                    text = best[1].strip()
                    confidence = best[2]
                else:
                    text, confidence = "", 0.0

            elif self.ocr_config.engine == "paddleocr":
                results = self._ocr_reader.ocr(thresh, cls=True)
                if results and results[0]:
                    all_texts = []
                    all_confs = []
                    for line in results[0]:
                        all_texts.append(line[1][0])
                        all_confs.append(line[1][1])
                    text = " ".join(all_texts).strip()
                    confidence = sum(all_confs) / len(all_confs)
                else:
                    text, confidence = "", 0.0
            else:
                text, confidence = "", 0.0

        except Exception as e:
            logger.error(f"OCR hatası: {e}")
            text, confidence = "", 0.0

        # Regex doğrulama
        if text and self.ocr_config.serial_regex:
            if not re.search(self.ocr_config.serial_regex, text):
                logger.warning(f"OCR sonucu regex'e uymadı: '{text}'")
                # Yine de döndür ama güveni düşür
                confidence *= 0.5

        logger.debug(f"OCR sonuç: '{text}' (güven: {confidence:.2f})")
        return text, confidence

    # ─────────────────── TAM ANALİZ ──────────────────────────────────

    def tam_analiz(self, frame: np.ndarray = None) -> AnalysisResult:
        """
        Tam parça analizi — tüm kontrolleri çalıştır ve sonuç döndür.

        Args:
            frame: Analiz edilecek kare. None ise kameradan yakalar.

        Returns:
            AnalysisResult nesnesi
        """
        start_time = cv2.getTickCount()
        result = AnalysisResult()

        # Kare yakala
        if frame is None:
            frame = self.goruntu_yakala()
            if frame is None:
                result.hata_detayi = "Kamera görüntüsü alınamadı"
                return result

        annotated = frame.copy()
        hata_listesi = []

        # ── 1. Beyaz Keçe Kontrolü ───────────────────────────────────
        try:
            result.beyaz_kece, white_mask = self.beyaz_kece_kontrol(frame)
            x1, y1, x2, y2 = self._roi_coords(frame, self.roi_config.WHITE_FELT_ROI)
            color = (46, 204, 113) if result.beyaz_kece else (231, 76, 60)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"Beyaz Kece: {'OK' if result.beyaz_kece else 'YOK'}"
            cv2.putText(annotated, label, (x1, y1 - 8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            if not result.beyaz_kece:
                hata_listesi.append("Beyaz kece eksik")
        except Exception as e:
            logger.error(f"Beyaz keçe kontrol hatası: {e}")
            hata_listesi.append(f"Beyaz kece hata: {e}")

        # ── 2. Gri Keçe Kontrolü ─────────────────────────────────────
        try:
            result.gri_kece, gray_mask = self.gri_kece_kontrol(frame)
            x1, y1, x2, y2 = self._roi_coords(frame, self.roi_config.GRAY_FELT_ROI)
            color = (46, 204, 113) if result.gri_kece else (231, 76, 60)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"Gri Kece: {'OK' if result.gri_kece else 'YOK'}"
            cv2.putText(annotated, label, (x1, y1 - 8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            if not result.gri_kece:
                hata_listesi.append("Gri kece eksik")
        except Exception as e:
            logger.error(f"Gri keçe kontrol hatası: {e}")
            hata_listesi.append(f"Gri kece hata: {e}")

        # ── 3. Bakır Halka Kontrolü (Keçe Eksik Göstergesi) ──────────
        try:
            if self.criteria.DETECT_COPPER_RING:
                # Her iki ROI'de de kontrol et
                copper_gray, _ = self.bakir_halka_kontrol(frame, "gray")
                copper_white, _ = self.bakir_halka_kontrol(frame, "white")
                result.bakir_halka_tespit = copper_gray or copper_white
                if copper_gray:
                    hata_listesi.append("Sol ROI: Bakir halka acik (kece eksik)")
                if copper_white:
                    hata_listesi.append("Sag ROI: Bakir halka acik (kece eksik)")
        except Exception as e:
            logger.error(f"Bakır halka kontrol hatası: {e}")

        # ── 4. Seri Numara Okuma (OCR) ────────────────────────────────
        try:
            result.seri_no, result.seri_no_guven = self.seri_no_oku(frame)
            x1, y1, x2, y2 = self._roi_coords(frame, self.roi_config.SERIAL_NUMBER_ROI)
            has_serial = bool(result.seri_no) and result.seri_no_guven >= self.ocr_config.confidence_threshold
            color = (52, 152, 219) if has_serial else (231, 76, 60)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"SN: {result.seri_no[:20]}" if result.seri_no else "SN: OKUNAMADI"
            cv2.putText(annotated, label, (x1, y1 - 8),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            if not has_serial and self.criteria.REQUIRE_SERIAL_NUMBER:
                hata_listesi.append("Seri numara okunamadi")
        except Exception as e:
            logger.error(f"OCR hatası: {e}")
            hata_listesi.append(f"OCR hata: {e}")

        # ── 5. Final Karar ────────────────────────────────────────────
        ok_conditions = []
        if self.criteria.REQUIRE_WHITE_FELT:
            ok_conditions.append(result.beyaz_kece)
        if self.criteria.REQUIRE_GRAY_FELT:
            ok_conditions.append(result.gri_kece)
        if self.criteria.REQUIRE_SERIAL_NUMBER:
            has_serial = bool(result.seri_no) and result.seri_no_guven >= self.ocr_config.confidence_threshold
            ok_conditions.append(has_serial)
        if self.criteria.DETECT_COPPER_RING:
            ok_conditions.append(not result.bakir_halka_tespit)  # Bakır halka OLMAMALI

        result.durum = "OK" if all(ok_conditions) else "NOK"
        result.hata_detayi = " | ".join(hata_listesi) if hata_listesi else ""
        result.annotated_frame = annotated

        # İşlem süresi
        end_time = cv2.getTickCount()
        result.islem_suresi_ms = (end_time - start_time) / cv2.getTickFrequency() * 1000

        # Durum etiketi
        status_color = (46, 204, 113) if result.durum == "OK" else (0, 0, 231)
        cv2.putText(annotated, result.durum, (20, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, status_color, 3)
        cv2.putText(annotated, f"{result.islem_suresi_ms:.0f}ms", (20, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        logger.info(
            f"Analiz tamamlandı: {result.durum} | "
            f"Süre: {result.islem_suresi_ms:.1f}ms | "
            f"Beyaz: {result.beyaz_kece} | Gri: {result.gri_kece} | "
            f"Bakır: {result.bakir_halka_tespit} | SN: '{result.seri_no}'"
        )

        return result

    # ─────────────────── NOK GÖRSEL ARŞİV ────────────────────────────

    def nok_gorsel_kaydet(self, frame: np.ndarray, seri_no: str = "") -> str:
        """
        NOK parçanın görselini tarih damgalı olarak kaydet.

        Returns:
            Kaydedilen dosya yolu
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        seri_clean = re.sub(r'[^\w]', '_', seri_no) if seri_no else "unknown"
        filename = f"NOK_{timestamp}_{seri_clean}.jpg"
        filepath = os.path.join(self.nok_image_dir, filename)
        try:
            cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            logger.info(f"NOK görsel kaydedildi: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"NOK görsel kaydetme hatası: {e}")
            return ""

    # ─────────────────── OpenVINO PLACEHOLDER'LAR ────────────────────

    def _openvino_init(self):
        """
        [PLACEHOLDER] OpenVINO modelini yükle.
        Intel N97 iGPU üzerinde optimize çıkarım için.

        Kullanım senaryoları:
        - Derin öğrenme tabanlı keçe tespiti (YOLOv8-nano vb.)
        - OCR modeli GPU hızlandırma
        - Anomali tespiti

        Gerekli adımlar:
        1. pip install openvino
        2. Model eğit ve .xml/.bin formatına dönüştür:
           mo --input_model model.onnx --compress_to_fp16
        3. Bu fonksiyonu implement et
        """
        if not self.openvino_config.enabled:
            return

        try:
            # from openvino.runtime import Core
            # ie = Core()
            # model = ie.read_model(self.openvino_config.model_path)
            # compiled = ie.compile_model(model, self.openvino_config.device)
            # self._openvino_model = compiled
            # logger.info(f"OpenVINO model yüklendi: {self.openvino_config.device}")
            logger.info("[PLACEHOLDER] OpenVINO henüz yapılandırılmadı")
        except Exception as e:
            logger.error(f"OpenVINO yükleme hatası: {e}")

    def _openvino_preprocess(self, frame: np.ndarray) -> np.ndarray:
        """[PLACEHOLDER] OpenVINO model girişi için ön-işleme."""
        # Normalizasyon, boyutlandırma, tensor dönüşümü
        # processed = cv2.resize(frame, (640, 640))
        # processed = processed.astype(np.float32) / 255.0
        # processed = np.transpose(processed, (2, 0, 1))
        # processed = np.expand_dims(processed, 0)
        return frame

    def _openvino_infer(self, preprocessed: np.ndarray) -> dict:
        """[PLACEHOLDER] OpenVINO çıkarımı çalıştır."""
        # if self._openvino_model:
        #     result = self._openvino_model([preprocessed])
        #     return {"detections": result[0], "confidences": result[1]}
        return {}

    # ─────────────────── REFERANS GÖRÜNTÜ ANALİZ ─────────────────────

    def referans_analiz(self, image_path: str) -> Dict[str, Any]:
        """
        Referans görüntüyü analiz et — HSV değerlerini kalibrasyon için kullan.

        Args:
            image_path: Referans görüntü dosya yolu

        Returns:
            HSV istatistikleri ve tespit sonuçları
        """
        frame = cv2.imread(image_path)
        if frame is None:
            logger.error(f"Referans görüntü okunamadı: {image_path}")
            return {}

        result = self.tam_analiz(frame)
        return {
            "dosya": image_path,
            "durum": result.durum,
            "beyaz_kece": result.beyaz_kece,
            "gri_kece": result.gri_kece,
            "bakir_halka": result.bakir_halka_tespit,
            "seri_no": result.seri_no,
            "islem_suresi_ms": result.islem_suresi_ms,
        }

    # ─────────────────── TEMİZLİK ────────────────────────────────────

    def cleanup(self):
        """Tüm kaynakları temizle."""
        self.kamera_durdur()
        self._ocr_reader = None
        self._ocr_initialized = False
        self._openvino_model = None
        logger.info("Vision Engine kaynakları temizlendi")
