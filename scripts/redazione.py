#!/usr/bin/env python3
"""TG di Famiglia - edizione del giorno preparata sul server, con voce neurale.

Dopo la raccolta (scripts/raccogli.py) questo script:
  1. fa scrivere a Gemini l'edizione del giorno (stesse regole dell'app: scaletta, notizie,
     Accadde oggi, podcast, sezioni di calcio, meteo, TV, rassegne della settimana);
  2. fa leggere OGNI testo a una voce neurale italiana gratuita con edge-tts
     (it-IT-ElsaNeural, riserva it-IT-IsabellaNeural) e salva gli MP3 in data/audio/;
  3. scrive data/edizione.json, che l'app usa al posto della generazione sul telefono.

Serve la chiave Gemini nel segreto GEMINI_API_KEY del repository. Se manca, o se Gemini
non risponde, lo script NON fallisce: non scrive l'edizione e l'app continua a prepararla
sul telefono come prima.

Uso:  python scripts/redazione.py [cartella_dati]      (prova voce: --prova-voce file.mp3)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
CONFIG = RADICE / "config"
API = "https://generativelanguage.googleapis.com/v1beta/models/"
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
METEO_CODICI = [(0, 0, "sereno"), (1, 1, "poco nuvoloso"), (2, 2, "parzialmente nuvoloso"), (3, 3, "coperto"), (45, 48, "nebbia"),
                (51, 57, "pioviggine"), (61, 67, "pioggia"), (71, 77, "neve"), (80, 82, "rovesci"), (85, 86, "rovesci di neve"), (95, 99, "temporali")]


def log(*a):
    print(*a, flush=True)


def meteo_testo(codice) -> str:
    return next((t for da, a, t in METEO_CODICI if da <= codice <= a), "variabile")


def giorno_nome(iso: str, con_numero: bool = True) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{GIORNI[d.weekday()]} {d.day}" if con_numero else GIORNI[d.weekday()]


# ================================================================ Gemini
class ErroreGemini(Exception):
    pass


def chiama_gemini(chiave: str, modello: str, corpo: dict, timeout: int = 110) -> dict:
    req = urllib.request.Request(f"{API}{modello}:generateContent", data=json.dumps(corpo).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": chiave}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def gemini(chiave: str, modelli: list[str], prompt: str, schema: dict | None = None) -> tuple[str, str]:
    """Prova i modelli in ordine (due giri). Restituisce (testo, modello usato)."""
    config = {"temperature": 0.4}
    if schema:
        config.update({"responseMimeType": "application/json", "responseSchema": schema})
    ultimo = "nessun modello disponibile"
    for giro in (1, 2):
        for modello in modelli:
            for pensiero in (True, False):  # alcuni modelli rifiutano thinkingBudget = 0
                cfg = dict(config, thinkingConfig={"thinkingBudget": 0}) if pensiero else config
                try:
                    j = chiama_gemini(chiave, modello, {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": cfg})
                    testo = "".join(p.get("text", "") for p in j.get("candidates", [{}])[0].get("content", {}).get("parts", []) if not p.get("thought"))
                    if testo.strip():
                        return testo.strip(), modello
                    ultimo = f"{modello}: risposta vuota"
                    break
                except urllib.error.HTTPError as e:
                    corpo = e.read().decode("utf-8", "replace")[:300].replace("\n", " ")
                    ultimo = f"{modello}: HTTP {e.code} {corpo}"
                    log(f"    ! {ultimo[:200]}")
                    if e.code == 400 and pensiero:
                        continue  # riprova senza thinkingConfig
                    if e.code == 429 and giro == 1:
                        time.sleep(20)
                    break
                except Exception as e:  # noqa: BLE001 - rete, timeout
                    ultimo = f"{modello}: {type(e).__name__} {e}"
                    log(f"    ! {ultimo[:200]}")
                    break
        time.sleep(15)
    raise ErroreGemini(ultimo)


# ================================================================ prompt (stesse regole di index.html)
def meteo_da_domani(grezzo: dict) -> list[dict]:
    giorni = (grezzo.get("meteo") or {}).get("giorni") or []
    futuri = [d for d in giorni if d["data"] > grezzo["giorno"]]
    return futuri or giorni[1:]


def quante_notizie(q: dict, cfg: dict) -> int:
    return q["notizie"] if isinstance(q.get("notizie"), int) else cfg["notizie_squadra"]


def prompt_redazione(grezzo: dict, cfg: dict) -> str:
    g = date.fromisoformat(grezzo["giorno"])
    giorno = f"{GIORNI[g.weekday()]} {g.day} {MESI[g.month - 1]} {g.year}"
    giorno_mese = f"{g.day} {MESI[g.month - 1]}"
    totale = sum(s["quante"] for s in cfg["sezioni"])
    naz, tus, spo = (s["quante"] for s in cfg["sezioni"])
    righe_max = cfg["righe_massime"]

    def riga(n):
        return f"{n['id']} | {n['fonte']} | {n['data'][5:16].replace('T', ' ')} | {n['titolo']}" + (f" — {n['sommario'][:160]}" if n.get("sommario") else "")

    def elenco(cat):
        return "\n".join(riga(n) for n in [n for n in grezzo["notizie"] if n["categoria"] == cat][: righe_max.get(cat, righe_max["altre"])]) or "(nessuna)"

    squadre = grezzo.get("squadre") or []
    pod = [f"{p['id']} | {'CALCIO' if p['calcio'] else 'attualità'} | {p['nome']} | episodio: {p['episodio']} | {(p.get('descrizione') or '')[:320]}"
           for p in grezzo["podcast"] if not p.get("gruppo")]
    meteo = [f"{giorno_nome(d['data'])} | {meteo_testo(d['codice'])} | min {d['tmin']}° max {d['tmax']}° | pioggia {d.get('pioggia_prob', '?')}% ({d['pioggia_mm']} mm) | vento {d['vento']} km/h"
             for d in meteo_da_domani(grezzo)]
    tv = grezzo.get("tv") or {}
    tv_serata = [f"{t['canale']} | {t['ora']} | {t['titolo']}{' [prima TV]' if t.get('prima_tv') else ''} | {t.get('descrizione', '')}" for t in tv.get("serata", [])]
    tv_sport = [f"{t['canale']} | {t['ora']} | {t['titolo']}" for t in tv.get("sport", [])]
    sezioni_calcio = "\n\n".join(f'SEZIONE CALCIO "{q["id"]}" ({q["nome"]}) – scegline {quante_notizie(q, cfg)}:\n{elenco(q["id"])}' for q in squadre)
    nl = "\n"
    return f"""Sei il caporedattore di un telegiornale italiano ascoltato ogni mattina da una famiglia di Viterbo. Oggi è {giorno}.
Qui sotto trovi il materiale raccolto stamattina: notizie dai feed RSS (formato: id | fonte | data | titolo — sommario), podcast, previsioni meteo e guida TV.

PRIMA DI TUTTO – "scaletta": l'elenco delle {totale} notizie che hai scelto per il telegiornale secondo le regole del compito 1, nello stesso ordine: per ciascuna solo "id", "categoria" e "titolo".

