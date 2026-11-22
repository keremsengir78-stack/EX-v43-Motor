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
