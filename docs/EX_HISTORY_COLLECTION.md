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
