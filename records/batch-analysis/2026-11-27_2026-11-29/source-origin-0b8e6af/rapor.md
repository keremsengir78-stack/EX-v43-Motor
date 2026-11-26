# EX v4.3 · Bağımsız kaynak kökeni denetimi

Başlangıç HEAD 3b1187884b9b4d6921dc26b44b71f54e1fe4c3c2. Denetim HEAD 0b8e6af8d6bd2203a102ac2f3e0473f952ffbad9. 103 hedef tahmin yeniden çalıştırılmadı. Girdi, arşivdeki form-acceptance-3b11878 kaydıdır.

| Ölçüm | Önce | Sonra |
|---|---:|---:|
| Kökeni onaylanan tarihsel olay | 0/29 | 0/29 |
| Kabul edilen form kullanımı | 0/46 | 0/46 |
| Bu kabulün katkı sağladığı hedef maç | 0/103 | 0/103 |
| Tam veri alımı onayı | 0/412 | 0/412 |
| İkinci kaynak onayı | 0/412 | 0/412 |
| Maç bağlamı onayı | 0/412 | 0/412 |
| Doğrulanmış EX-G | 0/412 | 0/412 |
| Gerçek EX FINAL | 0/412 | 0/412 |
| Maç öncesi mühürlü, sonuçla doğrulanmış aday örneği / hafta | 2 / 1 | 2 / 1 |

Dört arşivli resmî yayın nesnesi SHA-256 ve boyut üzerinden yeniden doğrulandı. 29 güncel ESPN özetinin tamamında aynı kesin lig, olay, yönlü takım kimlikleri, başlama saati ve skor görüldü. Güncel yanıtlar tarihsel ESPN yakalamasından farklı; arşivde ayrı gözlem olarak saklandı. 29 ESPN özetinin skor ve olay kapsamındaki header, meta ve keyEvents alanlarında skor üreticisine ilişkin yapılandırılmış atıf çıkmadı. Güncel özetler maç öncesi kanıt olarak kullanılamaz.

DFL ve Sportec Solutions'ın genel üretim zinciri belgeli. LaLiga–Perform veri ortaklığı ve ayrı olarak LaLiga–ESPN yayın ilişkisi belgeli. OM yayıncı kimliği ile LFP'nin kulüplere ve medya ortaklarına veri dağıtımı ayrı belgelendi. Eliteserien satırlarındaki 16 FIKS kimliği NFF'nin hakem onaylı raporlama zincirine araştırma dayanağı sağlıyor. 16 maç raporu isteğinde HTTP 403 alındı. Bu kayıtların hiçbiri ESPN skorunun diğer yayından ayrı bir üretim akışından geldiğini olay düzeyinde doğrulamadı. Farklı URL veya özet değeri kabul nedeni yapılmadı. Aynı olayın tekrarlanan form kullanımları yalnızca bir olay altında tutuldu.

Arşiv başında bu çalışma öncesindeki e804cdb3 kaydından sonra bağlam veya sonuç sağlayan yeni bir receipt yoktu. Tam bağlam onayı çıkmadı ve iki ileriye dönük örnek korundu. Sekiz haftalık koşul değişmedi.

Yerel test sonucu 947 başarılı.
