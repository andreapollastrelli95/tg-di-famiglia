# 📺 TG di Famiglia

Un notiziario quotidiano da ascoltare sul telefono: una sigla, poi una voce da
conduttrice che legge le 10 notizie del giorno (8 di attualità e 2 di calcio),
seguite da 10 podcast consigliati e da una radio musicale casuale.

È una web app installabile (PWA) ospitata gratis su GitHub Pages:
**https://andreapollastrelli95.github.io/tg-di-famiglia/**

Ognuno usa la **propria chiave gratuita della Gemini API**, che resta salvata solo
sul suo telefono.

---

## Cosa c'è dentro

L'app **parte da sola all'apertura**: cerca notizie e podcast e fa partire l'audio. Se il telefono non
lascia partire l'audio senza un tocco (succede su iPhone e nel browser normale), parte al primo tocco
sullo schermo.

**Scheda TG**

1. sigla, poi il saluto *"Buongiorno famiglia, queste sono le notizie e i podcast del giorno consigliati. Buon ascolto."*;
2. suono di 5 secondi, la voce dice *"Titoli del TG di Famiglia"* e legge **i titoli** delle 10 notizie, con un suono di 3 secondi tra un titolo e l'altro;
3. **5 notizie nazionali**, separate da uno stacco di 3 secondi;
4. stacco leggero di 5 secondi, *"Notizie dalla Tuscia"* e **3 notizie da Viterbo e provincia**;
5. stacco di 5 secondi, *"Notizie sportive"* e **2 notizie di sport**;
6. **Accadde oggi** (curiosità storica di circa 20 secondi) e chiusura;
7. finito il TG **parte da solo il primo podcast** consigliato. Sotto: i 10 podcast e le radio.

**Scheda CALCIO**: **Juventus** (3 notizie, 2 podcast, Radio Bianconera), **Inter** (3 notizie e podcast),
**Serie A, Champions e calciomercato** (5 notizie, 2 podcast, Radio Sportiva) e **Chiedi all'AI sul calcio**:
si scrive una domanda e Gemini risponde usando le notizie di calcio raccolte in giornata (la risposta si
può anche ascoltare).

**Scheda VARIE**: **meteo di Viterbo** (domani e settimana), **Stasera in TV** (prima serata e sport in
30 secondi), **Radio preferite** (5 radio nazionali già pronte, più la ricerca per aggiungerne altre: restano
salvate sul telefono) e **Rassegna stampa della domenica**: a scelta le notizie della settimana in 5 minuti,
la settimana nella Tuscia in 5 minuti oppure le 5 notizie sportive principali.

## Come funziona

```
 ogni mattina alle 04:30 UTC                      sul telefono, con la chiave dell'utente
┌──────────────────────────────┐   grezzo.json   ┌─────────────────────────────────────────┐
│ GitHub Actions (senza chiavi)│ ──────────────► │ Gemini (testo): sceglie e riscrive le    │
│ • feed RSS delle testate     │  GitHub Pages   │   10 notizie e spiega i 10 podcast       │
│ • podcast via iTunes Search  │                 │ Gemini TTS (voce "Kore") a blocchi       │
└──────────────────────────────┘                 │ cache del giorno in IndexedDB            │
                                                 └─────────────────────────────────────────┘
```

* **Raccolta (server)**: `scripts/raccogli.py` legge i feed in `config/fonti.json`
  e i podcast in `config/podcast.json` e scrive `data/grezzo.json`. Serve un server
  perché il browser non può leggere direttamente i feed RSS (blocco CORS).
  I dati vengono pubblicati con `actions/deploy-pages`, senza commit, quindi il
  repository non cresce.
* **Intelligenza (telefono)**: l'app chiama direttamente la Gemini API con la chiave
  dell'utente. Le notizie compaiono man mano che Gemini le scrive; la voce viene
  generata a blocchi di 2 notizie e il primo blocco parte appena è pronto, mentre la
  sigla suona e gli altri si preparano.
* **Rassegna della domenica**: il repository non conserva dati, quindi ogni mattina la raccolta scarica
  `data/settimana.json` già pubblicato sul sito, aggiunge i titoli del giorno e lo ripubblica (ultimi 7 giorni).
* **Cache del giorno**: testo e audio restano nel telefono (IndexedDB). Riascoltare lo
  stesso giorno è immediato e non consuma quota. Il giorno dopo si rigenera tutto.
