#!/usr/bin/env python3
"""Build an intelligence-report styled PDF from the Kurtlar Vadisi markdown report."""
import html
import re
import subprocess
import sys
from pathlib import Path

MD = Path("/home/user/OpenOSINT/docs/research/kurtlar-vadisi-gercek-hayat-semasi.md")
OUT_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
OUT_HTML = OUT_DIR / "kurtlar-vadisi-istihbarat-raporu.html"
OUT_PDF = OUT_DIR / "kurtlar-vadisi-istihbarat-raporu.pdf"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

# ---------------------------------------------------------------- colours
NAVY = "#0b1c2c"
INK = "#101418"
RED = "#b3261e"
AMBER = "#c77d00"
GREEN = "#2e7d32"
GREY = "#6b7280"
LINE = "#c9ced6"
PAPER = "#f7f6f2"
MONO = "'DejaVu Sans Mono', 'Liberation Mono', monospace"
SANS = "'DejaVu Sans', 'Liberation Sans', sans-serif"

GRADE_COLORS = {"Güçlü": GREEN, "Orta": AMBER, "Zayıf": RED, "Yok": GREY, "Tema": "#4a6fa5"}


def esc(s):
    return html.escape(s, quote=False)


# ---------------------------------------------------------------- inline md
def inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"(?<![\"'>])(https?://[^\s<]+)", r'<a href="\1">\1</a>', s)
    return s


def grade_badge(cell):
    m = re.search(r"(Güçlü|Orta|Zayıf|Yok|Tema)", cell)
    if not m or len(cell) > 40:
        return inline(cell)
    key = m.group(1)
    if "Güçlü" in cell:
        key = "Güçlü"
    elif "Orta" in cell:
        key = "Orta"
    col = GRADE_COLORS[key]
    return f'<span class="grade" style="border-color:{col};color:{col}">{inline(cell)}</span>'


