# EX v4.3 — Kalıcı Çalışma Devam Kaydı

> Yetkili çalışma dalı: `ex-v43-development`. Bu belge sohbet özeti değil, doğrulanabilir çalışma devri içindir.
> Güncelleme: 2026-11-22. EX FINAL: **KİLİTLİ**.

## Yeniden başlama protokolü (sayfa yenileme / yeni sohbet)
1. Önce bu dosyayı **GitHub'daki `ex-v43-development` dalından** oku; sonra README, ilgili kod, testler ve GitHub commit/CI durumlarını doğrula.
2. Önceki konuşma, hafıza ve raporları yalnızca **aday kanıt** say. GitHub'da mevcut commit ve testlerle karşılaştır; eski sonuçları yeni tamamlanmış çalışma gibi gösterme.
3. Her turda: **veri doğrulama → hesaplama → kalibrasyon → test → düzeltme**. Yapılan ile planlananı ayır; başarısız işlemde alternatif yöntem dene, sonuç alınamadıysa engeli kaydet.
4. Yalnızca `ex-v43-development` üzerinde değişiklik yap. **`main` dalına yazma, birleştirme yapma** (kullanıcının yeni açık onayı olmadıkça).
5. Otomatik düzeltme **beklemede**, manuel çalışma **aktif**. Kullanıcı ayrıca onaylamadıkça kendiliğinden düzeltme döngüsü açma.
6. EX FINAL için tüm zorunlu veri, bağımsız kaynak, saha örneklemi, hesap izi, kalibrasyon, Tur-2 ve Auto-Control kapıları gerçekten geçilmelidir. Eksik kanıt varsa FINAL kilitli kalır.
7. Her anlamlı commit sonrası GitHub CI durumlarını oku; yalnızca doğrulanan sonucu bildir. Her tur sonunda bu dosyanın 'Son doğrulama' bölümünü güncelle; sayfa yenilense bile devam noktası burada olsun.

## Korunacak teknik kararlar
- EX v4.3: takım gücü %50, maç koşulları %30, dış etkenler %20. Bu ağırlıklı puanlar tek başına kalibre edilmiş olasılık değildir.
- Ev/deplasman: ilgili saha son 5 %40, son 10 %30, mevcut sezon %20, önceki sezon ilgili saha %10; geçmiş sezon verisi gerçek maçlardan tamamlanır.
- Pazarlar bağımsız: 2.5 ÜST → KG VAR → MS1/MS2; PUP toplu karar katmanında, kullanıcının talebiyle.
- 1.19 ve altı oran PASS; 1.20 ve üzerindeki negatif EX-D tek başına PASS sebebi değil.
- Fikstür/kaynak kilidi, skor dağılımı, milli ara etkisi, Tur-2, Auto-Control ve eksiklik kilidi korunur.
- Kaynak zaman damgası, SHA-256 izi, çelişki halinde durdurma, yeniden üretilebilirlik ilkeleri korunur.
- Eksik hesap izi veya kalibrasyon varsa güven yüzdesi/EX FINAL uydurulmaz.

## Önceki sayfadan devralınan, yeniden doğrulanması gereken kayıtlar
- 72. geliştirmede 22/22 test; Premier League 430/430; 50 maç bağımsız doğrulama bekliyor. **Tarihsel bildirimdir, mevcut güncel durum olduğu varsayılmaz.**
- Bir denetimde 48 eşleşme / 25 uyuşmazlık; 16'sı Almanya. **Tarihsel örneklem; canlı sayı olarak sunulmaz.**
- Başka bir kesitte 12/21 doğrulama, 9 eksik (La Liga 4, Bundesliga 3, Premier League 2) raporlanmıştı. **Farklı kesit; 48/25 ile birleştirilmez.**
- Önceki testlerde son 5/10 saha örneklemi, bağımsız kaynak ve kalibrasyon eksikleri nedeniyle FINAL kapalı tutuldu.
- `ex_secondary_review_summary.py` ve `ex_germany_review_export.py` araçları ile GitHub Actions denetim raporu iş akışı geliştirildi. Bunların gerçek rapor üretimi ayrıca doğrulanmalıdır.

