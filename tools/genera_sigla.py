#!/usr/bin/env python3
"""Genera la musica ORIGINALE del TG di Famiglia, sintetizzata con numpy:

  assets/sigla.mp3    sigla di ~6,5 s in stile telegiornale: rullo di timpani,
                      archi pulsanti, segnale "telegrafo", fanfara di ottoni
  assets/stacco.mp3   stacco di 3 s tra una notizia e l'altra
  assets/stacco-lungo.mp3  stacco leggero di 5 s per l'inizio di una sezione (Tuscia, sport)
  assets/tappeto.wav  sottofondo di ~7,6 s che si ripete senza stacchi (suona
                      mentre la voce si prepara, come sotto i titoli di un TG)

Melodia e armonia sono composte apposta (Si bemolle maggiore, Bb - Gm - Eb - F - Bb)
e non riprendono sigle esistenti.

Uso:  pip install numpy lameenc   e poi   python tools/genera_sigla.py
"""
from pathlib import Path

import numpy as np

SR = 44100
OTTAVO = 60 / 126 / 2            # 126 bpm: un ottavo = 0,238 s
rng = np.random.default_rng(7)
NOMI = {"C": -9, "C#": -8, "Db": -8, "D": -7, "Eb": -6, "E": -5, "F": -4, "F#": -3,
        "G": -2, "Ab": -1, "A": 0, "Bb": 1, "B": 2}


def nota(n):
    return 440.0 * 2 ** ((NOMI[n[:-1]] + 12 * (int(n[-1]) - 4)) / 12)


class Brano:
    def __init__(self, durata, ciclico=False):
        self.n = int(SR * durata)
        self.buf = np.zeros((self.n, 2))
        self.ciclico = ciclico  # se True la coda dei suoni rientra dall'inizio (loop perfetto)

    def mixa(self, x, t0, pan=0.0):
        i = int(round(t0 * SR))
        g = np.array([np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)]) * 1.41
        if self.ciclico:
            idx = (i + np.arange(len(x))) % self.n
            np.add.at(self.buf, idx, x[:, None] * g)
        else:
            if i < 0:
                x, i = x[-i:], 0
            j = min(i + len(x), self.n)
            if j > i:
                self.buf[i:j] += x[: j - i, None] * g

    # ------------------------------------------------------------ strumenti
    def ottone(self, f, dur, vol=0.2, pan=0.0, t0=0.0):
        n = int((dur + 0.22) * SR)
        t = np.arange(n) / SR
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.3, 0, 1)
        fase = 2 * np.pi * f * np.cumsum(vib) / SR
        brill = np.clip(t / 0.05, 0, 1)
        out = np.zeros(n)
        for k in range(1, 14):
            if f * k > 11000:
                break
            out += (1 / k ** 1.05) * (brill if k > 3 else 1) * np.sin(k * fase + rng.uniform(0, 0.3))
        self.mixa(out * adsr(n, 0.03, 0.1, 0.78, 0.2) * vol, t0, pan)

    def archi(self, f, dur, vol=0.06, pan=0.0, t0=0.0, attacco=0.22, rilascio=0.4):
        n = int((dur + rilascio) * SR)
        t = np.arange(n) / SR
        out = np.zeros(n)
        for det in (-0.012, -0.005, 0, 0.006, 0.013):
            fase = 2 * np.pi * f * (1 + det / 2) * t + rng.uniform(0, 6.28)
            for k in range(1, 10):
                out += np.sin(k * fase) / k * (0.85 ** k)
        self.mixa(out / 5 * adsr(n, attacco, 0.1, 0.8, rilascio) * vol, t0, pan)

    def staccato(self, f, t0, vol=0.09, pan=0.0):
        """Colpo d'arco corto: è la pulsazione 'urgente' tipica delle sigle dei notiziari."""
        self.archi(f, 0.07, vol=vol, pan=pan, t0=t0, attacco=0.008, rilascio=0.09)

    def timpano(self, f, t0, vol=0.5):
        n = int(1.5 * SR)
        t = np.arange(n) / SR
        ff = f * (1 + 0.06 * np.exp(-t * 30))
        fase = 2 * np.pi * np.cumsum(ff) / SR
        corpo = np.sin(fase) + 0.35 * np.sin(1.5 * fase)
        colpo = rng.normal(0, 1, n) * np.exp(-t * 60) * 0.3
        self.mixa((corpo * np.exp(-t * 2.8) + colpo) * vol, t0, -0.15)

    def rullo(self, f, t0, dur, da=0.05, a=0.35):
        colpi = int(dur * 18)
        for i in range(colpi):
            x = i / max(colpi - 1, 1)
            self.timpano(f, t0 + i / 18 + rng.uniform(0, 0.008), vol=(da + (a - da) * x ** 2) * 0.6)

    def piatto(self, t0, dur=2.2, vol=0.2, crescendo=False):
        n = int(dur * SR)
        t = np.arange(n) / SR
        r = rng.normal(0, 1, n)
        for _ in range(3):
            r = np.diff(r, prepend=0)
        r /= np.max(np.abs(r)) + 1e-9
        env = (t / dur) ** 2.5 if crescendo else np.exp(-t * 2.2)
        self.mixa(r * env * vol, t0 - (dur if crescendo else 0), 0.25)

    def bip(self, t0, f=1864.66, vol=0.045, pan=0.45):
        """Segnale breve e acuto, tipo telegrafo/telescrivente."""
        n = int(0.05 * SR)
        t = np.arange(n) / SR
        env = np.minimum(t / 0.004, 1) * np.minimum((0.05 - t) / 0.012, 1)
        self.mixa(np.sin(2 * np.pi * f * t) * env * vol, t0, pan)

    def campana(self, f, t0, vol=0.12, pan=0.0, dur=1.6):
        """Nota cristallina tipo glockenspiel/arpa: per gli stacchi leggeri."""
        n = int(dur * SR)
        t = np.arange(n) / SR
        out = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 9) + 0.2 * np.sin(4 * np.pi * f * t) * np.exp(-t * 5)
        self.mixa(out * np.exp(-t * 3.2) * np.minimum(t / 0.003, 1) * vol, t0, pan)

    def basso(self, f, t0, dur, vol=0.16):
        n = int((dur + 0.1) * SR)
        t = np.arange(n) / SR
        out = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t)
        self.mixa(out * adsr(n, 0.01, 0.08, 0.7, 0.09) * vol, t0, 0)

    # ------------------------------------------------------------ uscita
    def master(self, picco=0.92, riverbero=0.6, sfuma=0.0):
        st = self.buf.copy()
        rev = np.zeros_like(st)
        for ritardo, g in ((0.031, 0.35), (0.047, 0.3), (0.071, 0.25), (0.113, 0.18), (0.167, 0.12)):
            k = int(ritardo * SR)
            if self.ciclico:
                rev += np.roll(st[:, ::-1], k, axis=0) * g
            else:
                rev[k:] += st[:-k, ::-1] * g
        st = st + rev * riverbero
        st = np.tanh(st * 1.6) / np.tanh(1.6)
        if sfuma:
            k = int(sfuma * SR)
            st[-k:] *= np.linspace(1, 0, k)[:, None] ** 2
        st *= picco / np.max(np.abs(st))
        return (st * 32767).astype(np.int16)


