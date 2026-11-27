# 103 maçlık model optimizasyonu

Kesim 27 Kasım 2026 09.55.23 TRT. Önceki tahmin arşivleri korunmuştur. Bu dizin aday araştırma değerlendirmesidir. Üretim kalibrasyonu veya ileriye dönük kabul örneği olarak kullanılmaz.

Kronolojik araştırma setinde 2.322 uygun örnek, 504 tam takım gücü, 2.047 başlangıçtan başlangıca yük ve 2 tarihli dış etken örneği vardı. Üç girdinin ortak örnek sayısı sıfır olduğu için A/B/C ağırlıkları değerlendirilemedi. İstatistiksel adayların ortak bölümü eğitim 169, doğrulama 133 ve test 124 maçtır. Bir geç sonuç bölme sınırında çıkarıldı. Adaylar kendi kapsamlarındaki daha geniş eğitim verisinden öğrenebildi. Ortak test üç hafta içerdi. Dış etkensiz saha-5 modelinin ayrı geniş testi 533 maç ve 11 hafta içerdi. Bu geniş test tarihsel yeniden oluşturmadır.

95 maçta dört pazar için en az bir istatistiksel aday üretildi. 69 tam formlu maçın tahminlerinin hiçbiri değiştirilmedi. 26 maç ayrı istatistiksel alternatifle kapsandı. Yük kullanan model 58 maçta, tam form modeli 69 maçta, saha-5 modeli 84 maçta hesaplandı. 95 aday için PUP BLOCKED döndürdü. Önceki Tur-2 ve Auto-Control sonuçları ayrı raporlanır. Skor dağılımı mevcut modelden gelir, istatistiksel adaylar için yeni ortak skor dağılımı kurulmadı.

9 resmî çapraz skor kontrolü yeniden doğrulandı. Kaynak üreticisi bağımsızlığı için yeni kabul verilmedi. Model hesaplamasında oran girdisi kullanılmaz. Oran, karar ve canlı pencere kuralları mevcut kapılarda kullanılır. Önemli eksik, ceza, rotasyon, millî yük ve olağanüstü hava için etkisi tahmin edilebilecek ortak tarihsel örneklem sağlanamadı.

Brier, log-loss, doğruluk, ECE10 ve en az yüzde 70 tahminlerin isabeti için CSV dosyasına bakın. Veri kapsamı, 103 maçlık çıktı, PUP kanıtı, süre ve girdi özetleri JSON içindedir. Yerel 958 test geçmiştir.
