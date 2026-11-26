# EX v4.3 · Tarihsel form kanıtı kabul denetimi

PR #2 HEAD 3b1187884b9b4d6921dc26b44b71f54e1fe4c3c2. Mevcut 103 tahmin değiştirilmedi. Ham kanıt ve karar kayıtları arşivden yeniden okundu.

| Ölçüm | Önce | Sonra |
|---|---:|---:|
| Resmî skor eşleşmesi | 31 | 31 |
| Olay kimliğiyle form penceresine bağlanan tarihsel olay | 0 | 29 |
| Bu olayların geçtiği hedef maç | 0 | 15/103 |
| Bağımsızlığı onaylanan form örneği | 0 | 0 |
| Tam veri alımı / ikinci kaynak / bağlam onayı | Her biri 0/412 | Her biri 0/412 |
| Tam kabul alan pazar | 0/412 | 0/412 |
| Mühürlü ileriye dönük örnek / hafta | 2 / 1 | 2 / 1 |
| EX-G / EX FINAL | 0 / 0 | 0 / 0 |

29 tarihsel olay 46 hedef maç ve takım tarafı kullanımına bağlandı. Yeniden oynatma sıralı form tarihlerini ve gol ortalamalarını doğruladı. Seçilen sağlayıcı kaydının olay kimliği, yönlü takım kimlikleri, UTC başlangıcı, skoru ve kaynak özeti denetlendi. Tüm resmî mühürler ilgili hedef kesiminden önceydi. İki yayının skor kökeni bağımsız olarak belgelenmediği için 46 form kullanımı BLOCKED kaldı. Denetim, gelecekte aynı tarihte farklı bir olayın kabul edilmesini önlemek için form tanılama çıktısına olay kimliklerini ekler.

15012720346 ve 15013517358 yalnız keşif raporlarıydı. Başarılı keşif satırının ham dosyası doğrulanır ve satır skor sayımı dışında kalır. 15010872359 de.2 satırı sıfır sonuç bildiren bir keşif yakalamasıydı. Sonradan eklenen ayrıştırıcı bu yakalamayı doğrulanmış sonuç kümesi gibi okumaya çalışıyordu. Ham dosya korunur ve kayıt skor sayımı dışında kalır. Pozitif kayıt iddialarında satırlar ancak sayım doğrulandıktan sonra yayımlanır. Üç yeniden oynatma hatası giderildi.

Kalibrasyon denetimi güncel arşivde iki mevcut örneği ve 2026'nın 48. haftasını korudu. Yeni mühürlü, doğrulanmış örnek bulunmadı. 240/155/164 bölünmesi, sekiz haftalık koşul ve performans eşikleri korundu.