def adsr(n, a, d, s, r):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    env = np.concatenate([np.linspace(0, 1, a, endpoint=False) ** 1.5, np.linspace(1, s, d, endpoint=False),
                          np.full(max(n - a - d - r, 0), s), np.linspace(s, 0, r)])
    return env[:n] if len(env) >= n else np.pad(env, (0, n - len(env)))


def salva_mp3(pcm, file, kbps=160):
    import lameenc
    enc = lameenc.Encoder()
    enc.set_bit_rate(kbps); enc.set_in_sample_rate(SR); enc.set_channels(2); enc.set_quality(2)
    dati = enc.encode(pcm.tobytes()) + enc.flush()
    file.parent.mkdir(exist_ok=True)
    file.write_bytes(dati)
    rms = float(np.sqrt(np.mean((pcm / 32768.0) ** 2)))
    print(f"Scritto {file} ({len(dati) // 1024} KB, {len(pcm) / SR:.1f} s, volume medio {20 * np.log10(rms):.1f} dBFS)")


SCHEMA_BIP = [1, 0, 1, 1, 0, 1, 0, 0]  # ritmo del "telegrafo" in sedicesimi


def sigla():
    b = Brano(6.6)
    T0 = 4 * OTTAVO  # 0,95 s: il colpo d'inizio dopo il rullo
    e = lambda i: T0 + i * OTTAVO  # noqa: E731 - tempo dell'ottavo i
    # introduzione: rullo di timpani + piatto in crescendo + archi che salgono
    b.rullo(nota("Bb2"), 0.0, T0 - 0.05)
    b.piatto(T0, dur=0.9, vol=0.14, crescendo=True)
    for n in ("Bb2", "F3", "Bb3", "D4"):
        b.archi(nota(n) * 2, T0 - 0.15, vol=0.045, t0=0.05, attacco=0.6)
    for i in range(8):
        b.bip(i * OTTAVO / 2 + 0.0, vol=0.02 + 0.004 * i)
    # accordi: (ottavo d'inizio, durata in ottavi, note)
    accordi = [(0, 6, ["Bb2", "F3", "Bb3", "D4"]), (6, 3, ["G2", "D3", "G3", "Bb3"]),
               (9, 3, ["Eb2", "Bb2", "Eb3", "G3"]), (12, 4, ["F2", "C3", "F3", "A3"])]
    for i0, d, note in accordi:
        for k, n in enumerate(note):
            b.archi(nota(n) * 2, d * OTTAVO, vol=0.045, pan=-0.5 + k * 0.3, t0=e(i0))
            if k < 3:
                b.ottone(nota(n), d * OTTAVO * 0.9, vol=0.075, pan=-0.3, t0=e(i0))
        b.timpano(nota(note[0]) * (2 if nota(note[0]) < 100 else 1), e(i0), vol=0.45)
        for i in range(i0, i0 + d):  # pulsazione degli archi in ottavi (basso / ottava sopra)
            b.staccato(nota(note[0]) * (4 if i % 2 == 0 else 8), e(i), vol=0.10, pan=-0.2)
            b.staccato(nota(note[2]) * 4, e(i) + OTTAVO / 2, vol=0.05, pan=0.3)
            b.basso(nota(note[0]) * (2 if nota(note[0]) < 100 else 1), e(i), OTTAVO * 0.6, vol=0.10)
    for s in range(32):  # telegrafo in sedicesimi
        if SCHEMA_BIP[s % 8]:
            b.bip(T0 + s * OTTAVO / 2)
    # melodia della tromba (originale): (ottavo, durata in ottavi, nota)
    melodia = [(0, .8, "F4"), (1, .8, "Bb4"), (2, 1.9, "D5"), (4, .8, "C5"), (5, .8, "D5"), (6, 2.8, "G5"),
               (9, .9, "F5"), (10, .9, "Eb5"), (11, .9, "D5"), (12, 1.8, "C5"), (14, .8, "D5"), (15, .8, "Eb5")]
    for i, d, n in melodia:
        b.ottone(nota(n), d * OTTAVO, vol=0.20, pan=0.15, t0=e(i))
        b.ottone(nota(n) / 2 * 1.002, d * OTTAVO, vol=0.07, pan=-0.15, t0=e(i))
    # finale: accordo pieno, piatto, tre colpi di timpano
    tf = e(16)
    for n, v, p in (("Bb1", .09, -.3), ("F2", .08, -.3), ("Bb2", .09, -.2), ("D3", .07, -.1), ("F3", .07, 0),
                    ("Bb4", .12, .3), ("D5", .12, .35), ("F5", .2, .15), ("Bb5", .1, .2)):
        b.ottone(nota(n) * (2 if n[-1] in "12" else 1), 1.45, vol=v, pan=p, t0=tf)
    for k, n in enumerate(("Bb2", "F3", "Bb3", "D4", "F4")):
        b.archi(nota(n) * 2, 1.4, vol=0.05, pan=-0.5 + k * 0.25, t0=tf)
    b.piatto(tf, dur=1.9, vol=0.24)
    b.timpano(nota("Bb2"), tf, vol=0.6)
    b.timpano(nota("F2") * 2, tf + 2 * OTTAVO, vol=0.4)
    b.timpano(nota("Bb2"), tf + 3 * OTTAVO, vol=0.65)
    return b.master(sfuma=0.45)


