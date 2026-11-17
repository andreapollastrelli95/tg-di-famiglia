# 📺 TG di Famiglia

Un notiziario quotidiano da ascoltare sul telefono: una sigla, poi una voce da
conduttrice che legge le 10 notizie del giorno (8 di attualità e 2 di calcio),
seguite da 10 podcast consigliati e da una radio musicale casuale.

È una web app installabile (PWA) ospitata gratis su GitHub Pages:
**https://andreapollastrelli95.github.io/tg-di-famiglia/**

Il notiziario viene preparato ogni mattina sul server, con una **voce neurale italiana gratuita**: sul
telefono non serve nessuna chiave. La chiave Gemini personale serve solo per "Chiedi all'AI" e come
riserva se un giorno l'edizione del server non c'è; resta salvata solo sul telefono.

---

## Cosa c'è dentro

L'app **parte da sola all'apertura**: cerca notizie e podcast e fa partire l'audio. Se il telefono non
lascia partire l'audio senza un tocco (succede su iPhone e nel browser normale), parte al primo tocco
sullo schermo.

**Scheda TG** (solo il notiziario)

1. sigla, poi il saluto *"Buongiorno famiglia, queste sono le notizie e i podcast del giorno consigliati. Buon ascolto."*;
2. suono di 5 secondi, la voce dice *"Titoli del TG di Famiglia"* e legge **i titoli** delle 10 notizie, con un suono di 3 secondi tra un titolo e l'altro;
3. **5 notizie nazionali**, separate da uno stacco di 3 secondi;
4. stacco leggero di 5 secondi, *"Notizie dalla Tuscia"* e **3 notizie da Viterbo e provincia**;
5. stacco di 5 secondi, *"Notizie sportive"* e **2 notizie di sport**;
6. **Accadde oggi** (curiosità storica di circa 20 secondi) e chiusura;
7. finito il TG **parte da solo il primo podcast** e si apre la scheda PODCAST.

**Scheda PODCAST**: i 10 podcast consigliati del giorno, caricati da soli all'apertura dell'app.

**Scheda RADIO**: radio casuali per genere (musica, classica, jazz, country, da viaggio, sportive, attualità)
e **Radio preferite** (5 radio nazionali già pronte, più la ricerca per aggiungerne altre: restano salvate
sul telefono).

**Scheda CALCIO**: quattro tasti che aprono ciascuno la sua sezione: **Juve** (3 notizie, 2 podcast, Radio
Bianconera), **Inter** (3 notizie e podcast), **Serie A, Champions e calciomercato** (5 notizie, 2 podcast,
Radio Sportiva) e **Chiedi all'AI sul calcio** (si scrive una domanda e Gemini risponde usando le notizie
di calcio raccolte in giornata; la risposta si può anche ascoltare).

**Scheda VARIE**: tasti che aprono **Meteo a Viterbo** (domani e settimana), **Stasera in TV** (prima
serata e sport in 30 secondi), **Accadde oggi**, **Rassegna stampa della domenica** (a scelta le notizie
della settimana in 5 minuti, la settimana nella Tuscia in 5 minuti oppure le 5 notizie sportive),
**Altri sport** (tennis, Formula 1 e MotoGP: notizie, risultati e orari TV quando sono noti),
**Partite di oggi** (orario e canale delle partite delle squadre italiane) e **Concerti, teatro e
mostre** dei prossimi 30 giorni a Roma, Viterbo, nella Tuscia o a Orvieto, a scelta.

**Scheda NOVITÀ**: **Eventi e sagre nella Tuscia** (quelli del fine settimana), **Raccolta
differenziata** (che cosa mettere fuori stasera e calendario dei ritiri, per Viterbo zona per zona e per
Vitorchiano), **Il detto del giorno** (un proverbio in dialetto viterbese o orvietano, con traduzione),
**Podcast fai da te** (scrivi un argomento: Marco e Giulia ne discutono per circa 10 minuti e cercano una
conclusione) e **Gran consiglio dell'IA** (racconti un problema: Leo il creativo, Sara la realista e Bruno
il pragmatico ne parlano per circa 10 minuti e propongono una soluzione) e **6 cappelli per pensare** (fai una domanda: sei voci la guardano ognuna dal suo punto di vista secondo il metodo di Edward de Bono, cioè fatti, emozioni, rischi, vantaggi, idee nuove e metodo, e una settima voce tira le somme). In queste tre sezioni la lettura parte da sola dopo pochi secondi, mentre il testo viene ancora scritto. Ogni sezione comincia con una
riga che spiega a che cosa serve.

Le sezioni informative (sport, partite, cultura, eventi, detto) sono scritte ogni mattina sul server a
partire dalle notizie raccolte e lette dalla voce neurale: se una cosa non compare nelle notizie (per
esempio il canale di una partita) non viene indicata. Podcast fai da te, Gran consiglio e 6 cappelli nascono sul
momento sul telefono: usano la chiave Gemini dell'utente e le voci di Gemini (con la voce del telefono
come riserva).