* **Riserve**: se la voce di Gemini non è disponibile (quota esaurita) l'app legge con
  la voce del telefono; se Gemini non risponde affatto legge i titoli raccolti.

---

## 1. Creare la chiave Gemini (gratis)

1. Apri **https://aistudio.google.com/apikey** e accedi con un account Google.
2. Tocca **Create API key** (Crea chiave API). Se lo chiede, scegli o crea un progetto.
3. Copia la chiave (inizia con `AIza…`) e incollala nell'app al primo avvio.

### Limitare la chiave (consigliato)

La chiave sta solo sul telefono, ma conviene comunque limitarla, così anche se
qualcuno la copiasse non potrebbe usarla altrove.

1. Apri **https://console.cloud.google.com/apis/credentials** (stesso account Google)
   e scegli il progetto della chiave in alto.
2. Clicca sul nome della chiave.
3. **Restrizioni dell'applicazione** → *Siti web* → **Aggiungi** →
   `https://andreapollastrelli95.github.io/*`
4. **Restrizioni delle API** → *Limita chiave* → seleziona solo
   **Generative Language API**.
5. **Salva**. Le modifiche possono impiegare qualche minuto ad attivarsi.

> Dopo questa restrizione la chiave funziona **solo** dentro l'app su github.io.
> Se l'app dice “La chiave è bloccata per questo sito”, controlla di aver scritto
> l'indirizzo esattamente come sopra.

### Quote gratuite

Il piano gratuito ha limiti al minuto e al giorno, in particolare per la voce (TTS).
Un notiziario usa circa 1 chiamata di testo e 13 chiamate di voce al giorno (una per notizia, una per "Accadde oggi" e due per i titoli di testa: la prima con l'annuncio e i primi 3 titoli, pronta in pochi secondi, la seconda con gli altri; l'app le divide poi sulle pause). Per far partire i titoli il prima possibile Gemini scrive per prima la sola scaletta dei titoli; se la voce tarda più di `CONFIG.attesaMassimaTitoli` (12 secondi) o `CONFIG.attesaMassimaNotizia` (20 secondi), legge la voce del telefono invece di lasciare la musica d'attesa. Ogni ascolto nelle schede CALCIO e VARIE ne usa altre: una per il meteo o la TV, 3-6 per una rassegna. La ricerca su Google non è inclusa nella quota gratuita, quindi "Chiedi all'AI" risponde con le notizie del giorno e le conoscenze del modello.
Grazie alla cache, riascoltarlo è gratis. Se la quota della voce finisce, l'app usa
la voce del telefono e lo segnala.

---

## 2. Installare l'app sul telefono

**Android (Chrome)**: apri il link → menu **⋮** → **Installa app** (o *Aggiungi a
schermata Home*).

**iPhone (Safari)**: apri il link → **Condividi** (quadrato con freccia) →
**Aggiungi alla schermata Home**.

Poi apri **TG Famiglia** dall'icona e incolla la chiave la prima volta.

> Su iPhone l'app installata ha una memoria separata da Safari: se hai inserito la
> chiave in Safari, inseriscila di nuovo dentro l'app installata.

### QR già configurato (per chi non vuole inserire la chiave)

Se l'indirizzo contiene `#key=…`, l'app salva la chiave da sola e la toglie subito
dalla barra degli indirizzi. Per creare il QR personale e il cartoncino:

```bash
pip install qrcode pillow reportlab
python tools/genera_qr_cartoncino.py --url https://andreapollastrelli95.github.io/tg-di-famiglia/ --chiave AIza... --nome papa
```

I file finiscono in `stampa/privato/`, una cartella esclusa da git. **Non pubblicare
quel QR**: contiene la chiave. Il QR e il cartoncino generici (senza chiave) sono in
`stampa/`.

---

## 3. Personalizzare

