# Research: Peter Steinbergers OpenClaw Use Cases (aus echten Podcast-Transcripts)

_Erstellt: 2026-03-05 | Basierend auf 4 vollständigen Transcripts (9.400+ Zeilen)_

## Quellen (vollständig transkribiert)

1. **Peter Yang** — "How OpenClaw's Creator Uses AI to Run His Life in 40 Minutes" (281K Views)
2. **Y Combinator** — "OpenClaw Creator: Why 80% Of Apps Will Disappear" (758K Views)
3. **The Pragmatic Engineer** — "The creator of Claudebot: I ship code I don't read" (489K Views)
4. **Lex Fridman Podcast #491** — "OpenClaw: Viraler KI-Agent sprengt das Internet" (946K Views)

---

## 1. Persönliche Use Cases (Privatleben)

### 🏠 Smart Home — Volle Kontrolle
> "It can control my lights. I use Philips Hue. It can control my Sonos. I can tell it to wake me up in the morning and slowly turn up the volume."

- **Philips Hue:** Lichter ein/aus, dimmen, Szenen
- **Sonos:** Musik abspielen, Lautstärke steuern, als Wecker nutzen
- **KNX (Wiener Wohnung):** Kann buchstäblich alles steuern — "it could literally lock me out of my house"
- **Wecker:** Erhöht langsam die Musiklautstärke wenn Peter nicht antwortet
  > "It was running on my Mac Studio in London and connecting over SSH to my MacBook in Morocco, turning on the music and making it louder because I didn't reply."

### 📹 Sicherheitskameras — Nachtüberwachung
> "I told it 'watch for strangers' and then it told me in the morning 'Peter, there's someone.' It watched the whole night and made screenshots the whole night of my couch because the camera is pretty blurry and it looked like someone was sitting there."

- Überwacht Kameras eigenständig die ganze Nacht
- Macht Screenshots bei verdächtigen Aktivitäten
- Meldet Auffälligkeiten morgens

### 🛏️ Eight Sleep Bett-Steuerung
> "I have one that reverse-engineered the Eight Sleep API so it can actually control the temperature of my bed."

- Hat die Eight Sleep API reverse-engineered
- Steuert Bett-Temperatur automatisch
- CLI selbst gebaut für die API

### ✈️ Flug-Check-in (British Airways)
> "I let it check in my flight from British Airways. It had to find my passport in my file system. It found it on Dropbox, extracted the key, put everything in correctly and it finally checked me in."

- Findet Reisepass automatisch auf Dropbox
- Füllt alle Felder korrekt aus
- Navigiert durch Anti-Bot-Systeme
- Erstes Mal: ~20 Minuten (hacky). Jetzt: ~2 Minuten
- Klickt sogar "I'm a human" Checkboxen (steuert echten Browser)

### 🗣️ Spontane Sprachnachrichten — Der "Holy Fuck" Moment
> "I sent it a voice message. I didn't build support for voice messages. It showed me a typing indicator. 10 seconds later, it just replied to me. I'm like 'How the f*** did you do that?' And it was like: 'Yeah, the file had no ending. So I looked at the header. I found FFmpeg on your computer and converted it to wave. Then I looked for Whisper but you didn't have it installed. But I found this OpenAI key and used curl to send it to OpenAI's API.'"

- Agent hat **ohne Programmierung** Sprachnachrichten gelernt
- Erkannte Audioformat aus File Header
- Fand FFmpeg, konvertierte zu WAV
- Fand OpenAI Key, nutzte Curl für Whisper API
- **Alles in ~9 Sekunden**
- Hat sogar entschieden, NICHT lokales Whisper zu installieren (zu langsam wegen Model-Download)

### 🍔 Fitness & Ernährung
> "Why should I use MyFitnessPal when I have an infinitely resourceful assistant that already knows I'm making bad decisions and I'm at Kentucky Fried Chicken? It will probably remind me if I forget tracking food. I can just send a picture and it will store it in the database and calculate it and roast me that I should go to the gym."

