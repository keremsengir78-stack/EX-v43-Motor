# EX tarihsel özellik toplama

`run_ex_history_collection.py` birden çok kulüp ve sezon için ESPN'in tüm müsabakalar uç noktasından takvim, tamamlanmış maç özeti, oyuncu ve saha bilgisi toplar. Takvim ve maç özeti maç kimliği, iki takımın kimliği ve başlama zamanı üzerinden karşılaştırılır. Aynı maç iki takımın takviminde görünürse tek özet sorgulanır. Sağlayıcının kapsadığı müsabakalar raporlanır. Takvim tamlığı ayrıca kanıt gerektirir.

## Yerel çalıştırma

```sh
python run_ex_history_collection.py --config config/ex_history_pilot.json \
  --cache ex_history_cache --output ex_history_report.json --budget 8
```

Aynı önbellek diziniyle yeniden çalıştırıldığında başarılı tamamlanmış özetler yeniden indirilmez. İstek bütçesine takılan işler raporda görünür. Geçici erişim hataları bir saatlik bekleme kaydı bırakır, takvimler yedi gün sonra yenilenir. Ham yanıtlar SHA-256 ile adreslenir. İşlem yeni bir kaynak zamanı aldığında eski yakalama ayrı dosyada kalır. Aynı yerel önbellek için bir yazıcı kullanın.

Mevcut UCL maç önü çalışmasından alınan UEFA HTML kaydı `--import-uefa-directory ucl_research_output/matchday_inputs` ile içe aktarılabilir. Dizin eski `report.json` dosyası ve onun kaynak dosyasını içermelidir. Kulüp ve UEFA maç kimliği yapılandırmaya uymalıdır. Sonradan edinilmiş bir sayfa önceden arşivlenmiş sayfanın yerini almaz. Maç başladığında veya sonrasında alınan UEFA kadro haberleri maç öncesi eksik özelliği olarak kullanılmaz.

## Alanlar ve sınırlar

- `hours_since_previous_observed_kickoff` görünen iki başlama zamanı arasındaki saattir. Tam dinlenme süresi veya bütün müsabakaların kapsandığı anlamına gelmez.
- `provider_minutes` doğrudan ESPN verisidir. `nominal_regulation_minutes` tamamlanmış normal süre maçlarında kadro ve değişiklik saatlerinden çıkarılır. Uzatma ve duraklama süresi yükünü içermez. Eksik saat ve ihraç durumunda alan boş kalabilir. Tutarsız takım toplamında nominal süreler kaldırılır.
- UEFA sayfasındaki bildirilen eksikler ve şüpheliler isimleriyle saklanır. Oyuncu etkisi veya ağırlığı hesaplanmaz.
- ESPN saha, tarafsız saha ve varsa hava bilgisi özetin yakalanma zamanıyla saklanır. Seyahat kanıtı kaynakta olmadığında boş kalır.
- Arşiv, maç öncesi yakalamaları maç başladıktan sonraki sonuç ve kadro verilerinden ayırır. Bağımsız sonuç doğrulaması ve yeterli zaman damgalı özellik kapsamı sağlanmadan %50/%30/%20 doğrulaması hazır sayılmaz. Toplayıcı kalibrasyon veya EX FINAL yetkisi vermez.

`config/ex_history_pilot.json` pilot sınırıdır. Diğer ligler veya sezonlar için ESPN takım kimliği, sezon ve tarih aralığı değiştirilir. Actions işinde rapor ve ham önbellek ayrı bir kanıt paketi olarak yayımlanır. Aynı ref üzerindeki sonraki çalıştırma en son kaydedilen önbelleği geri yükler.

## Toplu kapsam ve devam ettirme

`config/ex_history_bulk.json` iki ESPN sezon anahtarında (2025 ve 2026) 36 UCL takımını ve ana EX kapsamındaki İngiltere, Almanya, İspanya, İtalya ve Fransa birinci liglerini tanımlar. Sağlayıcı yanıtlarında bulunan kupa, Avrupa ve diğer müsabaka kayıtları da plana girer. Plan, tamamlanmış karşılaşmaları ESPN maç kimliğine göre tekilleştirir.

```sh
python run_ex_history_collection.py --config config/ex_history_bulk.json --profile all \
  --cache ex_history_cache --plan-only --output plan.json --budget 250 --request-interval 0.5
mkdir -p parts
python run_ex_history_collection.py --plan plan.json --cache ex_history_cache \
  --output parts/part-0.json --shard 0 --shards 1 --budget 40 --request-interval 0.5
python run_ex_history_merge.py --plan plan.json --parts parts --cache weather_cache \
  --venues config/ex_history_venues.json --output history-coverage.json
```

Actions sekmesindeki **EX bulk history** sekiz sabit bölümü en fazla iki eşzamanlı iş ile yürütür. Her bölüm her çalıştırmada en çok 170 yeni özet isteği yapar ve aynı ref üzerindeki önceki bölüm önbelleğinden devam eder. Aynı çalıştırmayı yeniden başlatırken tüm işleri yeniden çalıştırın. Plan, bölüm raporları, kapsam ve SHA-256 adresli ham kaynaklar ayrı Actions çıktılarıdır. Kapsam raporunda kalan maçlar ayrıca sayılır. Takvim önbelleği yedi gün sonra güncellenebilir.

