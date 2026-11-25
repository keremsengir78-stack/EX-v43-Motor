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

## 2026-11-22: 47. tur, kalan üç lig için kaynak önceliklendirme
- `86d7672ebeaf5d4f3c2ae23f776cdbb25418cc68` 4/4 CI başarılı; `45031405859` raporu `non_germany_shadow_validated=true` ve `reports/latest_multileague_shadow_validated.json` toplam 1506→1177, isim eşleşmesi 329, 0 bağımsız skor onayı gösterdi.
- `ex_multileague_priority_plan.py` İngiltere/İspanya/İtalya kaynak uyuşmazlıklarını aynı gün ortak takım ve aynı gün takım bulunamaması nedenlerine göre, doğrulanabilir öncelik puanıyla sınıflandırır. Hatalı/eksik/çift kayıtlar reddedilir. `tests/test_multileague_priority_plan.py` eklendi.
- Workflow `reports/latest_multileague_priority_plan.json` üretimini ve CI kilidini içeriyor. Bu tur CI sonucu henüz teyit edilmedi. EX FINAL kapalı.

## 2026-11-22: 48. tur, öncelik planı çapraz doğrulaması
- Önceki `6ca5e85c1bd064d2a6b5cefd5afdcd7d28a34804` 4/4 CI başarılı. En son yayımlanan audit eski `d000790f` koşusuna ait; yeni öncelik raporu henüz yayımlanmış olarak teyit edilmedi.
- `ex_multileague_priority_validation.py` ve regresyon testleri; gölge toplamı, üç lig kaynak nedenleri, tüm bucket sayıları, öncelik ağırlıkları, yinelenme ve EX FINAL kilidini çapraz doğrular.
- Workflow `reports/latest_multileague_priority_validated.json` yayımlamayı ve yoksa CI'yi başarısız saymayı zorunlu kılar. Bu turun yeni CI sonucu henüz teyit edilmedi. Bağımsız skor onayı 0.

## 2026-11-22: 49. tur, kaynak doğrulama için 50'li kayıt partileri
- `4bc4e44057bd960610b090e56666cca79e489dd6` 4/4 CI başarılı; `reports/latest_multileague_priority_plan.json` yayımlandı. Öncelik grupları İtalya tarih var/eşleşme yok 341, İngiltere aynı gün ortak takım 222, İspanya tarih var/eşleşme yok 328, İspanya ortak takım 114, İtalya ortak takım 87, İngiltere tarih var/eşleşme yok 85.
- `ex_multileague_review_batches.py` ve testleri gölge-sonrası 1177 eşleşmeyen maçı deterministik 50'li partilere ayırır, çift/eksik/bilinmeyen kaynak kayıtlarını reddeder; skorları onaylamaz.
- Workflow `reports/latest_multileague_review_batches.json` yayımlar, sayısal tamlığı denetler ve eksik raporda CI'yi başarısız sayar. Bu turun CI sonucu henüz teyit edilmedi. EX FINAL kapalı.

## 2026-11-22: 50. tur, 24 inceleme partisinin kimlik bazlı tamlık kilidi
- `bc9039bcc40020aff467621c11e0f4dfaf5d8df2` 4/4 CI başarılı; `reports/latest_multileague_review_batches.json` 1177 maçın 50'li 24 partisini yayımladı (son parti 27 kayıt). Skor onayı yok.
- `ex_multileague_batch_validation.py` kaynak gölge raporundaki her maçın lig/sezon/tarih/ev/deplasman kimliğini yayımlanan tüm partilerle birebir karşılaştırır; çift, eksik, sırasız ve onaylanmış gibi işaretlenen kayıtları reddeder. Testleri eklendi.
- Workflow `reports/latest_multileague_batches_validated.json` ve zorunlu CI tamlık kontrolünü ekledi. Bu yeni CI henüz teyit edilmedi. EX FINAL kilitli.

## 2026-11-22: 51. tur, parti içerik parmak izleri
- `e505a73a175ee54ae529b902c56e21d5b00d218a` 4/4 CI başarılı; 50'li 24 partinin kimlik doğrulama raporu kontrol sırasında henüz yayımlanmış değildi.
- `ex_multileague_batch_manifest.py` her inceleme partisinin kaynak maç kimliklerini SHA-256 ile özetler; skor onayı verilmez. Değişiklik algılama ve güvenlik regresyon testleri eklendi.
- Workflow `reports/latest_multileague_batch_manifest.json` raporunu ve zorunlu CI yayım kontrolünü içerir. Yeni sürüm CI/yayın teyidi bekliyor. EX FINAL kapalı.

