#!/usr/bin/env python3
"""Vox / Johnny Harris style explainer PDF for the Kurtlar Vadisi mapping report."""
import json
import re
import subprocess
import sys
from pathlib import Path

import build_kurtlar_vadisi_pdf as base

HERE = Path(__file__).resolve().parent
OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
OUT_HTML = OUT_DIR / "kurtlar-vadisi-vox-raporu.html"
OUT_PDF = OUT_DIR / "kurtlar-vadisi-vox-raporu.pdf"
FONTS = HERE / "fonts"
GEO = HERE / "geo" / "countries.geojson"

# ------------------------------------------------------------------ identity
YEL = "#FFE500"
BLK = "#0f0f0f"
PAPER = "#f6f3ec"
RED = "#e5322d"
INK = "#1b1b1b"
GREY = "#6b6b6b"
LINE = "#d8d3c6"
MAPSEA = "#161a1f"
MAPLAND = "#3c434b"
DISPLAY = "'Anton', 'DejaVu Sans Condensed', sans-serif"
CAPS = "'Oswald', 'DejaVu Sans Condensed', sans-serif"
SERIF = "'Lora', 'DejaVu Serif', serif"
HAND = "'Caveat', 'DejaVu Sans', cursive"
UI = "'Inter', 'DejaVu Sans', sans-serif"

# re-skin the shared chart helpers
base.NAVY, base.INK, base.RED, base.AMBER, base.GREEN, base.GREY, base.LINE, base.PAPER = BLK, INK, RED, "#c9a400", "#1e8449", GREY, LINE, PAPER
base.MONO, base.SANS = CAPS, UI
base.GRADE_COLORS.update({"Güçlü": "#1e8449", "Orta": "#b58900", "Zayıf": RED, "Yok": GREY, "Tema": "#2f6f9f"})


def grade_badge(cell):
    m = re.search(r"(Güçlü|Orta|Zayıf|Yok|Tema)", cell)
    if not m or len(cell) > 40:
        return base.inline(cell)
    if "Güçlü" in cell:
        return f'<span class="g g-strong">{base.inline(cell)}</span>'
    if "Orta" in cell:
        return f'<span class="g g-mid">{base.inline(cell)}</span>'
    if "Zayıf" in cell:
        return f'<span class="g g-weak">{base.inline(cell)}</span>'
    if "Tema" in cell:
        return f'<span class="g g-theme">{base.inline(cell)}</span>'
    return f'<span class="g g-none">{base.inline(cell)}</span>'


base.grade_badge = grade_badge