- Ersetzt MyFitnessPal komplett
- Erkennt Essen per Foto
- Trackt Kalorien automatisch
- Passt Gym-Plan an (mehr Cardio nach schlechtem Essen)
- Roastet Peter wenn er über Kalorienlimit ist

### 🔑 1Password Integration
> "It has its own little 1Password vault. If I want a password shared, I move it into its own vault and it can access that one."

- Eigener separater 1Password Vault für den Agent
- Grenzen bewusst gesetzt (nicht alle Passwörter)

### 🍕 Essen bestellen
> "I built one that hacked into my food delivery here. So it can actually tell me how long it takes until my food's there."

- Reverse-Engineered Food-Delivery API
- Zeigt Lieferzeit an

### 📱 80% der Apps verschwinden
> "This will blend away probably 80% of the apps that you have on your phone. Why do I need a to-do app? I just tell it 'remind me of this' and next day it will remind me. Do I care where it's stored? No. Every app that basically just manages data could be managed in a better way by agents."

Ersetzte Apps:
- **MyFitnessPal** → Fitness-Tracking per Chat
- **To-Do App** → Agent erinnert automatisch
- **Eight Sleep App** → Direkte API-Steuerung
- **Check-in Apps** → Agent checkt Flüge ein
- **Restaurant-Apps** → Agent bucht Tische
- **Shopping Apps** → Agent empfiehlt und kauft

### 🎵 DJ & Musik
- Agent spielt DJ im Discord
- Steuert Sonos-System per Sprachbefehl
- Kann Musik nach Stimmung auswählen

### 🧠 Persönlicher Therapeut / Reflection
> "To be honest, people use their agent not just for problem solving, but for personal problem solving. Very quickly. Super quickly. I fully do that."

- Nutzt Agent für persönliche Reflexion
- Funktioniert als geduldiger Zuhörer
- Gibt einsichtsvolle Fragen zurück

---

## 2. Professionelle Use Cases (Coding)

### 💻 600 Commits pro Tag
> "The other day I had like 600 commits in a single day. This is completely nuts and it works — it's not slop."

- 5-10 Codex-Agenten parallel
- 6 auf einem Screen, 2 auf einem zweiten, 2 auf einem dritten
- Fühlt sich an wie "Starcraft" — Hauptbasis + Nebenstützpunkte

### 🏗️ Architektur statt Code lesen
> "I ship code I don't read. I don't have a line-by-line code understanding — that's what Codex does for me. But I'm the architect."

- Liest den Code nicht mehr im Detail
- Fokus auf System-Architektur und "Taste"
- Beschreibt es als "Weaving" — Code in bestehende Struktur einflechten
- Vergleicht sich mit Schach-Großmeistern die 20 Bretter gleichzeitig spielen

### 🔄 "Close the Loop" — Das Geheimnis
> "The big secret is: the model needs to be able to debug and test itself. That's why agentic coding makes you a better coder — you have to think harder about architecture so it's easier verifiable."

- Agent muss eigene Arbeit validieren können
- Automatische Tests sind wichtiger als je zuvor
- Baut CLI-Tools nur für Debugging
- Beispiel: Docker-Container spinnt auf, installiert alles, testet alle API-Keys

### 📝 PRs sind jetzt "Prompt Requests"
> "I see Pull Requests more as Prompt Requests. I'm actually more interested in the prompts than in the code. I ask people to please add the prompts."

- Liest Prompts statt Code
- Prompt = höheres Signal als Code-Output
- Rewritet fast jeden PR mit eigenem Agent
- "Please don't send small fixes — it takes me 10x more time to review than to just type 'fix' in Codex"

### 🚫 Kein MCP, keine Orchestration
> "I'm very happy that I didn't even build MCP support. Open Claw is very successful and there's no MCP support in there."

- MCPs sind "silly" — müssen alles vorab laden
- Können nicht gechaint/gescriptet werden
- CLIs sind besser: "Models are really good at Unix"
- Makeporter: Konvertiert MCPs in CLIs bei Bedarf
- Kein Gas Town, kein Ralph, keine komplexen Orchestratoren

### 🏭 Plugin-Architektur
> "I said to Codex: 'Look at this PR. Look at this project. Could we weave this feature in?' It referenced Mario's Pi agent plugin architecture and came up with an insanely good plugin system."