## 2026-11-22: 52. tur, SHA-256 parmak izi bağımsız yeniden hesaplama
- `a7bbb985fd1c4d1ccd3608dd844e3e657484b583` 4/4 CI başarılı; kontrol sırasında SHA-256 manifest raporu henüz yayımlanmamıştı.
- `ex_multileague_manifest_validation.py` her parti hash'ini özgün maç listelerinden yeniden hesaplar, değiştirilmiş ve eksik manifestleri reddeder. Regresyon testleri eklendi.
- Workflow `reports/latest_multileague_manifest_validated.json` üretimini ve zorunlu CI kilidini içerir. Yeni CI sonucu henüz teyit edilmedi. EX FINAL kilitli.

## 2026-11-22: 53. tur, gerçek bağımsız kaynak kanıt kayıtlarına geçiş
- `ee8b7f15dc51b4e661e21fcdb3fe870334d9a0f9` 4/4 CI başarılı. Hash manifesti yayımlandı; ayrı hash doğrulama raporu kontrol anında henüz yayımlanmadı.
- `ex_multileague_evidence_ledger.py` ve testleri ilk 50 maç için ayrı kaynak URL/sağlayıcı/erişim tarihi, bağımsız takım ve skor alanları ile üç teyit bayrağını boş ve false başlatır. Bu aşama veri toplamaz, skor doğrulamaz.
- Workflow `reports/latest_multileague_evidence_ledger_batch1.json` raporunu güvenlik kilidiyle yayımlamak üzere güncellendi. Yeni CI ve yayın sonucu henüz teyit edilmedi. EX FINAL kapalı.

## 2026-11-22: 54. tur, ilk 50 kaynak kanıt kaydının güvenlik doğrulaması
- `c6d6ecf7cbfe9bb0cd8c57bd7c85fbbb27fe9d81` 4/4 CI başarılı; `reports/latest_multileague_manifest_validated.json` 24/24 SHA-256 hash doğrulaması yayımlandı.
- `ex_multileague_evidence_validation.py` kanıt defterindeki lig/sezon/tarih/takım kimliklerini özgün 50 maçla birebir denetler; kaynaksız URL, skor, yanlış durum ve sahte teyit reddedilir. Regresyon testleri eklendi.
- Workflow `reports/latest_multileague_evidence_validated_batch1.json` yayımlar ve eksik doğrulamada CI kilidini korur. Yeni CI sonucu henüz teyit edilmedi. EX FINAL kapalı.

## 2026-11-22: hızlandırılmış kaynak eşleştirme turu
- Meta raporlar yerine 1177 açık maç için gerçek football-data.co.uk sezon CSV verisinden aynı günün maçlarını bulup ev/deplasman isim benzerliğine göre sıralayan `ex_multileague_candidate_resolution.py` eklendi.
- `tests/test_multileague_candidate_resolution.py` farklı günün skorunun alınmamasını ve otomatik onay verilmemesini sınar.
- CI `reports/latest_multileague_source_candidates.json` raporunu üretmeye ayarlandı. Kaynak eşleşmesi sadece inceleme adayıdır, bağımsız skor onayı değildir. Yeni CI ve yayımlama henüz doğrulanmadı.

## 2026-11-22: 56. tur, gerçek kaynak adaylarının sayısal ölçümü
- `ad4d65a1e4d0de8cbcf8d44a1bc2b8a9453eaaf3` 4/4 CI başarılı; 1177 maçın aday raporu yayımlandı, ilk 50 kanıt kaydı doğrulandı. Aday raporu büyük olduğundan konektör çıktısı tam okunamadı.
- `ex_multileague_candidate_summary.py` her lig için aynı gün adayları, hiç aday bulunmayanlar, yüksek isim benzerliği ve kaynak hatalarını ayrı sayar; skor onayı üretmez.
- Regresyon testleri, CI yayın entegrasyonu ve `reports/latest_multileague_candidate_summary.json` eklendi. Yeni CI henüz teyit edilmedi.

## 2026-11-22: 58. tur, birebir kaynak eşleşme adayları
- `ex_multileague_unique_candidates.py` aynı gün, iki takımda yüksek isim benzerliği ve ikinci adayla güvenli fark koşullarını sağlayan kayıtları seçer. Bir kaynak maçına iki ayrı ana maç talip olursa ikisi de elenir.
- Regresyon testleri, CI entegrasyonu ve `reports/latest_multileague_unique_candidates.json` yayımı eklendi. Bunlar yalnızca inceleme adayıdır; bağımsız skor teyidi sıfır ve EX FINAL kapalı.
- Yeni sürüm CI ve rapor yayımı henüz teyit edilmedi.

## 2026-11-22: kaynak raporu yayımlama hatasına karşı zorunlu kilit
- GitHub Actions CI 4/4 geçmiş olsa da en son okunan pipeline status `d9b5353...` çalışmasına aitti ve aday özet/benzersiz aday raporları henüz depoda yoktu. CI sonucu ile gerçek kaynak doğrulama ayrı tutuluyor.
- `722078d1fdc6956c37766d92eb2019ab132fe3f1` workflow güncellemesi, kaynak aday/özet/benzersiz aday çıktıları yoksa açık hata verir; yayımlanan küçük özet ve benzersiz aday raporlarını son fail-closed aşamasında zorunlu kılar.
- 1177 açık kayıt, bağımsız skor onayı 0. Yeni workflow çalışmasının sonucu henüz teyit edilmedi.

