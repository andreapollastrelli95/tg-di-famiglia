#!/usr/bin/env python3
"""Genera i PACCHETTI SONORI del TG di Famiglia: musica ORIGINALE sintetizzata con numpy.

Ogni pacchetto (assets/suoni/N/) contiene quattro pezzi abbinati tra loro, con la stessa tonalità,
lo stesso tempo, gli stessi strumenti e lo stesso tema melodico:

  sigla.mp3         sigla d'apertura (6-8 secondi)
  stacco.mp3        stacco di 3 secondi tra un titolo/una notizia e l'altra (riprende il tema)
  stacco-lungo.mp3  stacco leggero di 5 secondi per l'inizio di una sezione (Tuscia, sport)
  tappeto.wav       sottofondo d'attesa che si ripete senza stacchi

L'app ne sceglie uno al giorno, a caso, sempre diverso dal giorno prima.
Melodie, armonie e arrangiamenti sono composti apposta: non riprendono sigle esistenti.

Uso:  pip install numpy lameenc   e poi   python tools/genera_suoni.py
"""
import json
import wave
from pathlib import Path

import numpy as np

SR = 44100
SR_TAPPETO = 22050           # il sottofondo è più leggero: mono a 22 kHz
CARTELLA = Path(__file__).resolve().parent.parent / "assets" / "suoni"

# ---------------------------------------------------------------- i pacchetti
# tonica = nota MIDI della tonica (60 = Do centrale); modo maggiore/minore; tempo in battiti al minuto.
STILI = [
    {"nome": "Classico", "tonica": 58, "modo": "maggiore", "bpm": 126, "melodia": "A", "lead": "ottone", "raddoppio": "ottone",
     "pad": "archi", "comp": "staccato", "basso": "basso", "perc": "orchestra", "bip": True},
    {"nome": "Sinfonico", "tonica": 62, "modo": "maggiore", "bpm": 112, "melodia": "B", "lead": "archi", "raddoppio": "corno",
     "pad": "archi", "comp": "staccato", "basso": "basso", "perc": "orchestra", "bip": False},
    {"nome": "Elettronico", "tonica": 57, "modo": "minore", "bpm": 122, "melodia": "E", "lead": "synth", "raddoppio": None,
     "pad": "pad", "comp": "pulsar", "basso": "basso_synth", "perc": "elettronica", "bip": True},
    {"nome": "Pianoforte", "tonica": 51, "modo": "maggiore", "bpm": 100, "melodia": "C", "lead": "piano", "raddoppio": None,
     "pad": "archi", "comp": "piano", "basso": "basso", "perc": "leggera", "bip": False},
    {"nome": "Fanfara", "tonica": 60, "modo": "maggiore", "bpm": 132, "melodia": "B", "lead": "ottone", "raddoppio": "ottone",
     "pad": "archi", "comp": "staccato", "basso": "basso", "perc": "orchestra", "bip": True},
    {"nome": "Serale", "tonica": 53, "modo": "maggiore", "bpm": 108, "melodia": "A", "lead": "corno", "raddoppio": None,
     "pad": "pad", "comp": "piano", "basso": "basso", "perc": "leggera", "bip": False},
    {"nome": "Ultima ora", "tonica": 55, "modo": "minore", "bpm": 128, "melodia": "D", "lead": "ottone", "raddoppio": "synth",
     "pad": "archi", "comp": "staccato", "basso": "basso_synth", "perc": "elettronica", "bip": True},
    {"nome": "Mattino", "tonica": 52, "modo": "maggiore", "bpm": 116, "melodia": "C", "lead": "marimba", "raddoppio": "campana",
     "pad": "pad", "comp": "marimba", "basso": "basso", "perc": "leggera", "bip": False},
    {"nome": "Notturno", "tonica": 48, "modo": "minore", "bpm": 104, "melodia": "D", "lead": "piano", "raddoppio": None,
     "pad": "pad", "comp": "piano", "basso": "basso", "perc": "leggera", "bip": True},
    {"nome": "Avventura", "tonica": 50, "modo": "minore", "bpm": 120, "melodia": "E", "lead": "corno", "raddoppio": "archi",
     "pad": "archi", "comp": "staccato", "basso": "basso", "perc": "orchestra", "bip": False},
]

