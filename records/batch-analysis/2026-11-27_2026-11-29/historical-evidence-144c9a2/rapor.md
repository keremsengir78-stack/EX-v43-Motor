# EX v4.3 · Bağımsız tarihsel kanıt ve kalibrasyon

Kesim 26 Kasım 2026 16:10 TRT. Kod commit'i 144c9a2d8fc8a23205a91621e8cea14a877da18e. 103 maçın araştırma tahminleri ve önceki arşiv kayıtları yeniden üretilmedi.

| Ölçüm | Önce | Sonra |
|---|---:|---:|
| Tarihsel arşivde kesin kimlikle karşılaştırılan resmî skor eşleşmeleri | Bu denetim yoktu | 31 |
| Tam bağımsız form kanıtı ile kabul edilen hedef maçlar | 0/103 | 0/103 |
| Tam kabul alan pazarlar | 0/412 | 0/412 |
| Kronolojik araştırma bölünmesi | 240/155/164 | 240/155/164 |
| Kronolojik araştırma testinde hafta | 4 | 4 |
| Mühürlü, sonuçla eşleşen ileriye dönük donmuş aday örneği | Bu sayım yoktu | 2 |
| İleriye dönük örnek haftası | Bu sayım yoktu | 1 |
| EX-G / EX FINAL | 0 / 0 | 0 / 0 |

6.820 tarihsel kayıt ve katalogdaki 15 organizasyon tarandı. 11 organizasyonda 612 tekil resmî sonuç satırı ayrıştırıldı. 31 skor, yönlü takım kimliği, kesin UTC başlangıcı, lig ve sonuçla eşleşti. Bundesliga 5, La Liga 3, Ligue 1 7, Eliteserien 16. Önceki 9 Şampiyonlar Ligi sonucu ayrı bir kanıt grubudur. 15 takım kesişiminin tümü farklı ligdedir. Bu dokuz skor, başlangıç tarihsel arşivinde olay ID'si olarak da yoktu. Başlama saatleri, ev/deplasman takım kimlikleri ve arşiv mühürleri JSON dosyasındadır.

31 eşleşmeden 29 tarihsel olay, 15 hedef maçın arşivlenmiş form örnek tarihlerinde aday olarak görünüyor. Tarih listesi aynı günlü örneklerin olay kimliğini tek başına ispatlamaz. Resmî yayın ile birincil arşiv baytları ayrı olsa da skorun ilk kaynağının bağımsızlığı ayrıca belgelenmelidir. Eşleşmeler üretim kabulüne aktarılmadı. Eksik 34 maçın aynı lig/saha şartı korundu.

14 tekil mühürlü tahminden donmuş aday sınırına ve doğrulanmış arşiv sonucu eşleşmesine uyan 2 kayıt var. Bunlar 2026'nın 48. haftasında. Üretim için sekiz haftalık test bloğu şartı karşılanmadı. Eldeki 240/155/164 tarihsel deneyin dört haftalık test süresi korunuyor. Sonuç sonrası tahmin oluşturulmadı.

Bağlam incelemesi her iki takımın maç yükü ve dinlenme kaydına tarihli önemli eksik ve rotasyon incelemesi bağlar. Kaynak dosyaları doğrulama sırasında yeniden okunur. İki takımın tüm parçaları bulunmadığında kabul üretilmez. Bu paket kapsamındaki arşivde kabul edilebilir tamamlanmış inceleme bulunmadı.

Yerel test sonucu 945 başarılı. 103 maçın mevcut 96 saatlik araştırma kapsamı, 48 saatlik canlı kabul sınırı ve onay kuralları korundu.