## Bilinen dal/iş akışı tutarsızlığı
- 2026-11-22'de `main` üzerindeki `.github/workflows/ex-data.yml` dosyasına raporları geliştirme dalına yayımlayan commit `eb219f410b531e13c9241bfebe38fff131342a4c` yazıldı. **Bu işlem kullanıcının `main` değiştirilmesin kuralıyla çelişiyor.** Bundan sonra `main` üzerinde yeni değişiklik yapma; önce kullanıcı onayı veya güvenli düzeltme planı gerekir.
- Raporların `reports/latest_secondary_review_summary.json` ve `reports/latest_germany_unresolved_review.csv` yollarına gerçekten yayımlandığı **henüz doğrulanmadı**. GitHub Actions artifact ve repo raporları yoksa yeni kaynak doğrulaması yapılmış sayılmaz.

## Son doğrulama
- 2026-11-22: `f7f48d40066f5e0aa80d339b77f58c0c2bb669e2` için GitHub durumları: syntax/safety/full/regression **4/4 success**.
- 2026-11-22: `main` iş akışı değişikliği commit `eb219f410b531e13c9241bfebe38fff131342a4c` dosyadan okunarak doğrulandı; Actions çalışması ve rapor üretimi **doğrulanmadı**.
- Yeni geliştirme commitlerinin CI'si ayrıca kontrol edilmelidir.
- **Sonraki somut iş:** Geliştirme dalında veri kaynağı/denetim çıktısını gerçek olarak erişilebilir kıl; mevcut `reports/` dosyalarını GitHub üzerinden ara; 25/16 gibi tarihsel sayıları ancak yeni kanıtla güncelle.

## Kalıcılık ilkesi
GitHub kodu + bu kayıt + commit SHA + CI + tarihli denetim kanıtı = devam için kaynak. Sohbet belleği tek başına doğrulama değildir. Her tamamlanan adımın commit SHA'sı ve test durumu bu dosyaya eklenmelidir.

## 2026-11-22 hızlı eksik giderme turu
- `ffc5bd7d31e3e77d9327421ed6d8b397a394feb5`: inceleme özetinde alias önerileri ve bağımsız kaynak hataları korunuyor.
- `0579c9783c840e1e2b4b6de1f00e397009c6ddd4`: bu alanlar ve hatalı kanıt biçimleri için regresyon testi eklendi.
- Bu commitlerin CI sonucu henüz doğrulanmadı. Canlı denetim raporları hâlâ erişim/doğrulama bekliyor; EX FINAL kilitli.

## 2026-11-22: Gerçek denetim raporları erişilebilir
- GitHub Actions `45029537883` durum kaydı: ingest=success, review=success, evidence_published=true, audit_status=BLOCKED, EX FINAL=false.
- `reports/latest_pipeline_status.json` doğrudan okundu. 2025-26/2026-27 çoklu lig denetiminde **1845** uyuşmazlık; Almanya (`de.1`) **339**. Bunlar önceki 25/16 örneklemiyle karşılaştırılmamalıdır.
- `reports/latest_germany_unresolved_review.csv` okundu: 339 satırın **74**'ü `SECONDARY_SAME_DAY_SHARED_TEAM`, **265**'i `SECONDARY_DATE_PRESENT_NO_TEAM_MATCH`. 74 kayıt, yalnızca adlandırma/aday karşılaştırmasına elverişlidir; doğrulanmış maç değildir.
- Kaynak inceleme raporları artık depoda; kalan iş, lig bazlı kontrollü alias incelemesi, bağımsız skor ve tarih eşleşmesi, ikinci tur test/kalibrasyondur. EX FINAL kilitli.

## 2026-11-22: Almanya alias aday raporu
- GitHub Actions run `45029715005`, kaynak commit `adf53aa7bbb189251746754fc7087314ddfe4bb4`: ingest/review başarılı, evidence_published=true, Almanya uyuşmazlık=339, otomatik çıkarılmış **16** alias adayı (`reports/latest_germany_alias_candidates.json`). Hepsi MANUAL_REVIEW_REQUIRED; otomatik onay yok.
- `7dfa827cd098fece1985e4d408ea9276fed676a5`: çakışan çoklu isim eşleştirmelerine `mapping_conflict` bayrağı eklendi.
- `4f0f5bee80fd664d95767b3dc5ac165019d38c0c`: çelişkili eşleştirme testi. Yeni commitlerin CI sonucu henüz doğrulanmadı; yayımlanmış 16 aday eski şemadadır, sonraki iş akışında conflict alanı bekleniyor.