## 2026-11-24: UCL 5. hafta araştırma doğrulaması

- Başlangıç dalı `df9767a3b31547e99491cbde4845b60312961521`. Önceki kod, aynı yerel ESPN/OpenFootball ham verileriyle 18 maçta 7 başlangıç hesabı üretti. Yeni kod 5.004 benzersiz yerel maç satırıyla 14/18 kalibre edilmemiş araştırma hesabı üretti. Sadece OpenFootball kullanılan karşılaştırmada kapsama 1/18'den 9/18'e çıktı.
- UEFA ve ESPN 18/18 fikstürün ev/deplasman ve UTC başlama saatinde örtüştü. İlk dört haftadaki 72/72 skor tarih ve saha yönüyle eşleşti. Ham dosyalar ve SHA-256 kayıtları araştırma çıktısında tutulur.
- Yerel lig karşılaştırmasında 1.179 tam skor eşleşmesi bulundu. Portekiz'de 16 Mayıs 2026 Moreirense–AVS skor kaydı iki kaynakta farklı olduğu için örneklemden çıkarıldı. Diğer tek kaynaklı satırlar araştırma verisi olarak kaldı.
- Slovan Bratislava–Real Betis, Sabah–Barcelona, Slavia Praha–Villarreal ve Shakhtar Donetsk–Fenerbahçe için ilk takımın yerel lig örneklemi eksik. ESPN istekleri 400/403 döndürdü. OpenFootball ve denenen Football-Data uzantıları 404 döndürdü. Alternatif kulüp/lig sayfalarına çalışma ortamından yapılan doğrudan istekler 403 ile engellendi.
- Ligler arası güç düzeltmesi ve kalibrasyon bekliyor. Lig gücü katsayısı uygulanmadığı raporda açıkça işaretli. Ana motorun 75 adaylı denetiminde 75 inceleme açık ve 0 otomatik sertifikasyon var. EX FINAL kilitli.
- Yerelde 829 unittest, Python derleme, beş depo denetimi ve 26 pipeline/entegrasyon smoke testi çalıştı. Başlangıç commit'i `a2375c7` için GitHub status 11/11 başarılı. Önceki araştırma çalışması `45356418996` başarılı.

## 2026-11-24: PR #2 kaynak tekrar oynatma ve dört pazarlı denetim

- `20f34fa` UEFA 403 durumunda URL ve SHA-256 kontrollü tarihli HTML maç kesitini tekrar işler. Ham yanıt ve kesit hash'leri ayrıdır. Arsenal–Dortmund dahil 18 fikstür ve ilk dört haftanın 72 skoru ESPN karşılaştırmasından geçer. Kaynak modu raporda belirtilir. Bu commit'in GitHub araştırma ve regresyon işleri başarılıdır.
- UEFA'nın takım bazlı resmi sayfası canlı alternatif olarak eklendi. Bu sayfanın 90 kaydı yerelde maç günü sayfasıyla aynı çıktı. Çelişkili yinelenen maç kimlikleri kabul edilmez.
- Git commit kimliğine sabitlenmiş OpenFootball Çekya ve Soccerway Ukrayna kaynakları karantina raporuna eklendi. Yerelde Slavia Praha için 9, Shakhtar Donetsk için 13 güncel sezon adayı var. Eksik önceki sezon ve bağımsız eşleşme nedeniyle motor veri setine aktarılmadılar. Dört açık maçla araştırma kapsamı 14/18.
- Lig gücü deneyi, 54 teyitli maçla rakip ve saha etkisini göz önüne alarak 18 ileri tarihli maçı sınadı. Kare hata 10,98568 ve saha avantajı referansı 10,76166. Düzeltme uygulanmadı.
- Ana motorun Tur-2 karşılaştırması artık tüm hesap izini denetler. Geriye dönük temel model denetimi dört pazarda Brier ve gerçekleşme sıklığını çıkarır. Yerel çalışmada pazar başına 1.063 maç incelendi. Kalibre EX-G kabulü için bağımsız, işlem zamanında dondurulmuş tahmin kanıtı bekliyor.
- 18 UCL kaydı üretim karar ağırlıkları, Tur-2 ve Auto-Control üzerinden denetlendi. 18/18 yeniden hesap uyuştu ve 18/18 Auto-Control kilitli kaldı. Doğrulanmış maç koşulları, dış etken, oran, bağımsız yerel lig kanıtı ve kalibrasyon olmadan PUP ve EX FINAL kapalı.

## 2026-11-24: PR #2 maç önü veri paketi ve skor karşılaştırması

