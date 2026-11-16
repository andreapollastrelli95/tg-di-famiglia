#!/usr/bin/env python3
"""Genera assets/sigla.mp3: una fanfara ORIGINALE di circa 6 secondi in stile
telegiornale (ottoni + archi + timpani + piatto), sintetizzata con numpy.

Melodia e armonia sono composte apposta per questo progetto (Si bemolle maggiore,
progressione Bb - Gm - Eb - F - Bb); non riprendono sigle esistenti.

Uso:  pip install numpy lameenc   e poi   python tools/genera_sigla.py
"""
from pathlib import Path

import numpy as np

SR = 44100
DURATA = 6.4
rng = np.random.default_rng(7)
t_tot = int(SR * DURATA)
L = np.zeros(t_tot)
R = np.zeros(t_tot)


def nota(n):
    """Nome nota -> frequenza (A4 = 440)."""
    nomi = {"C": -9, "C#": -8, "Db": -8, "D": -7, "Eb": -6, "E": -5, "F": -4, "F#": -3,
            "G": -2, "Ab": -1, "A": 0, "Bb": 1, "B": 2}
    nome, ott = n[:-1], int(n[-1])
    return 440.0 * 2 ** ((nomi[nome] + 12 * (ott - 4)) / 12)


def inviluppo(n, a, d, s, r, sr=SR):
    a, d, r = int(a * sr), int(d * sr), int(r * sr)
    s_len = max(n - a - d - r, 0)
    env = np.concatenate([
        np.linspace(0, 1, a, endpoint=False) ** 1.5,
        np.linspace(1, s, d, endpoint=False),
        np.full(s_len, s),
        np.linspace(s, 0, r) ** 1.2 * (1 if s > 0 else 0) + (np.linspace(s, 0, r) if s == 0 else 0),
    ])
    return env[:n] if len(env) >= n else np.pad(env, (0, n - len(env)))


def ottone(f, dur, vol=0.25, pan=0.0, t0=0.0):
    """Ottone sintetico: somma di armoniche con brillantezza che cresce con l'attacco."""
    n = int((dur + 0.25) * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.3, 0, 1)
    fase = 2 * np.pi * f * np.cumsum(vib) / SR
    brill = np.clip(t / 0.06, 0, 1)  # le armoniche alte entrano dopo l'attacco ("blare")
    out = np.zeros(n)
    for k in range(1, 14):
        if f * k > 12000:
            break
        amp = (1 / k ** 1.1) * (brill if k > 3 else 1)
        out += amp * np.sin(k * fase + rng.uniform(0, 0.3))
    out *= inviluppo(n, 0.035, 0.12, 0.75, 0.22)
    mixa(out * vol, t0, pan)