## 2026-11-22: İzole Almanya gölge testi
- 16 adaylı rapor doğrulandı, mapping_conflict=0, EX FINAL=false.
- `ex_germany_alias_pilot.py` adayları yalnızca izole test haritasına dönüştürür; onaylı alias dosyalarına yazmaz. `tests/test_germany_alias_pilot.py` güvenlik regresyonlarını içerir.
- `a6ed4f3eed876ebca9b9f485a6d9b73b231e6181` gölge karşılaştırma iş akışını ekledi. `b4f083d04b3dda0f3aa8cbaabdbfe9faab90af1e` gölge adım sonucu ve çıktı varlığı teşhisini ekledi.
- Son kontrol anında `reports/latest_germany_shadow_comparison.json` henüz yoktu; gölge testin sayısal etkisi **doğrulanmadı**. Sonraki turda `reports/latest_pipeline_status.json` ve ilgili Actions run logunu kontrol et.

## 2026-11-22: 5'li toplu çalışma, Almanya gölge test doğrulaması
- GitHub Actions `45030047515` raporu: ingest/review/shadow/offline_shadow=success; evidence_published=true; audit_status=BLOCKED.
- Kaynak Almanya unmatched=339, aday haritalı izole gölge unmatched=8, gölge farkı=331; gölge skor çelişkisi=0 ve kaynak hata listesi boş. Bu **331 bağımsız doğrulanmış maç değildir**. Offline inceleme: 36 tekil isim adayı, 0 doğrulanmış skor, 339 kayıt halen doğrulama bekliyor.
- `ex_germany_shadow_metrics.py` yeni sayısal ve EX FINAL güvenlik kontrolünü uygular; `tests/test_germany_shadow_metrics.py` regresyonları eklendi; `ex-review-sync.yml` doğrulanmış metrikleri ayrı rapora yazar ve yoksa CI başarısız olur.
- Son değişikliklerin yeni CI ve `reports/latest_germany_shadow_validated_metrics.json` çıktısı henüz teyit edilmedi. Onaylı alias map değişmedi; EX FINAL kilitli.

## 2026-11-22: 5'li toplu devam, kalan gölge uyuşmazlıklar
- Önceki metrik doğrulama işi `45030131008` başarıyla yayımlandı: 339 baseline, 8 shadow, 331 yalnızca gölge farkı, 36 isim adayı, 0 bağımsız doğrulama, 0 gölge skor çelişkisi. EX FINAL=false.
- `ex_germany_shadow_remaining.py` izole gölge denetiminin 8 kalan kaydını tam ayrıntılarıyla çıkarır; toplamlar tutmazsa reddeder.
- `tests/test_germany_shadow_remaining.py` iki regresyon testi eklendi.
- `ex-review-sync.yml` yeni `reports/latest_germany_shadow_remaining.json` dosyasını yayımlayacak ve eksikse çalışmayı başarısız sayacak.
- Yeni CI sonucu ve kalan 8 kaydın gerçek listesi **henüz teyit edilmedi**; sonraki turda kontrol edilmeli. Asıl 339 kayıt halen doğrulama bekliyor.

## 2026-11-22: Kalan sekiz Almanya gölge kaydı
- Gerçek `reports/latest_germany_shadow_remaining.json` sekiz kaydın tamamını yayımladı; hepsi 2026-27/de.1. Dört kayıtta `SC Paderborn 07` / `Paderborn`, dört kayıtta `SV 07 Elversberg` / `Elversberg` isim farkı görüldü.
- `ex_germany_remaining_candidates.py` mevcut adaylarla çapraz karşılaştırıp yeni adayları yalnızca manuel inceleme için çıkarır. Testi `tests/test_germany_remaining_candidates.py`.
- Workflow `reports/latest_germany_remaining_candidates.json` raporunu yayımlayacak. Son CI sonucu henüz doğrulanmadı. Hiçbir isim eşleştirmesi veya skor onaylanmadı, EX FINAL kilitli.

## 2026-11-22: 38. tur, genişletilmiş Almanya gölge testi
- CI 4/4 success ve gerçek `45030317436` raporu: 16 ilk aday + 2 yeni manuel aday (`SC Paderborn 07`→`Paderborn` 4 destek, `SV 07 Elversberg`→`Elversberg` 3 destek).
- Elversberg'in 4 gölge uyuşmazlığından biri, diğer tarafın adı da değiştiği için tekil aday çıkarma testinde sayılmadı; bu skor doğrulaması değildir.
- `ex_germany_shadow_merge.py` 16+2 adayın çakışmasız, onaysız birleşimini oluşturur; `tests/test_germany_shadow_merge.py` koruma testidir. Workflow yalnızca ayrı gölge denetimi yürütür, `reports/latest_germany_expanded_shadow.json` üretmeyi dener.
- Son CI ve genişletilmiş gölge sonuçları henüz doğrulanmadı. Onaylı eşleştirme dosyaları ve EX FINAL kilidi değişmedi.