- Shakhtar Donetsk için 13 güncel UPL maçının saha, tarih ve skorunu Soccerway dosyasıyla kulübün sonuç kaydı arasında eşleştirdik. Önceki sezonun 15 iç saha maçı Terrikon ile RSSSF ve iki kulüp maç raporundan kontrol edildi. Kaynak URL ve kayıt konumları `research/ucl/shakhtar-domestic.json` içinde. Shakhtar–Fenerbahçe örneklemi 5/10/13/15, genel başlangıç hesabı 15/18. Önceki sezon deplasman verisi bu pakette eklenmedi.
- 18 maçın UEFA kadro tahminleri, bildirilen eksikleri ve şüpheli oyuncuları ile ESPN stadyum ve son maç örnekleri toplandı. Son maç sayısı gösterilen örneklemle sınırlı. Tahmini kadro, doğrulanmış rotasyon veya yorgunluk puanı kabul edilmez. `reports/ucl_matchday5_prematch_2026_11_24.json` oranları, ham kaynak URL ve özetlerini içerir.
- DraftKings/ESPN gözleminde MS1 ve MS2 için 18'er, tam 2.5 ÜST için 4 oran var. KG VAR ve diğer 14 tam 2.5 ÜST oranı açık. Real Madrid MS1, Atlético MS1 ve Barcelona MS2 1,19 veya altında kaldı (PASS). EX-G ve EX-D hesaplanmadı.
- Bekleyen 75 tarihsel skor ESPN ham içeriklerinde tarih, ev/deplasman ve skorla 75/75 eşleşti. Sağlayıcı üst veri zinciri sertifikasyonu açık. `reports/external_2627_espn_content_reconciliation.json` kayıt başına kaynak işaretçisi içeriyor.
- Dört pazarın temeli 1.063 geçmiş maçtan hesaplandı. 4 Eylül 2026 öncesinde 368 eğitim, aynı gün ve sonrasında 695 holdout maçı kullanıldı. MS1 düzeltmesi iyileşmedi. KG VAR farkı yaklaşık 0,000006, 2.5 ÜST ve MS2 farkları da sınırlı. Deneme, geçmişe dönük üretilmiş başlangıç tahminidir. Kalibre EX-G sertifikası veya üretim katsayısı verilmedi.
- Lig gücü alternatifi eğitim maçlarının küçültülmüş gol farklarını kullandı. Holdout MSE 10,96943 ve saha avantajı referansı 10,76166. Sonuçlara uygulanmadı. EX FINAL kilitli.

- Slovan Bratislava için 15 güncel lig ve 16 önceki sezon iç saha lig skoru ikinci kaynakla eşleşti. Ev/deplasman ve skor için BeSoccer kullanıldı. Bir günlük gösterim farklarında yerel kulüp takvimi veya Eurofotbal tarihi korundu. Slovan–Betis eklendi, kapsama 16/18 ve 24 Kasım fikstüründe 9/9 oldu.
- Sabah için Terrikon/Trivela ile 11 güncel, Terrikon/BeSoccer ile 17 önceki iç saha skoru teyit edildi. Slavia için kulüp kaydı/BeSoccer ile 15 güncel ve 17 önceki iç saha skoru teyit edildi. 9 Mayıs 2026 Sparta maçı idari 0:3 olduğu için oynanmış gol örneklemine alınmadı. Son kapsam **18/18**, 5.123 lig satırı. Yeni kulüplerin önceki sezon deplasman kayıtları bu fikstürlerde kullanılan iç saha örnekleminin dışında. Fikstür başına başlangıç hesabı, eksik fiyat ve karar ayrımı `reports/ucl_matchday5_research_status_2026_11_24.json` içinde.
- Dört yerel lig arşivi önceki sezonun deplasman skorlarıyla da tamamlandı. Slovan 15 güncel/32 önceki, Sabah 11/33, Slavia 15/34 oynanmış, Shakhtar 13/30. Motor 5.187 lig satırıyla yine 18/18 başlangıç hesabı üretti. Genişletilmiş arşiv geri testte üç maç daha açtı. İstenen 1.063 maçlık deney ve güncel 1.066 maçlık deney aynı raporda duruyor.
- İkinci piyasa kaynağı MatchPulse, 18 fikstürün tamamında tam 2.5 ÜST ve KG VAR için bookmaker adıyla fiyat gösterdi. `reports/ucl_matchday5_market_comparator_2026_11_24.json` içinde derlendi. Bookmaker son güncelleme zamanı ve doğrudan kaynak teyidi eksik olduğu için bu fiyatlar üretim odds lock'a aktarılmadı.

## 2026-11-24: PR #2 matematiksel modelleme ve maç önü tekrar oynatma