COMPITO 1 – "notizie": le stesse {totale} notizie della scaletta, con gli stessi id e gli stessi titoli, esattamente in quest'ordine:
- {naz} di categoria "generale" (dall'elenco NOTIZIE NAZIONALI): le più importanti del giorno in Italia e nel mondo, variando gli argomenti (politica, economia, esteri, cronaca, scienza). Preferisci i fatti riportati da più testate; evita doppioni, gossip e notizie minori.
- {tus} di categoria "tuscia" (dall'elenco NOTIZIE DALLA TUSCIA): le più rilevanti per chi vive a Viterbo e provincia (cronaca, amministrazione, sanità, viabilità, lavoro, eventi importanti). Evita comunicati promozionali e doppioni.
- {spo} di categoria "sport" (dall'elenco NOTIZIE SPORTIVE): preferibilmente calcio italiano (Serie A, Nazionale, coppe europee); un altro sport solo se la notizia è davvero importante.
Per ciascuna:
- "id": l'id della voce più completa su quel fatto; "fonti_ids": tutti gli id che parlano dello stesso fatto (compreso "id").
- "titolo": massimo 10 parole, chiaro.
- "testo": tra 60 e 90 parole, riscritto con parole tue, in tono neutrale e fattuale da telegiornale, pensato per essere letto ad alta voce: frasi brevi, niente elenchi, niente emoji, sigle spiegate la prima volta, numeri leggibili (nel titolo invece scrivi anni e numeri in cifre). Usa solo le informazioni presenti nei titoli e nei sommari: non inventare dettagli, cifre o dichiarazioni.

COMPITO 2 – "accadde_oggi": una curiosità storica realmente accaduta il {giorno_mese} di un anno passato, tra 45 e 55 parole (circa 20 secondi di lettura). Scegli un fatto celebre e certo, indica l'anno, non inventare nulla. Non iniziare con "Accadde oggi".

COMPITO 3 – "podcast": scegli esattamente {cfg['podcast']} podcast dall'elenco PODCAST (tutti, se sono meno di {cfg['podcast']}), con almeno 1 di CALCIO se presente, mettendo prima i più interessanti e attuali. Per ciascuno "id" e "spiegazione": 2 frasi brevi (massimo 35 parole in tutto) che spiegano di cosa parla l'episodio.

COMPITO 4 – "squadre": per ogni sezione di calcio indicata sotto, le notizie più importanti prese dal suo elenco, nel numero indicato ("squadra" = id della sezione). Per ciascuna "id", "fonti_ids", "titolo" (massimo 10 parole) e "testo" (tra 40 e 60 parole, stesse regole del compito 1). Evita voci inconsistenti e doppioni; nella sezione "calcio" copri Serie A, coppe europee e calciomercato senza ripetere le notizie già scelte per le squadre.

COMPITO 5 – "meteo": previsioni per Viterbo da leggere ad alta voce, massimo 60 parole, molto riassuntive: prima domani (cielo, temperatura minima e massima, pioggia), poi in una o due frasi la tendenza del resto della settimana. Usa solo i dati dell'elenco METEO; scrivi "gradi" e non il simbolo. Se l'elenco è vuoto restituisci una stringa vuota.

COMPITO 6 – "tv": "Stasera in TV" da leggere ad alta voce in circa 30 secondi, tra 70 e 80 parole: i programmi più interessanti della prima serata (con canale e orario) e le partite o gli eventi sportivi in onda stasera, se presenti negli elenchi. Non inventare programmi. Non iniziare con "Stasera in TV". Se gli elenchi sono vuoti restituisci una stringa vuota.

Rispondi solo con il JSON richiesto.

NOTIZIE NAZIONALI (categoria "generale"):
{elenco('generale')}

NOTIZIE DALLA TUSCIA (categoria "tuscia"):
{elenco('tuscia')}

NOTIZIE SPORTIVE (categoria "sport"):
{elenco('sport')}

{sezioni_calcio}

PODCAST:
{nl.join(pod) or '(nessuno)'}

METEO ({(grezzo.get('meteo') or {}).get('localita', 'Viterbo')}, da domani):
{nl.join(meteo) or '(nessun dato)'}

TV PRIMA SERATA (canale | ora | titolo | descrizione):
{nl.join(tv_serata) or '(nessun dato)'}

TV SPORT DI STASERA:
{nl.join(tv_sport) or '(nessun dato)'}"""


def schema_redazione(grezzo: dict, cfg: dict) -> dict:
    S = {"type": "STRING"}
    categorie = {"type": "STRING", "enum": [s["categoria"] for s in cfg["sezioni"]]}

    def notizia(con_categoria):
        campi = ["id"] + (["categoria"] if con_categoria else []) + ["titolo", "testo", "fonti_ids"]
        prop = {"id": S, "titolo": S, "testo": S, "fonti_ids": {"type": "ARRAY", "items": S}}
        if con_categoria:
            prop["categoria"] = categorie
        return {"type": "OBJECT", "properties": prop, "required": campi, "propertyOrdering": campi}

    ids = [q["id"] for q in grezzo.get("squadre") or []]
    ordine = ["scaletta", "notizie", "accadde_oggi", "podcast", "squadre", "meteo", "tv"]
    return {"type": "OBJECT", "required": ordine, "propertyOrdering": ordine, "properties": {
        "scaletta": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": S, "categoria": categorie, "titolo": S},
                                                "required": ["id", "categoria", "titolo"], "propertyOrdering": ["id", "categoria", "titolo"]}},
        "notizie": {"type": "ARRAY", "items": notizia(True)},
        "accadde_oggi": S,
        "podcast": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"id": S, "spiegazione": S},
                                               "required": ["id", "spiegazione"], "propertyOrdering": ["id", "spiegazione"]}},
        "squadre": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"squadra": {"type": "STRING", "enum": ids} if ids else S,
                                                                               "notizie": {"type": "ARRAY", "items": notizia(False)}},
                                               "required": ["squadra", "notizie"], "propertyOrdering": ["squadra", "notizie"]}},
        "meteo": S, "tv": S}}


# ================================================================ composizione (come in index.html)
def pulisci_titolo(t) -> str:
    return re.sub(r"[.\s]+$", "", str(t or "").strip())


def riassunto(t) -> str:
    t = re.sub(r"\s+", " ", re.sub(r"https?://\S+", "", t or "")).strip()
    return t if len(t) <= 200 else re.sub(r"\s+\S*$", "", t[:200]) + "…"


def completa_notizia(grezzo: dict, n: dict, categoria: str) -> dict:
    per_id = {x["id"]: x for x in grezzo["notizie"]}
    voce = per_id.get(n.get("id"))
    ids = list(dict.fromkeys([n.get("id")] + list(n.get("fonti_ids") or [])))
    fonti = list(dict.fromkeys(per_id[i]["fonte"] for i in ids if i in per_id))
    return {"titolo": pulisci_titolo(n.get("titolo") or (voce or {}).get("titolo")),
            "testo": (n.get("testo") or (voce or {}).get("sommario") or "").strip(),
            "categoria": categoria,
            "fonte": ", ".join(fonti) or (voce or {}).get("fonte", ""),
            "link": (voce or {}).get("link") or next((per_id[i]["link"] for i in ids if i in per_id), "")}


def prime_notizie(grezzo: dict, cat: str, quante: int) -> list[dict]:
    lista = [n for n in grezzo["notizie"] if n["categoria"] == cat][:quante]
    return [{"id": n["id"], "titolo": n["titolo"], "testo": n.get("sommario") or n["titolo"], "fonti_ids": [n["id"]]} for n in lista]


def scegli_podcast(grezzo: dict, scelti: list[dict], quanti: int) -> list[dict]:
    generali = [p for p in grezzo["podcast"] if not p.get("gruppo")]
    per_id = {p["id"]: p for p in generali}
    lista = []
    for s in scelti:
        p = per_id.get(s.get("id"))
        if p and all(x["id"] != p["id"] for x in lista):
            lista.append({**p, "spiegazione": s.get("spiegazione", "")})
    for p in generali:
        if len(lista) >= quanti:
            break
        if all(x["id"] != p["id"] for x in lista):
            lista.append({**p, "spiegazione": riassunto(p.get("descrizione"))})
    lista = lista[:quanti]
    if not any(p["calcio"] for p in lista):
        c = next((p for p in generali if p["calcio"]), None)
        if c:
            lista = lista[: quanti - 1] + [{**c, "spiegazione": riassunto(c.get("descrizione"))}]
    return lista


def testo_meteo_luogo(meteo: dict, giorno: str) -> str:
    """Previsioni riassunte per una località (testo semplice, senza Gemini)."""
    d = meteo_da_domani({"meteo": meteo, "giorno": giorno})
    if not d:
        return ""
    dom = d[0]
    t = f"Domani a {meteo['localita']}: {meteo_testo(dom['codice'])}, minima {dom['tmin']} e massima {dom['tmax']} gradi"
    if dom.get("pioggia_prob") is not None:
        t += f", probabilità di pioggia {dom['pioggia_prob']} per cento"
    t += "."
    if len(d) > 1:
        t += " Nei giorni successivi: " + ", ".join(f"{giorno_nome(x['data'], False)} {meteo_testo(x['codice'])}, massima {x['tmax']} gradi" for x in d[1:6]) + "."
    return t


def testo_meteo(grezzo: dict) -> str:
    d = meteo_da_domani(grezzo)
    if not d:
        return ""
    dom = d[0]
    t = f"Domani a {grezzo['meteo']['localita']}: {meteo_testo(dom['codice'])}, minima {dom['tmin']} e massima {dom['tmax']} gradi"
    if dom.get("pioggia_prob") is not None:
        t += f", probabilità di pioggia {dom['pioggia_prob']} per cento"
    t += "."
    if len(d) > 1:
        t += " Nei giorni successivi: " + ", ".join(f"{giorno_nome(x['data'], False)} {meteo_testo(x['codice'])}" for x in d[1:6]) + "."
    return t


def testo_tv(grezzo: dict) -> str:
    tv = grezzo.get("tv") or {}
    if not tv.get("serata"):
        return ""
    t = "In prima serata: " + "; ".join(f"su {x['canale']} alle {x['ora']} {re.sub(r' *\([^)]*\) *$', '', x['titolo'])}" for x in tv["serata"][:6]) + "."
    if tv.get("sport"):
        t += " Per lo sport: " + "; ".join(f"{x['titolo']}, alle {x['ora']} su {x['canale']}" for x in tv["sport"][:3]) + "."
    return t


def componi(grezzo: dict, j: dict, cfg: dict) -> dict:
    categorie = [s["categoria"] for s in cfg["sezioni"]]
    totale = sum(s["quante"] for s in cfg["sezioni"])
    per_id = {x["id"]: x for x in grezzo["notizie"]}
    notizie, visti = [], set()
    for n in j.get("notizie") or []:
        if len(notizie) >= totale or n.get("id") in visti:
            continue
        visti.add(n.get("id"))
        cat = n.get("categoria") if n.get("categoria") in categorie else per_id.get(n.get("id"), {}).get("categoria")
        notizie.append(completa_notizia(grezzo, n, cat if cat in categorie else categorie[0]))
    if len(notizie) < 6:
        raise ErroreGemini(f"solo {len(notizie)} notizie valide")
    # ordine per sezione, come nella scaletta del TG
    notizie.sort(key=lambda n: categorie.index(n["categoria"]))
    accadde = re.sub(r"^accadde oggi[.:,]?\s*", "", (j.get("accadde_oggi") or "").strip(), flags=re.I)
    squadre = []
    for q in grezzo.get("squadre") or []:
        quante = quante_notizie(q, cfg)
        scelte = next((x.get("notizie") or [] for x in j.get("squadre") or [] if x.get("squadra") == q["id"]), []) or prime_notizie(grezzo, q["id"], quante)
        suoi = [p for p in grezzo["podcast"] if (p["calcio"] and not p.get("gruppo") if q.get("podcast_generali") else p.get("gruppo") == q["id"])]
        squadre.append({**q, "notizie": [completa_notizia(grezzo, n, q["id"]) for n in scelte[:quante]],
                        "podcast": [{**p, "spiegazione": riassunto(p.get("descrizione"))} for p in suoi[: cfg["podcast_squadra"]]]})
    varie = {"squadre": squadre, "meteo": (j.get("meteo") or "").strip() or testo_meteo(grezzo), "tv": (j.get("tv") or "").strip() or testo_tv(grezzo)}
    # le altre località (Vitorchiano, Orvieto, Civitavecchia, Tolfa): testo riassunto dai dati
    varie["meteo_luoghi"] = {m["id"]: (varie["meteo"] if m["id"] == "viterbo" else testo_meteo_luogo(m, grezzo["giorno"]))
                             for m in grezzo.get("meteo_luoghi") or [] if m.get("giorni")}
    # scaletta parlata: una traccia per notizia + la traccia finale
    blocchi = []
    for k, n in enumerate(notizie):
        nuova = k > 0 and notizie[k - 1]["categoria"] != n["categoria"]
        sezione = next(s for s in cfg["sezioni"] if s["categoria"] == n["categoria"])
        annuncio = f"{sezione['annuncio']}\n\n" if (nuova or k == 0) and sezione.get("annuncio") else ""
        blocchi.append({"testo": f"{annuncio}{n['titolo']}.\n\n{n['testo']}", "notizie": [k], "stacco": None if k == 0 else ("lungo" if nuova else "corto")})
    blocchi.append({"testo": (f"Accadde oggi.\n\n{accadde}\n\n" if accadde else "") + cfg["chiusura"], "notizie": [], "stacco": "corto",
                    "finale": True, "etichetta": "Accadde oggi" if accadde else "Chiusura"})
    return {"notizie": notizie, "scaletta": [n["titolo"] for n in notizie], "accadde": accadde,
            "podcast": scegli_podcast(grezzo, j.get("podcast") or [], cfg["podcast"]), "varie": varie, "blocchi": blocchi,
            "titoli": [{"testo": cfg["titoli"]}] + [{"testo": n["titolo"]} for n in notizie]}


# ================================================================ sezioni extra (VARIE e NOVITÀ)
CITTA = [("roma", "Roma", ["roma"]), ("viterbo", "Viterbo città", ["eventi", "tuscia"]),
         ("tuscia", "Tuscia (provincia di Viterbo, esclusa la città)", ["eventi", "tuscia"]), ("orvieto", "Orvieto", ["orvieto"]),
         ("civitavecchia", "Civitavecchia", ["civitavecchia"]), ("tolfa", "Tolfa", ["civitavecchia"])]
# eventi e sagre del fine settimana nelle città vicine (sotto quelli della Tuscia)
CITTA_EVENTI = [("civitavecchia", "Civitavecchia"), ("tolfa", "Tolfa"), ("orvieto", "Orvieto")]
SPORT = [("tennis", "Tennis (Sinner e gli altri italiani)"), ("formula1", "Formula 1"), ("motogp", "MotoGP")]


def fine_settimana(giorno: str) -> tuple[date, date]:
    """Venerdì e domenica del fine settimana in arrivo (o in corso)."""
    from datetime import timedelta
    g = date.fromisoformat(giorno)
    ven = g + timedelta(days=(4 - g.weekday()) % 7) if g.weekday() <= 4 else g - timedelta(days=g.weekday() - 4)
    return ven, ven + timedelta(days=2)


def prompt_extra(grezzo: dict, con_detto: bool) -> str:
    g = date.fromisoformat(grezzo["giorno"])
    oggi = f"{GIORNI[g.weekday()]} {g.day} {MESI[g.month - 1]} {g.year}"
    ven, dom = fine_settimana(grezzo["giorno"])

    def elenco(categorie, massimo):
        righe = [f"{n['fonte']} | {n['data'][5:16].replace('T', ' ')} | {n['titolo']}" + (f" — {n['sommario'][:200]}" if n.get("sommario") else "")
                 for n in grezzo["notizie"] if n["categoria"] in categorie][:massimo]
        return "\n".join(righe) or "(nessuna)"

    tv_sport = "\n".join(f"{t['canale']} | {t['ora']} | {t['titolo']}" for t in (grezzo.get("tv") or {}).get("sport", [])) or "(nessun dato)"
    detto = f"""
COMPITO 5 – "detto": il detto del giorno. Un proverbio popolare in dialetto {'viterbese' if g.toordinal() % 2 == 0 else 'orvietano'}, scelto tra quelli realmente tramandati nella tradizione contadina di quella zona (non inventarne uno nuovo). Oggi è il giorno numero {g.timetuple().tm_yday} dell'anno: non scegliere sempre i più ovvi. Campi: "dialetto", "proverbio" (in dialetto, grafia semplice), "traduzione" (in italiano), "spiegazione" (30-40 parole: che cosa insegna e quando si dice).""" if con_detto else '\nCOMPITO 5 – "detto": lascia tutti i campi vuoti.'
    return f"""Sei il redattore di un notiziario per una famiglia di Viterbo. Oggi è {oggi}.
Usa SOLO le informazioni presenti negli elenchi qui sotto: non inventare eventi, date, orari, luoghi, canali TV o risultati. Quando per una voce non c'è materiale, lascia "testo" vuoto ("") e "lista" vuota. I testi servono per essere letti ad alta voce: frasi brevi, niente elenchi puntati né emoji, orari e numeri scritti in modo leggibile. Scrivi in italiano corretto, con accenti e apostrofi normali.

COMPITO 1 – "eventi_weekend": eventi e sagre nella Tuscia (provincia di Viterbo) previsti nel fine settimana da venerdì {ven.day} {MESI[ven.month - 1]} a domenica {dom.day} {MESI[dom.month - 1]}. "lista": fino a 10 voci con "titolo", "dove" (comune e luogo), "quando" (giorno e ora, se indicati). "testo": tra 80 e 110 parole che presentano gli appuntamenti principali.
Poi "eventi_citta": gli eventi e le sagre dello stesso fine settimana a "civitavecchia", "tolfa" e "orvieto" (dagli elenchi CIVITAVECCHIA E TOLFA e ORVIETO; per Tolfa solo ciò che riguarda Tolfa). Per ogni città "lista" (fino a 6 voci, stessi campi) e "testo" (tra 40 e 70 parole).

COMPITO 2 – "altri_sport": tre testi, "tennis" (Sinner e gli altri italiani), "formula1" e "motogp". Ciascuno tra 60 e 80 parole: notizie principali, risultati più recenti e, solo se indicati negli elenchi, prossimi appuntamenti con giorno, orario e canale TV.

COMPITO 3 – "partite_oggi": le partite di calcio di oggi, {oggi}, che riguardano squadre italiane (Serie A, Coppa Italia, coppe europee, Nazionale). "lista": per ogni partita "partita", "competizione", "ora", "canale" (stringa vuota se orario o canale non risultano dagli elenchi). "testo": tra 40 e 80 parole. Se dagli elenchi non risultano partite in programma oggi scrivi nel testo: "Dalle notizie raccolte non risultano partite di squadre italiane in programma oggi." e lascia la lista vuota.

COMPITO 4 – "cultura": concerti, spettacoli teatrali e mostre in programma da oggi ai prossimi 30 giorni, separati per zona: "roma", "viterbo" (la città), "tuscia" (il resto della provincia), "orvieto", "civitavecchia" e "tolfa" (per queste due usa l'elenco CIVITAVECCHIA E TOLFA, assegnando a Tolfa solo ciò che riguarda Tolfa). Per ogni zona "lista": fino a 8 voci con "titolo", "tipo" (concerto, teatro, mostra o altro), "dove", "quando"; "testo": tra 60 e 90 parole.
{detto}

Rispondi solo con il JSON richiesto.

EVENTI E NOTIZIE DALLA TUSCIA:
{elenco(['eventi', 'tuscia'], 110)}

ORVIETO:
{elenco(['orvieto'], 45)}

CIVITAVECCHIA E TOLFA:
{elenco(['civitavecchia'], 70)}

ROMA:
{elenco(['roma'], 55)}

TENNIS:
{elenco(['tennis'], 30)}

FORMULA 1:
{elenco(['formula1'], 30)}

MOTOGP:
{elenco(['motogp'], 30)}

CALCIO E SPORT (per le partite di oggi):
{elenco(['sport', 'calcio', 'juve', 'inter'], 120)}

SPORT IN TV OGGI (canale | ora | programma):
{tv_sport}"""


def schema_extra() -> dict:
    S = {"type": "STRING"}

    def ogg(campi, extra=None):
        prop = {c: S for c in campi}
        prop.update(extra or {})
        ordine = list(prop)
        return {"type": "OBJECT", "properties": prop, "required": ordine, "propertyOrdering": ordine}

    def blocco(campi_lista):
        return ogg([], {"lista": {"type": "ARRAY", "items": ogg(campi_lista)}, "testo": S})

    ordine = ["eventi_weekend", "eventi_citta", "altri_sport", "partite_oggi", "cultura", "detto"]
    return {"type": "OBJECT", "required": ordine, "propertyOrdering": ordine, "properties": {
        "eventi_weekend": blocco(["titolo", "dove", "quando"]),
        "eventi_citta": ogg([], {c: blocco(["titolo", "dove", "quando"]) for c, _ in CITTA_EVENTI}),
        "altri_sport": ogg([c for c, _ in SPORT]),
        "partite_oggi": blocco(["partita", "competizione", "ora", "canale"]),
        "cultura": ogg([], {c: blocco(["titolo", "tipo", "dove", "quando"]) for c, _, _ in CITTA}),
        "detto": ogg(["dialetto", "proverbio", "traduzione", "spiegazione"])}}


def scrivi_extra(chiave: str, cfg: dict, grezzo: dict) -> tuple[dict, dict]:
    """Sezioni extra: eventi del fine settimana, altri sport, partite di oggi, cultura per zona, detto del giorno.
    Restituisce (dati per l'app, testi da far leggere alla voce)."""
    g = date.fromisoformat(grezzo["giorno"])
    try:
        miei = json.loads((CONFIG / "detti.json").read_text(encoding="utf-8")).get("detti") or []
    except Exception:  # noqa: BLE001
        miei = []
    try:
        testo, _ = gemini(chiave, cfg["modelli"], prompt_extra(grezzo, con_detto=not miei), schema_extra())
        j = json.loads(re.sub(r"^```(?:json)?\s*|```\s*$", "", testo.strip()))
    except Exception as e:  # noqa: BLE001
        log(f"  ! sezioni extra: {type(e).__name__} {str(e)[:200]}")
        j = {}
    ven, dom = fine_settimana(grezzo["giorno"])
    pulito = lambda b: {"testo": ((b or {}).get("testo") or "").strip(), "lista": [x for x in ((b or {}).get("lista") or []) if any(x.values())]}  # noqa: E731
    extra = {
        "eventi_weekend": {**pulito(j.get("eventi_weekend")), "periodo": f"da venerdì {ven.day} a domenica {dom.day} {MESI[dom.month - 1]}"},
        "eventi_citta": {c: pulito((j.get("eventi_citta") or {}).get(c)) for c, _ in CITTA_EVENTI},
        "altri_sport": {c: ((j.get("altri_sport") or {}).get(c) or "").strip() for c, _ in SPORT},
        "partite_oggi": pulito(j.get("partite_oggi")),
        "cultura": {c: pulito((j.get("cultura") or {}).get(c)) for c, _, _ in CITTA},
    }
    detto = miei[g.toordinal() % len(miei)] if miei else (j.get("detto") or {})
    if (detto.get("proverbio") or "").strip():
        extra["detto"] = {k: (detto.get(k) or "").strip() for k in ("dialetto", "proverbio", "traduzione", "spiegazione")}
        extra["detto"]["scelto_da"] = "famiglia" if miei else "ia"
    voce = {}
    if extra["eventi_weekend"]["testo"]:
        voce["eventi"] = "Eventi e sagre nella Tuscia.\n\n" + extra["eventi_weekend"]["testo"]
    for c, nome in CITTA_EVENTI:
        if extra["eventi_citta"][c]["testo"]:
            voce[f"eventi-{c}"] = f"Eventi e sagre a {nome}.\n\n" + extra["eventi_citta"][c]["testo"]
    for c, nome in SPORT:
        if extra["altri_sport"][c]:
            voce[f"sport-{c}"] = f"{nome.split(' (')[0]}.\n\n" + extra["altri_sport"][c]
    if extra["partite_oggi"]["testo"]:
        voce["partite"] = "Le partite di oggi.\n\n" + extra["partite_oggi"]["testo"]
    for c, nome, _ in CITTA:
        if extra["cultura"][c]["testo"]:
            voce[f"cultura-{c}"] = f"Concerti, teatro e mostre: {nome.split(' (')[0]}.\n\n" + extra["cultura"][c]["testo"]
    if extra.get("detto"):
        d = extra["detto"]
        voce["detto"] = f"Il detto del giorno, in dialetto {d['dialetto']}.\n\n{d['proverbio']}.\n\nVuol dire: {d['traduzione']}.\n\n{d['spiegazione']}"
    log(f"  extra: {len(extra['eventi_weekend']['lista'])} eventi, {len(extra['partite_oggi']['lista'])} partite, "
        f"città {[len(extra['eventi_citta'][c]['lista']) for c, _ in CITTA_EVENTI]}, cultura {[len(extra['cultura'][c]['lista']) for c, _, _ in CITTA]}, "
        f"detto {'sì' if extra.get('detto') else 'no'}")
    return extra, voce


# ================================================================ scheda TECH & AI
def prompt_tech(grezzo: dict, scintilla: tuple[str, str]) -> str:
    g = date.fromisoformat(grezzo["giorno"])
    oggi = f"{GIORNI[g.weekday()]} {g.day} {MESI[g.month - 1]} {g.year}"

    def elenco(cat, massimo):
        righe = [f"{n['id']} | {n['fonte']} | {n['data'][5:16].replace('T', ' ')} | {n['titolo']}" + (f" — {n['sommario'][:200]}" if n.get("sommario") else "")
                 for n in grezzo["notizie"] if n["categoria"] == cat][:massimo]
        return "\n".join(righe) or "(nessuna)"

    video = "\n".join(f"{v['vid']} | {v['canale']} | {v['data'][:10]} | {v['titolo']} — {v.get('descrizione', '')[:150]}"
                      for v in (grezzo.get("tech") or {}).get("youtube", [])[:60]) or "(nessuno)"
    pod = "\n".join(f"{p['id']} | {p['nome']} | episodio: {p['episodio']} | {(p.get('descrizione') or '')[:250]}"
                    for p in grezzo["podcast"] if p.get("gruppo") == "tech") or "(nessuno)"
    a, b = scintilla
    return f"""Sei il curatore di una rubrica su tecnologia e intelligenza artificiale per una famiglia italiana. Oggi è {oggi}.
Scrivi in italiano semplice e chiaro, adatto anche a chi non è esperto e da leggere ad alta voce: frasi brevi, niente elenchi puntati, niente emoji, sigle spiegate. Per notizie, futuro, video e podcast usa SOLO le informazioni degli elenchi: non inventare fatti, cifre, nomi o date.

COMPITO 1 – "notizie": le 10 notizie più importanti del giorno su tecnologia e intelligenza artificiale, dall'elenco NOTIZIE TECH (almeno 6 sull'intelligenza artificiale; evita offerte commerciali, recensioni di prodotti e doppioni; puoi usare fonti in inglese ma scrivi in italiano). Per ciascuna "id" (la voce più completa), "fonti_ids" (tutte le voci sullo stesso fatto), "titolo" (massimo 10 parole) e "testo" (tra 45 e 65 parole).

COMPITO 2 – "tendenze": tra 70 e 90 parole sui trend futuri che emergono dalle notizie di oggi: dove sta andando la tecnologia e che cosa potrebbe cambiare nella vita di tutti i giorni.

COMPITO 3 – "idee": 10 idee nuove e concrete da realizzare oggi con la tecnologia e l'intelligenza artificiale, per persone, famiglie, piccole imprese o il territorio (anche la Tuscia). Varia molto i campi. Per ciascuna "titolo" (massimo 8 parole), "idea" (tra 40 e 60 parole: che cosa è e a chi serve), "primo_passo" (massimo 20 parole) e "difficolta" ("facile", "media" o "impegnativa").

COMPITO 4 – "futuro": 10 pillole di futuro, cioè le scoperte e le novità più sorprendenti su scienza, tecnologia, intelligenza artificiale, robotica o sull'impatto dell'IA nel mondo reale, prese dagli elenchi NOTIZIE TECH e SCIENZA E FUTURO. Per ciascuna "id" (della voce usata), "titolo" (massimo 8 parole) e "testo" (tra 35 e 55 parole: che cosa è successo e perché è sorprendente).

COMPITO 5 – "video": fino a 10 video dall'elenco VIDEO che parlano davvero di notizie su tecnologia o intelligenza artificiale (scarta quelli su altri argomenti, le offerte e i giochi), dal più interessante. Per ciascuno "vid" e "perche" (massimo 25 parole: di che cosa parla).

COMPITO 6 – "podcast": per ogni podcast dell'elenco PODCAST "id" e "spiegazione" (2 frasi brevi, massimo 35 parole: di che cosa parla l'episodio).

COMPITO 7 – "scintilla": la scintilla della serendipità. Unisci i due concetti lontani "{a}" e "{b}" in modo inaspettato ma sensato. "ponte": una frase su che cosa li collega. "nome_idea": il nome dell'idea di business (massimo 5 parole). "idea": tra 60 e 80 parole, l'idea di business concreta (che cosa offre, a chi, come guadagna). "intuizione": tra 40 e 60 parole, l'intuizione creativa inaspettata che nasce dall'incontro dei due concetti. "primo_passo": massimo 20 parole.

Rispondi solo con il JSON richiesto.

NOTIZIE TECH:
{elenco('tech', 130)}

SCIENZA E FUTURO:
{elenco('futuro', 45)}

VIDEO (vid | canale | data | titolo — descrizione):
{video}

PODCAST:
{pod}"""


def schema_tech() -> dict:
    S = {"type": "STRING"}

    def ogg(campi, extra=None):
        prop = {c: S for c in campi}
        prop.update(extra or {})
        return {"type": "OBJECT", "properties": prop, "required": list(prop), "propertyOrdering": list(prop)}

    lista = lambda campi, extra=None: {"type": "ARRAY", "items": ogg(campi, extra)}  # noqa: E731
    ordine = ["notizie", "tendenze", "idee", "futuro", "video", "podcast", "scintilla"]
    return {"type": "OBJECT", "required": ordine, "propertyOrdering": ordine, "properties": {
        "notizie": lista(["id", "titolo", "testo"], {"fonti_ids": {"type": "ARRAY", "items": S}}),
        "tendenze": S,
        "idee": lista(["titolo", "idea", "primo_passo", "difficolta"]),
        "futuro": lista(["id", "titolo", "testo"]),
        "video": lista(["vid", "perche"]),
        "podcast": lista(["id", "spiegazione"]),
        "scintilla": ogg(["ponte", "nome_idea", "idea", "intuizione", "primo_passo"])}}


def prompt_dibattito(notizie: list[dict]) -> str:
    elenco = "\n".join(f"- {n['titolo']}: {n['testo']}" for n in notizie[:10]) or "(nessuna)"
    return f"""Scrivi in italiano il copione di un dibattito radiofonico sull'intelligenza artificiale tra due intelligenze artificiali: Ada (voce femminile) e Alan (voce maschile).
Ada è curiosa e ottimista: vede le opportunità per le persone, il lavoro, la medicina e la scuola. Alan è riflessivo e un po' scettico: si preoccupa di rischi, regole, lavoro e privacy. Si rispettano, si fanno domande, ogni tanto ironizzano sul fatto di essere loro stesse delle IA.
Partono dalle notizie di oggi qui sotto e allargano il discorso: che cosa cambia per una famiglia normale, che cosa conviene fare, che cosa tenere d'occhio. Alla fine trovano una conclusione condivisa e salutano.
Durata: circa 9 minuti, cioè tra 1150 e 1300 parole in tutto, in 22-24 battute alternate di 45-65 parole ciascuna, cominciando da Ada. Frasi adatte all'ascolto, niente elenchi, niente indicazioni di scena, niente emoji. Non inventare fatti oltre a quelli delle notizie.
"titolo": un titolo breve. "turni": le battute in ordine, con "chi" uguale a "Ada" oppure "Alan".

NOTIZIE DI OGGI SULL'INTELLIGENZA ARTIFICIALE E LA TECNOLOGIA:
{elenco}"""


SCHEMA_COPIONE = {"type": "OBJECT", "required": ["titolo", "turni"], "propertyOrdering": ["titolo", "turni"], "properties": {
    "titolo": {"type": "STRING"},
    "turni": {"type": "ARRAY", "items": {"type": "OBJECT", "required": ["chi", "testo"], "propertyOrdering": ["chi", "testo"],
                                         "properties": {"chi": {"type": "STRING"}, "testo": {"type": "STRING"}}}}}}


def scrivi_tech(chiave: str, cfg: dict, grezzo: dict) -> tuple[dict | None, dict, dict | None]:
    """Scheda TECH & AI: (dati per l'app, testi da far leggere alla voce, dibattito a due voci)."""
    import random
    t = grezzo.get("tech") or {}
    concetti = t.get("concetti") or {}
    rnd = random.Random(grezzo["giorno"])  # la scintilla del giorno: stessa per tutti, diversa ogni giorno
    scintilla = (rnd.choice(concetti.get("vicini") or ["orto"]), rnd.choice(concetti.get("lontani") or ["intelligenza artificiale"]))
    try:
        testo, _ = gemini(chiave, cfg["modelli"], prompt_tech(grezzo, scintilla), schema_tech())
        j = json.loads(re.sub(r"^```(?:json)?\s*|```\s*$", "", testo.strip()))
    except Exception as e:  # noqa: BLE001
        log(f"  ! tech: {type(e).__name__} {str(e)[:200]}")
        return None, {}, None
    per_id = {n["id"]: n for n in grezzo["notizie"]}
    notizie = [completa_notizia(grezzo, n, "tech") for n in (j.get("notizie") or []) if n.get("id") in per_id][:10]
    futuro = []
    for f in (j.get("futuro") or [])[:10]:
        voce = per_id.get(f.get("id"))
        futuro.append({"titolo": pulisci_titolo(f.get("titolo")), "testo": (f.get("testo") or "").strip(),
                       "fonte": (voce or {}).get("fonte", ""), "link": (voce or {}).get("link", "")})
    per_vid = {v["vid"]: v for v in t.get("youtube", [])}
    video = []
    for v in j.get("video") or []:
        if v.get("vid") in per_vid and all(x["id"] != per_vid[v["vid"]]["id"] for x in video):
            video.append({**per_vid[v["vid"]], "perche": (v.get("perche") or "").strip()})
    video = video[:10]
    spieg = {p.get("id"): p.get("spiegazione", "") for p in j.get("podcast") or []}
    podcast = [{**p, "spiegazione": spieg.get(p["id"]) or riassunto(p.get("descrizione"))} for p in grezzo["podcast"] if p.get("gruppo") == "tech"][:10]
    sc = {**(j.get("scintilla") or {}), "a": scintilla[0], "b": scintilla[1]}
    tech = {"notizie": notizie, "tendenze": (j.get("tendenze") or "").strip(), "idee": (j.get("idee") or [])[:10], "futuro": futuro,
            "video": video, "podcast": podcast, "scintilla": sc}
    voce = {}
    if notizie:
        voce["tech-notizie"] = "Le notizie di oggi su tecnologia e intelligenza artificiale.\n\n" + "\n\n".join(f"{n['titolo']}.\n\n{n['testo']}" for n in notizie) \
            + (f"\n\nE ora i trend del futuro.\n\n{tech['tendenze']}" if tech["tendenze"] else "")
    if tech["idee"]:
        voce["tech-idee"] = "Dieci idee da realizzare con la tecnologia e l'intelligenza artificiale.\n\n" + "\n\n".join(
            f"Idea numero {i + 1}: {x.get('titolo', '')}.\n\n{x.get('idea', '')} Primo passo: {x.get('primo_passo', '')}" for i, x in enumerate(tech["idee"]))
    if futuro:
        voce["tech-futuro"] = "Il futuro in pillole.\n\n" + "\n\n".join(f"{x['titolo']}.\n\n{x['testo']}" for x in futuro)
    if sc.get("idea"):
        voce["tech-scintilla"] = (f"La scintilla della serendipità. Oggi uniamo {sc['a']} e {sc['b']}.\n\n{sc.get('ponte', '')}\n\n"
                                  f"L'idea si chiama {sc.get('nome_idea', '')}.\n\n{sc['idea']}\n\nL'intuizione: {sc.get('intuizione', '')}\n\nPrimo passo: {sc.get('primo_passo', '')}")
    dibattito = None
    try:
        testo, _ = gemini(chiave, cfg["modelli"], prompt_dibattito(notizie), SCHEMA_COPIONE)
        dj = json.loads(re.sub(r"^```(?:json)?\s*|```\s*$", "", testo.strip()))
        turni = [{"chi": x["chi"], "testo": x["testo"].strip()} for x in dj.get("turni") or [] if x.get("chi") in ("Ada", "Alan") and x.get("testo")]
        if len(turni) >= 6:
            dibattito = {"titolo": (dj.get("titolo") or "Due IA parlano di IA").strip(), "turni": turni}
    except Exception as e:  # noqa: BLE001
        log(f"  ! dibattito: {type(e).__name__} {str(e)[:200]}")
    log(f"  tech: {len(notizie)} notizie, {len(tech['idee'])} idee, {len(futuro)} pillole, {len(video)} video, {len(podcast)} podcast, "
        f"scintilla {scintilla[0]} + {scintilla[1]}, dibattito {len(dibattito['turni']) if dibattito else 0} battute")
    return tech, voce, dibattito


# ================================================================ rassegne della settimana
RASSEGNE = {
    "generale": lambda g: f'Scrivi la rassegna stampa della settimana: un racconto discorsivo dei fatti principali in Italia e nel mondo negli ultimi {g} giorni. Lunghezza: tra 650 e 700 parole (circa 5 minuti di lettura ad alta voce), in 6 o 7 paragrafi separati da una riga vuota, un tema per paragrafo (politica, economia, esteri, cronaca, scienza e società). Comincia con "Rassegna stampa della settimana."',
    "tuscia": lambda g: f'Scrivi la rassegna della settimana per Viterbo e la Tuscia: un racconto discorsivo dei fatti locali principali degli ultimi {g} giorni. Lunghezza: tra 650 e 700 parole (circa 5 minuti di lettura ad alta voce), in 6 o 7 paragrafi separati da una riga vuota. Evita comunicati promozionali e fatti minori. Comincia con "La settimana nella Tuscia."',
    "sport": lambda g: f'Scegli le 5 notizie sportive nazionali più importanti degli ultimi {g} giorni e raccontale: 5 paragrafi separati da una riga vuota, ognuno di 50-60 parole, introdotti da "Prima notizia", "Seconda notizia" e così via. Comincia con "Lo sport della settimana."',
}


def scrivi_rassegne(chiave: str, cfg: dict, cartella: Path) -> dict:
    file = cartella / "settimana.json"
    if not cfg.get("rassegne") or not file.exists():
        return {}
    sett = json.loads(file.read_text(encoding="utf-8"))
    giorni = sorted(sett.get("giorni", {}))
    out = {}
    for tipo, compito in RASSEGNE.items():
        righe = "\n\n".join(f"## {giorno_nome(d)}\n" + "\n".join(f"{n['f']} | {n['t']}" + (f" — {n['s']}" if n.get("s") else "") for n in sett["giorni"][d].get(tipo, [])) for d in giorni)
        if len(righe) < 200:
            continue
        try:
            testo, _ = gemini(chiave, cfg["modelli"], f"""Sei il caporedattore di un notiziario radiofonico italiano. Qui sotto trovi i titoli (fonte | titolo — sommario) raccolti giorno per giorno nell'ultima settimana.
{compito(len(giorni))}
Dai più spazio ai fatti che ricorrono in più giorni o su più testate. Tono neutrale e fattuale, frasi brevi pensate per l'ascolto, niente elenchi, niente simboli, numeri scritti in modo leggibile. Usa solo le informazioni presenti nei titoli e nei sommari: non inventare nulla. Rispondi solo con il testo da leggere.

{righe}""")
            out[tipo] = {"testo": testo, "giorni": giorni}
            log(f"  rassegna {tipo}: {len(testo.split())} parole")
        except ErroreGemini as e:
            log(f"  ! rassegna {tipo}: {e}")
    return out


# ================================================================ voce neurale (edge-tts)
def pulisci_per_voce(testo: str) -> str:
    """Prepara il testo per la lettura: niente HTML, markdown, link o simboli; pause naturali tra i paragrafi."""
    t = re.sub(r"<[^>]+>", " ", testo or "")
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)            # link markdown -> solo il testo
    t = re.sub(r"https?://\S+|www\.\S+", " ", t)
    t = re.sub(r"[*_#`~>|]+", " ", t)
    for da, a in (("&", " e "), ("%", " per cento"), ("€", " euro"), ("°C", " gradi"), ("°", " gradi"), ("km/h", "chilometri orari"),
                  ("+", " più "), ("=", " uguale "), ("«", ""), ("»", ""), ("“", ""), ("”", ""), ('"', ""), (" - ", ", "), (" – ", ", "), (" — ", ", ")):
        t = t.replace(da, a)
    t = re.sub(r"^[\s…\.]+", "", t)                             # la chiusura comincia con i puntini
    t = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️‍]", " ", t)  # emoji e simboli
    paragrafi = []
    for p in re.split(r"\n\s*\n", t):
        p = re.sub(r"\s+", " ", p).strip()
        if p:
            paragrafi.append(p if p[-1] in ".!?:;…" else p + ".")
    return "\n".join(paragrafi)


def taglia_silenzi(file: Path) -> None:
    """Toglie il silenzio all'inizio e alla fine di una lettura (edge-tts ne lascia circa 0,2 e 0,3 secondi),
    lasciando un margine minimo: tra una notizia e lo stacco non ci sono pause morte. Serve ffmpeg; senza, non fa nulla."""
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        return
    tmp = file.with_suffix(".tmp.mp3")
    filtro = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,"
              "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.10,areverse")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(file), "-af", filtro, "-ar", "24000", "-ac", "1",
                        "-b:a", "48k", str(tmp)], check=True, timeout=60)
        if tmp.exists() and tmp.stat().st_size > 1500:
            tmp.replace(file)
    except Exception as e:  # noqa: BLE001 - se il taglio non riesce resta il file originale
        log(f"    ! taglio silenzi {file.name}: {e}")
    finally:
        tmp.unlink(missing_ok=True)


