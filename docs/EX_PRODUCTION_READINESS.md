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
| Dört ligde dakikalar | Ukrayna ve Çekya için 2 maç, 64 nominal oyuncu süresi | Resmî başlangıç kadrosu ve değişikliklerden 990 takım-dakika hesabı | Slovakya ve Azerbaycan için tamamlanmış zaman çizelgesi, Ukrayna ve Çekya pilotlarının toplu ayrıştırılması |
| EX-G, EX-D, Tur-2, Auto-Control ve PUP | Dokuz maç ve 36 pazar yeniden hesaplanıyor | Ortak karar katmanları ve gerçek zaman kesimi kullanılıyor. PUP yürütücüsü yerine engel denetimi var | Kalibre EX-G, doğrulanmış bağımsız bileşenler ve onaylı protokolün yürütme testi |
| EX FINAL | Yayına hazır karar 0 | Teknik denetim ve güvenli kilit mevcut | Yukarıdaki zorunlu kanıtlar ve kullanıcı onaylı koşullar |

Dondurulmuş Platt, önceki beş maçlık saha referansına özeldir. 25 Kasım araştırma kaydındaki Poisson olasılıklarına uygulanmaz. Gelecekteki değerlendirme, maç önü tahmin ve sonradan alınan sonuç için ayrı JSONL defterleriyle çalışır. Araştırma eşiği uygulama yetkisi vermez.

Ukrayna pilotu, 14 Eylül 2026 Shakhtar–Chornomorets maçının resmî hakem raporunu kullanıyor. Oyuncu süreleri normal sürenin nominal dakikalarıdır. [Resmî rapor](https://upl.ua/en/report/view/15927/report)

Bundesliga 2026/27 10. hafta, iki kaynaklı defterdeki adayları ve Football-Data sırasındaki yeni sonuçları resmî yayına karşı ayrı karşılaştırır. Bu kontrol giriş sağlayıcılarının maç bazlı kaynak zincirini onaylamaz. [DFL maç günü](https://www.bundesliga.com/en/bundesliga/matchday/2026-2027/10)

Maç koşulları ve dış etkenler için koşullu aralık, takım gücü araştırma referansı sabitken olası toplam ağırlıklı puanın alt ve üst sınırını verir. İki eksik bileşene değer atanmaz. Bu aralık sayısal kapsamı gösterir, kalibre olasılık veya EX-G girdisi olarak kullanılmaz.

Çekya pilotu, 31 Ekim Jablonec–Slavia maçı için ligin yayımladığı kadro ve değişiklik zamanlarını kullanıyor. Slovakya’da organizatör ve kulüp sayfaları fikstür ve kadro kanıtı sağlıyor. Tam dakika kapsamı açık. Azerbaycan PFL 6775 kaydı kupa finaline ait olduğu için yerel lig kapsamına alınmadı. [Chance Liga](https://www.chanceliga.cz/zapas/statistiky/8430-fk-jablonec-sk-slavia-praha) · [Niké liga](https://www.nikeliga.sk/zapas/2839-slo-mic/statistiky) · [PFL](https://pfl.az/x%C9%99b%C9%99rl%C9%99r/15473)
