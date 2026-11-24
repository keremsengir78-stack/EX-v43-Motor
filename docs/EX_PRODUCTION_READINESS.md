# EX v4.3 üretim hazırlığı

| Alan | Ölçüm | Yazılım | Gerçek veri veya kanıt bağımlılığı |
|---|---|---|---|
| Tarihsel arşiv | 6.820 özet ve 2.317 özellik satırı | Önceki Actions çıktıları korunuyor | Yeni kaynak talebi yok |
| KG VAR ve 2.5 ÜST | 1.328 eski eğitim satırı, yeni kesinleşmiş test örneği 0 | Platt adayları donduruluyor. Maç öncesi tahmin ve sonuç defterleri ayrı, eski fixture kimlikleri ve zaman sınırı engelleniyor | Aynı referans tanımıyla, tahmin anı saklanmış daha sonraki maçlar ve bağımsız sonuç kanıtı |
| MS1 ve MS2 | İki pazarda mevcut referans | Dondurulmuş aday bu pazarlara kalibrasyon uygulamıyor | Sabit pencerenin yeni test sonuçları |
| %50 takım gücü | Önceki ortak test 147 maç | %40/%30/%20/%10 pencere araştırma karşılaştırması tutuluyor | Daha geniş, sonradan oluşmuş ve zaman damgalı test. Aday karşılaştırması için en az 100 maç ve sekiz farklı hafta araştırma raporunda izleniyor |
| %30 maç koşulları | Yük ve süre gözlemleri, UEFA eksik haberi | Gerçek maç önü gözlemleri araştırma kaydında mevcut. Dinlenme, fikstür yoğunluğu ve oyuncu süre yoğunlaşması ayrı aday | Pazar başına koşul etkisinin bağımsız kronolojik doğrulaması |
| %20 dış etkenler | Dokuz saha konumu, tarafsız saha ve maç önü hava | Tahmin saat, konum ve yakalama zamanı denetleniyor | Doğrulanabilir yolculuk ve maç günü saha belgeleri, hava tahmini boyunca sonuç eşleşmesi, pazar etkisi |
| Skor kaynakları | 1.078 tekil, 99 iki sağlayıcılı, 38 önceki resmî sonuç, 1 çok kaynaklı kayıt, 9 yeni DFL çapraz eşleşmesi | Mutabakat, yeni DFL kontrolleri ve kaynak katmanları ayrılıyor | ESPN maç verisinin aday başına kökeni ve resmî kaynak denetimi |
| Dört ligde dakikalar | Ukrayna örneğinde 32 nominal oyuncu süresi | Resmî başlangıç kadrosu ve değişikliklerden 990 takım-dakika hesabı | Slovakya, Çekya ve Azerbaycan için güvenilir ayrıştırma ve zaman çizelgesi, Ukrayna pilotunun genişletilmesi |
| EX-G, EX-D, Tur-2, Auto-Control ve PUP | Dokuz maç ve 36 pazar yeniden hesaplanıyor | Ortak karar katmanları ve gerçek zaman kesimi kullanılıyor | Kalibre EX-G, doğrulanmış bağımsız bileşenler ve onaylı PUP kanıtı |
| EX FINAL | Yayına hazır karar 0 | Teknik denetim ve güvenli kilit mevcut | Yukarıdaki zorunlu kanıtlar ve kullanıcı onaylı koşullar |

Dondurulmuş Platt, önceki beş maçlık saha referansına özeldir. 25 Kasım araştırma kaydındaki Poisson olasılıklarına uygulanmaz. Gelecekteki değerlendirme, maç önü tahmin ve sonradan alınan sonuç için ayrı JSONL defterleriyle çalışır. Araştırma eşiği uygulama yetkisi vermez.

Ukrayna pilotu, 14 Eylül 2026 Shakhtar–Chornomorets maçının resmî hakem raporunu kullanıyor. Oyuncu süreleri normal sürenin nominal dakikalarıdır. [Resmî rapor](https://upl.ua/en/report/view/15927/report)

Bundesliga 2026/27 10. hafta, iki kaynaklı defterdeki adayları ve Football-Data sırasındaki yeni sonuçları resmî yayına karşı ayrı karşılaştırır. Bu kontrol giriş sağlayıcılarının maç bazlı kaynak zincirini onaylamaz. [DFL maç günü](https://www.bundesliga.com/en/bundesliga/matchday/2026-2027/10)