## 2026-11-22: Hızlandırılmış toplu tur, 18 aday gölge testi
- Gerçek CI `45030430515` (commit `f2a67dc`): dört custom check success, expanded_shadow_step success, evidence_published=true. Almanya baseline unmatched 339, ilk 16 aday gölgesi 8, 18 aday genişletilmiş gölge 0, skor çelişkisi 0, kaynak hata listesi boş. `independently_verified_added=0`, `aliases_approved=false`, `ex_final_allowed=false`.
- `ex_germany_expanded_validation.py` sıralı sayısal kontrol, aday sayısı, eşleştirme çakışmaları, kaynak hatası ve EX FINAL kilidini doğrular; `tests/test_germany_expanded_validation.py` negatif regresyonları eklendi.
- Workflow `reports/latest_germany_expanded_validated.json` üretmek ve yoksa CI başarısız saymak üzere güncellendi.
- Son değişikliklerin CI sonucu ve yeni doğrulanmış raporu henüz teyit edilmedi. Diğer liglerdeki uyuşmazlıklar (toplam 1845, Almanya 339) ve gerçek bağımsız kaynak kanıtı çözülmedi.

## 2026-11-22: Hızlandırılmış çok ligli uyuşmazlık incelemesi
- Almanya genişletilmiş gölge `reports/latest_germany_expanded_validated.json` yayımlandı: 339→0 yalnızca aday isim eşleştirmesiyle; 18 aday, 0 bağımsız doğrulama, EX FINAL kilitli.
- `ex_multileague_alias_candidates.py` İngiltere, İspanya, İtalya ve Fransa için toplam 1506 başlangıç uyuşmazlığından aynı gün aynı rakip kanıtlı isim adaylarını çıkarır; eşleştirme onaylamaz, skor doğrulamaz. `tests/test_multileague_alias_candidates.py` tamlık testleri eklendi.
- Workflow `reports/latest_multileague_alias_candidates.json` yayımlayacak, sayısal uyuşmazlık toplamını çapraz doğrulayacak, başarısızlığı saklamayacak. Yeni CI/rapor henüz doğrulanmadı.

## 2026-11-22: 40. tur, dört lig gölge karşılaştırması
- Gerçek pipeline `45030681373`: 1506 Almanya dışı uyuşmazlık; en.1=307, es.1=442, it.1=428, fr.1=329. Toplam 14 manuel isim adayı ve tamamı fr.1; 0 otomatik onay, 0 skor doğrulaması.
- `ex_multileague_shadow_map.py` adayları yalnızca izolasyon amaçlı ikincil→birincil isim haritasına çevirir; `tests/test_multileague_shadow_map.py` güvenlik testleri eklendi.
- Workflow dört ligi ayrı `ex_other_shadow` dizininde denetleyecek ve `reports/latest_multileague_shadow_comparison.json` yayımlayacak. Son CI ve gölge sonuçları henüz teyit edilmedi; EX FINAL kilitli.

## 2026-11-22: 41. tur, dört lig için hata nedeni ayrıştırma
- Önceki 14 manuel adayın tamamı Fransa (`fr.1`); İngiltere, İspanya, İtalya için tek tarafı eşleşen aday yok. Başlangıç dağılımı: en.1=307, es.1=442, fr.1=329, it.1=428.
- `ex_multileague_diagnostics.py` her ligde `source_presence_status` dağılımını ve sınırlı örnekleri tamlık denetimiyle çıkarır. `tests/test_multileague_diagnostics.py` eklendi.
- Workflow `reports/latest_multileague_diagnostics.json` dosyasını yayımlamak ve yoksa CI başarısız saymak için güncellendi.
- Önceki dört lig gölge raporu ve bu tur CI henüz teyit edilmedi. EX FINAL kilitli, hiçbir yeni skor bağımsız doğrulanmadı.

