# EX v4.3 · Toplu teknik tamamlama ve kök neden

Başlangıç c001217ca0c2a6968914f478aae528b3f524a5f6. Son kod başı a342531a55a53a873367850c009b00eb251af288. Temel kanıt live-cutoff-20261127T0554Z. 103 maçın tahminleri ve mühürleri korunmuştur.

| Engel | Arşiv sayısı | Düzeltme sonrası tanı | Kök neden |
|---|---:|---:|---|
| historical_samples:incomplete | 32 | 136 | 34 maç için aynı lig ve ilgili saha geçmişi eksik. Kısa saha çıktısı 104 pazarın tam form eksikliğini gizliyordu. |
| market_baselines:missing | 32 | 32 | Sekiz maçta kısa ve tam referans hesabı birlikte eksik. |
| ingestion:blocked | 412 | 412 | Tam veri alımı için doğrulanmış kabul paketi yok. |
| second_source:unverified | 412 | 412 | Farklı yayınlarda aynı skor görülebiliyor. Olay düzeyinde bağımsız üretim zinciri kanıtı eksik. |
| context:unverified | 412 | 412 | Tarihli takım bağlamı kanıtı ve kapsamı eksik. Bazı kaynak erişimlerinde HTTP 403. |
| odds_lock:blocked | 154 | 154 | Tam pazar veya doğru çizgi eksik. Alternatif ham kaynak erişimi veya sağlayıcı zamanı eksik. |
| exg:uncalibrated | 412 | 412 | Onaylı kalibratör yok. 164 test kaydı dört haftada. İleriye dönük iki kabul edilebilir örnek bir haftada. |

Tanı farkı arşivdeki dört pazar sonucunun engellerine kod düzeltmesinin uygulanmasıyla oluşturuldu. Üretim kararı yeniden yazılmadı. 103 fikstür çapraz doğrulaması, 69 tam araştırma formu ve 258 kaynaklı pazar oranı gözlemi mevcut. Bağımsız tarihsel form kabulü, tam veri alımı, tam bağlam, onaylı kalibratör, EX-G ve EX FINAL sayısı 0. Arşiv Auto-Control sonuçları 410 BLOCKED ve 2 PASS.

- Form örnekleri giriş sırasından bağımsız, kronolojik seçilir. %40/%30/%20/%10 ağırlıkları korundu. Lig değiştiren takımların önceki sezon verileri mevcut lig yerine kullanılmadı.
- Yeni kaynak denetleyicisi, güvenilir ve özet değerine bağlı inceleme kaydındaki ayrıştırıcı ile ham sonucu tekrar okur. Kesin maç kimliği, saha yönü, UTC başlangıcı, lig, skor, arşiv mührü ve karar kesimi kontrol edilir. Ortak kaynak kimlikleri reddedilir. Üretimde kullanılabilecek yeni incelenmiş kaynak kaydı bulunmadı.
- Bağlam kabulü iki takımın 14 günlük tamamlanmış maç kayıtlarından yük ve dinlenme yayını yeniden hesaplar. Yinelenen kayıt ve tutarsız dinlenme değerleri kabul edilmez. Kesin ilk 11 şartı eklenmedi. Oyuncu ve rotasyon kapsamı hâlâ dış kanıt gerektiriyor.
- Canlı arşivin Bet365 kesirli listelerinden 24 MS1, 24 MS2 ve 6 tam 2.5 ÜST fiyatı okundu. KG VAR yok. Açık pazar anahtarı ve 2.5 çizgisi zorunlu tutuldu. Yayın saati yok, tümü araştırma gözlemi. Canlı kabul sayısı değişmedi.
- %50/%30/%20 karar ağırlıkları doğrulandı. Dört pazarın arşiv hesapları üzerinde PUP çalıştırıldı. 103 maç BLOCKED. Skor dağılımı, Fixture/Odds Lock, Tur-2 ve Auto-Control yerel regresyon paketiyle sınandı.

Kalan teknik bağımlılık, belgeli kaynak kökeni kayıtlarını işletecek güvenilir inceleme verisinin sağlanması ve kabul hattına bağlanmasıdır. Yeni KG VAR ve eksik 2.5 ÜST kapsamı için pazar ve zaman doğrulaması sunan erişilebilir ham sağlayıcı gerekir. Kalibrasyon için mevcut bağımsız test ve sekiz haftalık kanıt şartı geçerlidir. Üretim eşikleri, zamanlamalar ve main korunmuştur.

Yerel test 952 başarılı.