def tappeto():
    """Sottofondo ciclico di 32 ottavi: Gm - Eb - Bb - F, archi pulsanti, basso e telegrafo."""
    b = Brano(32 * OTTAVO, ciclico=True)
    giro = [["G2", "D3", "G3", "Bb3"], ["Eb2", "Bb2", "Eb3", "G3"], ["Bb2", "F3", "Bb3", "D4"], ["F2", "C3", "F3", "A3"]]
    for a, note in enumerate(giro):
        t_acc = a * 8 * OTTAVO
        fond = nota(note[0]) * (2 if nota(note[0]) < 100 else 1)
        for k, n in enumerate(note):
            b.archi(nota(n) * 2, 8 * OTTAVO - 0.3, vol=0.035, pan=-0.5 + k * 0.3, t0=t_acc, attacco=0.35)
        b.timpano(fond, t_acc, vol=0.22)
        for i in range(8):
            t = t_acc + i * OTTAVO
            b.staccato(nota(note[0]) * (4 if i % 2 == 0 else 8), t, vol=0.085, pan=-0.2)
            b.staccato(nota(note[2 if i % 4 < 2 else 3]) * 4, t + OTTAVO / 2, vol=0.05, pan=0.3)
            if i % 2 == 0:
                b.basso(fond, t, OTTAVO * 0.9, vol=0.11)
        for s in range(16):
            if SCHEMA_BIP[s % 8]:
                b.bip(t_acc + s * OTTAVO / 2, vol=0.035)
    return b.master(picco=0.5, riverbero=0.45)  # più basso della sigla: è un sottofondo