# ------------------------------------------------------------------ map
def svg_map():
    data = json.loads(GEO.read_text(encoding="utf-8"))
    lon0, lon1, lat0, lat1 = 19.0, 50.5, 27.5, 46.0
    W, H = 1040, 640
    sx = W / (lon1 - lon0)
    sy = H / (lat1 - lat0)
    px = lambda lon: (lon - lon0) * sx
    py = lambda lat: (lat1 - lat) * sy

    def ring_path(ring):
        pts = [(px(x), py(y)) for x, y in ring]
        return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"

    paths = []
    for f in data["features"]:
        name = f["properties"].get("ADMIN") or f["properties"].get("NAME")
        geom = f["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        d = []
        for poly in polys:
            for ring in poly:
                xs = [p[0] for p in ring]
                ys = [p[1] for p in ring]
                if max(xs) < lon0 - 2 or min(xs) > lon1 + 2 or max(ys) < lat0 - 2 or min(ys) > lat1 + 2:
                    continue
                d.append(ring_path(ring))
        if d:
            fill = YEL if name == "Turkey" else MAPLAND
            paths.append(f'<path d="{" ".join(d)}" fill="{fill}" stroke="{MAPSEA}" stroke-width="1"/>')

    pins = [  # lon, lat, title, note, dx, dy
        (45.44, 35.56, "SÜLEYMANİYE", "Çuval olayı, 4 Tem 2003 → KV Irak filminin açılışı", -20, -110),
        (35.5, 33.89, "BEYRUT", "Hariri suikastı, Şub 2005 → b.88-90'da 'engellenen' suikast", -170, 30),
        (34.47, 31.5, "GAZZE", "Mavi Marmara, May 2010 → Filistin filmi yeniden yazıldı", -120, 60),
        (28.98, 41.01, "İSTANBUL", "Dizinin evreni; Dikilitaş (b.96), Yedikule (b.86)", 30, -70),
        (28.25, 41.07, "SİLİVRİ", "Ergenekon davası; Kozinoğlu ölümü 12 Kas 2011", -20, -115),
        (32.85, 39.93, "ANKARA", "Susurluk raporu, RTÜK kararları", 40, 95),
        (37.16, 36.2, "HALEP / ÖSO", "b.171 (2012): Polat ÖSO'ya silah verir", 90, 10),
        (35.7, 34.0, "BEKAA", "Gladio filmi: Öcalan, Bekaa kampları", 150, 45),
    ]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="{UI}">']
    s.append(f'<rect width="{W}" height="{H}" fill="{MAPSEA}"/>')
    s.extend(paths)
    # graticule
    for lon in range(20, 51, 5):
        s.append(f'<line x1="{px(lon)}" y1="0" x2="{px(lon)}" y2="{H}" stroke="white" stroke-opacity="0.06"/>')
    for lat in range(30, 46, 5):
        s.append(f'<line x1="0" y1="{py(lat)}" x2="{W}" y2="{py(lat)}" stroke="white" stroke-opacity="0.06"/>')
    for lon, lat, title, note, dx, dy in pins:
        X, Y = px(lon), py(lat)
        s.append(f'<circle cx="{X}" cy="{Y}" r="9" fill="{RED}" fill-opacity="0.25"/>')
        s.append(f'<circle cx="{X}" cy="{Y}" r="4" fill="{RED}" stroke="white" stroke-width="1.2"/>')
        s.append(f'<line x1="{X}" y1="{Y}" x2="{X+dx}" y2="{Y+dy}" stroke="white" stroke-width="1" stroke-opacity="0.8"/>')
        anchor = "start" if dx >= 0 else "end"
        tx = X + dx + (6 if dx >= 0 else -6)
        tw = max(len(title) * 9, len(note) * 5.6) + 12
        bx = tx - 6 if dx >= 0 else tx - tw + 6
        s.append(f'<rect x="{bx}" y="{Y+dy-18}" width="{tw}" height="36" fill="{MAPSEA}" fill-opacity="0.85" rx="2"/>')
        s.append(f'<text x="{tx}" y="{Y+dy-4}" font-size="15" font-family="{CAPS}" font-weight="700" fill="{YEL}" text-anchor="{anchor}" letter-spacing="1">{base.esc(title)}</text>')
        s.append(f'<text x="{tx}" y="{Y+dy+12}" font-size="11" fill="white" text-anchor="{anchor}">{base.esc(note)}</text>')
    s.append(f'<rect x="{W-350}" y="20" width="330" height="44" fill="{BLK}" stroke="{YEL}" stroke-width="1"/>')
    s.append(f'<text x="{W-340}" y="38" font-size="12" font-family="{CAPS}" fill="{YEL}" font-weight="700" letter-spacing="1">HARİTA DIŞI · LEEUWARDEN, HOLLANDA</text>')
    s.append(f'<text x="{W-340}" y="55" font-size="11" fill="white">Halil Havar: helikopterle kaçırılma (1991) → Halo Dayı, b.61-62</text>')
    s.append(f'<text x="24" y="{H-22}" font-size="22" font-family="{HAND}" fill="{YEL}">Dizinin coğrafyası gerçek haberlerin coğrafyasıyla birebir örtüşüyor.</text>')
    s.append(f'<text x="{W-20}" y="{H-14}" font-size="10" fill="white" fill-opacity="0.6" text-anchor="end">Natural Earth 1:50m · eşdikdörtgen izdüşüm</text>')
    s.append("</svg>")
    return "".join(s)


# ------------------------------------------------------------------ CSS
def font_face(name, file):
    return f"@font-face {{ font-family:'{name}'; src:url('{(FONTS / file).as_uri()}') format('truetype'); }}"


CSS = "\n".join([
    font_face("Anton", "Anton-Regular.ttf"),
    font_face("Oswald", "Oswald[wght].ttf"),
    font_face("Lora", "Lora[wght].ttf"),
    font_face("Caveat", "Caveat[wght].ttf"),
    font_face("Inter", "Inter[opsz,wght].ttf"),
]) + f"""
@page {{ size: A4; }}
* {{ box-sizing:border-box; }}
html, body {{ margin:0; padding:0; background:white; color:{INK}; font-family:{SERIF}; font-size:10pt; line-height:1.45; }}
a {{ color:{INK}; text-decoration:none; word-break:break-all; }}
code {{ font-family:{UI}; font-size:8.5pt; }}
mark {{ background:{YEL}; color:{BLK}; padding:0 2px; }}

/* cover */
.cover {{ page-break-after:always; background:{BLK}; color:white; margin:-22mm -16mm -20mm; padding:26mm 16mm 18mm; height:297mm; position:relative; }}
.cover .kicker {{ font-family:{CAPS}; font-weight:500; letter-spacing:.35em; font-size:10pt; color:{YEL}; text-transform:uppercase; }}
.cover h1 {{ font-family:{DISPLAY}; font-size:74pt; line-height:.92; margin:10mm 0 4mm; color:white; letter-spacing:.01em; }}
.cover h1 span {{ color:{YEL}; }}
.cover .deck {{ font-family:{SERIF}; font-size:15pt; line-height:1.35; max-width:150mm; color:#e8e6df; margin-top:6mm; }}
.cover .hand {{ font-family:{HAND}; font-size:20pt; color:{YEL}; position:absolute; right:16mm; top:196mm; width:78mm; transform:rotate(-4deg); line-height:1.1; }}
.cover .hand:before {{ content:"↘"; display:block; font-family:{UI}; font-size:20pt; }}
.stats {{ display:flex; gap:6mm; margin-top:16mm; }}
.stat {{ flex:1; border-top:2pt solid {YEL}; padding-top:3mm; }}
.stat .n {{ font-family:{DISPLAY}; font-size:34pt; line-height:1; color:{YEL}; }}
.stat .l {{ font-family:{CAPS}; font-size:8.5pt; letter-spacing:.15em; text-transform:uppercase; color:#cfcbbf; margin-top:1.5mm; }}
.cover .foot {{ position:absolute; left:16mm; right:16mm; bottom:14mm; display:flex; justify-content:space-between; font-family:{CAPS}; font-size:8.5pt; letter-spacing:.2em; color:#9c9890; text-transform:uppercase; }}

/* chapter openers */
.chap {{ break-inside:avoid; margin:8mm -16mm 8mm; padding:12mm 16mm 9mm; background:{BLK}; color:white; position:relative; }}
.chap.pb {{ break-before:page; margin-top:0; }}
.chap .num {{ font-family:{DISPLAY}; font-size:64pt; line-height:.85; color:{YEL}; }}
.chap h2 {{ font-family:{DISPLAY}; font-size:26pt; line-height:1; margin:6mm 0 3mm; color:white; border:0; padding:0; letter-spacing:.01em; }}
.chap .deck {{ font-family:{SERIF}; font-size:12pt; color:#dcd8cc; max-width:150mm; line-height:1.35; }}
.chap .tag {{ position:absolute; right:16mm; top:16mm; font-family:{CAPS}; font-size:8.5pt; letter-spacing:.3em; color:{YEL}; text-transform:uppercase; }}

h2.plain {{ font-family:{DISPLAY}; font-size:22pt; margin:8mm 0 3mm; line-height:1; color:{BLK}; }}
h2.plain .secno {{ display:inline-block; background:{YEL}; color:{BLK}; font-family:{CAPS}; font-size:10pt; padding:2pt 6pt; margin-right:6pt; vertical-align:middle; letter-spacing:.15em; }}
h3 {{ font-family:{CAPS}; font-weight:600; font-size:11.5pt; letter-spacing:.06em; text-transform:uppercase; margin:6mm 0 2mm; page-break-after:avoid; border-left:4pt solid {YEL}; padding-left:6pt; }}
p {{ margin:0 0 2.6mm; }}
p.lede {{ font-size:12pt; line-height:1.4; }}
table {{ width:100%; border-collapse:collapse; margin:2mm 0 4mm; font-size:8.1pt; font-family:{UI}; }}
thead {{ display:table-header-group; }}
tr {{ page-break-inside:avoid; }}
th {{ background:{BLK}; color:white; text-align:left; padding:3.5pt 4pt; font-family:{CAPS}; font-weight:500; font-size:8pt; letter-spacing:.08em; text-transform:uppercase; }}
td {{ border-bottom:.6pt solid {LINE}; padding:3.5pt 4pt; vertical-align:top; }}
tbody tr:nth-child(even) td {{ background:{PAPER}; }}
.g {{ font-family:{CAPS}; font-size:7.6pt; letter-spacing:.06em; padding:1pt 4pt; white-space:nowrap; font-weight:600; text-transform:uppercase; }}
.g-strong {{ background:{YEL}; color:{BLK}; }}
.g-mid {{ border:1.2pt solid {BLK}; color:{BLK}; }}
.g-weak {{ color:{GREY}; border:1pt solid {LINE}; }}
.g-none {{ color:{GREY}; }}
.g-theme {{ border:1.2pt solid #2f6f9f; color:#2f6f9f; }}
.callout {{ background:{YEL}; color:{BLK}; padding:4mm 5mm; margin:3mm 0 5mm; font-size:9.5pt; }}
.callout-tag {{ font-family:{CAPS}; font-size:8pt; letter-spacing:.3em; text-transform:uppercase; margin-bottom:1.5mm; font-weight:600; }}
.fig {{ margin:3mm 0 5mm; page-break-inside:avoid; }}
.fig svg {{ width:100%; height:auto; display:block; }}
.fig.map {{ margin:3mm 0 5mm; }}
.fig.map svg {{ width:100%; }}
.figcap {{ font-family:{CAPS}; font-size:8pt; letter-spacing:.15em; text-transform:uppercase; color:{GREY}; margin:1.5mm 0 0; }}
.note {{ font-family:{HAND}; font-size:15pt; color:{RED}; line-height:1.1; margin:1mm 0 4mm; padding-left:8mm; position:relative; page-break-inside:avoid; }}
.note:before {{ content:"↳"; position:absolute; left:0; top:0; font-family:{UI}; font-size:13pt; }}
.quote {{ border-left:5pt solid {YEL}; padding:2mm 0 2mm 6mm; margin:4mm 0 5mm; font-family:{SERIF}; font-style:italic; font-size:13pt; line-height:1.3; page-break-inside:avoid; }}
.quote .who {{ display:block; font-style:normal; font-family:{CAPS}; font-size:8.5pt; letter-spacing:.2em; text-transform:uppercase; color:{GREY}; margin-top:2mm; }}
.grid2 {{ display:flex; gap:6mm; }}
.grid2 > * {{ flex:1; }}
ul, ol {{ margin:0 0 2.5mm; padding-left:5mm; }}
li {{ margin-bottom:1.2pt; }}
.src {{ font-size:7.4pt; font-family:{UI}; columns:2; column-gap:6mm; }}
.src li {{ margin-bottom:0; break-inside:avoid; }}
.legend {{ display:flex; gap:5mm; font-family:{CAPS}; font-size:8pt; letter-spacing:.06em; text-transform:uppercase; margin:2mm 0 3mm; }}
"""

CHAPTERS = {
    "01": ("Yöntem", "Bir dizi karakterinin 'gerçekte kim olduğu' nasıl ölçülür? Üç soru sorduk: iddiayı kim kurdu, ne örtüşüyor, yapımcı ne dedi."),
    "02": ("Kronoloji", "2003'te Show TV'de başlayan hikâye, 2017'de bir 15 Temmuz filmiyle bitti. Arada ne yayınlandıysa, aynı ay manşetlerde de vardı."),
    "03": ("Kim kimdir?", "Susurluk ağı ekrana taşındı mı? İsimlerden çok, ilişkilerin kopyalanmış olması dikkat çekiyor."),
    "04": ("97 bölüm, tek tek", "İlk dizinin her bölümünü gerçek olaylarla yan yana koyduk. Çoğu bölümde paralel yok; olduğunda ise çok belirgin."),
    "05": ("Terör: iki bölümlük dizi", "2007'de bir bölüm yayınlandı, 16.597 şikâyet geldi, dizi kaldırıldı."),
    "06": ("Pusu: gündemi takip eden dizi", "300 bölüm boyunca senaryo, Ergenekon'dan 17-25 Aralık'a kadar Türkiye'nin gündemini iki hafta gecikmeyle yeniden anlattı."),
    "07": ("Filmler", "Dört film, dört gerçek olay. Burada gizli esinlenme yok; yapımcılar kaynağı saklamıyor."),
    "08": ("Bulgular", "Üç katman: kişi kopyalama, gündem takibi, açık uyarlama. Ve sistematik bir ayrışma."),
    "09": ("Boşluklar", "Neyi bulamadık, neyi doğrulayamadık."),
    "10": ("Kaynaklar", "Bu rapordaki her iddia bir bağlantıya dayanıyor."),
}

QUOTES = {
    "01": ("Hayır, hiç ilgisi yok.", "Osman Sınav, 'Polat Alemdar Abdullah Çatlı mı?' sorusuna · Habertürk, 2014"),
    "03": ("Bana 'yapar mısın' dediler, ben 'Susurluk'u yapalım' dedim.", "Soner Yalçın, konsept danışmanı · Habervitrini, 2004"),
    "06": ("İddianame Kurtlar Vadisi'yle kelimesi kelimesine örtüşüyor.", "Muzaffer Tekin, Ergenekon sanığı · Silivri, Kasım 2008"),
    "08": ("Ergenekon davasının her karesini anlattık, sonra bir baktık ki Türkiye'de böyle bir şey varmış.", "Pusu senaristleri · Medyatava, 2012"),
}

NOTES = {
    "Halil Havar": "1991, Hollanda: gerçek helikopter kaçırma. Dizide ülke değişmiş, olay aynı.",
    "Kaşif Kozinoğlu": "Dizideki ölüm: 10 Kasım. Gerçek ölüm: 12 Kasım. İki gün.",
    "Veli Küçük": "Gözaltı 22 Ocak → karakter ekranda 7 Şubat. 16 gün.",
    "Refik Hariri": "Gerçekte suikast başarılı oldu; dizide Polat engelledi.",
    "Uğur Çakıcı": "Gerçekte damat, kayınpederin kızını öldürttü. Dizide kayınpederin kızı, damadın kız kardeşini vuruyor.",
}


PB = {"03", "04", "06", "08", "10"}


def chapter(num, title, deck):
    return f'<div class="chap{" pb" if num in PB else ""}"><div class="tag">Bölüm {num} / 10</div><div class="num">{num}</div><h2>{base.esc(title)}</h2><div class="deck">{base.esc(deck)}</div></div>'


def build():
    md = base.MD.read_text(encoding="utf-8")
    body = base.md_to_html(md)

    # chapter openers replace h2s
    def rep(m):
        num = m.group(1)
        t, d = CHAPTERS[num]
        q = ""
        if num in QUOTES:
            q = f'<div class="quote">“{base.esc(QUOTES[num][0])}”<span class="who">{base.esc(QUOTES[num][1])}</span></div>'
        extra = ""
        if num == "02":
            extra = f'<div class="fig map">{svg_map()}</div><div class="figcap">Şekil 0 · Olay haritası. Sarı: Türkiye. Kırmızı: dizinin ve haberlerin kesiştiği yerler.</div>'
        return chapter(num, t, d) + q + extra
    body = re.sub(r'<h2><span class="secno">(\d\d)</span>.*?</h2>', rep, body)

    # figures
    body = body.replace("{{TIMELINE}}", f'<div class="fig">{base.svg_timeline()}</div><div class="figcap">Şekil 1 · Üstte dizi, altta manşetler. Aynı yıl, çoğu zaman aynı ay.</div>')
    body = body.replace("{{NETWORK}}", f'<div class="fig">{base.svg_network()}</div><div class="figcap">Şekil 2 · Kesikli çizgi = doğrulanmamış iddia. Yan kavisler aile bağları.</div>')
    body = body.replace('<div class="chap"><div class="tag">Bölüm 04', f'<div class="fig">{base.svg_grades()}</div><div class="figcap">Şekil 3 · İddiaların çoğu zayıf. Güçlü olanlar azınlıkta ama çok belirgin.</div><div class="fig">{base.svg_episodes()}</div><div class="figcap">Şekil 4 · 97 bölümde paralel yoğunluğu. Boş kutu = kaynak yok.</div><div class="chap"><div class="tag">Bölüm 04', 1)
    body = re.sub(r'(Bölüm 06 / 10.*?</div>\s*(?:<div class="quote">.*?</div>)?\s*<p>.*?</p>)', lambda m: m.group(1) + f'<div class="fig">{base.svg_pusu()}</div><div class="figcap">Şekil 5 · Beş kanal, on sezon, yedi gerçek olay bağı.</div>', body, count=1, flags=re.S)
    # map after chapter 02 deck paragraph

    # handwritten notes after rows that mention key names (first occurrence, inside table -> insert after the table)
    for key, note in NOTES.items():
        idx = body.find(key)
        if idx == -1:
            continue
        end = body.find("</table>", idx)
        if end == -1:
            continue
        end += len("</table>")
        body = body[:end] + f'<div class="note">{base.esc(note)}</div>' + body[end:]

    # highlighter on key phrases in first summary paragraph
    for phrase in ["neredeyse hiçbiri yapımcılar tarafından doğrulanmamıştır", "Susurluk'u yapalım"]:
        body = body.replace(phrase, f"<mark>{phrase}</mark>", 1)
    # sources compact
    body = re.sub(r'(Bölüm 10 / 10.*)$', lambda m: m.group(1).replace("<ul>", '<ul class="src">'), body, flags=re.S)
    # section-title inside bodies (h2 without chapter) none left; keep h3

    cover = f"""
<div class="cover">
  <div class="kicker">Açık kaynak araştırma · Eylül 2026</div>
  <h1>KURTLAR<br>VADİSİ<br><span>GERÇEK MİYDİ?</span></h1>
  <div class="deck">399 bölüm ve dört film boyunca Türkiye'nin en çok izlenen dizisi, derin devleti anlattı. Basın yıllarca "bu karakter aslında şu" dedi. Yapımcılar hep reddetti. Biz iddiaları tek tek kaynağına götürdük.</div>
  <div class="hand">Çakır'ın kayınpederi, Çakıcı'nın kayınpederiyle aynı adamı mı anlatıyor?</div>
  <div class="stats">
    <div class="stat"><div class="n">97</div><div class="l">bölüm · Kurtlar Vadisi</div></div>
    <div class="stat"><div class="n">300</div><div class="l">bölüm · Pusu</div></div>
    <div class="stat"><div class="n">4</div><div class="l">sinema filmi</div></div>
    <div class="stat"><div class="n">40+</div><div class="l">karakter eşleştirmesi</div></div>
    <div class="stat"><div class="n">0</div><div class="l">yapımcı doğrulaması</div></div>
  </div>
  <div class="foot"><span>OSINT-KV-2026-001</span><span>Doğrulanmamış iddialar içerir</span><span>Sınırsız dağıtım</span></div>
</div>
"""
    page = f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8"><title>Kurtlar Vadisi Gerçek miydi?</title><style>{CSS}</style></head><body>
{cover}
{body}
</body></html>"""
    OUT_HTML.write_text(page, encoding="utf-8")
    js = OUT_DIR / "print_vox.js"
    js.write_text(PRINT_JS.replace("__HTML__", OUT_HTML.as_uri()).replace("__PDF__", str(OUT_PDF)).replace("__CHROME__", base.CHROME).replace("__FONT__", (FONTS / "Oswald[wght].ttf").as_uri()))
    subprocess.run(["node", str(js)], check=True, timeout=300, env={**__import__("os").environ, "NODE_PATH": "/opt/node22/lib/node_modules"})
    print("wrote", OUT_PDF)


PRINT_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '__CHROME__', args: ['--no-sandbox', '--allow-file-access-from-files'] });
  const page = await browser.newPage();
  await page.goto('__HTML__', { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const caps = "font-family:'DejaVu Sans Condensed','DejaVu Sans',sans-serif;";
  const header = `<div style="width:100%;padding:7mm 16mm 0;${caps}font-size:7px;letter-spacing:.25em;text-transform:uppercase;color:#6b6b6b;display:flex;justify-content:space-between;border-bottom:1px solid #0f0f0f;padding-bottom:3px;"><span style="color:#0f0f0f;font-weight:bold;">Kurtlar Vadisi gerçek miydi?</span><span>Açık kaynak araştırma · Eylül 2026</span></div>`;
  const footer = `<div style="width:100%;padding:0 16mm 6mm;${caps}font-size:7px;letter-spacing:.2em;text-transform:uppercase;color:#6b6b6b;display:flex;justify-content:space-between;border-top:1px solid #d8d3c6;padding-top:3px;"><span>Doğrulanmamış iddialar içerir · kaynaklar: Bölüm 10</span><span style="background:#FFE500;color:#0f0f0f;padding:1px 6px;font-weight:bold;"><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`;
  await page.pdf({ path: '__PDF__', format: 'A4', printBackground: true, displayHeaderFooter: true,
    headerTemplate: header, footerTemplate: footer,
    margin: { top: '22mm', bottom: '20mm', left: '16mm', right: '16mm' } });
  await browser.close();
})();
"""

if __name__ == "__main__":
    build()
