#!/usr/bin/env python3
"""TG di Famiglia - raccolta dati del mattino.

Legge i feed RSS delle testate, i feed dei podcast, il meteo e la guida TV
indicati in config/ e scrive data/grezzo.json. Non usa chiavi API:
l'intelligenza (scelta e riscrittura delle notizie, voce) gira poi sul telefono
con la chiave Gemini di ciascun utente.

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
UA_BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
ROMA = ZoneInfo("Europe/Rome")
ORA = datetime.now(timezone.utc)


def log(*a):
    print(*a, flush=True)


def leggi_config(nome: str) -> dict:
    return json.loads((CONFIG / nome).read_text(encoding="utf-8"))


def scarica(url: str, timeout: int = 20, ua: str = UA) -> bytes:
    ultimo = None
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*", "Accept-Language": "it-IT,it;q=0.9"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - qualsiasi errore: riprovo e poi salto
            ultimo = e
            time.sleep(1.5)
    raise ultimo  # type: ignore[misc]


def pulisci(testo: str | None, massimo: int) -> str:
    if not testo:
        return ""
    t = html.unescape(testo)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > massimo:
        t = t[: massimo - 1].rsplit(" ", 1)[0] + "…"
    return t


MESI = {"gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7, "ago": 8, "set": 9, "ott": 10,
        "nov": 11, "dic": 12, "jan": 1, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "dec": 12}


def data_irregolare(testo: str):
    """Date che feedparser non capisce: 'lun, 16 nov 2026 13:03:00 GMT' (Sky TG24, Il Messaggero)
    oppure 'Mon, 16 Nov 2026 16:50:49 TIME_ZONE' (Viterbo News 24)."""
    m = re.search(r"(\d{1,2})\s+([a-zA-Z]{3})[a-z]*\.?\s+(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(.*)", testo or "")
    if not m or m.group(2).lower() not in MESI:
        return None
    g, mese, a, hh, mm, ss, coda = m.groups()
    d = datetime(int(a), MESI[mese.lower()], int(g), int(hh), int(mm), int(ss or 0))
    fuso = re.match(r"([+-])(\d{2}):?(\d{2})", coda.strip())
    if fuso:
        delta = timedelta(hours=int(fuso.group(2)), minutes=int(fuso.group(3))) * (1 if fuso.group(1) == "+" else -1)
        d = d.replace(tzinfo=timezone(delta))
    elif re.match(r"(GMT|UTC|Z)\b", coda.strip()):
        d = d.replace(tzinfo=timezone.utc)
    else:
        d = d.replace(tzinfo=ROMA)  # nessun fuso indicato: ora italiana
    return d.astimezone(timezone.utc).utctimetuple()


feedparser.registerDateHandler(data_irregolare)


def data_voce(e) -> datetime | None:
    for campo in ("published_parsed", "updated_parsed"):
        v = e.get(campo)
        if v:
            return datetime.fromtimestamp(calendar.timegm(v), tz=timezone.utc)
    return None


# ---------------------------------------------------------------- notizie
class _Pagina:
    """Risultato di una pagina web letta come se fosse un feed."""

    def __init__(self, entries):
        self.entries = entries


def pagina_civonline(url: str) -> _Pagina:
    """Civonline (Civitavecchia, Tolfa, litorale) non ha un feed RSS: si leggono gli articoli dalla homepage.
    Gli articoli in homepage sono quelli recenti, quindi prendono come data l'ora della raccolta."""
    pagina = scarica(url, ua=UA_BROWSER).decode("utf-8", "replace")
    voci, visti = [], set()
    for m in re.finditer(r'<a[^>]+href="(https://www\.civonline\.it/news/([a-z\-]+)/(\d+)/[^"]+\.html)"[^>]*>(.*?)</a>', pagina, re.S):
        link, sezione, numero, testo = m.groups()
        titolo = pulisci(testo, 200)
        if sezione in ("sport", "italia-e-mondo", "rubriche") or numero in visti or len(titolo) < 20:
            continue
        visti.add(numero)
        voci.append({"title": titolo, "link": link, "summary": "", "published_parsed": ORA.utctimetuple()})
    return _Pagina(voci)