- `run_ucl_model_integration.py` bugünkü 9 maçın mevcut kayıtlarını ağ erişimi olmadan tekrar oynatır. ESPN ve UEFA ham kayıtlarının SHA-256 özetleri kontrol edilir. Fikstür ve oran kapıları çalıştırılır. Skor dağılımı ve dört pazarı, bağımsız Poisson skor ızgarası dahil Tur-2 ile tekrar hesaplanır. Kaynaklar `ucl_research_output` altında saklanan önceki arşivdir.
- 18 takım için 7/14 günlük gözlenen asgari maç sayısı, son görülen başlama saatinden geçen sürenin üst sınırı, son teyitli yerel maç tarihi ve UEFA'nın bildirdiği eksik/şüpheli sayıları çıkarıldı. Örneğin Slovan’ın ESPN özetinde son görülen maç 504 saat önce, yerel kayıt ise 21 Kasım. Rotasyon ve oyuncu önem ağırlığı için oyuncu kimliği, iki teyitli ilk 11 ve önceki dakika verisi gerekli.
- 1.066 yerel maçta 204 eğitim, 245 doğrulama ve 617 ileri tarihli test ayrıldı. Dört pazarda referans, logit sabit düzeltme, Platt ve yük özellikli Platt karşılaştırıldı. Platt 2.5 ÜST ve KG VAR’da seçildi ve 54 sonraki UCL maçında da Brier hatasını düşürdü. Yerel testte haftalık bootstrap aralıkları sıfırı içeriyor. MS1/MS2’de referans seçildi. Maç yükü eklenen yöntem seçilmedi ve üretim parametresi yayımlanmadı.
- Lig gücü için 36/18/18 kronolojik ayrımda standart ridge, yüksek ceza ve uç gol farkı kırpılmış ridge, saha avantajı referansıyla karşılaştırıldı. Doğrulama referansı seçti. Lig katsayısı uygulanmadı.
- Dokuz maçta Tur-2 tutarlı, fikstür kilidi doğrulanmış, 20 fiyat kapısı geçerli. KG VAR için 9, tam 2.5 ÜST için 7 doğrudan fiyat eksik. %50/%30/%20 bileşimi için doğrulanmış pazar bazlı bağlam ve takım gücü ölçeği bekliyor. Araştırma takım gücü katkısı, maç başı engel ve çözüm ile EX-D önkoşulları `reports/ucl_matchday5_model_integration_2026_11_24.json` içinde. EX-G/EX-D boş, PUP/EX FINAL kapalı.

## 2026-11-24: EX-G, piyasa değeri ve FINAL kapılarının ayrılması

- Onaylı pazar kalibrasyonu `ex_decision.assess_markets` içinde yalnız %50/%30/%20 kanıt skorunu tüketir. Piyasa fiyatı EX-D tarafında ayrıca değerlendirilir. Kalibrasyon kaydı bu sürümde boş. Test, onaylı eşleme yerine geçici bir test eşlemesi kullanarak fiyat ve kesin kadro olmadan EX-G hesaplandığını gösterir. EX-D için aynı pazarın geçerli oranı gerekir. 1,19 ve altı PASS kuralı ile 1,20 ve üzerinde negatif EX-D'nin tek başına PASS oluşturmaması korunur.
- Bugünkü dokuz maçın yeni raporu başlangıç hesabı, kalibre edilmemiş araştırma olasılığı, EX-G ve FINAL durumlarını ayırır. Kesin ilk 11 önkoşul değildir. Gözlenen maç yükü, bildirilen eksikler ve saha bilgisi mevcut. Pazar bazlı doğrulanmış takım gücü, maç koşulu ve dış etki puanları ile onaylı kalibrasyon eksik. Oran replay uyuşmazlığı yalnız ilgili piyasa kontrolünü etkiler. Auto-Control ve PUP/FINAL yetki sınırları korunur.
- Varsayılan tekrar oynatma mevcut deneyleri çalıştırmaz. Önceki model deneyleri ayrı raporda kalır. Karar katmanlarının raporu `reports/ucl_matchday5_decision_stages_2026_11_24.json`.

## 2026-11-24: Ortak tarihsel özellikler ve bileşen testi

- 5.187 maçlık tarihli arşivden iki takımın da önceki yerel maç tarihi 4.982 kayıtta, iki takımın 10 maçlık ilgili saha penceresi 2.515 kayıtta çıkarıldı. Ana motor ve UCL aynı özellik çıkarıcıyı kullanır. Hedef maçın günü ve sonraki skorlar girdiye girmez.
- Dört pazar için saha gerçekleşme sıklıkları, son 5–10 maç gol farkı değişimi, dinlenme ve yerel fikstür yükü ayrı adaylar olarak sınandı. Birleşik aday da denendi. Karşılaştırma, aynı 979 maçta 173 eğitim, 271 doğrulama, 535 kronolojik test ve 54 UCL aktarım maçıyla yapıldı. Referans kimlik ve Platt arasından doğrulama döneminde seçildi.
- MS1 saha sıklığı hem yerel Brier (0,22009 → 0,21979) hem UCL Brier (0,29264 → 0,29159) değerini sayısal olarak düşürdü. Yerel %99 haftalık blok aralığı sıfırı içeriyor. 2.5 ÜST yük adayı iki testte kötüleşti, MS2 form adayı UCL'de kötüleşti ve KG VAR mevcut referansta kaldı.
- Arşivde seyahat, hava, saha değişikliği, zaman damgalı oyuncu durumu ve tüm müsabaka takvimi için yeterli tarihsel kanıt yok. Adayların hiçbiri üretimde doğrulanmış puan ya da kalibrasyon olarak kaydedilmedi. EX FINAL ve PUP sınırları korundu. Ayrıntılı rapor `reports/ex_component_experiment_2026_11_24.json`.