# Melodie: (ottavo d'inizio, durata in ottavi, semitoni dalla tonica dell'ottava sopra), poi la nota finale.
MELODIE = {
    "A": ([(0, .8, -5), (1, .8, 0), (2, 1.9, 4), (4, .8, 2), (5, .8, 4), (6, 2.8, 9), (9, .9, 7), (10, .9, 5),
           (11, .9, 4), (12, 1.8, 2), (14, .8, 4), (15, .8, 5)], 7),
    "B": ([(0, .9, 0), (1, .9, 4), (2, .9, 7), (3, 2.6, 12), (6, .9, 9), (7, .9, 12), (8, .9, 9), (9, 1.8, 5),
           (11, .9, 9), (12, .9, 7), (13, .9, 11), (14, 1.8, 14)], 12),
    "C": ([(0, 1.8, 4), (2, 1.8, 7), (4, 1.8, 9), (6, 2.7, 12), (9, .9, 9), (10, .9, 7), (11, .9, 5), (12, 2.7, 7),
           (15, .9, 11)], 12),
    "D": ([(0, .9, 0), (1, .9, 3), (2, 1.8, 7), (4, .9, 8), (5, .9, 7), (6, 2.7, 3), (9, .9, 5), (10, .9, 8),
           (11, .9, 12), (12, 1.8, 11), (14, 1.8, 7)], 12),
    "E": ([(0, .45, 7), (.5, .45, 7), (1, .9, 7), (2, .9, 3), (3, .9, 0), (4, 1.8, 7), (6, .9, 8), (7, .9, 12),
           (8, .9, 15), (9, 1.8, 12), (11, .9, 8), (12, 1.8, 11), (14, .9, 14), (15, .9, 11)], 12),
}
# Giro armonico della sigla: (ottavo d'inizio, durata in ottavi, fondamentale in semitoni, qualità)
GIRI = {
    "maggiore": [(0, 6, 0, "M"), (6, 3, 9, "m"), (9, 3, 5, "M"), (12, 4, 7, "M")],
    "minore": [(0, 6, 0, "m"), (6, 3, 8, "M"), (9, 3, 5, "m"), (12, 4, 7, "M")],
}
# Giro del sottofondo (32 ottavi, si ripete)
GIRI_TAPPETO = {
    "maggiore": [(9, "m"), (5, "M"), (0, "M"), (7, "M")],
    "minore": [(0, "m"), (8, "M"), (5, "m"), (7, "M")],
}
QUALITA = {"M": [0, 4, 7], "m": [0, 3, 7]}
SCHEMA_BIP = [1, 0, 1, 1, 0, 1, 0, 0]  # ritmo del "telegrafo" in sedicesimi


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def adsr(n, a, d, s, r, sr):
    a, d, r = int(a * sr), int(d * sr), int(r * sr)
    env = np.concatenate([np.linspace(0, 1, a, endpoint=False) ** 1.5, np.linspace(1, s, d, endpoint=False),
                          np.full(max(n - a - d - r, 0), s), np.linspace(s, 0, r)])
    return env[:n] if len(env) >= n else np.pad(env, (0, n - len(env)))


