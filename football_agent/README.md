# football_agent — AI destekli futbolcu menajerliği & eşleştirme motoru

> Pilot: **2026/27 UEFA Şampiyonlar Ligi lig aşamasındaki 36 kulüp.**
> Tez: doğru transfer, salt istatistik değil; takım kimyası, mental uyum, sakatlık geçmişi,
> kulüp prensipleri ve bağlam birlikte okunduğunda ortaya çıkar — ve bu iş otomatikleştiğinde
> menajerlik komisyonu **%2** ile sürdürülebilir.

*(English summary below.)*

## Ne yapıyor?

1. **Veri katmanı** (`data/`): her kulüp için tek bir JSON dosyası — güncel kadro, teknik direktör ve sistem,
   2025/26 istatistikleri, artılar/eksiler, **pozisyonel ihtiyaçlar** (öncelik, profil, bütçe), pozisyon
   bazlı performans kıyas değerleri, kulüp kimliği (prensipler, karakter, sahiplik, kamuya açık kurumsal
   bağlam, dil, maaş yapısı, transfer politikası). Her oyuncu için: istatistikler, oyun stili etiketleri,
   kamuya açık kaynaklı mental profil, sakatlık geçmişi, saha dışı bağlam. **Her dosya `sources` ve
   `as_of` taşır; doğrulanamayan değer `null` bırakılır, asla uydurulmaz.** Şema: `data/SCHEMA.md`.
2. **Eşleştirme motoru** (`matching/`): deterministik, açıklanabilir, çift yönlü. Bir oyuncu × kulüp çifti
   için 8 boyutta 0–100 puan üretir ve her boyutun gerekçesini yazar:

   | Boyut | Ağırlık | Ne ölçer |
   |---|---|---|
   | Pozisyonel ihtiyaç | 0.20 | Kulüp o pozisyonda gerçekten oyuncu arıyor mu; profil (yaş aralığı, ayak, anahtar kelimeler) tutuyor mu |
   | İstatistiksel uyum | 0.20 | Oyuncunun /90 üretimi kulübün pozisyon kıyas değerine ve mevcut ilk 11'ine göre nerede; lig gücü iskontosu |
   | Taktik/sistem uyumu | 0.15 | Stil etiketleri ↔ hocanın sistemi ve kulüp oyun anlayışı; "zayıf olduğu" alan kulübün istediğiyle çakışıyor mu |
   | Finansal fizibilite | 0.15 | Bonservis ve maaş ↔ ihtiyaç bütçesi / kulübün harcama kademesi; sözleşme kaldıraç etkisi |
   | Yaş & sözleşme | 0.05 | Yaş eğrisi ↔ kulübün transfer politikası (ör. U25 yeniden satış); sözleşme bitiş yılı |
   | Sakatlık riski | 0.08 | Belgelenmiş sakatlık günleri, yapısal sakatlıklar, kulübün sakatlık yönetimi itibarı |
   | Mentalite & kimya | 0.10 | Kamuya açık mental profil ↔ kulüp karakteri (baskı seviyesi, gelişim kulübü, liderlik ihtiyacı) |
   | Kültürel adaptasyon | 0.07 | **Hofstede 5-D** mesafesi (Kogut-Singh, %60) + ortak dil (%25) + lig aşinalığı (%15). Kamuya açık demeçler **puanlanmaz**, insan incelemesine gider |

   Siyasi/sosyal bağlam ve saha dışı bilgiler **sayısal puana girmez**; `human_review` listesine
   düşer. Yumuşak sinyallerin toplam ağırlığı sınırlıdır: tek başına bir eşleşmeyi çeviremez.
   Motor ayrıca **karşılıklı eşleşme** üretir: oyuncu kulübün ilk N adayı içinde *ve* kulüp oyuncunun
   ilk N kulübü içindeyse — menajerin gerçekten telefon açacağı liste budur.