## Come funziona

```
 ogni mattina alle 04:30 UTC, su GitHub Actions
┌───────────────────────────────────────────────────────────────────────────────┐
│ 1. raccogli.py   feed RSS, podcast, meteo, guida TV      -> data/grezzo.json   │
│ 2. redazione.py  Gemini scrive l'edizione (chiave nel    -> data/edizione.json │
│                  segreto GEMINI_API_KEY) e edge-tts la   -> data/audio/*.mp3   │
│                  legge con una voce neurale gratuita                           │
└───────────────────────────────────────────────────────────────────────────────┘
        │ GitHub Pages (nessun commit dei dati: il repository non cresce)
        ▼
 sul telefono: l'app scarica l'edizione e suona subito gli MP3. Nessuna chiave, nessuna attesa.
```

* **Raccolta**: `scripts/raccogli.py` legge i feed in `config/fonti.json`, i podcast in
  `config/podcast.json`, meteo e guida TV (`config/varie.json`) e scrive `data/grezzo.json`.
* **Edizione con voce neurale**: `scripts/redazione.py` fa scrivere a Gemini scaletta, notizie, Accadde
  oggi, podcast, sezioni di calcio, meteo, TV e rassegne, poi fa leggere ogni testo a
  [edge-tts](https://github.com/rany2/edge-tts) con la voce **`it-IT-ElsaNeural`** (riserva
  `it-IT-IsabellaNeural`, 3 tentativi per voce). Ogni lettura è un MP3 in `data/audio/`: saluto, un file
  per titolo, uno per notizia, il finale, le sezioni di calcio, meteo, TV, Accadde oggi e le rassegne.
  Impostazioni in `config/tg.json` (voci, velocità, saluto, scaletta): vanno tenute allineate a `CONFIG`
  in `index.html`.
* **Sul telefono**: se c'è l'edizione del giorno l'app la usa così com'è, con lo stesso elemento audio
  (schermo spento, comandi sulla schermata di blocco e in auto). Gli MP3 hanno un parametro `?v=` che
  cambia a ogni edizione; il service worker li tiene in cache, così funzionano anche senza connessione.
* **Riserve, in ordine**: se l'edizione del server non c'è (segreto non impostato, Gemini non risponde,
  primo avvio prima della raccolta) l'app prepara tutto sul telefono come prima, con la chiave
  dell'utente: testi con Gemini, voce con Gemini TTS finché c'è quota, e come ultima riserva la migliore
  voce italiana del dispositivo. Lo stesso vale per i testi nati sul momento ("Chiedi all'AI").
* **Rassegna della domenica**: il repository non conserva dati, quindi ogni mattina la raccolta scarica
  `data/settimana.json` già pubblicato sul sito, aggiunge i titoli del giorno e lo ripubblica (ultimi 7 giorni).
* **Cache del giorno** (solo per la preparazione sul telefono): testo e audio restano in IndexedDB.

### Attivare l'edizione con voce neurale

Serve una chiave Gemini salvata come **segreto** del repository (non è visibile a nessuno e non finisce
nel sito): GitHub → repository → **Settings** → **Secrets and variables** → **Actions** →
**New repository secret**, nome `GEMINI_API_KEY`. Oppure, dal terminale: `gh secret set GEMINI_API_KEY`.
La chiave del segreto **non deve avere la restrizione "Siti web"** (le chiamate partono dai server di
GitHub, non dal browser); la restrizione alla sola Generative Language API va bene.
Il server fa 5 chiamate di testo al giorno (edizione, sezioni extra e tre rassegne). Conviene che la chiave del segreto sia diversa da quella usata sul telefono (un altro progetto Google), così le funzioni che nascono sul telefono non restano senza quota. La voce edge-tts è gratuita e non
usa la quota di Gemini; è un servizio non ufficiale di Microsoft, quindi potrebbe cambiare: in quel caso
l'app ripiega da sola sulla preparazione sul telefono.

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
| **Raccolta differenziata** | `config/differenziata.json`: i giorni di Viterbo per zona (da aggiornare a mano se Viterbo Ambiente cambia i calendari) e l'indirizzo da cui si scarica ogni mattina il calendario di Vitorchiano. |
| **Il detto del giorno** | `config/detti.json`: se l'elenco `detti` è vuoto il proverbio lo sceglie Gemini; aggiungendo i proverbi di famiglia ne viene letto uno al giorno, a rotazione. |
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
scripts/redazione.py    edizione del giorno: testi con Gemini, voce neurale con edge-tts
tools/                  generatori di sigla, icone, QR e cartoncino
stampa/                 QR e cartoncino da stampare
.github/workflows/      pubblicazione giornaliera e keepalive
```

## Privacy

* La chiave Gemini resta nel `localStorage` del telefono e viene inviata solo a
  `generativelanguage.googleapis.com`. Non è nel repository né su altri server.
* Il sito non usa cookie né statistiche. Le notizie appartengono alle rispettive
  testate: l'app mostra un riassunto e rimanda all'articolo originale.