class Brano:
    """Un pezzo stereo. ciclico=True: la coda dei suoni rientra dall'inizio (per il sottofondo che si ripete)."""

    def __init__(self, durata, sr=SR, ciclico=False, seme=1):
        self.sr = sr
        self.n = int(sr * durata)
        self.buf = np.zeros((self.n, 2))
        self.ciclico = ciclico
        self.rng = np.random.default_rng(seme)

    def t(self, dur):
        return np.arange(int(dur * self.sr)) / self.sr

    def mixa(self, x, t0, pan=0.0):
        i = int(round(t0 * self.sr))
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

    # ------------------------------------------------------------ strumenti melodici
    def ottone(self, f, dur, vol=0.2, pan=0.0, t0=0.0, morbido=False):
        t = self.t(dur + 0.22)
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.3, 0, 1)
        fase = 2 * np.pi * f * np.cumsum(vib) / self.sr
        brill = np.clip(t / (0.09 if morbido else 0.05), 0, 1)
        out = np.zeros(len(t))
        for k in range(1, 14):
            if f * k > min(11000, self.sr / 2.2):
                break
            ampiezza = 1 / k ** (1.8 if morbido else 1.05)
            out += ampiezza * (brill if k > 3 else 1) * np.sin(k * fase + self.rng.uniform(0, 0.3))
        a = 0.06 if morbido else 0.03
        self.mixa(out * adsr(len(t), a, 0.1, 0.78, 0.2, self.sr) * vol, t0, pan)

    def corno(self, f, dur, vol=0.2, pan=0.0, t0=0.0):
        self.ottone(f, dur, vol * 1.3, pan, t0, morbido=True)

    def archi(self, f, dur, vol=0.06, pan=0.0, t0=0.0, attacco=0.22, rilascio=0.4, voci=5):
        t = self.t(dur + rilascio)
        out = np.zeros(len(t))
        stonature = (-0.012, -0.005, 0, 0.006, 0.013)[:voci] if voci > 1 else (0,)
        vib = 1 + 0.003 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t / 0.4, 0, 1) if voci == 1 else 1
        for det in stonature:
            fase = 2 * np.pi * f * (1 + det / 2) * np.cumsum(np.ones(len(t)) * vib) / self.sr + self.rng.uniform(0, 6.28)
            for k in range(1, 10):
                if f * k > self.sr / 2.2:
                    break
                out += np.sin(k * fase) / k * (0.85 ** k)
        self.mixa(out / len(stonature) * adsr(len(t), attacco, 0.1, 0.8, rilascio, self.sr) * vol, t0, pan)

    def archi_solo(self, f, dur, vol=0.2, pan=0.0, t0=0.0):
        self.archi(f, dur, vol * 1.6, pan, t0, attacco=0.07, rilascio=0.25, voci=3)

    def staccato(self, f, t0, vol=0.09, pan=0.0):
        self.archi(f, 0.07, vol=vol, pan=pan, t0=t0, attacco=0.008, rilascio=0.09)

    def synth(self, f, dur, vol=0.2, pan=0.0, t0=0.0):
        t = self.t(dur + 0.15)
        out = np.zeros(len(t))
        for det in (-0.004, 0.004):
            fase = 2 * np.pi * f * (1 + det) * t
            for k in range(1, 18):
                if f * k > self.sr / 2.2:
                    break
                out += np.sin(k * fase) / k * np.exp(-t * k * 0.9)  # le armoniche alte si spengono: "filtro" che si chiude
        self.mixa(out * 0.6 * adsr(len(t), 0.008, 0.15, 0.65, 0.15, self.sr) * vol, t0, pan)

    def pulsar(self, f, t0, vol=0.08, pan=0.0):
        t = self.t(0.16)
        out = sum(np.sin(2 * np.pi * f * k * t) / k for k in (1, 3, 5, 7) if f * k < self.sr / 2.2)
        self.mixa(out * np.exp(-t * 22) * np.minimum(t / 0.003, 1) * vol, t0, pan)

    def piano(self, f, dur, vol=0.2, pan=0.0, t0=0.0):
        t = self.t(min(dur + 1.2, 3.0))
        out = np.zeros(len(t))
        for k in range(1, 11):
            fk = f * k * (1 + 0.0004 * k * k)  # leggera inarmonicità delle corde
            if fk > self.sr / 2.2:
                break
            out += np.sin(2 * np.pi * fk * t) / k ** 1.3 * np.exp(-t * (1.1 + 0.7 * k))
        rilascio = np.clip((dur + 0.15 - t) / 0.15, 0, 1) ** 0.5 * 0.85 + 0.15 * np.exp(-np.maximum(t - dur, 0) * 4)
        self.mixa(out * np.minimum(t / 0.003, 1) * rilascio * vol * 1.4, t0, pan)

    def marimba(self, f, dur, vol=0.2, pan=0.0, t0=0.0):
        t = self.t(1.0)
        out = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 18) + 0.15 * np.sin(2 * np.pi * f * 9.9 * t) * np.exp(-t * 40)
        self.mixa(out * np.exp(-t * (4.5 if f < 600 else 6)) * np.minimum(t / 0.002, 1) * vol * 1.5, t0, pan)

    def campana(self, f, t0, vol=0.12, pan=0.0, dur=1.6):
        t = self.t(dur)
        out = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 9) + 0.2 * np.sin(4 * np.pi * f * t) * np.exp(-t * 5)
        self.mixa(out * np.exp(-t * 3.2) * np.minimum(t / 0.003, 1) * vol, t0, pan)

    def pad(self, f, dur, vol=0.06, pan=0.0, t0=0.0, attacco=0.4, rilascio=0.6):
        t = self.t(dur + rilascio)
        out = np.zeros(len(t))
        for det in (-0.007, 0, 0.007):
            fase = 2 * np.pi * f * (1 + det) * t + self.rng.uniform(0, 6.28)
            for k in range(1, 7):
                out += np.sin(k * fase) / k ** 1.6
        self.mixa(out / 3 * adsr(len(t), attacco, 0.1, 0.85, rilascio, self.sr) * vol * 1.1, t0, pan)

    def lead(self, nome, f, dur, vol, pan, t0):
        if nome == "campana":
            self.campana(f, t0, vol=vol * 0.8, pan=pan, dur=max(dur, 0.8) + 0.6)
        else:
            {"ottone": self.ottone, "corno": self.corno, "archi": self.archi_solo, "synth": self.synth,
             "piano": self.piano, "marimba": self.marimba}[nome](f, dur, vol, pan, t0)

    def tappeto_armonico(self, nome, f, dur, vol, pan, t0, attacco=0.22, rilascio=0.4):
        if nome == "pad":
            self.pad(f, dur, vol, pan, t0, attacco=max(attacco, 0.3), rilascio=rilascio + 0.2)
        else:
            self.archi(f, dur, vol, pan, t0, attacco=attacco, rilascio=rilascio)

    # ------------------------------------------------------------ bassi e percussioni
    def basso(self, f, t0, dur, vol=0.16, synth=False):
        t = self.t(dur + 0.1)
        if synth:
            out = sum(np.sin(2 * np.pi * f * k * t) / k for k in (1, 2, 3, 5)) * 0.8
        else:
            out = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t)
        self.mixa(out * adsr(len(t), 0.01, 0.08, 0.7, 0.09, self.sr) * vol, t0, 0)

    def timpano(self, f, t0, vol=0.5):
        t = self.t(1.5)
        ff = f * (1 + 0.06 * np.exp(-t * 30))
        fase = 2 * np.pi * np.cumsum(ff) / self.sr
        corpo = np.sin(fase) + 0.35 * np.sin(1.5 * fase)
        colpo = self.rng.normal(0, 1, len(t)) * np.exp(-t * 60) * 0.3
        self.mixa((corpo * np.exp(-t * 2.8) + colpo) * vol, t0, -0.15)

    def rullo(self, f, t0, dur, da=0.05, a=0.35):
        colpi = int(dur * 18)
        for i in range(colpi):
            x = i / max(colpi - 1, 1)
            self.timpano(f, t0 + i / 18 + self.rng.uniform(0, 0.008), vol=(da + (a - da) * x ** 2) * 0.6)

    def rumore_alto(self, n):
        r = self.rng.normal(0, 1, n)
        for _ in range(3):
            r = np.diff(r, prepend=0)
        return r / (np.max(np.abs(r)) + 1e-9)

    def piatto(self, t0, dur=2.2, vol=0.2, crescendo=False):
        t = self.t(dur)
        env = (t / dur) ** 2.5 if crescendo else np.exp(-t * 2.2)
        self.mixa(self.rumore_alto(len(t)) * env * vol, t0 - (dur if crescendo else 0), 0.25)

    def cassa(self, t0, vol=0.5):
        t = self.t(0.35)
        f = 45 + 110 * np.exp(-t * 28)
        self.mixa(np.sin(2 * np.pi * np.cumsum(f) / self.sr) * np.exp(-t * 9) * vol, t0, 0)

    def charleston(self, t0, vol=0.07, lungo=False):
        t = self.t(0.18 if lungo else 0.06)
        self.mixa(self.rumore_alto(len(t)) * np.exp(-t * (18 if lungo else 60)) * vol, t0, 0.3)

    def shaker(self, t0, vol=0.04):
        t = self.t(0.09)
        self.mixa(self.rumore_alto(len(t)) * np.sin(np.pi * t / 0.09) * vol, t0, -0.3)

    def bip(self, t0, f=1864.66, vol=0.045, pan=0.45):
        t = self.t(0.05)
        env = np.minimum(t / 0.004, 1) * np.minimum((0.05 - t) / 0.012, 1)
        self.mixa(np.sin(2 * np.pi * f * t) * env * vol, t0, pan)

    # ------------------------------------------------------------ uscita
    def master(self, picco=0.92, riverbero=0.6, sfuma=0.0):
        st = self.buf.copy()
        rev = np.zeros_like(st)
        for ritardo, g in ((0.031, 0.35), (0.047, 0.3), (0.071, 0.25), (0.113, 0.18), (0.167, 0.12)):
            k = int(ritardo * self.sr)
            if self.ciclico:
                rev += np.roll(st[:, ::-1], k, axis=0) * g
            else:
                rev[k:] += st[:-k, ::-1] * g
        st = st + rev * riverbero
        st = np.tanh(st * 1.6) / np.tanh(1.6)
        if sfuma:
            k = int(sfuma * self.sr)
            st[-k:] *= np.linspace(1, 0, k)[:, None] ** 2
        st *= picco / np.max(np.abs(st))
        return (st * 32767).astype(np.int16)


