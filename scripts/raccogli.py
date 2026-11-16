#!/usr/bin/env python3
"""TG di Famiglia - raccolta dati del mattino.

Legge i feed RSS delle testate e i feed dei podcast elencati in config/
e scrive data/grezzo.json. Non usa chiavi API: l'intelligenza (scelta e
riscrittura delle notizie, voce) gira poi sul telefono con la chiave Gemini
di ciascun utente.

Uso:  python scripts/raccogli.py [cartella_output]
"""
from __future__ import annotations

import calendar
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser

RADICE = Path(__file__).resolve().parent.parent
CONFIG = RADICE / "config"
UA = "Mozilla/5.0 (compatible; TGdiFamiglia/1.0; lettore RSS personale)"
ROMA = ZoneInfo("Europe/Rome")
ORA = datetime.now(timezone.utc)


def log(*a):
    print(*a, flush=True)


def scarica(url: str, timeout: int = 20) -> bytes:
    ultimo = None
    for tentativo in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - qualsiasi errore: riprovo e poi salto
            ultimo = e
            time.sleep(1.5)
    raise ultimo  # type: ignore[misc]


def pulisci(testo: str | None, massimo: int) -> str:
    if not testo:
        return ""
    t = re.sub(r"<[^>]+>", " ", testo)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > massimo:
        t = t[: massimo - 1].rsplit(" ", 1)[0] + "…"
    return t