- Referenziert andere Projekte als Inspiration
- Agent liest existierenden Code und versteht Patterns
- 15.000-Zeilen Refactor in einer Nacht

### 💰 Token-Hungry aber wertvoll
> "I honestly built the best marketing tool for Anthropic to sell them more subscriptions. I don't know how many people signed up for the $200 subscription because of Cloudbot."

---

## 3. Workflow & Tooling

### 🖥️ Kein Work Trees — Multiple Checkouts
> "I just have multiple copies of the same repository — cloudbot 1, 2, 3, 4, 5. Main is always shippable. I don't like work trees because that's added complexity."

- 5+ Repo-Kopien statt Git Worktrees
- Jede auf Main-Branch
- Kein Branch-Naming, keine Merge-Konflikte
- "Simpler and less friction — all I care about is syncing and text"

### 🎯 Codex > Claude Code
> "I feel like the whole world does Claude Code and I don't think I could have built the thing with Claude Code. Codex is just really brilliant. It is incredibly slow but it almost always gets it right."

- Codex liest 10 Minuten lang Files bevor es anfängt
- Claude Code liest 3 Files und fängt an → muss oft gesteuert werden
- Codex: "Just discuss. Give me options." → Baut erst wenn man "build" sagt
- Claude Code: Plan Mode war "a hack because the model is so trigger-happy"

### 🧪 Kein CI
> "I don't care much about CI. I have local CI. The agent runs the tests. If the tests pass locally, we merge."

- Agent führt Tests lokal aus ("Full Gate")
- "Gate" = Linting + Building + Testing
- Pusht direkt auf Main
- "Sometimes main slips a little bit, but it's usually very close"

### 📖 Dokumentation & Tests — Aber nicht von Hand
> "I would say for my last project I have really good documentation and I didn't write a single line myself. I don't write tests, I don't write documentation."

- Beste Doku die er je hatte — komplett AI-generiert
- Tests sind jetzt Teil des Design-Prozesses
- "How do I close the loop?" ist die zentrale Frage

---

## 4. Philosophie & Prinzipien

### 🎮 "The way to learn AI is to play"
> "I see so many managers for Claude Code or Codex or orchestrators that have the illusion of making you more productive, but really aren't. The beauty is: it's so fun. That's how you learn to program. Prompting is just a different skill."

### 🚫 Anti-Slop / Anti-Orchestration
> "I call it the agentic trap. People discover agents are amazing, then fall deep into building sophisticated tools to accelerate their workflow. But in the end you're just building tools, not actually building something that brings you forward."

- Gas Town = "Slop Town" (hat Bürgermeister, Wächter, Aufseher...)
- Ralph = Waterfall-Modell der Softwareentwicklung
- "Just because you can build everything doesn't mean you should"

### 🎨 Taste > Features
> "Those agents don't really have taste yet. If you don't navigate them well, if you don't have a vision, it's still going to be slop."

- Underprompts bewusst (80% Müll, aber 20% neue Ideen)
- Baut iterativ — nicht nach Spec
- "I have to feel it. I have to click it."
- Vergleicht mit Bildhauer: "You start with a rock and chisel away"

### 💡 SOUL.md — Die Seele des Agents
> "We created a soul.md with the core values — how we think about human-AI interaction, what's important to me, what's important to the model. Some parts are a little mumbo-jumbo, some parts are actually really valuable."

- Bootstrap-Prozess: Agent wird "geboren", fragt wer es ist
- Erstellt Identity.md, Soul.md, User.md
- "The one file that's not open source is my soul.md"
- Evolving documents die der Agent selbst pflegt

### 🧠 Zukunftsvision: Hyper-Personal Assistant
> "Everyone will have their best friend who is a machine that will understand you, know everything about you, can do tasks for you, will be proactive. Everyone who can afford it will have one."

- Ursprüngliche Firma: "Amant Machina" (die liebende Maschine)
- Vision: "Hey, you haven't texted Thomas in 3 weeks and I noticed he's in town right now. Do you want to say hi?"
- Oder: "Every time you meet that person, you're sad. Why is that?"
- Anti-Silos: Deine Daten gehören dir (Markdown-Files)