def table_html(lines):
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
    head, body = rows[0], rows[2:]
    grade_idx = [i for i, h in enumerate(head) if h.strip() in ("Derece",)]
    out = ['<table><thead><tr>' + "".join(f"<th>{inline(h)}</th>" for h in head) + "</tr></thead><tbody>"]
    for r in body:
        cells = []
        for i, c in enumerate(r):
            cells.append(f"<td>{grade_badge(c) if i in grade_idx else inline(c)}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def md_to_html(md):
    """Very small markdown subset converter; mermaid blocks become placeholders."""
    lines = md.splitlines()
    out, i, n = [], 0, len(lines)
    sec_no = 0
    while i < n:
        ln = lines[i]
        if ln.startswith("```mermaid"):
            while i < n and not lines[i].startswith("```"[0] * 3 + "") or lines[i].startswith("```mermaid"):
                i += 1
                if i < n and lines[i].strip() == "```":
                    break
            i += 1
            out.append("{{TIMELINE}}" if "{{TIMELINE}}" not in "".join(out) else "{{NETWORK}}")
            continue
        if ln.startswith("# "):
            i += 1
            continue  # title handled by cover
        if ln.startswith("## "):
            sec_no += 1
            title = re.sub(r"^\d+\.\s*", "", ln[3:])
            out.append(f'<h2><span class="secno">{sec_no:02d}</span>{inline(title)}</h2>')
            i += 1
            continue
        if ln.startswith("### "):
            title = re.sub(r"^\d+\.\d+\s*", "", ln[4:])
            out.append(f"<h3>{inline(title)}</h3>")
            i += 1
            continue
        if ln.startswith("|"):
            j = i
            while j < n and lines[j].startswith("|"):
                j += 1
            out.append(table_html(lines[i:j]))
            i = j
            continue
        if ln.startswith("> "):
            j = i
            buf = []
            while j < n and lines[j].startswith(">"):
                buf.append(lines[j][1:].strip())
                j += 1
            out.append('<div class="callout"><div class="callout-tag">UYARI</div>' + inline(" ".join(buf)) + "</div>")
            i = j
            continue
        if re.match(r"^(\d+\.|-)\s", ln):
            j = i
            items = []
            ordered = ln[0].isdigit()
            while j < n and re.match(r"^(\d+\.|-)\s", lines[j]):
                items.append(re.sub(r"^(\d+\.|-)\s", "", lines[j]))
                j += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            i = j
            continue
        if ln.strip() == "---":
            i += 1
            continue
        if ln.strip() == "":
            i += 1
            continue
        # paragraph
        j = i
        buf = []
        while j < n and lines[j].strip() and not lines[j].startswith(("|", "#", ">", "```", "- ")) and not re.match(r"^\d+\.\s", lines[j]):
            buf.append(lines[j].strip())
            j += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
        i = j
    return "\n".join(out)


# ---------------------------------------------------------------- SVG: timeline
def svg_timeline():
    years = list(range(2003, 2018))
    W, H = 1040, 420
    x0, x1 = 60, W - 80
    sx = (x1 - x0) / (years[-1] - years[0])
    yr = lambda y: x0 + (y - years[0]) * sx
    mid = 215
    dizi = [  # (year_frac, label)
        (2003.04, "KV başlar (15 Oca)"),
        (2004.27, "Çakır ölür (b.45)"),
        (2005.78, "Lübnan arkı (b.88-90)"),
        (2005.99, "KV final (b.97)"),
        (2006.09, "Irak filmi"),
        (2007.1, "Terör kaldırılır"),
        (2007.3, "Pusu başlar"),
        (2008.1, "İskender Büyük (b.25)"),
        (2009.88, "Gladio filmi"),
        (2010.05, "Mossad bölümü"),
        (2011.07, "Filistin filmi"),
        (2011.86, "Kaşifoğlu ölür (b.139)"),
        (2012.89, "ÖSO bölümü (b.171)"),
        (2014.2, "Paralel yapı (b.218)"),
        (2016.45, "Pusu final (b.300)"),
        (2017.74, "Vatan filmi"),
    ]
    real = [
        (2003.22, "Irak işgali"),
        (2003.51, "Çuval olayı"),
        (2004.45, "DGM'ler kaldırılır"),
        (2005.12, "Hariri suikastı"),
        (2007.05, "Hrant Dink"),
        (2007.45, "Ergenekon op."),
        (2008.06, "Veli Küçük gözaltı"),
        (2009.6, "Kürt açılımı"),
        (2010.05, "İsrail notası"),
        (2010.41, "Mavi Marmara"),
        (2011.25, "Suriye iç savaşı"),
        (2011.87, "Kozinoğlu ölür"),
        (2013.45, "Gezi"),
        (2013.96, "17-25 Aralık"),
        (2016.54, "15 Temmuz"),
    ]
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="{SANS}">']
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    s.append(f'<text x="{x0}" y="26" font-size="12" font-family="{MONO}" fill="{GREY}">ŞEKİL 1 · YAYIN VE GERÇEK OLAY KRONOLOJİSİ (2003–2017)</text>')
    s.append(f'<line x1="{x0}" y1="{mid}" x2="{x1}" y2="{mid}" stroke="{INK}" stroke-width="2"/>')
    for y in years:
        X = yr(y)
        s.append(f'<line x1="{X}" y1="{mid-6}" x2="{X}" y2="{mid+6}" stroke="{INK}"/>')
        s.append(f'<text x="{X}" y="{mid+22}" font-size="11" text-anchor="middle" font-family="{MONO}" fill="{INK}">{y}</text>')
    s.append(f'<text x="{x0-8}" y="70" font-size="11" font-family="{MONO}" fill="{NAVY}" text-anchor="start" transform="rotate(-90 {x0-8},70)" ></text>')
    s.append(f'<text x="{x0}" y="52" font-size="11" font-family="{MONO}" fill="{NAVY}" font-weight="bold">▲ DİZİ / FİLM</text>')
    s.append(f'<text x="{x0}" y="{H-8}" font-size="11" font-family="{MONO}" fill="{RED}" font-weight="bold">▼ GERÇEK OLAYLAR</text>')

    def stack(items, up):
        last_x = -999
        lvl = 0
        for k, (yf, lab) in enumerate(items):
            X = yr(yf)
            lvl = (lvl + 1) % 4 if X - last_x < 95 else 0
            last_x = X
            L = 34 + lvl * 32
            Y = mid - L if up else mid + L + 14
            col = NAVY if up else RED
            s.append(f'<line x1="{X}" y1="{mid}" x2="{X}" y2="{Y + (4 if up else -12)}" stroke="{col}" stroke-width="1" stroke-dasharray="2,2"/>')
            s.append(f'<circle cx="{X}" cy="{mid}" r="4" fill="{col}"/>')
            tw = len(lab) * 5.9 + 12
            s.append(f'<rect x="{X - tw/2}" y="{Y - 11}" width="{tw}" height="15" rx="2" fill="white" stroke="{col}" stroke-width="0.8"/>')
            s.append(f'<text x="{X}" y="{Y}" font-size="9.5" text-anchor="middle" fill="{col}">{esc(lab)}</text>')

    stack(dizi, True)
    stack(real, False)
    s.append("</svg>")
    return "".join(s)


# ---------------------------------------------------------------- SVG: network
def svg_network():
    W, H = 1040, 470
    real = ["Abdullah Çatlı", "Alaattin Çakıcı", "Uğur Çakıcı", "Dündar Kılıç", "Hiram Abas", "Halil Havar", "Veli Küçük", "Kaşif Kozinoğlu"]
    fict = ["Polat Alemdar", "Süleyman Çakır", "Nesrin Çakır", "Laz Ziya", "Aslan Akbey", "Halo Dayı", "İskender Büyük", "Kazım Kaşifoğlu"]
    grade = ["Orta–Güçlü", "Orta–Güçlü", "Orta", "Orta", "Orta", "Güçlü–Orta", "Orta–Güçlü", "Güçlü"]
    gcol = {"Güçlü": GREEN, "Güçlü–Orta": GREEN, "Orta–Güçlü": AMBER, "Orta": AMBER}
    xl, xr = 250, 790
    top, step = 80, 46
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="{SANS}">']
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    s.append(f'<text x="40" y="26" font-size="12" font-family="{MONO}" fill="{GREY}">ŞEKİL 2 · İLİŞKİ AĞI: GERÇEK FİGÜRLER ↔ KURGU KARAKTERLER (yalnızca Orta ve üstü)</text>')
    s.append(f'<text x="{xl}" y="58" font-size="11" font-family="{MONO}" fill="{RED}" text-anchor="middle" font-weight="bold">GERÇEK (Susurluk ağı / Ergenekon dönemi)</text>')
    s.append(f'<text x="{xr}" y="58" font-size="11" font-family="{MONO}" fill="{NAVY}" text-anchor="middle" font-weight="bold">KURGU (Kurtlar Vadisi / Pusu)</text>')
    # real-world family ties
    ties = [(1, 2, "evli"), (3, 2, "baba–kız")]
    for a, b, lab in ties:
        ya, yb = top + a * step, top + b * step
        s.append(f'<path d="M {xl-110} {ya} C {xl-170} {ya}, {xl-170} {yb}, {xl-110} {yb}" fill="none" stroke="{RED}" stroke-width="1.2"/>')
        s.append(f'<text x="{xl-160}" y="{(ya+yb)/2+3}" font-size="9" fill="{RED}" text-anchor="middle" font-family="{MONO}">{lab}</text>')
    fties = [(1, 2, "evli"), (3, 2, "baba–kız")]
    for a, b, lab in fties:
        ya, yb = top + a * step, top + b * step
        s.append(f'<path d="M {xr+110} {ya} C {xr+170} {ya}, {xr+170} {yb}, {xr+110} {yb}" fill="none" stroke="{NAVY}" stroke-width="1.2"/>')
        s.append(f'<text x="{xr+160}" y="{(ya+yb)/2+3}" font-size="9" fill="{NAVY}" text-anchor="middle" font-family="{MONO}">{lab}</text>')
    for k in range(len(real)):
        y = top + k * step
        col = gcol[grade[k]]
        s.append(f'<line x1="{xl+110}" y1="{y}" x2="{xr-110}" y2="{y}" stroke="{col}" stroke-width="2.2" stroke-dasharray="6,4"/>')
        s.append(f'<rect x="{(xl+xr)/2-42}" y="{y-9}" width="84" height="16" rx="8" fill="white" stroke="{col}"/>')
        s.append(f'<text x="{(xl+xr)/2}" y="{y+3}" font-size="9" text-anchor="middle" fill="{col}" font-family="{MONO}">{esc(grade[k])}</text>')
        for X, lab, c in ((xl, real[k], RED), (xr, fict[k], NAVY)):
            s.append(f'<rect x="{X-110}" y="{y-15}" width="220" height="30" rx="3" fill="{PAPER}" stroke="{c}" stroke-width="1.4"/>')
            s.append(f'<text x="{X}" y="{y+5}" font-size="12" text-anchor="middle" fill="{INK}">{esc(lab)}</text>')
    s.append(f'<text x="40" y="{H-14}" font-size="10" fill="{GREY}">Kesikli çizgi = basın/sözlük iddiası; hiçbiri yapımcı tarafından doğrulanmadı. Yan bağlar gerçek ve kurgudaki aile ilişkilerini gösterir; ağ yapısının kopyalanmış olması en güçlü yapısal kanıttır.</text>')
    s.append("</svg>")
    return "".join(s)


# ---------------------------------------------------------------- SVG: grade distribution
def svg_grades():
    data = [
        ("Kurtlar Vadisi (2003–05) karakterleri", {"Güçlü": 1, "Orta": 9, "Zayıf": 12, "Yok": 3}),
        ("Pusu (2007–16) karakterleri", {"Güçlü": 3, "Orta": 5, "Zayıf": 4, "Yok": 2}),
        ("KV bölüm olayları (1–97, paralel iddia edilen)", {"Güçlü": 1, "Orta": 7, "Zayıf": 21, "Yok": 0}),
        ("Pusu arkları + filmler", {"Güçlü": 7, "Orta": 6, "Zayıf": 1, "Yok": 1}),
    ]
    W, H = 1040, 250
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="{SANS}">']
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    s.append(f'<text x="40" y="26" font-size="12" font-family="{MONO}" fill="{GREY}">ŞEKİL 3 · KANIT DERECESİ DAĞILIMI (satır = iddia grubu, kutu = iddia sayısı)</text>')
    y = 60
    xb = 380
    for lab, d in data:
        s.append(f'<text x="{xb-12}" y="{y+15}" font-size="12" text-anchor="end" fill="{INK}">{esc(lab)}</text>')
        x = xb
        for g in ("Güçlü", "Orta", "Zayıf", "Yok"):
            w = d[g] * 22
            if w:
                s.append(f'<rect x="{x}" y="{y}" width="{w-2}" height="22" fill="{GRADE_COLORS[g]}" opacity="0.85"/>')
                s.append(f'<text x="{x + w/2 - 1}" y="{y+15}" font-size="11" text-anchor="middle" fill="white" font-weight="bold">{d[g]}</text>')
            x += w
        y += 40
    lx = xb
    for g in ("Güçlü", "Orta", "Zayıf", "Yok"):
        s.append(f'<rect x="{lx}" y="{H-30}" width="14" height="14" fill="{GRADE_COLORS[g]}"/>')
        s.append(f'<text x="{lx+20}" y="{H-19}" font-size="11" fill="{INK}">{g}</text>')
        lx += 90
    s.append("</svg>")
    return "".join(s)


# ---------------------------------------------------------------- SVG: episode heat strip
EP_STRENGTH = {  # episode: (level, label)
    1: (2, "Çatlı sahte kimlik"), 10: (2, "Irak işgali"), 15: (2, "SARS"), 43: (2, "Çakır vurulur (ayrışma)"),
    45: (1, "Çakır ölür"), 52: (2, "Uğur Çakıcı (ters)"), 55: (2, "Hiram Abas"), 61: (3, "Halil Havar"), 62: (3, "Halil Havar"),
    85: (1, "Ü. Garih"), 86: (2, "Eşref Bitlis"), 88: (2, "Hariri"), 89: (2, "Hariri"), 90: (2, "Hariri"), 97: (1, "Susurluk davası"),
    3: (1, ""), 6: (1, ""), 9: (1, ""), 14: (1, ""), 18: (1, ""), 19: (1, ""), 21: (1, ""), 29: (1, ""), 34: (1, ""), 36: (1, ""), 37: (1, ""),
    46: (1, ""), 49: (1, ""), 57: (1, ""), 80: (1, ""), 91: (1, ""),
}
UNKNOWN = set(range(65, 73)) | {78} | set(range(81, 85))


def svg_episodes():
    W, H = 1040, 300
    cols = 25
    cw, ch = 36, 30
    x0, y0 = 60, 60
    lv = {0: "#e5e7eb", 1: "#f4c7c3", 2: AMBER, 3: GREEN}
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="{SANS}">']
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    s.append(f'<text x="40" y="26" font-size="12" font-family="{MONO}" fill="{GREY}">ŞEKİL 4 · KURTLAR VADİSİ 1–97: BÖLÜM BAŞINA GERÇEK HAYAT PARALELİ YOĞUNLUĞU</text>')
    seasons = [(1, 20, "S1"), (21, 55, "S2"), (56, 86, "S3"), (87, 97, "S4")]
    for ep in range(1, 98):
        r, c = divmod(ep - 1, cols)
        X, Y = x0 + c * cw, y0 + r * ch
        if ep in UNKNOWN:
            fill, txtc = "white", GREY
        else:
            level = EP_STRENGTH.get(ep, (0, ""))[0]
            fill = lv[level]
            txtc = "white" if level >= 2 else INK
        s.append(f'<rect x="{X}" y="{Y}" width="{cw-3}" height="{ch-3}" fill="{fill}" stroke="{LINE if ep not in UNKNOWN else GREY}" stroke-dasharray="{"3,2" if ep in UNKNOWN else "0"}"/>')
        s.append(f'<text x="{X + (cw-3)/2}" y="{Y + 18}" font-size="11" text-anchor="middle" fill="{txtc}" font-family="{MONO}">{ep}</text>')
    # season brackets
    ys = y0 + 4 * ch + 8
    for a, b, lab in seasons:
        ra, ca = divmod(a - 1, cols)
        s.append(f'<text x="{x0 + ca*cw}" y="{ys+10}" font-size="9" fill="{GREY}" font-family="{MONO}">{lab}: b.{a}–{b}</text>')
        ys += 12
    lx, ly = 250, y0 + 4 * ch + 14
    for col, lab in ((lv[3], "Güçlü olay örtüşmesi"), (lv[2], "Orta"), (lv[1], "Zayıf / tema"), (lv[0], "Paralel iddiası yok"), ("white", "Bölüm özeti kaynağı zayıf")):
        s.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{col}" stroke="{GREY}"/>')
        s.append(f'<text x="{lx+20}" y="{ly+11}" font-size="10" fill="{INK}">{lab}</text>')
        ly += 18
    # callouts
    s.append(f'<text x="{x0+560}" y="{y0 + 4*ch + 14 + 11}" font-size="10" fill="{INK}"></text>')
    notes = ["b.61–62 Halo Dayı ↔ Halil Havar (1991, helikopterle kaçırma)", "b.88–90 Lübnan başbakanı suikastı ↔ Hariri (Şub 2005)", "b.52 Nesrin, Meral'i vurur ↔ Uğur Çakıcı cinayeti (1995, ters)", "b.55 Akbey suikastı ↔ Hiram Abas (1990)"]
    ny = y0 + 4 * ch + 14 + 11
    for t in notes:
        s.append(f'<text x="{x0+540}" y="{ny}" font-size="9" fill="{INK}">• {esc(t)}</text>')
        ny += 16
    s.append("</svg>")
    return "".join(s)


# ---------------------------------------------------------------- SVG: pusu strip
def svg_pusu():
    W, H = 1040, 250
    seasons = [(1, 9, "Show TV"), (10, 41, "Show TV"), (42, 63, "Show TV"), (64, 93, "Star TV"), (94, 128, "atv"), (129, 161, "TNT"), (162, 195, "atv"), (196, 229, "atv"), (230, 263, "Kanal D"), (264, 300, "Kanal D")]
    chan = {"Show TV": "#1f4e79", "Star TV": "#6a1b9a", "atv": "#00796b", "TNT": "#5d4037", "Kanal D": "#c62828"}
    events = [(25, "İskender Büyük\n(Veli Küçük?)", "Orta–Güçlü"), (13, "Muro / PKK", "Orta"), (80, "Mossad bölümü\nİsrail notası", "Güçlü"), (139, "Kaşifoğlu ölür\nKozinoğlu +2 gün", "Güçlü"), (171, "ÖSO'ya silah", "Orta"), (218, "Paralel yapı\n17-25 Aralık", "Güçlü"), (232, "Ebola", "Zayıf")]
    x0, x1, y = 60, W - 30, 120
    sx = (x1 - x0) / 300
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="{SANS}">']
    s.append(f'<rect width="{W}" height="{H}" fill="white"/>')
    s.append(f'<text x="40" y="26" font-size="12" font-family="{MONO}" fill="{GREY}">ŞEKİL 5 · KURTLAR VADİSİ PUSU 1–300: SEZONLAR, KANALLAR VE GERÇEK OLAY BAĞLARI</text>')
    for k, (a, b, ch) in enumerate(seasons):
        X = x0 + (a - 1) * sx
        w = (b - a + 1) * sx
        s.append(f'<rect x="{X}" y="{y}" width="{w-1}" height="28" fill="{chan[ch]}" opacity="0.85"/>')
        s.append(f'<text x="{X + w/2}" y="{y+18}" font-size="10" text-anchor="middle" fill="white" font-family="{MONO}">S{k+1}</text>')
        s.append(f'<text x="{X + w/2}" y="{y+42}" font-size="9" text-anchor="middle" fill="{GREY}" font-family="{MONO}">{a}–{b}</text>')
    lx = x0
    for ch, col in chan.items():
        s.append(f'<rect x="{lx}" y="{H-24}" width="12" height="12" fill="{col}"/>')
        s.append(f'<text x="{lx+16}" y="{H-14}" font-size="10" fill="{INK}">{ch}</text>')
        lx += 80
    gc = {"Güçlü": GREEN, "Orta–Güçlü": AMBER, "Orta": AMBER, "Zayıf": RED}
    for i, (ep, lab, g) in enumerate(sorted(events)):
        X = x0 + (ep - 0.5) * sx
        up = i % 2 == 0
        Y = y - 20 if up else y + 62
        s.append(f'<line x1="{X}" y1="{y if up else y+28}" x2="{X}" y2="{Y + (6 if up else -14)}" stroke="{gc[g]}" stroke-width="1.5"/>')
        for j, t in enumerate(lab.split("\n")):
            s.append(f'<text x="{X}" y="{Y - 12 + j*12 if up else Y + j*12}" font-size="9.5" text-anchor="middle" fill="{gc[g]}" font-weight="bold">{esc(t)}</text>')
        s.append(f'<text x="{X}" y="{Y - 12 + len(lab.split(chr(10)))*12 if up else Y + len(lab.split(chr(10)))*12}" font-size="8.5" text-anchor="middle" fill="{GREY}" font-family="{MONO}">b.{ep}</text>')
    s.append("</svg>")
    return "".join(s)


# ---------------------------------------------------------------- assemble
CSS = f"""
@page {{ size: A4; }}
* {{ box-sizing: border-box; }}
html, body {{ margin:0; padding:0; background:white; color:{INK}; font-family:{SANS}; font-size:9.6pt; line-height:1.38; }}
a {{ color:{NAVY}; text-decoration:none; word-break:break-all; }}
code {{ font-family:{MONO}; font-size:8.5pt; }}
.classif {{ position:fixed; left:0; right:0; text-align:center; font-family:{MONO}; font-size:8pt; letter-spacing:.25em; color:{RED}; font-weight:bold; }}
.classif.top {{ top:0; }}
.classif.bottom {{ bottom:0; }}
.hdr {{ position:fixed; top:5mm; left:0; right:0; border-bottom:.6pt solid {LINE}; font-family:{MONO}; font-size:7.5pt; color:{GREY}; display:flex; justify-content:space-between; padding-bottom:2pt; }}
.ftr {{ position:fixed; bottom:5mm; left:0; right:0; border-top:.6pt solid {LINE}; font-family:{MONO}; font-size:7.5pt; color:{GREY}; display:flex; justify-content:space-between; padding-top:2pt; }}

/* cover */
.cover {{ page-break-after:always; min-height:230mm; position:relative; padding-top:2mm; }}
.cover .band {{ background:{NAVY}; color:white; padding:24mm 12mm 10mm; margin:0 -4mm; }}
.cover .band .kicker {{ font-family:{MONO}; font-size:9pt; letter-spacing:.3em; color:#9fb3c8; }}
.cover h1 {{ font-size:26pt; margin:6mm 0 3mm; line-height:1.15; font-weight:bold; }}
.cover .sub {{ font-size:12pt; color:#dbe4ee; }}
.meta {{ margin-top:10mm; width:100%; border-collapse:collapse; font-family:{MONO}; font-size:8.8pt; }}
.meta td {{ border-bottom:.5pt solid {LINE}; padding:5pt 4pt; vertical-align:top; }}
.meta td:first-child {{ color:{GREY}; width:38mm; letter-spacing:.08em; }}
.stamp {{ position:absolute; right:8mm; top:6mm; border:2.5pt solid #ff6b61; color:#ff6b61; font-family:{MONO}; font-weight:bold; font-size:12pt; letter-spacing:.2em; padding:5pt 10pt; transform:rotate(-8deg); opacity:.85; }}
.stamp2 {{ display:block; margin-top:8mm; border:1.5pt solid {NAVY}; color:{NAVY}; font-family:{MONO}; font-size:8pt; padding:4pt 8pt; max-width:120mm; line-height:1.4; }}
.keyfind {{ margin-top:8mm; }}
.keyfind h4 {{ font-family:{MONO}; letter-spacing:.2em; font-size:8.5pt; color:{GREY}; margin:0 0 3mm; }}
.keyfind ol {{ margin:0; padding-left:5mm; font-size:9.5pt; }}
.keyfind li {{ margin-bottom:2pt; }}

h2 {{ font-size:14pt; margin:9mm 0 3mm; padding-bottom:2pt; border-bottom:1.8pt solid {NAVY}; page-break-after:avoid; color:{NAVY}; }}
h2 .secno {{ font-family:{MONO}; background:{NAVY}; color:white; padding:1pt 6pt; margin-right:6pt; font-size:10pt; letter-spacing:.15em; vertical-align:middle; }}
h3 {{ font-size:10.5pt; margin:5mm 0 2mm; color:{INK}; page-break-after:avoid; font-family:{MONO}; letter-spacing:.04em; }}
p {{ margin:0 0 2.2mm; }}
table {{ width:100%; border-collapse:collapse; margin:2mm 0 4mm; font-size:8.2pt; page-break-inside:auto; }}
thead {{ display:table-header-group; }}
tr {{ page-break-inside:avoid; }}
th {{ background:{NAVY}; color:white; text-align:left; padding:3pt 4pt; font-family:{MONO}; font-weight:normal; font-size:7.5pt; letter-spacing:.05em; }}
td {{ border-bottom:.5pt solid {LINE}; padding:3pt 4pt; vertical-align:top; }}
tbody tr:nth-child(even) td {{ background:{PAPER}; }}
.grade {{ font-family:{MONO}; font-size:7.3pt; border:1pt solid; padding:0 3pt; white-space:nowrap; font-weight:bold; }}
.callout {{ border-left:3pt solid {RED}; background:#fbf1f0; padding:3mm 4mm; margin:3mm 0 4mm; font-size:9pt; }}
.callout-tag {{ font-family:{MONO}; color:{RED}; font-size:7.5pt; letter-spacing:.25em; margin-bottom:1.5mm; font-weight:bold; }}
.fig {{ margin:3mm 0 5mm; border:.6pt solid {LINE}; page-break-inside:avoid; }}
.fig svg {{ width:100%; height:auto; display:block; }}
table.frame {{ margin:0; border-collapse:collapse; width:100%; }}
table.frame > thead > tr > td {{ height:17mm; padding:0; border:0; background:none; }}
table.frame > tfoot > tr > td {{ height:24mm; padding:0; border:0; background:none; }}
table.frame > tbody > tr > td {{ padding:0; border:0; background:none; }}
table.frame > tbody > tr {{ page-break-inside:auto; }}
ul, ol {{ margin:0 0 2.5mm; padding-left:5mm; }}
li {{ margin-bottom:1pt; }}
.src {{ font-size:7.6pt; }}
.src li {{ margin-bottom:0; }}
"""


PRINT_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ executablePath: '__CHROME__', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.goto('__HTML__', { waitUntil: 'load' });
  const mono = "font-family:'DejaVu Sans Mono',monospace;";
  const classif = `<div style="width:100%;text-align:center;${mono}font-size:7.5px;letter-spacing:.25em;color:#b3261e;font-weight:bold;">AÇIK KAYNAK · OSINT · DOĞRULANMAMIŞ İDDİALAR İÇERİR</div>`;
  const header = `<div style="width:100%;padding:6mm 16mm 0;${mono}font-size:7px;color:#6b7280;">${classif}<div style="display:flex;justify-content:space-between;border-bottom:.6px solid #c9ced6;padding:3px 0 2px;margin-top:3px;"><span>OSINT-KV-2026-001</span><span>KURTLAR VADİSİ ↔ GERÇEK HAYAT EŞLEŞTİRME ŞEMASI</span><span>13 EYL 2026</span></div></div>`;
  const footer = `<div style="width:100%;padding:0 16mm 5mm;${mono}font-size:7px;color:#6b7280;"><div style="display:flex;justify-content:space-between;border-top:.6px solid #c9ced6;padding:2px 0 3px;"><span>Kaynaklar: bkz. Bölüm 10</span><span>Kanıt ölçeği: Güçlü / Orta / Zayıf / Yok</span><span>Sayfa <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>${classif}</div>`;
  await page.pdf({ path: '__PDF__', format: 'A4', printBackground: true, displayHeaderFooter: true,
    headerTemplate: header, footerTemplate: footer,
    margin: { top: '22mm', bottom: '20mm', left: '16mm', right: '16mm' } });
  await browser.close();
})();
"""


def build():
    md = MD.read_text(encoding="utf-8")
    body = md_to_html(md)
    body = body.replace("{{TIMELINE}}", f'<div class="fig">{svg_timeline()}</div>')
    body = body.replace("{{NETWORK}}", f'<div class="fig">{svg_network()}</div>')
    # insert extra figures
    body = body.replace('<h2><span class="secno">04</span>', f'<div class="fig">{svg_grades()}</div><div class="fig">{svg_episodes()}</div><h2><span class="secno">04</span>', 1)
    body = body.replace('<h2><span class="secno">06</span>', '<h2><span class="secno">06</span>', 1)
    body = re.sub(r'(<h2><span class="secno">06</span>.*?</h2>\s*<p>.*?</p>)', lambda m: m.group(1) + f'<div class="fig">{svg_pusu()}</div>', body, count=1, flags=re.S)
    # sources section smaller
    body = re.sub(r'(<h2><span class="secno">10</span>.*)$', lambda m: m.group(1).replace("<ul>", '<ul class="src">'), body, flags=re.S)

    cover = f"""