async def leggi(testo: str, file: Path, cfg: dict, voci: list[str] | None = None) -> str | None:
    """Sintetizza un testo in MP3. 3 tentativi per voce, poi la voce di riserva. Restituisce la voce usata.
    voci: per far parlare qualcun altro (es. i due conduttori del dibattito); altrimenti la voce del TG."""
    import edge_tts
    pulito = pulisci_per_voce(testo)
    if not pulito:
        return None
    for voce in voci or cfg["voci"]:
        for tentativo in range(3):
            try:
                await edge_tts.Communicate(pulito, voce, rate=cfg.get("velocita", "+0%"), pitch=cfg.get("tono", "+0Hz")).save(str(file))
                if file.exists() and file.stat().st_size > 1500:
                    if cfg.get("taglia_silenzi"):
                        await asyncio.to_thread(taglia_silenzi, file)
                    return voce
                raise RuntimeError("file audio vuoto")
            except Exception as e:  # noqa: BLE001 - rete o servizio momentaneamente non disponibile
                log(f"    ! voce {voce}, tentativo {tentativo + 1} per {file.name}: {type(e).__name__} {str(e)[:120]}")
                await asyncio.sleep(4 * (tentativo + 1))
    file.unlink(missing_ok=True)
    return None


def parti_di(testo: str, massimo: int = 135) -> list[str]:
    """Un testo lungo diventa più file (parte subito e si può mettere in pausa senza perdere il punto)."""
    out, corrente = [], ""
    for par in [p.strip() for p in re.split(r"\n\s*\n", testo) if p.strip()]:
        if len(corrente.split()) >= 15 and len((corrente + " " + par).split()) > massimo:  # un titolo da solo non fa una parte
            out.append(corrente)
            corrente = ""
        corrente += ("\n\n" if corrente else "") + par
    if corrente:
        out.append(corrente)
    return out