def stacco():
    """Stacco di 3 secondi tra una notizia e l'altra: colpo, archi pulsanti, due note di tromba."""
    b = Brano(3.0)
    b.timpano(nota("Bb2"), 0.02, vol=0.5)
    b.piatto(0.02, dur=1.2, vol=0.10)
    for k, n in enumerate(("Bb2", "F3", "Bb3", "D4")):
        b.archi(nota(n) * 2, 1.5, vol=0.04, pan=-0.5 + k * 0.3, t0=0.02, attacco=0.05)
    for i in range(6):
        b.staccato(nota("Bb2") * (4 if i % 2 == 0 else 8), 0.02 + i * OTTAVO, vol=0.10, pan=-0.2)
        b.staccato(nota("F3") * 4, 0.02 + i * OTTAVO + OTTAVO / 2, vol=0.05, pan=0.3)
    for s in range(12):
        if SCHEMA_BIP[s % 8]:
            b.bip(0.02 + s * OTTAVO / 2, vol=0.04)
    for t0, d, n in ((0.02, 1.7, "F5"), (2 * OTTAVO, 1.7, "Bb5"), (4 * OTTAVO, 3.2, "D6")):
        b.ottone(nota(n) / 2, d * OTTAVO, vol=0.17, pan=0.15, t0=t0 if t0 > 0.02 else 0.02)
    b.timpano(nota("Bb2"), 6 * OTTAVO, vol=0.55)
    for n, pan in (("Bb3", -0.2), ("D4", 0.0), ("F4", 0.2), ("Bb4", 0.3)):
        b.ottone(nota(n), 0.9, vol=0.09, pan=pan, t0=6 * OTTAVO)
    return b.master(picco=0.8, sfuma=0.7)


def stacco_lungo():
    """Stacco leggero di 5 secondi per l'inizio di una sezione: arpeggio cristallino su archi morbidi."""
    b = Brano(5.0)
    for acc, t0, d in ((("Eb3", "Bb3", "Eb4", "G4"), 0.0, 2.3), (("Bb2", "F3", "Bb3", "D4"), 2.3, 2.6)):
        for k, n in enumerate(acc):
            b.archi(nota(n) * 2, d - 0.3, vol=0.04, pan=-0.5 + k * 0.3, t0=t0, attacco=0.5, rilascio=0.8)
    arpeggio = ["Eb5", "G5", "Bb5", "Eb6", "D6", "Bb5", "G5", "Bb5", "D5", "F5", "Bb5", "D6", "F6"]
    for i, n in enumerate(arpeggio):
        b.campana(nota(n), 0.15 + i * OTTAVO * 1.25, vol=0.11, pan=-0.3 + 0.6 * (i % 3) / 2)
    b.campana(nota("Bb6"), 0.15 + 13 * OTTAVO * 1.25, vol=0.10, dur=1.3)
    b.campana(nota("Bb4"), 0.15 + 13 * OTTAVO * 1.25, vol=0.10, dur=1.3)
    return b.master(picco=0.55, riverbero=0.8, sfuma=1.0)


if __name__ == "__main__":
    assets = Path(__file__).resolve().parent.parent / "assets"
    salva_mp3(sigla(), assets / "sigla.mp3")
    salva_mp3(stacco(), assets / "stacco.mp3", kbps=128)
    salva_mp3(stacco_lungo(), assets / "stacco-lungo.mp3", kbps=128)
    # il sottofondo è in WAV mono: l'MP3 lascerebbe un piccolo vuoto a ogni ripetizione
    import wave
    mono = tappeto().astype(np.int32).sum(axis=1) // 2
    with wave.open(str(assets / "tappeto.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(mono.astype(np.int16).tobytes())
    print(f"Scritto {assets / 'tappeto.wav'} ({len(mono) * 2 // 1024} KB)")