## 2026-11-24: Tarihsel kaynak toplama altyapısı

- Python ve GitHub Actions, birden çok takım/sezonun ESPN takvimini ve maç özetlerini bütçeli olarak toplar. UEFA maç önü eksik kaydı SHA-256 doğrulamalı eski yakalamadan tekrar oynatılabilir. Arşiv, geçmiş ve yeni yakalamaları ayrı tutar.
- Arsenal ve Dortmund pilotu 44 farklı takvim maçı gösterdi. Seçilen tarih aralığında beş müsabakadan 14 maçın özeti ve 579 oyuncu satırı alındı. 539 satırda nominal normal süre çıkarıldı. ESPN doğrudan dakika vermedi. 14 özet saha verisi sağladı. Hava ve seyahat kanıtı bulunmadı.
- Bütçe duraklaması 8 istek, devam 9 yeni istek ve 8 önbellek okuması, tamamlanmış tekrar 0 istek ve 17 önbellek okuması ile doğrulandı. Son kayıtlar önceki model araştırmalarını değiştirmez. Bağımsız maç önü ve sonuç kapsamı henüz %50/%30/%20 model doğrulaması için yetersiz.
- Çalıştırma bilgileri `docs/EX_HISTORY_COLLECTION.md`, ölçümler `reports/ex_history_collection_pilot_2026_11_24.json` içinde.

## 2026-11-24 — Toplu tarihsel veri çalışması

- 36 UCL takımı için 72/72 takım-sezon takvimi alındı. Beş ana EX ligiyle birlikte 222/222 takım-sezon yanıtı ve tekil 4.177 tamamlanmış maç gözlendi. Aynı planın tekrarında 223 önbellek kaydı kullanıldı ve yeni ağ isteği yapılmadı.
- Yerel sekiz bölümlü toplamada 462 özet doğrulandı ve 3.715 özet sonraki bütçeye kaldı. Özetlerin 208'i 2025, 254'ü 2026 sağlayıcı sezonuna ait. Nominal süre aritmetiğine uygun 819 takım toplamının tamamı 990 dakika verdi.
- Ortak özellik çıkarıcı, kaynağın analiz kesiminden önce gözlendiğini kontrol ederek fikstür aralıklarını, 14 günlük görünür maç yükünü ve oyuncu sürelerini çıkarır. Open-Meteo 403 döndürdü. Kayıtlı sahalarda bir coğrafi mesafe hesaplanabildi. Bağımsız model kalibrasyonu için kanıt yetersiz.
- Toplu çalıştırma `.github/workflows/ex-history-bulk.yml`, yöntem ve devam talimatları `docs/EX_HISTORY_COLLECTION.md`, ölçümler `reports/ex_history_bulk_2026_11_24.json` içindedir.

## 2026-11-24 — Toplu tarihsel toplamayı sürdürme

- Korunan önbellekten ilk devam turunda 654 eski ve 320 yeni özet doğrulandı. Toplam 974/4.177, kalan 3.203. Nominal süreye uygun 1.723 takım toplamının tamamı 990 dakikaydı.
- Sekiz bölümde en çok iki eşzamanlı işi koruyarak bölüm başına bütçe 100'e çıkarıldı. Kaynak hataları ve bekleme kayıtları sınıflandırılıyor. NASA POWER hava alternatifi, diğer 11 lig için genişleme yapılandırması ve ana motorun iki skor kuyruğu için günlük kanıt toplayıcısı eklendi.

## 2026-11-24 — Onuncu çalışma paketi

- Özet, hava ve skor önbellekleri aynı bölüm anahtarlarıyla korunarak genişletilmiş profil çalıştırıldı. Sezon tabloları doğrulanabilen ek liglerin katılımcıları planla birleştirildi. ESPN kapsamı bulunmayan ligler için mevcut iki kaynak bağlantılı kulüp listeleri ayrı kısmi kanıt olarak eklendi.
- EX ve UCL girişleri, takım kimliği ile eşleşen dakika, yük, dinlenme ve saha gözlemlerini aynı zamana duyarlı özellik çıkarıcıdan alır. Dokuz UCL tekrarı ve dört pazarın Tur-2 ve Auto-Control doğrulaması çalıştırıldı. Sonradan edinilen tarihsel arşiv, maç önü kalibrasyon girdisi sayılmaz.
- Ayrı Bundesliga skor adaptörü, daha geniş hava örneklemi ve kulüp yayınlarına dayanan dört belgelenmiş seyahat gözlemi eklendi. OpenLigaDB ve ESPN içerik eşleşmeleri kaynak bağımsızlığı onayı vermez.

