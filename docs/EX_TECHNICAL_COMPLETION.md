# EX v4.3 teknik tamamlanma denetimi

| Alan | Yazılım ve doğrulama | Açık veri veya üretim engeli |
|---|---|---|
| Oyuncu dakikaları | Dört resmî kaynak alanı için kuyruk doğrulama, toplu nominal dakika, kabul/ret kaydı. Chance Liga'nın incelenmiş satır biçimi ayrıştırılıyor | Slovakya ve Azerbaycan'da tam resmî değişiklik zaman çizelgesi, dört sitenin uçtan uca otomatik ham belge ayrıştırması |
| Skor kökeni | 1.078 kayıt maç bazında mutabakat, resmî doğrulama, bağımsız inceleme, kanıtlanamayan köken ve çelişki sınıflarıyla ayrı listeleniyor | Sağlayıcıların kayıt başına üst kaynak zinciri |
| PUP | Dört pazarda ayrı EX-G kimliği, aralık ve kalibrasyon denetimi test edildi | Depoda kullanıcı onaylı yürütülebilir PUP protokolü yok. PUP ve EX FINAL kapalı |
| Maç önü | Kayıtlı 19 lig ve müsabaka kodu tek geçişte işleniyor. İngiltere ve Almanya ikinci ligleri dahil | Başarısız sağlayıcı yanıtı ayrı kaydedilir. Desteksiz liglerde alternatif maç önü beslemesi |
| Sonuç ve performans | Actions arşiv fişi, kesin santra, takım kimliği, maç durumu ve resmî karşılaştırma. Çok günlük arşivler en erken geçerli zaman damgasıyla birleştiriliyor | Yeni maçlar ve resmî sonuç inceleme defteri. Tek sağlayıcılı sonuç geçici kalır |
| %50/%30/%20 | Her pazarda bileşen kapsaması ölçülüyor. Tam doğrulanmış puanlar oluştuğunda kronolojik araştırma karşılaştırması çalışır | Tam pazar bileşenleri, bağımsız sonuçlar ve yeterli zaman örneklemi |
| Otomasyon | `EX prospective operations` iş akışı denetim, yakalama ve sonuçlandırma kipleri içeriyor | Yeni zamanlanmış tetikleyici yok. Resmî sonuç beslemesi için inceleme paketi gerekiyor |

## Örneklem tasarımı

Brier kaybı farkı aynı maçta aday eksi referans olarak hesaplanır. Maç farkları hafta içinde ortalanır. Pilot hafta ortalamalarının örneklem standart sapması `s`, önceden ilan edilen en küçük anlamlı iyileşme `delta`, aile hata oranı `alpha` ve güç `1-beta` ile yaklaşım `ceil(((z_(1-alpha/10)+z_(1-beta))*s/delta)^2)` bağımsız hafta verir. On karşılaştırma iki Platt, dört sabit takım gücü ve dört bileşen deneyinden gelir. Pilot sapması ve hedef kazanç bilinmeden tek bir asgari maç sayısı tanımlanamaz. Haftalar arasındaki bağımsızlık varsayımı ayrıca değerlendirilir.

`run_ex_power_design.py` pilot farkları ve önceden belirlenen araştırma kararıyla tasarım dosyası oluşturur. Hoeffding sınırına dayanan ihtiyatlı güç boyutu ayrıca raporlanır. Aile duyarlı araştırma kabulü, önceden belirlenen pencere sona erdiğinde, yeterli hafta, negatif tek yönlü üst Brier sınırı ve hedef kazanç birlikte gerçekleştiğinde verilir. Bu karar EX-G veya EX FINAL yetkisi vermez.

`capture` kipinde UTC gün ve isteğe bağlı güncel tarihsel arşiv çalışması verilir. `settle` kipinde virgülle ayrılmış tahmin arşivi kimlikleri verilir. Aynı depoda yayımlanmış resmî inceleme ve araştırma tasarımı çıktıları isteğe bağlıdır. Hâlihazırda tamamlanan geçmiş maç kaynakları yeniden indirilmez.