def raccogli_notizie() -> list[dict]:
    cfg = leggi_config("fonti.json")
    notizie, visti = [], set()
    for f in cfg["feed"]:
        limite = ORA - timedelta(hours=f.get("ore_massime", cfg.get("ore_massime", 30)))
        per_feed = f.get("max", cfg.get("max_per_feed", 25))
        try:
            if f.get("tipo") == "civonline":
                feed = pagina_civonline(f["url"])
            else:
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
            if not titolo or not link or quando is None or quando < limite or quando > ORA + timedelta(hours=3):
                continue
            chiave = f["categoria"] + re.sub(r"\W+", "", titolo.lower())[:80]
            if (f["categoria"], link) in visti or chiave in visti:
                continue
            visti.update({(f["categoria"], link), chiave})
            notizie.append({
                "titolo": titolo,
                "sommario": pulisci(e.get("summary") or e.get("description"), 320),
                "link": link,
                "fonte": f["fonte"],
                "data": quando.isoformat(timespec="minutes"),
                "categoria": f["categoria"],
            })
            presi += 1
        log(f"  {f['categoria']:<9} {f['fonte']:<24} {presi:>3} notizie  ({f['url']})")
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
    cfg = leggi_config("podcast.json")
    risultato = []
    for p in cfg["podcast"]:
        giorni = p.get("giorni_massimi", cfg.get("giorni_massimi", 3))
        limite = ORA - timedelta(days=giorni)
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
                log(f"  - {p['nome']}: nessun episodio pubblico negli ultimi {giorni} giorni")
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
                "gruppo": p.get("gruppo"),
                "data": quando.isoformat(timespec="minutes"),
                "immagine": immagine or (feed.feed.get("image") or {}).get("href"),
            })
            log(f"  + {p['nome']}: {risultato[-1]['episodio'][:70]}")
        except Exception as ex:  # noqa: BLE001
            log(f"  ! {p['nome']}: errore {ex}")
    for i, p in enumerate(risultato, 1):
        p["id"] = f"p{i}"
    return risultato


# ---------------------------------------------------------------- meteo
def _giorni_meteo(d: dict) -> list[dict]:
    return [{
        "data": d["time"][i], "codice": d["weather_code"][i],
        "tmax": round(d["temperature_2m_max"][i]), "tmin": round(d["temperature_2m_min"][i]),
        "pioggia_prob": d["precipitation_probability_max"][i], "pioggia_mm": d["precipitation_sum"][i],
        "vento": round(d["wind_speed_10m_max"][i]),
    } for i in range(len(d["time"]))]


def raccogli_meteo_luoghi(luoghi: list[dict]) -> list[dict]:
    """Previsioni giornaliere da Open-Meteo (gratuito, senza chiave) per tutte le località in UNA richiesta,
    con più tentativi: a volte il servizio risponde lentamente ai server di GitHub."""
    if not luoghi:
        return []
    q = urllib.parse.urlencode({
        "latitude": ",".join(str(l["lat"]) for l in luoghi), "longitude": ",".join(str(l["lon"]) for l in luoghi),
        "timezone": "Europe/Rome", "forecast_days": 8,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max",
    })
    for tentativo in range(4):
        try:
            dati = json.loads(scarica(f"https://api.open-meteo.com/v1/forecast?{q}", timeout=45))
            dati = dati if isinstance(dati, list) else [dati]
            out = [{"id": l.get("id"), "localita": l["localita"], "giorni": _giorni_meteo(d["daily"])} for l, d in zip(luoghi, dati)]
            log(f"  meteo: {', '.join(m['localita'] for m in out)} ({len(out[0]['giorni'])} giorni)")
            return out
        except Exception as e:  # noqa: BLE001
            log(f"  ! meteo, tentativo {tentativo + 1}: {e}")
            time.sleep(10 * (tentativo + 1))
    return []


def raccogli_meteo(cfg: dict) -> dict | None:
    m = raccogli_meteo_luoghi([cfg])
    return m[0] if m else None