<div class="cover">
  <div class="band">
    <div class="kicker">AÇIK KAYNAK İSTİHBARAT DEĞERLENDİRMESİ · OSINT</div>
    <h1>Kurtlar Vadisi ↔ Gerçek Hayat<br>Eşleştirme Şeması</h1>
    <div class="sub">Kurtlar Vadisi (97 bölüm), Terör (2), Pusu (300) ve dört sinema filminin gerçek kişi ve olaylarla kaynaklı karşılaştırması</div>
  </div>
  <div class="stamp">DOĞRULANMAMIŞ İDDİALAR İÇERİR</div>
  <table class="meta">
    <tr><td>RAPOR NO</td><td>OSINT-KV-2026-001</td></tr>
    <tr><td>TARİH</td><td>13 Eylül 2026</td></tr>
    <tr><td>KAPSAM</td><td>2003–2017 yayın dönemi; 399 dizi bölümü, 4 film</td></tr>
    <tr><td>YÖNTEM</td><td>Açık kaynak taraması (basın arşivi, Vikipedi, sözlük/forum, yapımcı röportajları); her eşleştirme için iddia sahibi, örtüşme türü ve yapımcı tutumu kaydedildi</td></tr>
    <tr><td>KANIT ÖLÇEĞİ</td><td><span class="grade" style="border-color:{GREEN};color:{GREEN}">Güçlü</span> &nbsp;<span class="grade" style="border-color:{AMBER};color:{AMBER}">Orta</span> &nbsp;<span class="grade" style="border-color:{RED};color:{RED}">Zayıf</span> &nbsp;<span class="grade" style="border-color:{GREY};color:{GREY}">Yok</span></td></tr>
    <tr><td>DAĞITIM</td><td>Sınırsız · Kişisel araştırma amaçlı</td></tr>
  </table>
  <div class="keyfind">
    <h4>ÖZET BULGULAR</h4>
    <ol>
      <li><b>Yapımcılar kişi bazlı esinlenmeyi reddediyor.</b> Tek yarı-itiraf konsept danışmanı Soner Yalçın'ın "Susurluk'u yapalım" sözü ve Çatlı ailesinin beyanlarıdır.</li>
      <li><b>En güçlü kişi örtüşmeleri:</b> Halo Dayı ↔ Halil Havar (1991 helikopterle kaçırma), Çakır–Nesrin–Laz Ziya ↔ Çakıcı–Uğur Çakıcı–Dündar Kılıç ağı, Kaşifoğlu ↔ Kaşif Kozinoğlu (ölümler iki gün arayla; 2026'da senaristler ifadeye çağrıldı).</li>
      <li><b>En güçlü olay örtüşmeleri:</b> Pusu İsrail elçiliği bölümü (2010, diplomatik nota doğurdu), b.218 (17-25 Aralık), b.88–90 (Hariri suikastının tersine çevrilmiş hâli) ve dört filmin tamamı.</li>
      <li><b>Sistematik ayrışma:</b> Dizi, eşleştirilen kişileri gerçekte hayattayken öldürür; devlet operasyonunu beraatle bitirirken gerçek Susurluk davası mahkûmiyetle bitti.</li>
      <li><b>Yanlışlanan iddialar:</b> "Suriye bayrağı kehaneti", Terör'ün "Çözüm Süreci" nedeniyle kaldırılması, Çakır'ın 51. bölümde ölmesi, İskender Büyük = Cem Uzan.</li>
    </ol>
  </div>
  <div class="stamp2">HUKUKİ NOT · Bu belgedeki gerçek kişi eşleştirmeleri basın, sözlük ve fan iddialarının derlemesidir; adı geçen kişiler hakkında olgu tespiti veya suçlama değildir. Her satırda iddianın kaynağı ve yapımcı tutumu ayrıca belirtilmiştir.</div>
</div>
"""
    page = f"""<!DOCTYPE html><html lang="tr"><head><meta charset="utf-8"><title>Kurtlar Vadisi OSINT Raporu</title><style>{CSS}</style></head><body>
{cover}
{body}
</body></html>"""
    OUT_HTML.write_text(page, encoding="utf-8")
    js = OUT_DIR / "print.js"
    js.write_text(PRINT_JS.replace("__HTML__", OUT_HTML.as_uri()).replace("__PDF__", str(OUT_PDF)).replace("__CHROME__", CHROME))
    subprocess.run(["node", str(js)], check=True, timeout=240, env={**__import__("os").environ, "NODE_PATH": "/opt/node22/lib/node_modules"})
    print("wrote", OUT_PDF)


if __name__ == "__main__":
    build()
