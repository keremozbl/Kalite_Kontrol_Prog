# -*- coding: utf-8 -*-
"""
Endüstriyel Kalite Kontrol Sistemi — PLC Haberleşme Modülü
============================================================
Modbus RTU (RS485) ve Modbus TCP üzerinden PLC iletişimi.
Opsiyonel modül — PLC bağlı olmadan da sistem çalışabilir.

Desteklenen Protokoller:
  - Modbus TCP (Ethernet)
  - Modbus RTU (RS485 / Seri Port)
"""

import time
import logging
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker

logger = logging.getLogger("plc_comm")


class PLCManager(QThread):
    """
    PLC haberleşme yöneticisi — arka plan thread'inde çalışır.

    Signals:
        tetikleme_alindi: PLC'den parça hazır sinyali geldiğinde
        baglanti_durumu_degisti(bool): Bağlantı durumu değiştiğinde
        hata_olustu(str): Haberleşme hatası oluştuğunda
        heartbeat_tick(int): Watchdog heartbeat sayacı
    """

    tetikleme_alindi = pyqtSignal()
    baglanti_durumu_degisti = pyqtSignal(bool)
    hata_olustu = pyqtSignal(str)
    heartbeat_tick = pyqtSignal(int)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        from config import ModbusConfig
        self.config = config or ModbusConfig()
        self._client = None
        self._running = False
        self._connected = False
        self._mutex = QMutex()
        self._heartbeat_counter = 0
        self._last_trigger_state = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_enabled(self) -> bool:
        return self.config.enabled

    # ─────────────────── BAĞLANTI YÖNETİMİ ──────────────────────────

    def _create_client(self):
        """Konfigürasyona göre Modbus client oluştur."""
        try:
            if self.config.protocol == "tcp":
                from pymodbus.client import ModbusTcpClient
                self._client = ModbusTcpClient(
                    host=self.config.tcp_host,
                    port=self.config.tcp_port,
                    timeout=self.config.timeout,
                    retries=self.config.retries,
                )
                logger.info(
                    f"Modbus TCP client oluşturuldu: "
                    f"{self.config.tcp_host}:{self.config.tcp_port}"
                )
            elif self.config.protocol == "rtu":
                from pymodbus.client import ModbusSerialClient
                self._client = ModbusSerialClient(
                    port=self.config.rtu_port,
                    baudrate=self.config.rtu_baudrate,
                    parity=self.config.rtu_parity,
                    stopbits=self.config.rtu_stopbits,
                    bytesize=self.config.rtu_bytesize,
                    timeout=self.config.timeout,
                    retries=self.config.retries,
                )
                logger.info(
                    f"Modbus RTU client oluşturuldu: "
                    f"{self.config.rtu_port} @ {self.config.rtu_baudrate}"
                )
            else:
                raise ValueError(f"Bilinmeyen protokol: {self.config.protocol}")
        except ImportError:
            logger.error("pymodbus yüklü değil: pip install pymodbus")
            self._client = None
            raise
        except Exception as e:
            logger.error(f"Client oluşturma hatası: {e}")
            self._client = None
            raise

    def baglanti_kur(self) -> bool:
        """PLC'ye bağlan. Başarılıysa True döner."""
        if not self.config.enabled:
            logger.info("PLC haberleşme devre dışı (opsiyonel mod)")
            return False

        try:
            if self._client is None:
                self._create_client()
            connected = self._client.connect()
            self._connected = connected
            self.baglanti_durumu_degisti.emit(connected)
            if connected:
                logger.info("PLC bağlantısı başarılı")
            else:
                logger.warning("PLC bağlantısı kurulamadı")
            return connected
        except Exception as e:
            self._connected = False
            self.baglanti_durumu_degisti.emit(False)
            self.hata_olustu.emit(f"PLC bağlantı hatası: {str(e)}")
            logger.error(f"PLC bağlantı hatası: {e}")
            return False

    def baglanti_kes(self):
        """PLC bağlantısını kapat."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._connected = False
            self.baglanti_durumu_degisti.emit(False)
            logger.info("PLC bağlantısı kapatıldı")

    # ─────────────────── REGISTER OKUMA / YAZMA ─────────────────────

    def register_oku(self, address: int, count: int = 1) -> Optional[list]:
        """Holding register oku."""
        if not self._connected or not self._client:
            return None
        try:
            with QMutexLocker(self._mutex):
                result = self._client.read_holding_registers(
                    address=address,
                    count=count,
                    slave=self.config.slave_id
                )
            if result.isError():
                logger.warning(f"Register okuma hatası @ {address}: {result}")
                return None
            return result.registers
        except Exception as e:
            self._handle_comm_error(f"Register okuma hatası @ {address}: {e}")
            return None

    def register_yaz(self, address: int, value: int) -> bool:
        """Holding register'a tek değer yaz."""
        if not self._connected or not self._client:
            return False
        try:
            with QMutexLocker(self._mutex):
                result = self._client.write_register(
                    address=address,
                    value=value,
                    slave=self.config.slave_id
                )
            if result.isError():
                logger.warning(f"Register yazma hatası @ {address}: {result}")
                return False
            logger.debug(f"Register yazıldı: HR{address} = {value}")
            return True
        except Exception as e:
            self._handle_comm_error(f"Register yazma hatası @ {address}: {e}")
            return False

    # ─────────────────── YÜKSEK SEVİYE FONKSİYONLAR ─────────────────

    def sonuc_yaz(self, durum: str) -> bool:
        """
        Analiz sonucunu PLC'ye yaz.
        OK → 1, NOK → 2

        Args:
            durum: "OK" veya "NOK"
        """
        value = 1 if durum == "OK" else 2
        success = self.register_yaz(self.config.REG_RESULT, value)
        if success:
            logger.info(f"PLC'ye sonuç yazıldı: {durum} ({value})")
        return success

    def hata_kodu_yaz(self, kod: int) -> bool:
        """
        Hata kodunu PLC'ye yaz.
        0=Yok, 1=Kamera hatası, 2=OCR hatası, 3=Genel hata
        """
        return self.register_yaz(self.config.REG_ERROR_CODE, kod)

    def parca_sayisi_yaz(self, sayi: int) -> bool:
        """Toplam parça sayısını PLC'ye yaz."""
        return self.register_yaz(self.config.REG_PART_COUNT, sayi)

    def tetikleme_kontrol(self) -> bool:
        """
        Tetikleme register'ını oku.
        1 = Parça Hazır, 0 = Boş

        Returns:
            True eğer yeni tetikleme varsa
        """
        regs = self.register_oku(self.config.REG_TRIGGER)
        if regs is None:
            return False
        current = regs[0]
        # Yükselen kenar tespiti (0→1)
        if current == 1 and self._last_trigger_state == 0:
            self._last_trigger_state = current
            return True
        self._last_trigger_state = current
        return False

    def _heartbeat_gonder(self):
        """Watchdog heartbeat sayacını artır ve PLC'ye yaz."""
        self._heartbeat_counter = (self._heartbeat_counter + 1) % 65536
        self.register_yaz(self.config.REG_HEARTBEAT, self._heartbeat_counter)
        self.heartbeat_tick.emit(self._heartbeat_counter)

    # ─────────────────── HATA YÖNETİMİ ──────────────────────────────

    def _handle_comm_error(self, msg: str):
        """Haberleşme hatası işle — bağlantıyı kontrol et."""
        logger.error(msg)
        self._connected = False
        self.baglanti_durumu_degisti.emit(False)
        self.hata_olustu.emit(msg)

    def _yeniden_baglan(self) -> bool:
        """Üstel geri çekilme ile yeniden bağlanma dene."""
        for retry in range(self.config.retries):
            delay = self.config.retry_delay * (2 ** retry)
            logger.info(f"Yeniden bağlanma denemesi {retry + 1}/{self.config.retries} "
                       f"({delay:.1f}s sonra)")
            time.sleep(delay)
            if self.baglanti_kur():
                return True
        logger.error("Tüm yeniden bağlanma denemeleri başarısız")
        return False

    # ─────────────────── ANA DÖNGÜ (THREAD) ──────────────────────────

    def run(self):
        """
        Arka plan thread'i — PLC tetikleme sinyalini dinler.
        config.enabled=False ise çalışmaz.
        """
        if not self.config.enabled:
            logger.info("PLC thread başlatılmadı (devre dışı)")
            return

        self._running = True
        logger.info("PLC dinleme thread'i başlatıldı")

        # İlk bağlantı
        if not self.baglanti_kur():
            if not self._yeniden_baglan():
                self.hata_olustu.emit("PLC'ye bağlanılamadı — tüm denemeler başarısız")
                self._running = False
                return

        poll_sec = self.config.poll_interval_ms / 1000.0
        heartbeat_interval = 50  # Her 50 poll'da bir heartbeat
        poll_count = 0

        while self._running:
            try:
                if not self._connected:
                    if not self._yeniden_baglan():
                        time.sleep(5)
                        continue

                # Tetikleme kontrolü
                if self.tetikleme_kontrol():
                    logger.info(">>> PLC tetikleme sinyali alındı!")
                    self.tetikleme_alindi.emit()

                # Periyodik heartbeat
                poll_count += 1
                if poll_count >= heartbeat_interval:
                    self._heartbeat_gonder()
                    poll_count = 0

                time.sleep(poll_sec)

            except Exception as e:
                logger.error(f"PLC döngü hatası: {e}")
                self._connected = False
                self.baglanti_durumu_degisti.emit(False)
                time.sleep(1)

        self.baglanti_kes()
        logger.info("PLC dinleme thread'i durduruldu")

    def durdur(self):
        """PLC thread'ini güvenli şekilde durdur."""
        self._running = False
        self.wait(3000)  # Max 3 saniye bekle
        logger.info("PLC manager durduruldu")


class PLCSimulator:
    """
    PLC olmadan test için simülatör.
    Aynı arayüzü sağlar, gerçek haberleşme yapmaz.
    """

    def __init__(self):
        self._connected = False
        self._registers = {}
        logger.info("PLC Simülatör başlatıldı (test modu)")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_enabled(self) -> bool:
        return False

    def baglanti_kur(self) -> bool:
        self._connected = True
        return True

    def baglanti_kes(self):
        self._connected = False

    def sonuc_yaz(self, durum: str) -> bool:
        logger.info(f"[SİMÜLATÖR] Sonuç: {durum}")
        return True

    def hata_kodu_yaz(self, kod: int) -> bool:
        logger.info(f"[SİMÜLATÖR] Hata kodu: {kod}")
        return True

    def parca_sayisi_yaz(self, sayi: int) -> bool:
        return True

    def tetikleme_kontrol(self) -> bool:
        return False

    def durdur(self):
        pass