def archi(f, dur, vol=0.08, pan=0.0, t0=0.0):
    """Sezione d'archi: 5 seghe leggermente stonate con attacco morbido."""
    n = int((dur + 0.5) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for det in (-0.012, -0.005, 0, 0.006, 0.013):
        ff = f * (1 + det / 2)
        fase = 2 * np.pi * ff * t + rng.uniform(0, 6.28)
        for k in range(1, 10):
            out += np.sin(k * fase) / k * (0.85 ** k)
    out *= inviluppo(n, 0.25, 0.2, 0.8, 0.45) / 5
    mixa(out * vol, t0, pan)


def timpano(f, t0, vol=0.5):
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    ff = f * (1 + 0.06 * np.exp(-t * 30))
    corpo = np.sin(2 * np.pi * np.cumsum(ff) / SR) + 0.35 * np.sin(2 * np.pi * 1.5 * np.cumsum(ff) / SR)
    colpo = rng.normal(0, 1, n) * np.exp(-t * 60) * 0.3
    out = (corpo * np.exp(-t * 2.8) + colpo) * vol
    mixa(out, t0, -0.15)


def rullo(f, t0, dur, vol_da=0.05, vol_a=0.35):
    colpi = int(dur * 18)
    for i in range(colpi):
        x = i / max(colpi - 1, 1)
        timpano(f, t0 + i / 18 + rng.uniform(0, 0.008), vol=(vol_da + (vol_a - vol_da) * x ** 2) * 0.6)


def piatto(t0, dur=2.4, vol=0.18, swell=False):
    n = int(dur * SR)
    t = np.arange(n) / SR
    rumore = rng.normal(0, 1, n)
    # passa-alto rudimentale: differenza prima ripetuta
    for _ in range(3):
        rumore = np.diff(rumore, prepend=0)
    rumore /= np.max(np.abs(rumore)) + 1e-9
    env = (t / dur) ** 2.5 if swell else np.exp(-t * 2.2)
    mixa(rumore * env * vol, t0 - (dur if swell else 0), 0.25)


def mixa(x, t0, pan):
    i = int(t0 * SR)
    if i < 0:
        x, i = x[-i:], 0
    j = min(i + len(x), t_tot)
    x = x[: j - i]
    gl, gr = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    L[i:j] += x * gl * 1.41
    R[i:j] += x * gr * 1.41


# ------------------------------------------------------------ composizione
# Introduzione: rullo di timpano in crescendo + archi che salgono
rullo(nota("Bb1") * 2, 0.0, 0.75)
piatto(0.8, dur=0.8, vol=0.12, swell=True)
for n in ("Bb2", "F3", "Bb3", "D4"):
    archi(nota(n), 0.7, vol=0.05, t0=0.05)

# Accordi (archi + ottoni gravi): Bb | Gm | Eb | F | Bb
accordi = [
    (0.80, 1.45, ["Bb2", "F3", "Bb3", "D4"]),
    (2.25, 0.75, ["G2", "D3", "G3", "Bb3"]),
    (3.00, 0.80, ["Eb2", "Bb2", "Eb3", "G3"]),
    (3.80, 0.80, ["F2", "C3", "F3", "A3"]),
    (4.60, 1.60, ["Bb1", "F2", "Bb2", "D3", "F3"]),
]
for t0, d, note in accordi:
    for k, n in enumerate(note):
        archi(nota(n) * 2, d, vol=0.06, pan=-0.5 + k * 0.25, t0=t0)
        if k < 3:
            ottone(nota(n), d * 0.9, vol=0.09, pan=-0.3, t0=t0)
    timpano(nota(note[0]) if nota(note[0]) > 60 else nota(note[0]) * 2, t0, vol=0.45)

# Melodia della tromba (originale)
melodia = [
    (0.80, 0.18, "F4"), (1.00, 0.18, "Bb4"), (1.20, 0.50, "D5"),
    (1.75, 0.18, "C5"), (1.95, 0.20, "D5"), (2.20, 0.70, "G5"),
    (3.00, 0.30, "F5"), (3.33, 0.20, "Eb5"), (3.55, 0.22, "D5"),
    (3.80, 0.35, "C5"), (4.18, 0.18, "D5"), (4.38, 0.18, "Eb5"),
    (4.60, 1.55, "F5"),
]
for t0, d, n in melodia:
    ottone(nota(n), d, vol=0.20, pan=0.15, t0=t0)
    ottone(nota(n) / 2 * 1.002, d, vol=0.07, pan=-0.15, t0=t0)  # raddoppio all'ottava sotto
# Accordo finale degli ottoni alti
for n in ("Bb4", "D5"):
    ottone(nota(n), 1.5, vol=0.12, pan=0.35, t0=4.6)
piatto(4.6, dur=1.8, vol=0.22)
rullo(nota("Bb1") * 2, 4.62, 0.9, vol_da=0.25, vol_a=0.05)
timpano(nota("Bb1") * 2, 5.55, vol=0.6)

# ------------------------------------------------------------ mastering
st = np.stack([L, R], axis=1)
# riverbero semplice: alcune eco smorzate
rev = np.zeros_like(st)
for ritardo, g in ((0.031, 0.35), (0.047, 0.3), (0.071, 0.25), (0.113, 0.18), (0.167, 0.12)):
    k = int(ritardo * SR)
    rev[k:, 0] += st[:-k, 1] * g
    rev[k:, 1] += st[:-k, 0] * g
st = st + rev * 0.6
st = np.tanh(st * 1.6) / np.tanh(1.6)  # leggera saturazione/compressione
fine = int(0.5 * SR)
st[-fine:] *= np.linspace(1, 0, fine)[:, None] ** 2
st /= np.max(np.abs(st)) / 0.92
pcm = (st * 32767).astype(np.int16)

uscita = Path(__file__).resolve().parent.parent / "assets" / "sigla.mp3"
uscita.parent.mkdir(exist_ok=True)
try:
    import lameenc

    enc = lameenc.Encoder()
    enc.set_bit_rate(160)
    enc.set_in_sample_rate(SR)
    enc.set_channels(2)
    enc.set_quality(2)
    mp3 = enc.encode(pcm.tobytes()) + enc.flush()
    uscita.write_bytes(mp3)
    print(f"Scritto {uscita} ({len(mp3) // 1024} KB, {DURATA} s)")
except ImportError:
    import wave

    w = uscita.with_suffix(".wav")
    with wave.open(str(w), "wb") as f:
        f.setnchannels(2), f.setsampwidth(2), f.setframerate(SR), f.writeframes(pcm.tobytes())
    print(f"lameenc non installato: scritto {w}. Convertilo in MP3 con ffmpeg.")
