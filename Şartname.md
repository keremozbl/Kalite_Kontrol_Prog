import os

# Markdown içeriği
markdown_text = """# Endüstriyel Görüntü İşleme ve Kalite Kontrol Sistemi - Teknik İsterler Dökümanı

Bu döküman, üretim hattı üzerindeki metal parçaların keçe varlık kontrolü ve seri numarası takibi projesine ait tüm teknik ve fonksiyonel gereksinimleri kapsamaktadır.

## 1. Sistem Mimarisi ve Donanım (Hardware)
Sistem, tozlu ve titreşimli fabrika ortamında 7/24 çalışacak şekilde tasarlanacaktır.

* **Panel PC:** E-Life EPC-616 G3 (Intel N97 İşlemci, Windows 10/11 IoT).
* **Kamera:** Endüstriyel USB Global Shutter (Hareket bulanıklığını önlemek için).
* **Optik:** CPL (Polarize) filtre seti (Metalik parlamaları minimize etmek için).
* **Aydınlatma:** Harici tetiklemeli Dome Light veya homojen beyaz LED panel.
* **Haberleşme:** RS485 üzerinden Modbus RTU veya Ethernet üzerinden Modbus TCP.
* **Mekanik:** Kamera ve aydınlatma için 3D yazıcı (Bambu Lab P1S) ile üretilmiş ayarlanabilir montaj aparatları.

## 2. Yazılım Gereksinimleri (Software Stack)
* **Dil:** Python 3.11+.
* **Görüntü İşleme:** OpenCV & OpenVINO (Intel N97 GPU optimizasyonu için).
* **OCR Modülü:** PaddleOCR veya EasyOCR.
* **Kullanıcı Arayüzü:** PyQt6.
* **Veritabanı:** SQLite3.
* **PLC Haberleşme:** PyModbus.

## 3. Fonksiyonel İsterler

### A. Görüntü Analizi ve Karar Mekanizması
1.  **Tetikleme (Trigger):** PLC'den "Parça Hazır" sinyali geldiğinde (milisaniyeler içinde) görüntü yakalanmalıdır.
2.  **Keçe Kontrolü:** Parça üzerindeki belirlenmiş ROI (İlgi Alanı) bölgelerinde:
    * Beyaz keçe tespiti (HSV Thresholding).
    * Gri keçe tespiti (HSV Thresholding).
3.  **Seri No Okuma (OCR):** Parça üzerindeki lazer markalama kodu okunmalı, regex ile format kontrolü yapılmalıdır.
4.  **Final Karar:** Keçeler mevcutsa ve seri no okunabiliyorsa **OK**, aksi takdirde **NOK** kararı üretilmelidir.

### B. Real-Time Haberleşme
* **PLC Yazma:** Analiz sonucu (OK: 1, NOK: 2) Modbus üzerinden ilgili register adresine anlık olarak yazılmalıdır.
* **Gecikme Süresi:** Toplam işlem süresi (Capture + Process + Modbus Write) hattın çevrim süresinin altında kalmalıdır.

### C. Kayıt ve Raporlama
* **Lokal Veritabanı:** Her parça geçişinde; `ID`, `Seri_No`, `Durum (OK/NOK)`, `Tarih_Saat` ve `Hata_Detayi` (örn: Gri keçe eksik) verileri SQLite'a kaydedilmelidir.
* **Görsel Arşiv:** Hatalı (NOK) olarak işaretlenen tüm parçaların o anki fotoğrafları, tarih-saat damgasıyla bir klasörde saklanmalıdır.
* **Excel Çıktısı:** Kullanıcı arayüzünden seçilen tarih aralığına göre tüm üretim verileri `.xlsx` formatında dışa aktarılabilmelidir.

## 4. Kullanıcı Arayüzü (GUI) İsterleri
* **Canlı Yayın:** Kameradan gelen görüntü üzerinde tespit edilen bölgelerin işaretlenmiş (bounding box) hali gösterilmelidir.
* **Sayaçlar:** Ekranda "Toplam", "OK" ve "NOK" sayıları canlı olarak güncellenmelidir.
* **Ayarlar Paneli:** Kamera pozlama süresi, renk eşik değerleri ve seri port konfigürasyonu şifreli bir menü ile değiştirilebilmelidir.

## 5. Kararlılık ve Güvenlik (Stability)
* **Auto-Start:** Panel PC açıldığında yazılım tam ekran (Kiosk Mode) olarak otomatik başlamalıdır.
* **Watchdog:** Yazılımın kilitlenmesi durumunda sistem kendini otomatik olarak yeniden başlatmalıdır.
* **Hata Yakalama:** Kamera kablosu çıkması veya PLC iletişiminin kopması durumunda ekranda sesli ve görsel alarm verilmelidir.

---
**Hazırlayan:** Kerem (Embedded Systems Engineer)
**Proje Durumu:** Planlama Aşaması
**Son Güncelleme:** 2026-04
"""

# Dosyayı kaydet
file_name = "PROJE_ISTERLERI.md"
with open(file_name, "w", encoding="utf-8") as f:
    f.write(markdown_text)

print(f"{file_name} başarıyla oluşturuldu.")