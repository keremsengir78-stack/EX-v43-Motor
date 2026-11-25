# EX v4.3 teknik tamamlanma denetimi

| Alan | Yazılım ve doğrulama | Açık veri veya üretim engeli |
|---|---|---|
| Oyuncu dakikaları | Çekya, Slovakya ve Ukrayna HTML raporları ile Azerbaycan PFL PDF protokolleri gerçek belgelerle test edildi | PFL API sezon, tur, maç ve protokol PDF bağlantısını toplu keşfediyor. Kırmızı kartlar ve belirsiz değişiklikler ayrı incelemeye kalıyor |
| Skor kökeni | Bundesliga, LALIGA, Premier League, Serie A ve Marseille kulüp arşivindeki Ligue 1 resmî maç sonuçları ham arşivle işleniyor. Denetim lig ve sezon bazında kapsama ve çelişkileri gösteriyor | Kalan maçlar için diğer resmî liglerin kapsamı ve sağlayıcıların kayıt başına üst kaynak zinciri |
| PUP | Açık taleple çalışır. Skor senaryoları, oran sınırları ve EX-G ayrı denetlenir. Çoklu uygun pazarda EX-G, piyasa olasılığı, EX-D, skor bağlamı ve uygunluk gerekçesi incelemeye sunulur | Otomatik sıralama ancak ayrıca onaylanmış karar kuralıyla yapılabilir |
| Maç önü | Üç alternatif takvim EX araştırmasına kaynak kimliği, varsa resmî maç bağlantısı, UTC başlangıcı ve saha yönü şeklinde bağlanıyor | PFL lig ve takım kimlikleri doğrulanabilir. ESPN çapraz eşlemesi için tekil lig, santra, ev ve deplasman eşleşmesi gerekir. Yayımlanan kulüp kadrosu, teyitli ilk 11 alanından ayrı tutulur |
| Sonuç ve performans | `cycle` yeni maç öncesi arşivleri üretir ve önceki mühürlü arşivleri aynı çalıştırmada sonuçlandırır | Gerçek performans için maç sonu ve bağımsız resmî sonuç kaynağı. Tek sağlayıcılı sonuç geçici kalır |
| %50/%30/%20 | Dört pazarda bileşen kapsamı, sabit ağırlıklı adayın Brier kaybı ve dondurulmuş Platt adayları ayrı raporlanır | Bağımsız sonuçlu tamamlanmış kohort, yeterli hafta ve önceden ilan edilmiş değerlendirme tasarımı |
| Otomasyon | Denetim, yakalama, sonuçlandırma ve birleşik `cycle` kipleri test edildi | Yeni zamanlanmış tetikleyici etkin değildir |

## Örneklem tasarımı

Brier kaybı farkı aynı maçta aday eksi referans olarak hesaplanır. Maç farkları hafta içinde ortalanır. Pilot hafta ortalamalarının örneklem standart sapması `s`, önceden ilan edilen en küçük anlamlı iyileşme `delta`, aile hata oranı `alpha` ve güç `1-beta` ile yaklaşım `ceil(((z_(1-alpha/10)+z_(1-beta))*s/delta)^2)` bağımsız hafta verir. On karşılaştırma iki Platt, dört sabit takım gücü ve dört bileşen deneyinden gelir. Pilot sapması ve hedef kazanç bilinmeden tek bir asgari maç sayısı tanımlanamaz. Haftalar arasındaki bağımsızlık varsayımı ayrıca değerlendirilir.

`run_ex_power_design.py` pilot farkları ve önceden belirlenen araştırma kararıyla tasarım dosyası oluşturur. Hoeffding sınırına dayanan ihtiyatlı güç boyutu ayrıca raporlanır. Aile duyarlı araştırma kabulü, önceden belirlenen pencere sona erdiğinde, yeterli hafta, negatif tek yönlü üst Brier sınırı ve hedef kazanç birlikte gerçekleştiğinde verilir. Bu karar EX-G veya EX FINAL yetkisi vermez.

`capture` kipinde UTC gün ve isteğe bağlı güncel tarihsel arşiv çalışması verilir. `settle` kipinde virgülle ayrılmış tahmin arşivi kimlikleri verilir. Aynı depoda yayımlanmış resmî inceleme ve araştırma tasarımı çıktıları isteğe bağlıdır. Hâlihazırda tamamlanan geçmiş maç kaynakları yeniden indirilmez.


## Lig kapsamı

`python run_ex_league_coverage.py` kullanıcı onaylı 13 müsabakayı ana veri alımı, tarihsel skor, takvim, oran adaptörü ve sonuç doğrulama açısından karşılaştırır. İngiltere Championship eski çağıranlar için desteklenir ve onaylı ana kataloğun dışında kalır. Bir ESPN adaptörü gerçek kadro, likit oran veya bağımsız skor teyidi bulunduğu anlamına gelmez.

Eerste Divisie ve Eliteserien alımı ESPN'nin yayımladığı sezon takviminden günlük ham kopyaları arşivler. Varsayılan sezon sınırı yaz liglerinde 1 Temmuz, Eliteserien'de 1 Ocak. Sonuç hesapları hedef tarihin öncesiyle sınırlı. UEFA için yalnız normal sürede tamamlanan maçlar ortak tarihsel gol veri setine girer. Gün bütçesi sınırlanan veya kaynak eksiği bulunan alım, kapsamı kısmi olarak işaretler. Canlı ve tarihsel kanıt akışlarında EX FINAL güvenlik kuralları geçerlidir.

Dünya liglerine genişlemede güvenilir sezon başlangıcı, müsabaka aşaması ve kaynak takım kimlikleri tanımlanmalı. Toplu dakikalar `EX league minutes collection` iş akışındaki manuel aralıklarla toplanır. Ham raporlar ve PDF'ler önceki Actions arşivinden özeti doğrulanarak kullanılabilir.