MESI_IT = {"gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
           "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12}


def data_italiana(testo: str):
    """Alcuni feed (es. Sky TG24) scrivono 'lun, 16 nov 2026 13:03:00 GMT'."""
    m = re.search(r"(\d{1,2})\s+([a-zA-Z]{3})[a-z]*\.?\s+(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", testo or "")
    if not m or m.group(2).lower() not in MESI_IT:
        return None
    g, mese, a, hh, mm, ss = m.groups()
    d = datetime(int(a), MESI_IT[mese.lower()], int(g), int(hh), int(mm), int(ss or 0), tzinfo=timezone.utc)
    if not re.search(r"GMT|UTC|Z|\+0000", testo):
        d = d.replace(tzinfo=ROMA).astimezone(timezone.utc)
    return d.utctimetuple()


feedparser.registerDateHandler(data_italiana)


def data_voce(e) -> datetime | None:
    for campo in ("published_parsed", "updated_parsed"):
        v = e.get(campo)
        if v:
            return datetime.fromtimestamp(calendar.timegm(v), tz=timezone.utc)
    return None


# ---------------------------------------------------------------- notizie
def raccogli_notizie() -> list[dict]:
    cfg = json.loads((CONFIG / "fonti.json").read_text(encoding="utf-8"))
    limite = ORA - timedelta(hours=cfg.get("ore_massime", 30))
    per_feed = cfg.get("max_per_feed", 25)
    notizie, visti = [], set()
    for f in cfg["feed"]:
        try:
            feed = feedparser.parse(scarica(f["url"]))
        except Exception as e:  # noqa: BLE001
            log(f"  ! salto {f['fonte']} ({f['url']}): {e}")
            continue
        presi = 0
        for e in feed.entries:
            if presi >= per_feed:
                break
            titolo = pulisci(e.get("title"), 200)
            link = e.get("link", "")
            quando = data_voce(e)
            if not titolo or not link or (quando and quando < limite) or quando is None:
                continue
            chiave = re.sub(r"\W+", "", titolo.lower())[:80]
            if link in visti or chiave in visti:
                continue
            visti.update({link, chiave})
            notizie.append({
                "titolo": titolo,
                "sommario": pulisci(e.get("summary") or e.get("description"), 320),
                "link": link,
                "fonte": f["fonte"],
                "data": quando.isoformat(timespec="minutes"),
                "categoria": f["categoria"],
            })
            presi += 1
        log(f"  {f['fonte']:<24} {presi:>3} notizie  ({f['url']})")
    notizie.sort(key=lambda n: n["data"], reverse=True)
    for i, n in enumerate(notizie, 1):
        n["id"] = f"n{i}"
    return notizie


# ---------------------------------------------------------------- podcast
def normalizza(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def cerca_feed(p: dict) -> tuple[str | None, str | None]:
    """Trova il feed con la iTunes Search API. Accetta solo un risultato il cui
    titolo contiene il nome e il cui autore contiene 'autore' (la ricerca di
    iTunes è molto approssimativa e altrimenti restituisce podcast sbagliati)."""
    if p.get("feedUrl"):
        return p["feedUrl"], p.get("immagine")
    termine = p.get("cerca") or f"{p['nome']} {p.get('autore', '')}".strip()
    nome, autore = normalizza(p["nome"]), normalizza(p.get("autore", ""))
    for t in dict.fromkeys([termine, p["nome"]]):
        q = urllib.parse.urlencode({"term": t, "country": "it", "media": "podcast", "limit": 15})
        dati = json.loads(scarica(f"https://itunes.apple.com/search?{q}"))
        for r in dati.get("results", []):
            if (r.get("feedUrl") and nome in normalizza(r.get("collectionName", ""))
                    and autore in normalizza(r.get("artistName", ""))):
                return r["feedUrl"], r.get("artworkUrl600") or r.get("artworkUrl100")
    return None, None


def audio_di(e) -> str | None:
    for enc in e.get("enclosures", []) + [l for l in e.get("links", []) if l.get("rel") == "enclosure"]:
        url = enc.get("href") or enc.get("url")
        tipo = (enc.get("type") or "").lower()
        if url and (tipo.startswith("audio") or re.search(r"\.(mp3|m4a|aac|ogg)(\?|$)", url, re.I)):
            return url
    return None


def audio_https(url: str) -> str | None:
    """Il sito è HTTPS: un audio http:// verrebbe bloccato. Provo a passare a https."""
    if url.startswith("https://"):
        return url
    prova = "https://" + url.split("://", 1)[1]
    try:
        req = urllib.request.Request(prova, headers={"User-Agent": UA, "Range": "bytes=0-1"})
        with urllib.request.urlopen(req, timeout=15) as r:
            if r.status in (200, 206):
                return r.geturl()
    except Exception:  # noqa: BLE001
        pass
    return None


def raccogli_podcast() -> list[dict]:
    cfg = json.loads((CONFIG / "podcast.json").read_text(encoding="utf-8"))
    limite = ORA - timedelta(days=cfg.get("giorni_massimi", 3))
    risultato = []
    for p in cfg["podcast"]:
        try:
            feed_url, immagine = cerca_feed(p)
            if not feed_url:
                log(f"  ! {p['nome']}: non trovato su iTunes")
                continue
            feed = feedparser.parse(scarica(feed_url))
            if (feed.feed.get("itunes_block") or "").lower() == "yes":
                log(f"  ! {p['nome']}: feed bloccato")
                continue
            scelto = None
            for e in feed.entries:
                quando = data_voce(e)
                audio = audio_di(e)
                if quando and quando >= limite and audio:
                    if scelto is None or quando > scelto[0]:
                        scelto = (quando, e, audio)
            if not scelto:
                log(f"  - {p['nome']}: nessun episodio pubblico negli ultimi {cfg.get('giorni_massimi', 3)} giorni")
                continue
            quando, e, audio = scelto
            audio = audio_https(audio)
            if not audio:
                log(f"  - {p['nome']}: audio solo http, salto")
                continue
            risultato.append({
                "nome": pulisci(feed.feed.get("title"), 120) or p["nome"],
                "episodio": pulisci(e.get("title"), 200),
                "descrizione": pulisci(e.get("summary") or e.get("description"), 600),
                "audio": audio,
                "link": e.get("link") or feed.feed.get("link") or audio,
                "calcio": bool(p.get("calcio")),
                "data": quando.isoformat(timespec="minutes"),
                "immagine": immagine or (feed.feed.get("image") or {}).get("href"),
            })
            log(f"  + {p['nome']}: {risultato[-1]['episodio'][:70]}")
        except Exception as ex:  # noqa: BLE001
            log(f"  ! {p['nome']}: errore {ex}")
    for i, p in enumerate(risultato, 1):
        p["id"] = f"p{i}"
    return risultato


def main():
    uscita = Path(sys.argv[1]) if len(sys.argv) > 1 else RADICE / "data"
    uscita.mkdir(parents=True, exist_ok=True)
    log("Notizie:")
    notizie = raccogli_notizie()
    log("Podcast:")
    podcast = raccogli_podcast()
    dati = {
        "versione": 1,
        "generato": ORA.isoformat(timespec="seconds"),
        "giorno": ORA.astimezone(ROMA).date().isoformat(),
        "notizie": notizie,
        "podcast": podcast,
    }
    (uscita / "grezzo.json").write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")
    g = sum(n["categoria"] == "generale" for n in notizie)
    c = len(notizie) - g
    log(f"\nScritto {uscita / 'grezzo.json'}: {g} notizie generali, {c} di calcio, {len(podcast)} podcast")
    if g < 8 or c < 2:
        log("ERRORE: troppe poche notizie, controlla i feed")
        sys.exit(1)


if __name__ == "__main__":
    main()
