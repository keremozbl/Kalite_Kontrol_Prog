# Endüstriyel Kalite Kontrol Sistemi v1.0.0

Bu yazılım, Intel N97 işlemcili Panel PC'ler için optimize edilmiş, OpenCV tabanlı bir kalite kontrol uygulamasıdır. Parça üzerindeki beyaz keçe, gri keçe varlığını kontrol eder ve seri numarasını OCR ile okur.

## 🚀 Başlangıç

Projeyi başka bir bilgisayarda çalıştırmak için aşağıdaki adımları izleyin.

### 1. Gereksinimler

*   **Python:** 3.8 veya daha yeni bir sürüm (3.10-3.11 önerilir).
*   **Donanım:** 
    *   USB Kamera veya Dahili Webcam.
    *   (Opsiyonel) Modbus TCP/RTU destekli PLC.

### 2. Kurulum

Önce projeyi bilgisayarınıza indirin veya clone'layın:

```bash
git clone https://github.com/keremozbl/Kalite_Kontrol_Prog.git
cd Kalite_Kontrol_Prog
```

Gerekli kütüphaneleri yükleyin:

```bash
pip install -r requirements.txt
```

### 3. Çalıştırma

Uygulamayı başlatmak için:

```bash
python main.py
```

Eğer tam ekran (Kiosk) modunda başlatmak isterseniz:

```bash
python main.py --kiosk
```

## ⚙️ Yapılandırma

Tüm sistem ayarları `config.py` içerisinden yapılabilir:
*   **Kamera İndeksi:** `CameraConfig > index` (0, 1, 2...).
*   **PLC Bağlantısı:** `ModbusConfig > enabled: True/False`.
*   **Hata Eşikleri:** Keçe tespiti için HSV değerleri ve minimum alan ayarları.
*   **Şifre:** Ayarlar paneli varsayılan şifresi: `1234`.

## 🛠 Kullanılan Teknolojiler

*   **UI:** PyQt6 (Modern Dark Mode Arayüz)
*   **Görüntü İşleme:** OpenCV (Hızlı ve hafif analiz)
*   **OCR:** EasyOCR / PyTorch
*   **Haberleşme:** Pymodbus
*   **Veritabanı:** SQLite & OpenPyXL (Raporlama)

## ⚠️ Dikkat Edilmesi Gerekenler

1.  **OCR Hatası:** Bazı Python sürümlerinde (örn: 3.13) `torch` DLL hatası verebilir. Bu durumda program keçe tespitine devam eder ancak OCR devre dışı kalır. Sorunsuz OCR için Python 3.10 veya 3.11 önerilir.
2.  **Işık Koşulları:** Görüntü işleme HSV tabanlıdır. Ortam ışığı çok değişirse `config.py` üzerinden renk eşiklerini (thresholds) güncellemeniz gerekebilir.
3.  **Kamera İzinleri:** Windows'ta "Kamera Erişimine İzin Ver" ayarının açık olduğundan emin olun.

---
*Geliştirici: Antigravity - Industrial Coding Assistant*