3. **Backend** (`api.py`, FastAPI) ve **CLI** (`python -m football_agent`).
4. **LLM katmanı** (`llm.py`, opsiyonel): Claude puanı **üretmez**; puanı anlatır, sorgular ve
   müzakereci için memo taslağı yazar. `ANTHROPIC_API_KEY` yoksa deterministik özet döner.
5. **Komisyon modeli** (`commission.py`): %2 (bonservis + sözleşme süresi × brüt maaş) vs piyasa %10.
   FIFA Futbol Menajerliği Yönetmeliği tavanlarının (%3/%5 maaş, %10 bonservis) içinde kalır.

### Kültürel uyum: Hofstede modeli (`culture.py`, `data/hofstede.json`)

Geert Hofstede'nin ulusal kültür boyutları kullanılır. Varsayılan **klasik 5-D** set: Güç Mesafesi (PDI),
Bireycilik (IDV), Erillik (MAS), Belirsizlikten Kaçınma (UAI), Uzun Vadeli Yönelim (LTO). 2010'da eklenen
altıncı boyut Hoşgörü (IVR) veri dosyasında mevcuttur; `HOFSTEDE_DIMENSIONS` ile açılabilir.

* **Mesafe**: Kogut & Singh (1988) bileşik endeksi — boyut farklarının karesi, o boyutun ülkeler arası
  varyansına bölünür ve ortalaması alınır. Uluslararası işletme literatürünün standart ölçüsüdür.
