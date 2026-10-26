# ami-topolino-can-decode

Citroën Ami / Opel Rocks-e / Fiat Topolino OBD-CAN hattından ESP32 ile kaydedilmiş
trafiğin **topluluk tarafından çözümlenmesi**. Amaç: kimliği belirsiz CAN ID'lerini
birlikte çözmek ve ESP32 tabanlı gösterge/loglayıcı projelerinin kullanabileceği bir DBC üretmek.

> **Durum: deneysel.** Aşağıdaki çözümlerin çoğu tek bir araçtaki ~650 bin karenin
> istatistiksel analizine dayanır. Güven seviyesi her satırda belirtilmiştir.
> Kendi aracınızda doğrulayıp Issue/PR açarsanız çok sevinirim.

## Gizlilik

Ham loglar VIN içerdiği için **repoda yoktur** ve `.gitignore` ile engellenmiştir.
Katkı verirken `0x710`, `0x711`, `0x712` kareleri (VIN parçaları) dahil hiçbir kişisel
veri paylaşmayın. `tools/analyze_captures.py` bu kareleri çıktıda maskeler.

## Veri kaynağı

- ESP32 + CAN transceiver, OBD portu, `.jsonl` log (`can_id`, `data_hex`, `dlc`, `extended`, `esp_timestamp_us`, `timestamp_utc`)
- Sürüş ve şarj oturumları, toplam ~651 bin kare
- Karelerin büyük bölümü bit hatası kaynaklı gürültü: ~4500 farklı ID görülüyor ama
  gerçek trafik yaklaşık 40 ID. Extended kareler ve tek seferlik 11-bit ID'ler atılmalı.

## Çözülenler

| ID | Alan | Çözüm | Güven |
|----|------|-------|-------|
| 0x595 (1 Hz) | B0:B1, B2:B3 | u16 LE, 0,01 V paket gerilimi (0x580 ile r≈0,99) | Yüksek |
| 0x595 | B4 | SOC ile ilişkili, ölçek belirsiz | Düşük |
| 0x580 (B6=0x13) | B0:B1 | s16 LE, 0,1 A akım (− deşarj, + rejenerasyon) | Yüksek |
| 0x580 | B2:B3 | u16 LE, 0,01 V gerilim | Yüksek |
| 0x580 | B5 | SOC adayı (% , gün boyu 79→13 monoton) | Orta |
| 0x580 | B4 | Sıcaklık adayı (21→23) | Düşük |
| 0x024 | B6 | Paket gerilimi, tam volt | Yüksek |
| 0x060 | B2:B3 | u16 BE, 0,1 V gerilim | Orta |
| 0x060 | B5 / B4 | Sayaç / CRC benzeri | Orta |
| 0x060 | B6:B7 | 0x7FFF merkezli değer, ivmelenmede 0x8xxx–0x99xx; anlamı belirsiz | Düşük |
| 0x4E8 | B1, B2 | Yavaş değişen sıcaklık adayları | Düşük |
| 0x710–0x712 | tümü | ASCII VIN parçaları (3+6+8 bayt) | Yüksek |

> **Not:** `0x580` sinyalleri yalnızca `B6=0x13` yerleşimi için geçerlidir; şarj yerleşimindeki
> karelerde (`B6=0x6C/0x36`) ve bit hatalı karelerde aralık dışı değerler çıkar.

## Çözümler ne işe yarar?

### Akım ve gerilim (0x580, 0x595, 0x024, 0x060)
- **Anlık güç göstergesi:** `kW = V × A / 1000`. Akım işaretli olduğu için ivmelenmede negatif, rejenerasyonda pozitif çıkar. Bir ibre/bar göstergede "harcama / geri kazanım" olarak gösterilebilir.
- **Enerji ve tüketim (Wh/km):** güç değerini zamanla toplayarak (`Wh += kW × dt`) sürüş başına tüketim hesaplanır. Hız kaynağı ayrıca gerekir (bu repoda henüz çözülmedi).
- **Rejenerasyon göstergesi:** pozitif akım = fren/bırakma sırasında bataryaya geri akış.
- **Voltaj sarkması ve batarya sağlığı ipucu:** gerilim yük altında düşer (örnek: boştayken ~53 V, ağır ivmelenmede ~50 V). Sarkma ÷ akım yaklaşık iç direnci verir; zamanla izlenirse batarya yaşlanması için kaba bir gösterge olur.
- **Aynı gerilimin 4 farklı yerden gelmesi:** 0x595 (iki alan), 0x580 ve 0x060. Biri bozulursa diğerine düşülebilir, birbirleriyle karşılaştırılarak okuma hatası ve kontak/kablo kaybı fark edilebilir.
- **0x024 B6 (tam volt):** tek bayt, sabit ölçek. Düşük kaynaklı mikrodenetleyicilerde en ucuz gerilim okuması.