# ---------------------------------------------------------------- arrangiamento comune
class Kit:
    def __init__(self, stile):
        self.s = stile
        self.ottavo = 60 / stile["bpm"] / 2
        self.tonica = stile["tonica"]
        self.melodia, self.finale = MELODIE[stile["melodia"]]
        self.giro = GIRI[stile["modo"]]
        self.qualita_tonica = "M" if stile["modo"] == "maggiore" else "m"

    def nota_melodia(self, semitoni):
        return hz(self.tonica + 12 + semitoni)

    def accordo(self, radice, qualita, ottava=12):
        return [hz(self.tonica + radice + ottava + x) for x in QUALITA[qualita]]

    def fondamentale(self, radice):
        m = self.tonica + radice - 12
        while m > 50:
            m -= 12
        while m < 33:
            m += 12
        return hz(m)

    def pulsazione(self, b, radice, qualita, t, i, vol=1.0):
        """Accompagnamento ritmico su un ottavo."""
        c, s = self.s["comp"], self.s
        tono = self.accordo(radice, qualita)
        if c == "staccato":
            b.staccato(tono[0] * (2 if i % 2 == 0 else 4), t, vol=0.10 * vol, pan=-0.2)
            b.staccato(tono[2] * 2, t + self.ottavo / 2, vol=0.05 * vol, pan=0.3)
        elif c == "pulsar":
            b.pulsar(tono[0] * 2, t, vol=0.08 * vol, pan=-0.2)
            b.pulsar(tono[1 + i % 2] * 2, t + self.ottavo / 2, vol=0.05 * vol, pan=0.3)
        elif c == "piano":
            if i % 2 == 0:
                for k, f in enumerate(tono):
                    b.piano(f, self.ottavo * 1.6, vol=0.06 * vol, pan=-0.3 + k * 0.3, t0=t + k * 0.012)
        elif c == "marimba":
            b.marimba(tono[i % 3] * 2, self.ottavo, vol=0.07 * vol, pan=-0.3 + 0.3 * (i % 3), t0=t)
        if s["perc"] == "elettronica":
            if i % 2 == 0:
                b.cassa(t, vol=0.45 * vol)
            b.charleston(t + self.ottavo / 2, vol=0.06 * vol)
        elif s["perc"] == "leggera":
            b.shaker(t, vol=0.035 * vol)

    def colpo(self, b, radice, t, vol=0.45):
        """Accento sui cambi d'accordo."""
        p = self.s["perc"]
        if p == "orchestra":
            b.timpano(self.fondamentale(radice) * (2 if self.fondamentale(radice) < 90 else 1), t, vol=vol)
        elif p == "elettronica":
            b.cassa(t, vol=vol + 0.15)
            b.timpano(self.fondamentale(radice) * 2, t, vol=vol * 0.4)
        else:
            b.marimba(self.fondamentale(radice) * 2, 0.4, vol=vol * 0.25, t0=t)

    # ------------------------------------------------------------ i quattro pezzi
    def sigla(self):
        o = self.ottavo
        T0 = 4 * o
        e = lambda i: T0 + i * o  # noqa: E731
        b = Brano(T0 + 16 * o + 1.75, seme=self.tonica)
        s = self.s
        # introduzione
        if s["perc"] == "orchestra":
            b.rullo(self.fondamentale(0) * 2, 0.0, T0 - 0.05)
            b.piatto(T0, dur=T0, vol=0.14, crescendo=True)
        elif s["perc"] == "elettronica":
            b.piatto(T0, dur=T0, vol=0.16, crescendo=True)
            for i in range(4):
                b.cassa(i * o, vol=0.25 + 0.08 * i)
        else:
            for i in range(8):
                b.shaker(i * o / 2, vol=0.015 + 0.006 * i)
            for i, x in enumerate(QUALITA[self.qualita_tonica] + [12]):
                b.campana(hz(self.tonica + 24 + x), i * o, vol=0.06)
        for k, f in enumerate(self.accordo(0, self.qualita_tonica)):
            b.tappeto_armonico(s["pad"], f, T0 - 0.15, vol=0.045, pan=-0.4 + k * 0.4, t0=0.05, attacco=T0 * 0.7)
        if s["bip"]:
            for i in range(8):
                b.bip(i * o / 2, vol=0.02 + 0.004 * i)
        # corpo: giro armonico, pulsazione, basso, melodia
        for i0, d, radice, q in self.giro:
            for k, f in enumerate(self.accordo(radice, q)):
                b.tappeto_armonico(s["pad"], f, d * o, vol=0.045, pan=-0.5 + k * 0.4, t0=e(i0))
            self.colpo(b, radice, e(i0))
            for i in range(i0, i0 + d):
                self.pulsazione(b, radice, q, e(i), i)
                b.basso(self.fondamentale(radice), e(i), o * 0.6, vol=0.10, synth=s["basso"] == "basso_synth")
        if s["bip"]:
            for x in range(32):
                if SCHEMA_BIP[x % 8]:
                    b.bip(T0 + x * o / 2)
        for i, d, semi in self.melodia:
            b.lead(s["lead"], self.nota_melodia(semi), d * o, 0.20, 0.15, e(i))
            if s["raddoppio"]:
                b.lead(s["raddoppio"], self.nota_melodia(semi) / 2 * 1.002, d * o, 0.07, -0.15, e(i))
        # finale: accordo pieno e colpi di chiusura
        tf = e(16)
        b.lead(s["lead"], self.nota_melodia(self.finale), 1.45, 0.20, 0.15, tf)
        for k, f in enumerate(self.accordo(0, self.qualita_tonica, 0) + self.accordo(0, self.qualita_tonica, 12)):
            b.lead(s["lead"] if s["lead"] in ("ottone", "corno", "archi") else "corno", f, 1.4, 0.07, -0.4 + k * 0.15, tf)
        for k, f in enumerate(self.accordo(0, self.qualita_tonica)):
            b.tappeto_armonico(s["pad"], f, 1.4, vol=0.05, pan=-0.5 + k * 0.4, t0=tf)
        b.basso(self.fondamentale(0), tf, 1.3, vol=0.14, synth=s["basso"] == "basso_synth")
        if s["perc"] == "orchestra":
            b.piatto(tf, dur=1.8, vol=0.22)
            b.timpano(self.fondamentale(0) * 2, tf, vol=0.6)
            b.timpano(hz(self.tonica - 5), tf + 2 * o, vol=0.4)
            b.timpano(self.fondamentale(0) * 2, tf + 3 * o, vol=0.65)
        elif s["perc"] == "elettronica":
            b.piatto(tf, dur=1.6, vol=0.2)
            for k in (0, 2, 3):
                b.cassa(tf + k * o, vol=0.6)
        else:
            b.campana(hz(self.tonica + 24), tf, vol=0.09)
            b.campana(hz(self.tonica + 31), tf + o, vol=0.07)
        return b.master(sfuma=0.35)

    def stacco(self):
        """3 secondi: accento, le prime note del tema e l'accordo di arrivo che si spegne dentro i 3 secondi."""
        o = min(self.ottavo, 0.25)
        b = Brano(3.0, seme=self.tonica + 1)
        s = self.s
        self.colpo(b, 0, 0.0, vol=0.5)
        if s["perc"] == "orchestra":
            b.piatto(0.0, dur=1.0, vol=0.10)
        elif s["perc"] == "elettronica":
            b.charleston(0.0, vol=0.08, lungo=True)
        for k, f in enumerate(self.accordo(0, self.qualita_tonica)):
            b.tappeto_armonico(s["pad"], f, 1.3, vol=0.04, pan=-0.5 + k * 0.4, t0=0.0, attacco=0.04, rilascio=0.5)
        for i in range(6):
            self.pulsazione(b, 0, self.qualita_tonica, i * o, i, vol=0.9)
        if s["bip"]:
            for x in range(12):
                if SCHEMA_BIP[x % 8]:
                    b.bip(x * o / 2, vol=0.035)
        note = []
        for _, _, semi in self.melodia:
            if semi not in note:
                note.append(semi)
            if len(note) == 3:
                break
        for k, semi in enumerate(note):
            b.lead(s["lead"], self.nota_melodia(semi), 1.7 * o if k < 2 else 3 * o, 0.17, 0.15, k * 2 * o)
        arrivo = 6 * o
        self.colpo(b, 0, arrivo, vol=0.5)
        b.lead(s["lead"], self.nota_melodia(self.finale), 0.9, 0.16, 0.15, arrivo)
        for k, f in enumerate(self.accordo(0, self.qualita_tonica, 12)):
            b.tappeto_armonico(s["pad"], f, 0.8, vol=0.05, pan=-0.3 + k * 0.3, t0=arrivo, attacco=0.03, rilascio=0.5)
        b.basso(self.fondamentale(0), arrivo, 0.9, vol=0.12, synth=s["basso"] == "basso_synth")
        return b.master(picco=0.8, sfuma=0.25)

    def stacco_lungo(self):
        """5 secondi, leggero: arpeggio cristallino sul IV e poi sul I, sopra un tappeto morbido."""
        b = Brano(5.0, seme=self.tonica + 2)
        s = self.s
        quarto = (5, "M" if s["modo"] == "maggiore" else "m")
        for (radice, q), t0, d in ((quarto, 0.0, 2.3), ((0, self.qualita_tonica), 2.3, 2.5)):
            for k, f in enumerate(self.accordo(radice, q)):
                b.tappeto_armonico(s["pad"], f, d - 0.3, vol=0.04, pan=-0.5 + k * 0.4, t0=t0, attacco=0.5, rilascio=0.5)
            b.basso(self.fondamentale(radice), t0, d - 0.2, vol=0.06, synth=s["basso"] == "basso_synth")
        passo = 0.29
        arpeggio = [hz(self.tonica + 24 + 5 + x) for x in QUALITA[quarto[1]]] + [hz(self.tonica + 36 + 5)] + \
                   [hz(self.tonica + 24 + 5 + x) for x in QUALITA[quarto[1]]][::-1][1:] + \
                   [hz(self.tonica + 24 + x) for x in QUALITA[self.qualita_tonica]] + [hz(self.tonica + 36)] + \
                   [hz(self.tonica + 24 + x) for x in QUALITA[self.qualita_tonica]][::-1][1:]
        voce = "campana" if s["lead"] not in ("piano", "marimba") else s["lead"]
        for i, f in enumerate(arpeggio[:13]):
            b.lead(voce, f, 0.5, 0.10, -0.3 + 0.3 * (i % 3), 0.12 + i * passo)
        b.lead(voce, hz(self.tonica + 36), 1.0, 0.09, 0.0, 0.12 + 13 * passo)
        b.lead(voce, hz(self.tonica + 24), 1.0, 0.09, 0.0, 0.12 + 13 * passo)
        return b.master(picco=0.55, riverbero=0.8, sfuma=0.5)

    def tappeto(self):
        """Sottofondo d'attesa: 32 ottavi che si ripetono senza stacchi, più piano della sigla."""
        o = self.ottavo
        b = Brano(32 * o, sr=SR_TAPPETO, ciclico=True, seme=self.tonica + 3)
        s = self.s
        for a, (radice, q) in enumerate(GIRI_TAPPETO[s["modo"]]):
            t_acc = a * 8 * o
            for k, f in enumerate(self.accordo(radice, q)):
                b.tappeto_armonico(s["pad"], f, 8 * o - 0.3, vol=0.035, pan=-0.5 + k * 0.3, t0=t_acc, attacco=0.35)
            self.colpo(b, radice, t_acc, vol=0.22)
            for i in range(8):
                self.pulsazione(b, radice, q, t_acc + i * o, i, vol=0.85)
                if i % 2 == 0:
                    b.basso(self.fondamentale(radice), t_acc + i * o, o * 0.9, vol=0.11, synth=s["basso"] == "basso_synth")
            if s["bip"]:
                for x in range(16):
                    if SCHEMA_BIP[x % 8]:
                        b.bip(t_acc + x * o / 2, vol=0.03)
        return b.master(picco=0.5, riverbero=0.45)


