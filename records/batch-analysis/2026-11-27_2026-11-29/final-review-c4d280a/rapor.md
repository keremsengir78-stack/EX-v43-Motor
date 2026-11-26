# EX v4.3 · FINAL engelleri, 27–29 Kasım 2026

PR #2 başı c4d280a257e8006b408b915fb1f9e6d0d6948789. 943 yerel test ve 30 CI kontrolü geçti. Altı koşullu CI işi atlandı. Toplu işin üç günü ve arşive yayımlama adımı geçti.

| Ölçüm | Önce | Sonra |
|---|---:|---:|
| Bağımsız fikstür | 103/103 | 103/103 |
| Referans ve V1 | 69/103 | 69/103 |
| Tur-2 araştırma | 95/103 | 95/103 |
| İki taraf için kaynaklı tamamlanma ve maç yükü izi | yayımlanmıyordu | 80/103 |
| Form örneklerinde bağımsız skor eşleşmesi bulunan maç | ölçülmüyordu | 0/103 |
| Tam veri alımı / ikinci kaynak / maç bağlamı kabulü | 0/412 her biri | 0/412 her biri |
| Doğrulanmış EX-G / gerçek EX FINAL | 0 / 0 | 0 / 0 |

Arşivden 9 bağımsız sonuç geri alındı. Hiçbiri toplu analizde kullanılan aynı ligdeki tarihsel form örnekleriyle eşleşmedi. Denetim etkinlik, başlangıç, lig, saha yönü ve skoru denetler. Arşiv mühür zamanı karar kesiminden önce olmalıdır. Kaynak geçmişi bir skorsuz kayıt ile karşılaşırsa kesinleşmiş, kimliği aynı arşiv satırı artık atlanmaz. Bu çalışmada yeni bir model çifti açılmadı.

34 eksik maçtaki 35 takım tarafının lig geçişi resmî lig, federasyon veya kulüp kaynaklarıyla belgelendi. Bu tarafların önceki sezonunda aranan lig örneği oluşmadı. Alt veya üst lig geçmişi ikame edilmedi. Ayrıntılar CSV dosyasında.

Maç bağlamı izi maç kimliği, organizasyon, başlangıç, tamamlanma kanıtı, sağlayıcı zamanı ve özet SHA-256 özetini içerir. Kaydedilen Avrupa maçı sayısı gözlenen alt sınırdır. 80 maçın iki tarafında iz mevcut. Önemli eksikler ve rotasyon için yeterli maç öncesi kanıt bulunmadığından bağlam onaylanmadı. 24 maç canlı 48 saatlik penceredeydi. Pencere kuralları değişmedi.

Dört pazarın referans ve aday olasılıkları üzerinde 240/155/164 kronolojik araştırma örnekleriyle kimlik, kesişim ve Platt yöntemleri karşılaştırıldı. Kesişim ve Platt katsayıları yalnız eğitim bloğunda uyarlandı. Kimlik dönüşümü sekiz model-pazar karşılaştırmasının yedisinde seçildi. V1 KG VAR için seçilen Platt bağımsız test Brier kaybını 0,249998'den 0,250091'e yükseltti. Bağımsız test dört haftalık blok içerdiği için mevcut sekiz blok şartıyla %99 güven aralığı hesaplanamadı. Tam bileşen puanı ve üretim kalibratörü için kabul çıkmadı.

[Toplu koşu](https://github.com/keremsengir78-stack/EX-v43-Motor/actions/runs/45825937760) · [PR kontrolleri](https://github.com/keremsengir78-stack/EX-v43-Motor/pull/2/checks)