async def genera_audio(ed: dict, rassegne: dict, cfg: dict, cartella: Path, voce_extra: dict | None = None, sigla_edizione: str = "",
                      dibattito: dict | None = None) -> dict:
    # Ogni edizione ha la sua cartella (data/audio/<edizione>/): così l'audio di un'edizione non può mai
    # mescolarsi con la scaletta di un'altra, anche se il sito viene ripubblicato mentre qualcuno ascolta.
    sottocartella = f"audio/{sigla_edizione}" if sigla_edizione else "audio"
    audio = cartella / sottocartella
    audio.mkdir(parents=True, exist_ok=True)
    lavori = []  # (file, testo, dove mettere il percorso)
    ed["saluto"] = {"testo": cfg["saluto"]}
    lavori.append(("saluto.mp3", cfg["saluto"], ed["saluto"]))
    for i, t in enumerate(ed["titoli"]):
        lavori.append((f"titolo-{i}.mp3", t["testo"], t))
    for i, b in enumerate(ed["blocchi"]):
        lavori.append(("finale.mp3" if b.get("finale") else f"notizia-{i + 1}.mp3", b["testo"], b))
    varie = {}
    for q in ed["varie"]["squadre"]:
        if q["notizie"]:
            varie[f"squadra-{q['id']}"] = f"Le notizie: {q['nome']}.\n\n" + "\n\n".join(f"{n['titolo']}.\n\n{n['testo']}" for n in q["notizie"])
    if ed["varie"]["meteo"]:
        varie["meteo"] = ed["varie"]["meteo"]
    for luogo, testo in (ed["varie"].get("meteo_luoghi") or {}).items():
        if testo and luogo != "viterbo":
            varie[f"meteo-{luogo}"] = testo
    if ed["varie"]["tv"]:
        varie["tv"] = "Stasera in TV.\n\n" + ed["varie"]["tv"]
    if ed["accadde"]:
        varie["accadde"] = "Accadde oggi.\n\n" + ed["accadde"]
    varie.update(voce_extra or {})
    ed["audio_varie"] = {}
    for chiave, testo in varie.items():
        parti = parti_di(testo, 170)  # i testi lunghi in più file: partono subito
        ed["audio_varie"][chiave] = [{} for _ in parti]
        for i, (parte, voce) in enumerate(zip(parti, ed["audio_varie"][chiave])):
            lavori.append((f"{chiave}.mp3" if len(parti) == 1 else f"{chiave}-{i + 1}.mp3", parte, voce))
    if dibattito and dibattito.get("turni"):
        voci_d = cfg.get("voci_dibattito", {})
        for i, t in enumerate(dibattito["turni"]):
            lavori.append((f"dibattito-{i + 1:02d}.mp3", t["testo"], t, voci_d.get(t["chi"])))
    for tipo, r in rassegne.items():
        r["parti"] = []
        for i, parte in enumerate(parti_di(r["testo"])):
            voce = {}
            r["parti"].append(voce)
            lavori.append((f"rassegna-{tipo}-{i + 1}.mp3", parte, voce))
    limite = asyncio.Semaphore(4)
    usate = set()

    async def uno(nome, testo, dove, voci=None):
        async with limite:
            voce = await leggi(testo, audio / nome, cfg, voci)
        dove["audio"] = f"data/{sottocartella}/{nome}" if voce else None
        if voce:
            usate.add(voce)

    await asyncio.gather(*(uno(*l) for l in lavori))
    riusciti = sum(1 for l in lavori if l[2].get("audio"))
    log(f"  voce: {riusciti}/{len(lavori)} file audio, {sum(f.stat().st_size for f in audio.glob('*.mp3')) // 1024} KB, voci usate: {', '.join(sorted(usate)) or 'nessuna'}")
    ed["audio_varie"] = {k: [p["audio"] for p in v] for k, v in ed["audio_varie"].items() if v and all(p.get("audio") for p in v)}
    if dibattito and dibattito.get("turni"):
        dibattito["audio"] = [t.pop("audio", None) for t in dibattito["turni"]]
        if not all(dibattito["audio"]):
            dibattito.pop("audio")
    ed["rassegne"] = {t: {"testo": r["testo"], "giorni": r["giorni"], "audio": [p["audio"] for p in r["parti"]]}
                      for t, r in rassegne.items() if r["parti"] and all(p.get("audio") for p in r["parti"])}
    if riusciti < len(ed["titoli"]) + len(ed["blocchi"]):  # troppi buchi: meglio lasciare la preparazione al telefono
        raise RuntimeError(f"audio incompleto ({riusciti}/{len(lavori)})")
    return ed


