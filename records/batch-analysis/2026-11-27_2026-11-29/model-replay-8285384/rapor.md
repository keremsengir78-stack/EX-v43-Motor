# EX v4.3 · 69 maçlık uçtan uca araştırma testi

Başlangıç a342531a55a53a873367850c009b00eb251af288. Denetim kodu 828538490b0eb08d1dbcd3878abf1f06d231d905. Kaynaklar 15120670577, 15120047712 ve 15120800827 numaralı maç önü arşivleri ve bu maçların orijinal karar kesiminde mevcut tarihsel kayıtlar.

| Ölçüm | Sonuç |
|---|---:|
| Tam formu bulunan ve dört ham pazarı yeniden hesaplanan maç | 69/69 |
| Referans ve V1 birleşik pazar yeniden hesaplaması | 552/552 |
| Maç bazında iki skor dağılımı | 69/69 |
| PUP çalıştırılan maç | 69/69 |
| PUP uygun seçim | 0/69 |
| Tüm %50/%30/%20 araştırma bileşenleri dolu maç | 0/69 |
| Doğrulanmış EX-G / gerçek FINAL | 0 / 0 |

Takımların son 5 ve 10 ilgili saha, mevcut sezon ve önceki sezon ilgili saha pencereleri tam olarak yeniden kuruldu. Hesap girdileri her maç için örnek tarihleri, olay kimlikleri ve hücum-savunma oranlarıyla JSON içinde. Referans ağırlıklı hücum-savunma formunu kullanır. V1 ayrıca rakip gücüne göre düzeltilmiş form, takım kalite tabanı, varsa lig farkı ve dondurulmuş model ayarlarını kullanır. Bağlam ve dış etken bileşenleri ayrı izlenir. Ham pazar olasılıklarına eksik bileşen ataması yapılmadı. Takım gücü araştırma bileşeni 69 maçta, maç koşulları 56 maçta ve dış etken 0 maçta bulunuyordu.

Bağımsız 48×48 skor ızgarası ile en büyük olasılık farkı 3,33e-16. Arşivlenmiş dört pazar ile maksimum fark 1,55e-15. Bütün maçlarda 1–1, 2–0, 3–0 ve iki yönde tek taraflı üç gol veya fazlası denetlendi. 54 maçta tam sayı ve tarih dizileri eşleşirken ağırlıklı form sonucunda kayan nokta son basamak farkı görüldü. Denetimdeki kesin eşitlik yanlış alarmı düzeltildi. Motorun tahmin sonucunu değiştirecek matematiksel hata veya sayısal engel gözlenmedi.

PUP dört pazar tamamlandıktan sonra çalıştırıldı ve 69 maçta BLOCKED kaldı. Gerekçeler maç ve pazar bazında arşivde. Mevcut Tur-2 ve Auto-Control kayıtları korunmuştur. Bağımsız sonuç kökeni, tam bağlam, uygun pazar fiyatı ve kalibrasyon kabulleri üretim engelleri olarak devam ediyor. İki sayısal girdi açığı var. Tam maç koşulları 13 maçta ve dış etken bileşeni 69 maçta yok. Ham araştırma hesaplama hattı 69 maçta çalıştı. Onaylı üretim hattı için eksik kanıtlar ve kalibratör gereklidir.

69 hedef maçın bu çalışmanın kesiminde doğrulanmış sonucu 0. Önceden mühürlü 25 Kasım dokuz UCL maçının referans tahmini ayrı olarak doğrulanmış skorla eşleşti. Brier değerleri 2.5 ÜST 0,2450, KG VAR 0,2692, MS1 0,2576, MS2 0,2732. İleriye dönük donmuş kısa saha kalibrasyonunda iki maç tek haftaya yayıldı. Bu sonuçlar 69 hedef maçın performansı veya V1 üretim doğrulaması değildir. Gerçek ileriye dönük çift model sonucu yok. Modelin daha önceki 240/155/164 kronolojik tarihsel araştırma deneyi ayrıca kaydedildi.

954 yerel test başarılı. Matematiksel doğrulamada yalnızca yeniden oynatma denetimi kodu eklendi. Model ağırlıkları, 96/48 saat sınırları, mevcut eşikler, manuel çalışma düzeni, main ve geçmiş mühürler korundu.