* **Oyuncunun aşina olduğu kültürler**: uyruk ülkeleri + şu an oynadığı ligin ülkesi. Hedef kulübün
  ülkesine en yakın aşina kültür esas alınır (Eredivisie'de 3 yıl oynamış bir Brezilyalı için Hollanda da sayılır).
* **Puan**: mesafe 0 → 100, ~1 → 78, ~2 → 56, ≥4.3 → taban 5. Her boyut farkı futbol diline çevrilir
  (ör. "PDI +31: oyuncunun aşina olduğu kültür daha hiyerarşik; daha yatay hoca-oyuncu ilişkisi bekleyin").
* **Veri**: Hofstede'nin 2015 "dimension data matrix"i. geerthofstede.com bu ortamda engelli olduğu için
  plotly/datasets aynasından alındı; sütun düzeni ve çapa değerler (TUR 66/37/45/85/46/49, GBR 35/89/66/35/51/69)
  yayımlanmış matrisle eşleşiyor. ENG/SCO/WAL = GBR. Hofstede'nin örneklemediği ülkeler (Senegal, Fildişi,
  Kamerun, Azerbaycan'ın temel dört boyutu) için **puan üretilmez**; bölgesel "Arap ülkeleri" / "Batı Afrika"
  vektörleri yalnızca Hofstede'nin o örnekleme dahil ettiği ülkeler için vekil olarak kullanılır.
* Bilinen eleştiriler (ülke = kültür varsayımı, 1970'lerin IBM örneklemi, bireye genelleme) nedeniyle bu
  boyutun ağırlığı 0.07'de tutulur ve çıktı "brifing verilecek fark" olarak sunulur, "uyumsuzluk hükmü" olarak değil.

```bash
uv run python -m football_agent culture TUR ENG      # mesafe + boyut bazlı okuma
curl 'localhost:8090/culture/distance?from_country=BRA&to_country=ESP'
```

## Hızlı başlangıç

```bash
uv sync --extra dev                       # veya: pip install -e ".[dev]"
uv run python -m football_agent status    # hangi kulüp ne kadar doğrulanmış?
uv run python -m football_agent validate  # şema kontrolü
uv run python -m football_agent clubs
uv run python -m football_agent report --club arsenal
uv run python -m football_agent --demo candidates aston_villa --position CB
uv run python -m football_agent --demo clubs-for demo_lw_kaan_demirel
uv run python -m football_agent --demo match demo_lw_kaan_demirel arsenal
uv run python -m football_agent --demo mutual --min-total 60
uv run python -m football_agent commission 35 4 --years 4
uv run python -m football_agent serve      # http://127.0.0.1:8090/docs
uv run pytest tests/test_football_agent.py
```

API uçları: `/clubs`, `/clubs/{id}`, `/clubs/{id}/recommendations`, `/clubs/{id}/candidates`,
`/players`, `/players/{id}/clubs`, `/match/{player}/{club}?narrative=true`, `/matches/mutual`,
`/commission`, `/dataset/status`, `/dataset/validate`.
`FOOTBALL_AGENT_INCLUDE_DEMO=1` ile API demo oyuncuları da yükler.

## Veri durumu — dürüst tablo

Araştırma yalnızca web arama özetleriyle yapıldı: egress proxy transfermarkt, fbref, uefa.com, wikipedia ve
kulüp sitelerini engelliyor (WebFetch 403). Buna rağmen:

* **36/36 kulüp** eşleştirmeye uygun (kadro ≥ 15, ihtiyaçlar tanımlı). 30 kulüp `medium` (hoca + 2025/26
  tablosu + kura rakipleri + kadro kaynaklı), 6 kulüp `low` (Stuttgart, Sabah, Slovan, Club Brugge, Real Madrid,
  Viking): eksik alanlar her dosyanın `data_quality.notes` alanında yazılı.
* **39 gerçek oyuncu** hedef havuzunda (`data/players/`); 8 kurgusal demo profili `data/demo_players/` altında
  tutuluyor ve yalnızca `--demo` ile yüklenir. Panel ve dosyalar kurgusal veri içermez.
* Oyuncu–kulüp çelişkileri iki yönlü tarandı ve düzeltildi (Ueda → Lille, Curtis Jones → Inter, Ceballos → Betis,
  Nelson → Feyenoord, Oosterwolde → Roma, Grimaldo → Atlético). Martinelli (Al Hilal, resmi değil) ve Zinchenko
  (serbest) düşük güvende, Arsenal kadrosunda "çözümlenmedi" notuyla duruyor.
* Oyuncu başına 2025/26 dakika ve /90 verileri çoğu kayıtta `null`: kaynaklı bulunamadı. Üretimde lisanslı
  sağlayıcıdan gelmeli; şema buna göre tasarlandı.
* `python -m football_agent status` güncel tabloyu verir; `python -m football_agent dashboard` paneli üretir.

## Etik çerçeve

* Mental, saha dışı ve siyasi/sosyal alanlar **yalnızca kaynaklı kamu kaydı** ile doldurulur; özel hayat
  hakkında spekülasyon yok. Oyuncunun rızası olmadan kamuya açık olmayan veri saklanmaz.
* Bu alanlar motorda ağırlığı sınırlı yumuşak sinyaldir ya da hiç puanlanmaz (insan incelemesi).
* Her puanın gerekçesi vardır; "kara kutu" yoktur. Claude yalnızca anlatır ve itiraz eder.

---

## English summary

`football_agent` is a self-contained Python package (independent of the OSINT tooling in this repo)
implementing an explainable player↔club matching engine for an AI-assisted, 2%-commission player
agency. Pilot dataset: the 36 clubs of the 2026/27 UEFA Champions League league phase — current squad,
coach & system, 2025/26 numbers, strengths/weaknesses, positional needs with budgets, and club identity
(principles, character, ownership, documented institutional context). Scores are deterministic across
eight weighted dimensions, every dimension carries a justification, soft/social signals are weight-capped
or routed to human review rather than scored, and Claude (optional) only narrates and stress-tests.
FastAPI backend + CLI + tests. Run `python -m football_agent status` to see exactly which club files are
source-verified and which are skeletons awaiting research (this session hit the web-search budget and an
egress block on football data sites; see "Veri durumu" above).