## 2026-11-24 — On birinci çalışma paketi

- Ham 6.820 özet, skor defteri ve plan Actions'ta ağsız olarak tekrar işlendi. Tamamlanmış maçlardan elde edilebilen veriler ve gerçek maç önü yakalama gerektiren veriler ayrı tutuldu. Kronolojik pazar deneyleri ve skor kaynakları arasındaki tekil fikstür kapsamı araştırma çıktısına eklendi.
- Maç öncesi ESPN yakalama işi, zamanı doğrulanmış ham kayıtları gelecekteki değerlendirmeler için saklıyor. Dört ek ligde resmî oyuncu ve kadro kaynakları dokümante edildi.

### Kalıcı arşiv ve haftalık doğrulama

- `EX prospective operations` iş akışını maçlar başlamadan önce `mode=capture`
  ve UTC fikstür tarihiyle çalıştır. Onaylı 13 müsabaka sorgulanır. Arşivlenen
  araştırma tahminleri EX-G ve EX FINAL alanlarını doldurmaz.
- Haftalık envanter için `EX weekly research evidence` akışına UTC pazartesi
  tarihini ver. `artifact_ids` alanına kalıcı hale getirilecek arşiv paketlerini
  virgülle ayırarak yaz. Kaynak GitHub makbuzu, ZIP özeti ve her dosyanın SHA-256
  özeti doğrulanır. Maç önü veri, araştırma tahmini, doğrulanmış sonuç ve
  sonuç kaynağı ayrı indekslenir. Aynı paketin tekrar yazımı etkisizdir ve
  içerik değişikliği reddedilir. Depo yöneticisi yetkileri için Git dalına
  ayrıca koruma uygulanması gerekir.
- `mode=settle` kalıcı tahmin paketlerini kendisi okur. Bağımsız resmî
  kontroller varsa `official_run_id` ver. Resmî kanıtı bulunmayan sonuçlar
  geçici defterde tutulur ve ileriye dönük ölçüme katılmaz. Yeni sonuç
  paketinin kimliğini sonraki hafta kalıcı arşiv çalışmasına ekle.
  Yeni günlük analiz, ham kaynağıyla arşivlenmiş ve tahmin kesiminden
  önce doğrulanmış sonuçları geçmiş hesaplarına ekler.
- Haftalık rapor yayımlanmış fikstürü, mühürlenmiş araştırma tahminini ve
  tam takım gücü penceresini ayrı sayar. Fikstür envanterinde başarısız
  kaynak günleri ayrıca listelenir. 23–29 Kasım 2026 UTC örneğinde 91/91
  sorgudan 128 fikstür görüldü. Bu sayı lig ve kupa takvimine göre değişir.
- Süre senaryoları, 2.317 geriye dönük satır içindeki uygun 503 satırın
  13 haftalık eşleştirilmiş Brier farkını kullanır. Hafta içi örneklem
  büyüklüğü `m` ve varsayımsal korelasyon `rho` için göreli varyans
  `rho + (1 - rho) / m` ile ölçeklenir. Haftalar arası bağımsızlık
  planlama varsayımıdır. Kesin kabul testinin haftalık güven sınırı ve
  ileriye dönük veri koşulları ayrıca uygulanır. Tam üç bileşenli
  modelin süresi, uygun ileriye dönük pilot oluştuğunda hesaplanabilir.
- Akışlar elle başlatılabilir. Yeni zamanlayıcı tanımlanmadı.

### Paket 20 — günlük araştırma ve arşiv çalıştırma

- `python run_ex_prospective_pipeline.py --daily-capture YYYY-MM-DD --historical-facts /path/to/historical-facts.jsonl --domestic-packs /path/to/restored-ucl-packs --prior-settlements /path/to/restored-settlements --cache pregame-cache --output-dir forecasts`
  onaylı 13 müsabakayı tarar, ham kanıtı ve günlük dört pazar karar kaydını
  yazar, hesaplanan başlangıçları Tur-2 ve Auto-Control üzerinden geçirir.
  İlk çalıştırmada `--historical-facts` yerine `--plan` ve `--history`
  ile doğrulanabilir ham özetler kullanılabilir.
- UCL'nin maç günü 5 yurtiçi sonuç arşivi, yalnızca kayıtlı iki takım ve UTC
  başlama saati eşleştiğinde kullanılır. Sonuçlar `daily-analysis.json`
  dosyasında kalır. Dondurulan venue5 kalibrasyon defterinin örneklem
  ölçütlerine dahil edilmez.
- `mode=cycle`, kendisinin ürettiği arşivleri SHA-256 doğrulaması yapan
  yazıcıya otomatik iletir. Geriye dönük özetlerden üretilen 6.820
  normalleştirilmiş kayıt kaynak özetleriyle birlikte sayısal parmak
  izlerini tutar. Ham dosya sağlama doğrulama ve yeni ham geçmiş
  yükleme yolu açıktır.