# ---------------------------------------------------------------- stasera in TV
SPORT_TV = re.compile(r"calcio|serie a|serie b|champions|europa league|conference|nations league|coppa italia|"
                      r"qualificazion|amichevole|tennis|atp|formula 1|motogp|basket|volley|rugby|ciclismo|sci ", re.I)


def raccogli_tv(cfg: dict) -> dict | None:
    """Prima serata e sport della sera, letti dalla pagina della guida TV."""
    try:
        pagina = ""
        for url in cfg["url"] if isinstance(cfg["url"], list) else [cfg["url"]]:
            try:
                pagina += scarica(url, ua=UA_BROWSER).decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                log(f"  ! tv {url}: {e}")
        t = re.sub(r"<script.*?</script>|<style.*?</style>", "", pagina, flags=re.S | re.I)
        righe = [r.strip() for r in html.unescape(re.sub(r"<[^>]+>", "\n", t)).split("\n")]
        righe = [r for r in righe if r]
        canali = cfg["canali"]
        serata, sport, visti = [], [], set()
        canale_corrente = None
        for i, r in enumerate(righe):
            if r in canali:
                canale_corrente = r
                # blocco "prima serata": nome canale, orario, [Prima TV], [numero], titolo, descrizione
                if i + 1 < len(righe) and re.fullmatch(r"\d{1,2}[:.]\d{2}", righe[i + 1]) and r not in visti:
                    j = i + 2
                    while j < len(righe) and (righe[j] == "Prima TV" or righe[j].isdigit()):
                        j += 1
                    if j < len(righe):
                        descr = righe[j + 1] if j + 1 < len(righe) and righe[j + 1] != "[continua]" else ""
                        visti.add(r)
                        serata.append({"canale": r, "ora": righe[i + 1].replace(".", ":"), "titolo": pulisci(righe[j], 120),
                                       "descrizione": pulisci(descr, 200), "prima_tv": "Prima TV" in righe[i + 2:j]})
                continue
            m = re.fullmatch(r"(\d{2}):(\d{2}) - (.+)", r)
            if m and canale_corrente and 17 <= int(m.group(1)) <= 23 and SPORT_TV.search(m.group(3)):
                voce = {"canale": canale_corrente, "ora": f"{m.group(1)}:{m.group(2)}", "titolo": pulisci(m.group(3), 140)}
                if voce not in sport:
                    sport.append(voce)
        log(f"  tv: {len(serata)} prime serate, {len(sport)} eventi sportivi")
        return {"serata": serata, "sport": sport} if serata else None
    except Exception as e:  # noqa: BLE001
        log(f"  ! tv: {e}")
        return None


# ---------------------------------------------------------------- raccolta differenziata
def raccogli_differenziata() -> dict | None:
    """Viterbo: calendari settimanali da config/differenziata.json. Vitorchiano: il calendario con le
    date (festività comprese) scaricato dal sito del Comune, per le prossime tre settimane."""
    try:
        cfg = leggi_config("differenziata.json")
    except Exception as e:  # noqa: BLE001
        log(f"  ! differenziata: {e}")
        return None
    cfg.pop("_nota", None)
    vit = cfg.get("vitorchiano") or {}
    vit["calendario"] = []
    if vit.get("calendario_url"):
        try:
            oggi = ORA.astimezone(ROMA).date()
            fine = oggi + timedelta(days=21)
            dati = json.loads(scarica(vit["calendario_url"], ua=UA_BROWSER)).get("data", [])
            per_giorno: dict[str, list[str]] = {}
            for v in dati:
                if oggi.isoformat() <= v.get("date", "") <= fine.isoformat() and v.get("title"):
                    per_giorno.setdefault(v["date"], []).append(v["title"])
            vit["calendario"] = [{"data": d, "materiali": sorted(set(m))} for d, m in sorted(per_giorno.items())]
            log(f"  differenziata Vitorchiano: {len(vit['calendario'])} giorni di ritiro nelle prossime 3 settimane")
        except Exception as e:  # noqa: BLE001
            log(f"  ! differenziata Vitorchiano: {e}")
    vit.pop("calendario_url", None)
    orv = cfg.get("orvieto") or {}
    for z in orv.get("zone", []):
        z["calendario"] = []
        try:
            oggi = ORA.astimezone(ROMA).date()
            fine = oggi + timedelta(days=21)
            pagina = scarica(f"{orv['junker']}/{z['id']}/calendario", ua=UA_BROWSER).decode("utf-8", "replace")
            i = pagina.index("var events = ") + len("var events = ")
            eventi, _ = json.JSONDecoder().raw_decode(pagina[i:])
            per_giorno: dict[str, list[str]] = {}
            for v in eventi:
                if oggi.isoformat() <= v.get("date", "") <= fine.isoformat() and v.get("vbin_desc"):
                    per_giorno.setdefault(v["date"], []).append(v["vbin_desc"])
            z["calendario"] = [{"data": d, "materiali": sorted(set(m))} for d, m in sorted(per_giorno.items())]
        except Exception as e:  # noqa: BLE001
            log(f"  ! differenziata Orvieto {z['nome']}: {e}")
    if orv.get("zone"):
        log(f"  differenziata Orvieto: {[len(z['calendario']) for z in orv['zone']]} giorni di ritiro per zona")
    return cfg


