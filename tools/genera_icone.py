#!/usr/bin/env python3
"""Genera le icone dell'app (logo "TG" su fondo blu con banda rossa). Richiede Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CARTELLA = Path(__file__).resolve().parent.parent / "icons"
BLU, ROSSO, BIANCO = (11, 42, 85), (200, 16, 46), (255, 255, 255)
FONT = ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]


def font(px):
    for f in FONT:
        try:
            return ImageFont.truetype(f, px)
        except OSError:
            pass
    return ImageFont.load_default()


def icona(lato, margine_sicuro=1.0, arrotonda=True):
    s = lato * 4  # disegno a risoluzione 4x e poi riduco (bordi morbidi)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(s * 0.22) if arrotonda else 0
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=BLU)
    k = margine_sicuro  # <1 per le icone "maskable": il contenuto sta nel cerchio centrale
    c = s / 2
    # banda rossa in basso con la scritta "di Famiglia"
    h_banda = s * 0.2 * k
    y_banda = c + s * 0.19 * k
    d.rectangle([c - s * 0.36 * k, y_banda, c + s * 0.36 * k, y_banda + h_banda], fill=ROSSO)
    f_tg = font(int(s * 0.42 * k))
    d.text((c, c - s * 0.06 * k), "TG", font=f_tg, fill=BIANCO, anchor="mm")
    f_sotto = font(int(s * 0.105 * k))
    d.text((c, y_banda + h_banda / 2), "di Famiglia", font=f_sotto, fill=BIANCO, anchor="mm")
    return img.resize((lato, lato), Image.LANCZOS)


CARTELLA.mkdir(exist_ok=True)
icona(192).save(CARTELLA / "icon-192.png")
icona(512).save(CARTELLA / "icon-512.png")
icona(512, margine_sicuro=0.78, arrotonda=False).save(CARTELLA / "icon-maskable-512.png")
ios = icona(180, arrotonda=False).convert("RGB")  # iOS arrotonda da solo e non vuole trasparenze
ios.save(CARTELLA / "apple-touch-icon.png")
print("Icone create in", CARTELLA)