- Günlük ve haftalık arşiv iş akışlarında cron tanımları hazırdır.
  GitHub Actions `schedule` olayı ancak varsayılan dalda bulunan akışta
  çalışır. Bu depoda varsayılan dal `main` olduğundan PR üzerindeki
  cron tanımları kendiliğinden çalışmaya başlamaz. Geliştirme dalında
  `workflow_dispatch` ile aynı işler çalıştırılabilir.
- `ex-evidence-archive` korumasını bir depo yöneticisi GitHub
  Settings → Branches veya Rules → Rulesets altında bu dala özel
  tanımlayabilir. Zorla gönderimi ve silmeyi engelle, normal hızlı ileri
  Actions yazımını açık tut. REST kullanılıyorsa depo için
  Administration: write yetkili fine-grained PAT veya GitHub App gerekir.

### Birleştirilmiş paket — kayan arşiv ve bağımsız skorlar

- UCL günlük araştırması takım adından lig tahmin etmez. Maç önü ESPN
  takım kimliği, ilgili sezonun yerel lig kayıtları ve doğru saha yönüyle
  eşleşir. Birden fazla güncel lig veya eksik pencere başlangıç hesabını
  engeller. 5. maç günü arşivi yalnızca doğrulanan fikstürlere geri dönüş
  sağlar. Mühürlenmiş haftalık skor tablolarından alınan yeni sonuçlar
  yalnızca araştırma takım gücü geçmişine girer.
- `run_ex_rolling_validation.py --facts ... --examples ... --output ...`
  kalıcı arşivden 6.820 özet ve 2.317 referans satırıyla kronolojik
  karşılaştırma yapar. Bu arşivdeki 255 bitmiş UCL maçının 34'ünde kayan
  yerel lig başlangıcı, sekizinde karşılaştırılabilir venue5 referansı
  bulundu. Son test dilimindeki üç maç üretim kararı için yetersiz.
- Haftalık rapor 48 saatlik maç önü penceresi henüz açılmayan maçları
  erişim paydasından ayırır. Maç özeti erişilemese bile mühürlü maç önü
  fikstür tablosu sonuç takibini başlatabilir. Haftalık cron raporu
  arşiv yazıcısına kendisi iletir.
- `mode=source-audit` gerçek resmî sayfaları toplar ve ham kanıtı
  saklar. DFL, LaLiga, KNVB, Eliteserien ve UEFA kaynakları ile
  Fransa'da Marsilya arşivi desteklenir. Belçika güncel hafta ve
  bilinen maç belgeleriyle, Portekiz eşleştirilmiş maç belgesiyle
  sınırlıdır. TFF güncel hafta sayfası boş veya gelecek skorları
  kabul etmez.
- Varsayılan dalı değiştirmeden otomatik çalışma için yetkili bir dış
  zamanlayıcı aynı `gh workflow run` çağrılarını PR dalı ref'iyle
  yapabilir. GitHub'da `Actions: write` yetkili GitHub App veya
  fine-grained PAT ile çalıştırılır. Bu pakette bir dış zamanlayıcı
  kurulmadı ve varsayılan dal ayarı değiştirilmedi.

### Paket 21 — dış zamanlayıcı ve arşiv dalı yetkileri

1. Dış zamanlayıcının çalışacağı ortamda Python ve GitHub CLI kurulu olmalı.
   GitHub App kurulum token’ını veya yalnız bu depoya erişen fine-grained
   PAT’i `GH_TOKEN` gizli değişkenine koy. **Actions: write** yetkisi ver.
2. Geliştirme dalından `python run_ex_archive_dispatch.py` ve
   `python run_ex_archive_dispatch.py --weekly` ile komutları önizle.
   `--execute` doğrudan çalıştırır. Günlük komut UTC bugün, yarın ve
   ertesi günün tahtalarını tarar. Maç önü 48 saat sınırı korunur.
   Haftalık komut önceki haftayı raporlar ve arşiv yazıcısına gönderir.
   Bu kurulum `main` içindeki yerleşik cron tanımına bağlı değildir.
3. GitHub deposunda **Settings → Rules → Rulesets → New ruleset →
   New branch ruleset** yolunu aç. Durumu **Active** yap.
4. Hedef dal desenini yalnızca `ex-evidence-archive` olarak belirle.
   **Restrict deletions** ve **Block force pushes** kurallarını etkinleştir.
   Normal Actions yazımı için **Restrict updates** ve zorunlu pull request
   seçeneklerini bu kuralda açma. Kaydet ve dal ekranındaki koruma durumunu
   doğrula. REST ile işlem yapılıyorsa **Administration: write** gerekir.

Ortak arşiv yazıcısının kuyruğunu doldurmamak için üç günlük çağrıyı
`--offset 0`, `--offset 1`, `--offset 2` ile ayrı zaman aralıklarına
yay. `--weekly --execute` ayrı bir haftalık çağrıdır.