def main() -> None:
    cfg = json.loads((CONFIG / "tg.json").read_text(encoding="utf-8"))
    if len(sys.argv) > 2 and sys.argv[1] == "--prova-voce":
        voce = asyncio.run(leggi("Buongiorno. Questa è una prova della voce del TG di Famiglia: l'80% delle notizie arriva alle 6 del mattino.", Path(sys.argv[2]), cfg))
        log(f"Prova voce: {'ok con ' + voce if voce else 'FALLITA'} -> {sys.argv[2]}")
        sys.exit(0 if voce else 1)
    cartella = Path(sys.argv[1]) if len(sys.argv) > 1 else RADICE / "data"
    chiave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not chiave:
        log("Edizione del server: segreto GEMINI_API_KEY non impostato, salto (l'app prepara il notiziario sul telefono).")
        return
    grezzo = json.loads((cartella / "grezzo.json").read_text(encoding="utf-8"))
    try:
        log("Edizione del server:")
        testo, modello = gemini(chiave, cfg["modelli"], prompt_redazione(grezzo, cfg), schema_redazione(grezzo, cfg))
        j = json.loads(re.sub(r"^```(?:json)?\s*|```\s*$", "", testo.strip()))
        ed = componi(grezzo, j, cfg)
        log(f"  testi: {len(ed['notizie'])} notizie, {len(ed['podcast'])} podcast, {len(ed['varie']['squadre'])} sezioni calcio (modello {modello})")
        ed["extra"], voce_extra = scrivi_extra(chiave, cfg, grezzo)
        ed["tech"], voce_tech, dibattito = scrivi_tech(chiave, cfg, grezzo)
        voce_extra.update(voce_tech)
        rassegne = scrivi_rassegne(chiave, cfg, cartella)
        sigla_edizione = re.sub(r"\D", "", grezzo["generato"])[:14]  # es. 20261117042712
        ed = asyncio.run(genera_audio(ed, rassegne, cfg, cartella, voce_extra, sigla_edizione, dibattito))
        if ed.get("tech") and dibattito:
            ed["tech"]["dibattito"] = dibattito
        # controllo di coerenza: titolo k e notizia k devono essere la stessa notizia, nello stesso ordine
        for k, n in enumerate(ed["notizie"]):
            assert ed["titoli"][k + 1]["testo"] == n["titolo"] and ed["blocchi"][k]["notizie"] == [k], f"scaletta incoerente alla notizia {k + 1}"
        ed.update({"versione": 2, "sigla": sigla_edizione, "generato": grezzo["generato"], "giorno": grezzo["giorno"], "modello": modello,
                   "scritto": datetime.now().astimezone().isoformat(timespec="seconds")})
        (cartella / "edizione.json").write_text(json.dumps(ed, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"Scritto {cartella / 'edizione.json'}")
    except Exception as e:  # noqa: BLE001 - mai far fallire la pubblicazione: l'app ha la sua preparazione di riserva
        log(f"ATTENZIONE: edizione del server non creata ({type(e).__name__}: {str(e)[:300]}). L'app userà la preparazione sul telefono.")
        (cartella / "edizione.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