## 2026-11-22: 42. tur, bağımsız kaynak inceleme sırası
- `reports/latest_multileague_diagnostics.json` gerçek CI `45030861642` ile yayımlandı: en.1 222 aynı gün ortak takım / 85 aynı gün takım yok; es.1 114 / 328; fr.1 146 / 183; it.1 87 / 341. Toplam 1506 başlangıç uyuşmazlığı. Gölge 14 Fransa adayıyla 329→0, diğer üç lig 1177 kaldı.
- `ex_multileague_review_queue.py` tüm 1506 kayıt için deterministik öncelik sıralaması üretir, ilk 100 kaydı ayrı raporda yayımlar; `tests/test_multileague_review_queue.py` eksik veri testleri eklendi.
- Workflow `reports/latest_multileague_review_queue.json` raporunu yayımlamayı ve yoksa CI'yi başarısız saymayı zorunlu kılar. Son CI ve yeni rapor henüz teyit edilmedi. EX FINAL kilitli.

## 2026-11-22: 43. tur, bağımsız kaynak kuyruğu sertleştirmesi
- `ex_multileague_review_queue.py` yinelenen maçları reddeder; deterministik sıralama sürümü 2 ve öncelikli ilk 100 kaydı sunar.
- `ex_multileague_queue_validation.py` kuyruk ve tanı raporu toplamlarını karşılaştırır. Negatif regresyonlar eklendi.
- Workflow `reports/latest_multileague_queue_validated.json` raporunu üretmek ve yoksa CI başarısız saymak üzere güncellendi. Yeni CI henüz doğrulanmadı. EX FINAL kilitli.

## 2026-11-22: 44. tur, CI tanı raporu güvenliği
- `320bec952d66dfa8cd049d4f80444a7399f305e7` için 4/4 kontrol başarılı; run `45031102253` gerçek audit ve `non_germany_queue_validated=true` raporunu yayımladı. `latest_multileague_queue_validated.json` kontrol edilebilir.
- Önceki başarısız test koşusunda `ingest_step=skipped` olmasına rağmen `latest_pipeline_status.json` üzerine yazılmıştı. Workflow `a0a16ccd` artık ingest skipped ise yayımlamayı durdurur ve kapanış kontrolünde `run_id` ile aktif workflow kimliğini karşılaştırarak eski raporun yeni sonuç gibi kullanılmasını reddeder.
- Bu son CI korumasının workflow sonucu henüz teyit edilmedi. 1177 üç lig uyuşmazlığı, 0 bağımsız skor onayı ve EX FINAL kilidi korunuyor.

## 2026-11-22: 45. tur, gölge sonrası gerçek inceleme kuyruğu
- `a0a16ccde454f25f1e76cf33c411d537f334825f` 4/4 CI başarılı; `45031178981` raporunda ingest/review/shadow success, `non_germany_queue_validated=true`, 1845 başlangıç ve gölgede Almanya 0, Fransa 0, diğer üç lig 1177 uyuşmazlık. 0 bağımsız skor onayı.
- `ex-review-sync.yml` dört lig gölge audit çıktısından `ex_secondary_review_summary.py` ile ayrı tamlık raporu, ardından `ex_multileague_review_queue.py` ile ilk 100 gölge-sonrası gerçek inceleme kaydı üretecek. `reports/latest_multileague_shadow_review_queue.json` yayımlanacak, sayısı mevcut `multileague_shadow_comparison.json` ile karşılaştırılacak. Rapor/CI henüz teyit edilmedi.
- EX FINAL kapalı; gölge ad eşleştirmeleri onaylanmış bağımsız skor doğrulaması değildir.

## 2026-11-22: 46. tur, gölge-sonrası inceleme ve çapraz aritmetik
- `9d2d719ed4ad23e8c5432e322a5ece124176fdc1` için CI 4/4 başarılı. `reports/latest_multileague_shadow_review_queue.json` 1177 toplam / ilk 100 öncelikli maç / queue_version=2 olarak yayımlandı.
- `ex-review-sync.yml` şimdi gölge audit dosyasından ayrı `reports/latest_multileague_shadow_diagnostics.json` üretiyor.
- `ex_multileague_shadow_validation.py` ve testleri lig toplamlarını, 0 skor çelişkisini, 0 kaynak hatasını, 0 bağımsız doğrulamayı, onaylanmamış alias ve EX FINAL kilidini doğruluyor. `reports/latest_multileague_shadow_validated.json` için zorunlu CI kontrolü eklendi.
- Son geliştirme CI sonucu henüz teyit edilmedi. EX FINAL kapalı.