### Şarj durumu (0x580 B5, 0x595 B4)
- **Yüzde göstergesi:** 0x580 B5 gün boyunca 79'dan 13'e monoton düştü, yani SOC adayı. Gösterge ekranında yüzde olarak kullanılabilir, ama doğrulanmadan aracın kendi göstergesinin yerine geçmesin.
- **Kalan menzil tahmini:** SOC × batarya kapasitesi ÷ son dönem ortalama tüketim.
- 0x595 B4'ün ölçeği tutarsız çıktı; kullanmadan önce kendi aracınızda 0x580 B5 ile karşılaştırın.

### Sıcaklık adayları (0x4E8 B1/B2, 0x580 B4)
- Batarya/güç elektroniği ısınma uyarısı ve şarj sonrası soğuma takibi için kullanılabilir. Hangi alanın hangi parça olduğu belli değil; hata yaparsanız yanlış uyarı verir, bu yüzden bilgi amaçlı gösterin.

### VIN parçaları (0x710, 0x711, 0x712)
- Cihazın hangi araca bağlı olduğunu tanımak için: aracı otomatik algılayıp doğru çözüm tablosunu seçmek, birden fazla araçta log ayırmak.
- **Gizlilik uyarısı:** VIN kişiyi/aracı tanımlar. Log paylaşırken bu kareleri atın; araç içinde ekranda göstermeyin.

### Sayaç ve CRC baytları (0x060 B5/B4 ve benzerleri)
- **Kare doğrulama:** sayaç düzgün artıyor mu diye bakarak kayıp kare ve bozuk kare tespit edilir. Loglarda ~4500 ID'nin neredeyse hepsi bit hatası olduğundan, yalnızca bilinen ID listesini ve sayaç tutarlılığını kabul etmek veriyi temizler.
- **Hat canlı mı kontrolü:** 60 ms periyotlu sabit kareler (0x715, 0x012) görünüyorsa araç uyanık ve hat sağlıklı demektir. İçerikleri sabit olduğu için başka bir amaca yaramaz.

### Hâlâ çözülmeyenin pratik anlamı
- **Hız, gaz pedalı, vites, fren:** bu repoda yok. 0x060 B6:B7 (0x7FFF merkezli değer) ivmelenmeyle birlikte hareket ediyor, muhtemelen tork/güç isteği ile ilgili. Hız referanslı bir kayıt gelirse buraya eklenecek.

## Anlamı çıkmayanlar / sabit olanlar

- `0x715`, `0x012`, `0x1B0`: pratikte sabit içerik.
- `0x050`, `0x05A`, `0x05E`, `0x03C`, `0x5C0`: sayaç/CRC baskın; anlamlı alanlar çözülemedi.
- `0x580` şarj oturumunda (B6=0x6C/0x36) farklı yerleşim gösteriyor, çözülmedi.
- `0x581`, `0x582`, `0x593`, `0x594`, `0x713`, `0x714`: mevcut açık kaynak DBC'lerde var, burada tekrar yorumlanmadı.

## Kullanım

```bash
# 1) Kendi loglarınızı özetleyin (loglar repoya girmesin!)
python3 tools/analyze_captures.py ./Captures 200

# 2) DBC'yi cantools ile deneyin
pip install cantools
python3 -c "import cantools; db=cantools.database.load_file('dbc/ami_topolino_extra.dbc'); \
print(db.decode_message(0x595, bytes.fromhex('4D144A1444 0000DE'.replace(' ',''))))"
```

Örnek ESP32 (Arduino) çözümü:

```cpp
// 0x580: akım (0,1 A, işaretli) ve gerilim (0,01 V)
float amps  = (int16_t)(d[0] | (d[1] << 8)) * 0.1f;
float volts = (uint16_t)(d[2] | (d[3] << 8)) * 0.01f;
```

## Katkı

1. Aracınızı, model yılını ve durumu (sürüş/şarj/rölanti) belirtin; VIN yazmayın.
2. Bir ID için kanıt (zaman serisi, korelasyon) paylaşın.
3. Güven seviyesini tabloya PR ile ekleyin.

Özellikle işe yarayacaklar: hız / gaz pedalı referanslı kayıtlar, şarj oturumu etiketli loglar,
Topolino ve Rocks-e'den karşılaştırma.

## Yasal

Bu çalışma yorumlama (reverse engineering) amaçlıdır, üreticiyle ilgisi yoktur.
CAN hattına yazma yapmak aracın güvenliğini etkileyebilir; bu repo yalnızca **dinleme/okuma** içindir.
Garanti verilmez. Lisans: MIT.

---

## English summary

Community effort to decode CAN traffic from the Citroën Ami / Opel Rocks-e / Fiat Topolino OBD port
(ESP32 logger). Raw logs are intentionally excluded because they contain the VIN.
See the table above for decoded signals with confidence levels (pack voltage/current/SOC candidates,
VIN-fragment frames, etc.). Read-only use. PRs with verification from other vehicles are very welcome.
