#!/usr/bin/env python3
"""Genera il QR code (PNG) e il cartoncino stampabile (PDF, formato A6 orizzontale,
entra in una bustina C6) con le istruzioni per Android e iPhone.

Uso:
  python tools/genera_qr_cartoncino.py --url https://UTENTE.github.io/tg-di-famiglia/
  python tools/genera_qr_cartoncino.py --url https://UTENTE.github.io/tg-di-famiglia/ --chiave AIza... --nome papa

Con --chiave il QR contiene già la chiave (#key=...): i file finiscono in
stampa/privato/ (esclusa da git). NON pubblicare né condividere quel QR.
Richiede: pip install qrcode pillow reportlab
"""
import argparse
from pathlib import Path

import qrcode
from qrcode.constants import ERROR_CORRECT_M
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A6, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

RADICE = Path(__file__).resolve().parent.parent
BLU, ROSSO, GRIGIO, VERDE = HexColor("#0b2a55"), HexColor("#c8102e"), HexColor("#555555"), HexColor("#0f6b3a")


def registra_font():
    coppie = [("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
              ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
              ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf")]
    for norm, gras in coppie:
        if Path(norm).exists() and Path(gras).exists():
            pdfmetrics.registerFont(TTFont("F", norm))
            pdfmetrics.registerFont(TTFont("FB", gras))
            return "F", "FB"
    return "Helvetica", "Helvetica-Bold"


F, FB = registra_font()


def crea_qr(testo: str, file: Path):
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=16, border=2)
    qr.add_data(testo)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b2a55", back_color="white").convert("RGB")
    file.parent.mkdir(parents=True, exist_ok=True)
    img.save(file)
    return file


# ------------------------------------------------------------ pittogrammi
def telefono(c, x, y, w=11 * mm, h=19 * mm):
    c.setStrokeColor(BLU); c.setFillColor(white); c.setLineWidth(1.1)
    c.roundRect(x, y, w, h, 1.8 * mm, stroke=1, fill=1)
    c.setFillColor(BLU); c.circle(x + w / 2, y + 1.4 * mm, 0.5 * mm, stroke=0, fill=1)
    return x + 1.2 * mm, y + 3 * mm, w - 2.4 * mm, h - 4.6 * mm  # area schermo


def pitto_qr(c, x, y):
    sx, sy, sw, sh = telefono(c, x, y)
    c.setFillColor(BLU)
    q = sw * 0.8; ox, oy = sx + (sw - q) / 2, sy + (sh - q) / 2
    m = q / 7
    schema = ["1110111", "1010101", "1110111", "0001000", "1101011", "0110110", "1011101"]
    for r, riga in enumerate(schema):
        for k, v in enumerate(riga):
            if v == "1":
                c.rect(ox + k * m, oy + (6 - r) * m, m, m, stroke=0, fill=1)


def pitto_menu_android(c, x, y):
    sx, sy, sw, sh = telefono(c, x, y)
    c.setFillColor(ROSSO)
    for i in range(3):
        c.circle(sx + sw - 1.2 * mm, sy + sh - 1.2 * mm - i * 1.3 * mm, 0.45 * mm, stroke=0, fill=1)
    c.setStrokeColor(GRIGIO); c.setFillColor(HexColor("#eef2f8")); c.setLineWidth(0.5)
    c.rect(sx + 0.8 * mm, sy + 2 * mm, sw - 1.6 * mm, 6 * mm, stroke=1, fill=1)
    c.setFillColor(BLU); c.setFont(FB, 4.2)
    c.drawCentredString(sx + sw / 2, sy + 5.6 * mm, "Installa")
    c.drawCentredString(sx + sw / 2, sy + 3.4 * mm, "app")


def pitto_condividi_ios(c, x, y):
    sx, sy, sw, sh = telefono(c, x, y)
    cx, cy = sx + sw / 2, sy + 2.4 * mm
    c.setStrokeColor(ROSSO); c.setLineWidth(0.9)
    c.rect(cx - 1.4 * mm, cy - 1.4 * mm, 2.8 * mm, 2.6 * mm, stroke=1, fill=0)
    c.line(cx, cy - 0.4 * mm, cx, cy + 2.8 * mm)
    c.line(cx - 0.9 * mm, cy + 1.9 * mm, cx, cy + 2.8 * mm)
    c.line(cx + 0.9 * mm, cy + 1.9 * mm, cx, cy + 2.8 * mm)
    c.setStrokeColor(GRIGIO); c.setFillColor(HexColor("#eef2f8")); c.setLineWidth(0.5)
    c.rect(sx + 0.6 * mm, sy + 6.2 * mm, sw - 1.2 * mm, 6.5 * mm, stroke=1, fill=1)
    c.setFillColor(BLU); c.setFont(FB, 3.8)
    c.drawCentredString(sx + sw / 2, sy + 10.4 * mm, "Aggiungi a")
    c.drawCentredString(sx + sw / 2, sy + 8.0 * mm, "Home")


def pitto_app(c, x, y):
    sx, sy, sw, sh = telefono(c, x, y)
    c.setFillColor(HexColor("#d7dde8"))
    lato = sw / 3.2
    for r in range(3):
        for k in range(2):
            c.roundRect(sx + 0.9 * mm + k * (lato + 1.6 * mm), sy + sh - 1 * mm - (r + 1) * (lato + 0.8 * mm), lato, lato, 0.6 * mm, stroke=0, fill=1)
    c.setFillColor(ROSSO)
    c.roundRect(sx + sw / 2 - 2.6 * mm, sy + 0.8 * mm, 5.2 * mm, 5.2 * mm, 1 * mm, stroke=0, fill=1)
    c.setFillColor(white); c.setFont(FB, 6)
    c.drawCentredString(sx + sw / 2, sy + 2.5 * mm, "TG")


def testo_a_capo(c, testo, x, y, larghezza, font=F, size=7.6, interlinea=9.2):
    """Scrive testo a capo automatico; **così** è grassetto (anche su più righe)."""
    parole = []
    for i, pezzo in enumerate(testo.split("**")):
        parole += [(w, i % 2 == 1) for w in pezzo.split()]
    spazio = pdfmetrics.stringWidth(" ", font, size)
    righe, riga, w_riga = [], [], 0.0
    for w, g in parole:
        lw = pdfmetrics.stringWidth(w, FB if g else font, size)
        attacca = w[0] in ".,;:!?)"
        extra = lw + (0 if not riga or attacca else spazio)
        if riga and w_riga + extra > larghezza and not attacca:
            righe.append(riga); riga, w_riga = [], 0.0; extra = lw
        riga.append((w, g, attacca)); w_riga += extra
    righe.append(riga)
    for r in righe:
        cx = x
        for j, (w, g, attacca) in enumerate(r):
            if j and not attacca:
                cx += spazio
            fnt = FB if g else font
            c.setFont(fnt, size); c.drawString(cx, y, w)
            cx += pdfmetrics.stringWidth(w, fnt, size)
        y -= interlinea
    return y


def colonna(c, x, y_top, larghezza, titolo, colore, passi):
    c.setFillColor(colore)
    c.roundRect(x, y_top - 7 * mm, larghezza, 7 * mm, 1.5 * mm, stroke=0, fill=1)
    c.setFillColor(white); c.setFont(FB, 10)
    c.drawCentredString(x + larghezza / 2, y_top - 4.9 * mm, titolo)
    y = y_top - 10 * mm
    for n, (pitto, testo) in enumerate(passi, 1):
        alto = 20 * mm
        pitto(c, x + 1 * mm, y - alto + 0.5 * mm)
        c.setFillColor(ROSSO); c.circle(x + 15.5 * mm, y - 2.6 * mm, 2.2 * mm, stroke=0, fill=1)
        c.setFillColor(white); c.setFont(FB, 8); c.drawCentredString(x + 15.5 * mm, y - 3.5 * mm, str(n))
        c.setFillColor(HexColor("#111418"))
        testo_a_capo(c, testo, x + 19 * mm, y - 3.4 * mm, larghezza - 20 * mm)
        y -= alto + 1.2 * mm


def crea_cartoncino(url_qr: str, url_visibile: str, qr_png: Path, file_pdf: Path, personale: bool):
    W, H = landscape(A6)  # 148 x 105 mm
    c = canvas.Canvas(str(file_pdf), pagesize=(W, H))
    c.setTitle("TG di Famiglia – cartoncino")
    # fascia superiore
    c.setFillColor(BLU); c.rect(0, H - 15 * mm, W, 15 * mm, stroke=0, fill=1)
    c.setFillColor(ROSSO); c.roundRect(5 * mm, H - 12.5 * mm, 10 * mm, 10 * mm, 2 * mm, stroke=0, fill=1)
    c.setFillColor(white); c.setFont(FB, 11); c.drawCentredString(10 * mm, H - 9 * mm, "TG")
    c.setFont(FB, 15); c.drawString(18 * mm, H - 8.4 * mm, "TG di Famiglia")
    c.setFont(F, 8); c.drawString(18 * mm, H - 12.2 * mm, "Il notiziario di ogni mattina, con la voce e i podcast del giorno")
    # QR a sinistra
    lato = 40 * mm
    qx, qy = 5 * mm, H - 17 * mm - lato
    c.drawImage(ImageReader(str(qr_png)), qx, qy, lato, lato)
    c.setFillColor(BLU); c.setFont(FB, 8.5)
    c.drawCentredString(qx + lato / 2, qy - 4 * mm, "Inquadra con la fotocamera")
    c.setFont(F, 6.3); c.setFillColor(GRIGIO)
    y = qy - 8 * mm
    for pezzo in [url_visibile[i:i + 34] for i in range(0, len(url_visibile), 34)]:
        c.drawCentredString(qx + lato / 2, y, pezzo); y -= 2.8 * mm
    c.setFillColor(HexColor("#111418")); c.setFont(F, 6.8)
    nota = ("La chiave è già dentro il QR: non serve inserirla." if personale
            else "Al primo avvio serve la chiave gratuita di Google Gemini (aistudio.google.com/apikey).")
    testo_a_capo(c, nota, qx, y - 1.5 * mm, lato, size=6.5, interlinea=7.6)
    # due colonne di istruzioni
    x0 = qx + lato + 4 * mm
    larg = (W - x0 - 5 * mm - 3 * mm) / 2
    passo3 = ("Apri **TG Famiglia** dalla schermata Home e tocca il grande tasto rosso." if personale else
              "Apri **TG Famiglia**, incolla la chiave la prima volta, poi tocca il grande tasto rosso.")
    colonna(c, x0, H - 17 * mm, larg, "Android", VERDE, [
        (pitto_qr, "Inquadra il QR con la **fotocamera** e apri il link con **Chrome**."),
        (pitto_menu_android, "Tocca i **tre puntini** in alto a destra e poi **Installa app** (o **Aggiungi a schermata Home**)."),
        (pitto_app, passo3),
    ])
    colonna(c, x0 + larg + 3 * mm, H - 17 * mm, larg, "iPhone", BLU, [
        (pitto_qr, "Inquadra il QR con la **Fotocamera** e apri il link con **Safari**."),
        (pitto_condividi_ios, "Tocca **Condividi** (quadrato con freccia) e poi **Aggiungi alla schermata Home**."),
        (pitto_app, passo3),
    ])
    c.showPage(); c.save()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Indirizzo GitHub Pages, es. https://utente.github.io/tg-di-famiglia/")
    ap.add_argument("--chiave", help="Chiave Gemini da inserire nel QR (#key=...)")
    ap.add_argument("--nome", default="personale", help="Suffisso dei file personali (es. papa)")
    a = ap.parse_args()
    url = a.url if a.url.endswith("/") else a.url + "/"
    if a.chiave:
        cartella = RADICE / "stampa" / "privato"
        url_qr = f"{url}#key={a.chiave.strip()}"
        qr = crea_qr(url_qr, cartella / f"qr-{a.nome}.png")
        pdf = cartella / f"cartoncino-{a.nome}.pdf"
        crea_cartoncino(url_qr, url, qr, pdf, personale=True)
    else:
        cartella = RADICE / "stampa"
        qr = crea_qr(url, cartella / "qr.png")
        pdf = cartella / "cartoncino.pdf"
        crea_cartoncino(url, url, qr, pdf, personale=False)
    print("Creati:", qr, "e", pdf)


if __name__ == "__main__":
    main()