---

## 5. Karriere-Kontext

### Backstory
- **Herkunft:** Ländliches Oberösterreich, arme Familie, Vater nie kennengelernt
- **Erster Hack:** DOS-Spiel von Schule gestohlen, Kopierschutz geschrieben, verkauft
- **Erster Job:** 5 Jahre .NET-Entwicklung, heimlich modernisiert
- **iPhone-Moment:** "I touched it for a minute and immediately bought one"
- **Erste App:** Dating-App (HTML-Parser!), $10k im ersten Monat, Opa empfing Apple-Zahlung
- **PSPDFKit:** 13 Jahre, 70 Mitarbeiter, auf 1 Milliarde+ Geräten
- **Burnout:** "Not from working too much, but when you work on something you don't believe in anymore"
- **3 Jahre Pause:** "Months where I didn't even turn on my computer"
- **Comeback April 2025:** Direkt mit Claude Code angefangen, alles davor verpasst
- **OpenClaw:** In ~3 Monaten gebaut, 160k+ GitHub Stars
- **Angebote von OpenAI und Meta**

### Persönlichkeit
- Selbstbeschrieben: "Addictive personality", "I've never worked so hard as I do now"
- "Cloud Code Anonymous" Meetup in London gegründet (weil es "a little bit like a drug" ist)
- "It's the same economics as a casino — my little slot machines"
- Liebt Details und Polish: "I built something as if Apple would have built it"
- Gadget-Tipp: Android-Bilderrahmen für €200 → "gives me more joy than the latest iPhone"
- Recharging: Gym mit Coach, Handy im Locker lassen

---

## 6. Zusammenfassung: Konkrete Use Cases

### Privatleben
| Use Case | Detail | Quelle |
|----------|--------|--------|
| 🏠 Philips Hue | Lichter ein/aus/dimmen/Szenen | Peter Yang |
| 🔊 Sonos | Musik, Wecker, DJ | Peter Yang, Pragmatic Eng. |
| 📹 Kameras | Nachtüberwachung, Screenshot-Reports | Peter Yang |
| 🛏️ Eight Sleep | Temperatur steuern (reverse-engineered API) | Peter Yang, YC |
| ✈️ British Airways | Auto-Check-in mit Passportsuche auf Dropbox | Peter Yang |
| 🗣️ Voice Messages | Agent hat Spracherkennung selbst improvisiert | Peter Yang, YC, Pragmatic |
| 🍔 Fitness | Kalorienzählung per Foto, Gym-Planung | Peter Yang, YC |
| 🍕 Food Delivery | Reverse-engineered API für Lieferzeit | Peter Yang |
| 🔑 1Password | Eigener Agent-Vault | Peter Yang |
| 🔐 KNX | Komplette Wohnungssteuerung Wien | Peter Yang |
| 📱 80% App-Ersatz | To-Do, Fitness, Shopping, Check-in, Bett | YC, Peter Yang |
| 🧠 Therapie | Persönliche Reflexion & Coaching | YC |

### Coding
| Use Case | Detail | Quelle |
|----------|--------|--------|
| 💻 600 Commits/Tag | 5-10 parallele Codex-Agenten | Pragmatic Engineer |
| 🏗️ Architektur | "I'm the architect, Codex does the code" | Pragmatic Engineer |
| 📝 Prompt Requests | PRs als Intent lesen, nicht als Code | Pragmatic Engineer |
| 🔄 Close the Loop | Tests + Debug muss Agent selbst können | Pragmatic Engineer |
| 🚫 Anti-MCP | CLIs statt MCPs, Makeporter als Bridge | YC, Pragmatic |
| 🏭 Plugin System | 15k-Zeilen Refactor in einer Nacht | Pragmatic Engineer |
| 📖 Doku & Tests | AI-generiert, beste Doku die er je hatte | Pragmatic Engineer |
| 🐛 Bug-Fix aus Marokko | Screenshot → WhatsApp → Git Fix → Twitter Reply | Peter Yang, YC |