# ---------------------------------------------------------------- scheda TECH & AI
def raccogli_tech() -> dict | None:
    """Video recenti dei canali YouTube (dai feed RSS pubblici, senza chiave) e i dati fissi della scheda."""
    try:
        cfg = leggi_config("tech.json")
    except Exception as e:  # noqa: BLE001
        log(f"  ! tech: {e}")
        return None
    limite = ORA - timedelta(days=cfg.get("youtube_giorni", 10))
    video = []
    for c in cfg.get("youtube", []):
        try:
            feed = feedparser.parse(scarica(f"https://www.youtube.com/feeds/videos.xml?channel_id={c['canale']}", ua=UA_BROWSER))
            presi = 0
            for e in feed.entries:
                quando = data_voce(e)
                vid = e.get("yt_videoid") or (e.get("id", "").split(":")[-1])
                if not vid or not quando or quando < limite or "/shorts/" in e.get("link", ""):
                    continue
                video.append({"id": vid, "titolo": pulisci(e.get("title"), 160), "canale": c["nome"],
                              "descrizione": pulisci(e.get("summary") or (e.get("media_description") or ""), 220),
                              "data": quando.isoformat(timespec="minutes"), "link": f"https://www.youtube.com/watch?v={vid}",
                              "immagine": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"})
                presi += 1
            log(f"  youtube {c['nome']:<18} {presi:>2} video recenti")
        except Exception as e:  # noqa: BLE001
            log(f"  ! youtube {c['nome']}: {e}")
    video.sort(key=lambda v: v["data"], reverse=True)
    for i, v in enumerate(video, 1):
        v["vid"] = f"y{i}"
    radio = []
    for r in cfg.get("radio", []):
        r = dict(r)
        if r.get("feed"):  # niente diretta: si ascolta l'ultima puntata
            try:
                feed = feedparser.parse(scarica(r["feed"], ua=UA_BROWSER))
                for e in feed.entries:
                    audio = audio_di(e)
                    if audio and audio.startswith("https://"):
                        r["episodio"] = {"titolo": pulisci(e.get("title"), 160), "audio": audio, "link": e.get("link") or audio,
                                         "data": (data_voce(e) or ORA).isoformat(timespec="minutes")}
                        break
            except Exception as e:  # noqa: BLE001
                log(f"  ! radio {r['nome']}: {e}")
        radio.append(r)
    return {"youtube": video, "radio": radio, "libri": cfg.get("libri", []), "concetti": cfg.get("concetti", {})}


# ---------------------------------------------------------------- archivio della settimana
def aggiorna_settimana(cfg: dict, notizie: list[dict], giorno: str, uscita: Path) -> None:
    """Rassegna della domenica: conserva i titoli degli ultimi giorni in data/settimana.json.
    Il repository non contiene dati, quindi si riparte dal file già pubblicato sul sito:
    lo si scarica, si aggiunge la giornata di oggi e si ripubblica."""
    archivio = {"giorni": {}}
    sito = cfg.get("url_sito") or pagina_del_sito()
    if sito:
        try:
            archivio = json.loads(scarica(sito.rstrip("/") + "/data/settimana.json", timeout=20))
        except Exception as e:  # noqa: BLE001 - prima esecuzione o sito non raggiungibile
            log(f"  - settimana: archivio precedente non disponibile ({e}), riparto da oggi")
    giorni = archivio.get("giorni", {})
    oggi = {}
    for cat, quante in cfg.get("per_giorno", {}).items():
        oggi[cat] = [{"t": n["titolo"], "s": n["sommario"][:140], "f": n["fonte"]}
                     for n in notizie if n["categoria"] == cat][:quante]
    giorni[giorno] = oggi
    tenuti = sorted(giorni)[-cfg.get("giorni", 7):]
    archivio = {"aggiornato": ORA.isoformat(timespec="seconds"), "giorni": {g: giorni[g] for g in tenuti}}
    (uscita / "settimana.json").write_text(json.dumps(archivio, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log(f"  settimana: {len(tenuti)} giorni in archivio ({', '.join(tenuti)})")


def pagina_del_sito() -> str | None:
    """Indirizzo di GitHub Pages ricavato dalle variabili di GitHub Actions (utente/repo)."""
    import os
    repo = os.environ.get("GITHUB_REPOSITORY")  # es. andreapollastrelli95/tg-di-famiglia
    if not repo or "/" not in repo:
        return None
    utente, nome = repo.split("/", 1)
    return f"https://{utente.lower()}.github.io/{nome}"


def main():
    uscita = Path(sys.argv[1]) if len(sys.argv) > 1 else RADICE / "data"
    uscita.mkdir(parents=True, exist_ok=True)
    varie = leggi_config("varie.json")
    log("Notizie:")
    notizie = raccogli_notizie()
    log("Podcast:")
    podcast = raccogli_podcast()
    log("Varie:")
    dati = {
        "versione": 4,
        "generato": ORA.isoformat(timespec="seconds"),
        "giorno": ORA.astimezone(ROMA).date().isoformat(),
        "notizie": notizie,
        "podcast": podcast,
        "squadre": varie.get("squadre", []),
        "radio_preferite": varie.get("radio_preferite", []),
        "differenziata": raccogli_differenziata(),
        "tech": raccogli_tech(),
        "sentieri": leggi_config("sentieri.json").get("sentieri", []),
        "piatti": leggi_config("ricette.json").get("piatti", []),
        "meteo_luoghi": raccogli_meteo_luoghi(varie.get("meteo_luoghi") or ([dict(varie["meteo"], id="viterbo")] if varie.get("meteo") else [])),
        "tv": raccogli_tv(varie["tv"]) if varie.get("tv") else None,
    }
    dati["meteo"] = next((m for m in dati["meteo_luoghi"] if m.get("id") == "viterbo"), dati["meteo_luoghi"][0] if dati["meteo_luoghi"] else None)
    (uscita / "grezzo.json").write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")
    if varie.get("settimana"):
        aggiorna_settimana(varie["settimana"], notizie, dati["giorno"], uscita)
    conta = {}
    for n in notizie:
        conta[n["categoria"]] = conta.get(n["categoria"], 0) + 1
    log(f"\nScritto {uscita / 'grezzo.json'}: notizie {conta}, {len(podcast)} podcast "
        f"({sum(1 for p in podcast if p['gruppo'])} di squadra)")
    if conta.get("generale", 0) < 5 or conta.get("sport", 0) < 2:
        log("ERRORE: troppe poche notizie nazionali o sportive, controlla i feed")
        sys.exit(1)
    if conta.get("tuscia", 0) < 3:
        log("ATTENZIONE: meno di 3 notizie dalla Tuscia")


if __name__ == "__main__":
    main()