| Cosa | Dove |
|---|---|
| **Feed delle notizie** | `config/fonti.json`: aggiungi o togli voci `{"fonte", "categoria": "generale" o "calcio", "url"}`. Se un feed non risponde viene saltato. `ore_massime` indica quanto possono essere vecchie le notizie. |
| **Scaletta del TG** | `index.html`, `CONFIG.sezioni`: categorie, quante notizie per sezione e frase d'annuncio (es. "Notizie dalla Tuscia."). Le categorie devono esistere in `config/fonti.json` (`generale`, `tuscia`, `sport`). |
| **Schede CALCIO e VARIE** | `config/varie.json`: `squadre` = sezioni della scheda CALCIO (per aggiungerne una: nuovo `id`, feed con quella `categoria` in `fonti.json`, podcast con quel `gruppo` in `podcast.json`, eventuale stream della radio), `meteo` (località e coordinate), `tv` (pagine della guida e canali), `radio_preferite` (quelle proposte la prima volta) e `settimana` (quanti titoli al giorno conservare per la rassegna). |
| **Avvio automatico e podcast a fine TG** | `index.html`, `CONFIG.avvioAutomatico` e `CONFIG.podcastAFineTG` (`true`/`false`). |
| **Podcast** | `config/podcast.json`: `nome` (parte del titolo su Apple Podcasts), `autore` (parte del nome dell'editore) e `calcio`. Se la ricerca non lo trova, aggiungi `"feedUrl": "https://…"`. Vengono presi solo episodi con audio pubblico usciti negli ultimi `giorni_massimi` giorni. |
| **Voce** | `index.html`, oggetto `CONFIG` in cima allo script: `voce` (es. `Kore`, `Aoede`, `Leda`, `Callirrhoe`, `Zephyr`) . Alla voce viene inviato solo il testo da leggere, senza istruzioni di tono, perché i modelli vocali a volte le leggono ad alta voce. Dopo una modifica conviene alzare `VERSIONE_CACHE` (es. `'v4'`) per rigenerare gli audio salvati. |
| **Modelli Gemini** | `CONFIG.modelliTesto` e `CONFIG.modelliVoce`: vengono provati in ordine finché uno funziona; se un modello è sovraccarico o non risponde entro `CONFIG.attesaTesto` si passa al successivo, e l'app ricorda quello che ha funzionato. (Novembre 2026: `gemini-2.5-flash` non è più disponibile per le chiavi nuove e `gemini-flash-latest` è spesso sovraccarico, per questo ci sono `gemini-3.5-flash` e `gemini-3-flash-preview` come riserve.) |
| **Saluto e chiusura** | `CONFIG.saluto` e `CONFIG.chiusura`. |
| **Orario della raccolta** | `.github/workflows/pubblica.yml`, riga `cron: "30 4 * * *"`, in **UTC** (04:30 UTC = 05:30 in inverno, 06:30 in estate in Italia). |

Ogni modifica committata su `main` ripubblica il sito e rifà la raccolta.

### Avviare la raccolta a mano

GitHub → repository → **Actions** → *Raccolta notizie e pubblicazione* →
**Run workflow**.

### Keepalive

GitHub sospende i workflow programmati dopo 60 giorni senza attività nel
repository. `.github/workflows/keepalive.yml` fa un piccolo commit il giorno 1 di
ogni mese e riattiva il workflow di raccolta.

---

## Rigenerare le risorse

```bash
pip install numpy lameenc pillow qrcode reportlab
python tools/genera_sigla.py          # sigla, stacchi e sottofondo in assets/ (musica originale sintetizzata)
python tools/genera_icone.py          # icons/*.png
python tools/genera_qr_cartoncino.py --url https://andreapollastrelli95.github.io/tg-di-famiglia/
```

Per provare la raccolta in locale: `pip install feedparser` e poi
`python scripts/raccogli.py` (scrive `data/grezzo.json`, che non viene committato).

## Struttura

```
index.html              app (HTML + CSS + JS in un solo file)
manifest.json, sw.js    PWA: installazione e cache offline
icons/, assets/         icone e sigla
config/                 feed RSS e podcast
scripts/raccogli.py     raccolta dati (GitHub Actions)
tools/                  generatori di sigla, icone, QR e cartoncino
stampa/                 QR e cartoncino da stampare
.github/workflows/      pubblicazione giornaliera e keepalive
```

## Privacy

* La chiave Gemini resta nel `localStorage` del telefono e viene inviata solo a
  `generativelanguage.googleapis.com`. Non è nel repository né su altri server.
* Il sito non usa cookie né statistiche. Le notizie appartengono alle rispettive
  testate: l'app mostra un riassunto e rimanda all'articolo originale.