Open-Meteo geçmiş hava arşivi, doğrulanmış saha konumları için sonradan üretilen yeniden analiz kaydını ayrı tutar. Ardışık bilinen sahaların büyük daire mesafesi ölçülebilir bir coğrafi vekildir. Gerçek seyahat rotası, zemin durumu veya maç öncesi hava tahmini olarak kullanılmaz. Saha kayıtları kimlik, ad ve koordinat kaynağı gerektirir. Ortak özellik çıkarıcı, analiz zamanından önce yakalanan maçları ve kadro sürelerini hesaba katar.

Yerel çalışmanın ölçümleri `reports/ex_history_bulk_2026_11_24.json` dosyasındadır. Open-Meteo erişimi dört istekte HTTP 403 ile sonuçlandı. %50/%30/%20 modelinin bağımsız sınaması için zamanında yakalanmış dış etkenler, tam fikstür kapsamı ve bağımsız maç sonucu kökeni hâlâ gereklidir.

## Devam toplaması ve skor kanıtı

Mevcut sekiz bölüm ve önbellek anahtarları korunur. Bölüm başına yeni özet bütçesi 170 istektir. Başarılı tamamlanmış özetler ağ isteği yapmadan okunur ve en fazla iki bölüm aynı anda çalışır. Hatalar erişim engeli, hız sınırı, bulunamayan kaynak, sunucu/bağlantı hatası ve geçersiz içerik olarak raporlanır. HTTP 429 sonrasında ilgili iş aynı sunucuya yeni istekleri geçici olarak durdurur. Saniye ve HTTP tarihi biçimindeki Retry-After işlenir. İçerik ayrıştırıcısının sürümü değiştiğinde yalnızca eski geçersiz içerik kaydı yeniden denenebilir.

Open-Meteo sonuç veremediğinde NASA POWER saatlik UTC yeniden analiz kaynağı denenir. Kaynak ve grid mesafesi çıktıda saklanır. Coğrafi saha mesafeleri `venue_geodesic_transitions` içinde, belgelenmiş seyahat gözlemleri `verified_travel_observations` alanında yer alır.

`expanded` profili diğer 11 kayıtlı EX ligi için `config/ex_history_expansion.json` içindeki kaynakta görülen kulüp kimliklerini kullanır. Bu başlangıç listesi tam lig kadrosu veya tam sezon kapsamı garantisi vermez. Varsayılan `all` profili mevcut 4.177 maçlık planın ilerleyişini sürdürür.

Skor kanıtı işi, ana motor denetiminden tarihsel eşleşmeyen maçları ve daha yeni tek kaynaklı sonuçları alır. Her lig ve gün için bir ESPN skor tablosu kullanır ve SHA-256 kaynak kaydı üretir. Aynı skorlar bağımsızlık incelemesi bekleyen aday, farklı skorlar çelişki olarak çıkar. Veri bu aşamada motor geçmişine aktarılmaz.

## Paket 10 — Lig kapsamı ve karar girdileri

PR çalışması `expanded` profiliyle başlar. ESPN sezon tablosu aynı müsabaka kimliği ve yıl ile doğrulanan kulüpler planla birleştirilir. Desteksiz dört müsabakada UCL'nin iki kaynak bağlantılı kulüp kayıtları kısmi kanıt olarak ayrı listelenir. Toplu özet işinde bölüm başına en fazla 290 yeni istek ve iki eşzamanlı bölüm uygulanır. Skor işi ayrı önbellekte lig-gün başına tek yanıtı arşivler. Geçici aktarım hataları 5 dakika sonrasında yeniden denenir. OpenLigaDB Bundesliga gözlemleri ayrı kaynak defterine yazılır.

Ana motor `--history-plan`, `--history-parts` ve `--history-at` parametreleriyle geçmiş sağlayıcı arşivi kabul eder. Fikstür CSV'sinde `home_espn_id` ve `away_espn_id` alanları araştırma girdisini ilgili taraflarla eşleştirir. UCL arşiv tekrarı ilk iki parametreyle, doğrulanmış maç önü ESPN takım kimliklerini ve sabit tekrar kesimini kullanır. Her iki girişte dakika, 14 günlük yük, son başlama zamanı aralığı ve son saha araştırma alanlarıdır. Kapsam işi bu gözlemlerin tarihsel hedef maçların başlama anından önce gerçekten yakalanıp yakalanmadığını sayar.

Konum defteri 10 saha içerir. Hava toplama bütçesi 80 istek olup sahalar arasında dönüşümlüdür. Kulüp yayınlarıyla belgelenmiş seyahat ve çim bakımı kayıtları geçmişe dönük ayrı gözlemlerdir. Zamanında arşivlenmiş hava tahmini, fiilî rota, maç gününe ait zemin ölçümü veya doğrulanmış bileşen puanı olarak kullanılmaz.