def salva_mp3(pcm, file, kbps):
    import lameenc
    enc = lameenc.Encoder()
    enc.set_bit_rate(kbps); enc.set_in_sample_rate(SR); enc.set_channels(2); enc.set_quality(2)
    file.write_bytes(enc.encode(pcm.tobytes()) + enc.flush())
    return len(pcm) / SR


def salva_wav_mono(pcm, file):
    mono = (pcm.astype(np.int32).sum(axis=1) // 2).astype(np.int16)
    with wave.open(str(file), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR_TAPPETO); w.writeframes(mono.tobytes())
    return len(mono) / SR_TAPPETO


def main():
    elenco = []
    for n, stile in enumerate(STILI, 1):
        kit = Kit(stile)
        cartella = CARTELLA / str(n)
        cartella.mkdir(parents=True, exist_ok=True)
        durate = {
            "sigla": salva_mp3(kit.sigla(), cartella / "sigla.mp3", 160),
            "stacco": salva_mp3(kit.stacco(), cartella / "stacco.mp3", 128),
            "stacco-lungo": salva_mp3(kit.stacco_lungo(), cartella / "stacco-lungo.mp3", 128),
            "tappeto": salva_wav_mono(kit.tappeto(), cartella / "tappeto.wav"),
        }
        kb = sum(f.stat().st_size for f in cartella.iterdir()) // 1024
        print(f"{n:>2}. {stile['nome']:<12} {', '.join(f'{k} {v:.1f}s' for k, v in durate.items())}  ({kb} KB)")
        elenco.append({"n": n, "nome": stile["nome"]})
    (CARTELLA / "elenco.json").write_text(json.dumps(elenco, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Scritti {len(STILI)} pacchetti in {CARTELLA}")


if __name__ == "__main__":
    main()
