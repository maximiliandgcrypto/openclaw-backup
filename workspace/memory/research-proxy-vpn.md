# Research: Proxy / VPN für Server (YouTube IP-Block umgehen)

_Erstellt: 2026-03-05 | Problem: YouTube und andere Services blocken Cloud-IPs (Hetzner, AWS, GCP etc.)_

## Das Problem

- YouTube erkennt Hetzner-IPs als Cloud-Provider und blockt Anfragen
- Betrifft: yt-dlp, youtube-transcript-api, Web Scraping generell
- Auch andere Services blocken Cloud-IPs (Twitter, LinkedIn, etc.)

## Optionen im Vergleich

### 🥇 Option 1: Residential Proxy (EMPFEHLUNG)

**Was:** Proxy-Server mit echten Heim-IPs (von ISPs, nicht Rechenzentren)
**Warum beste Option:** YouTube sieht eine normale Heim-IP, kein Cloud-Provider

| Anbieter | Preis | Qualität | ARM64 Support |
|----------|-------|----------|---------------|
| **Bright Data** | ab $5.04/GB | Sehr gut, 72M+ IPs, YouTube funktioniert | Ja (API-basiert) |
| **Oxylabs** | ab $8/GB | Premium, sehr zuverlässig | Ja (API-basiert) |
| **Smartproxy** | ab $2.2/GB | Gutes Preis-Leistung | Ja (API-basiert) |
| **IPRoyal** | ab $1.75/GB | Budget-Option, gut für YouTube | Ja (API-basiert) |
| **Webshare** | ab $1/GB (Rotating) | Günstigste Option, okay Qualität | Ja (API-basiert) |

**Integration:**
```bash
# HTTP Proxy in yt-dlp
yt-dlp --proxy "http://user:pass@proxy.example.com:port" "VIDEO_URL"

# Oder als Env-Variable für alle Tools
export HTTP_PROXY="http://user:pass@proxy.example.com:port"
export HTTPS_PROXY="http://user:pass@proxy.example.com:port"
```

**Vorteile:**
- YouTube-Block wird zuverlässig umgangen
- Rotierende IPs (schwer zu blocken)
- Keine Software-Installation nötig (HTTP-Proxy)
- Pay-per-GB (nur zahlen was du brauchst)

**Nachteile:**
- Kosten pro GB Traffic
- Latenz etwas höher

---

### 🥈 Option 2: SOCKS5 Proxy (Günstige Alternative)

**Was:** SOCKS5-Proxies von Residential-Anbietern
**Warum:** Schneller als HTTP-Proxies, besser für Streaming

| Anbieter | Preis | Typ |
|----------|-------|-----|
| **ProxyScrape** | ab $3/Monat | Rotating Residential SOCKS5 |
| **922proxy** | ab $2/GB | Residential SOCKS5 |

**Integration:**
```bash
yt-dlp --proxy "socks5://user:pass@proxy:port" "VIDEO_URL"
```

---

### 🥉 Option 3: VPN auf dem Server

**Was:** VPN-Client auf dem Hetzner-Server → Traffic läuft über VPN
**Warum:** Gesamter Traffic wird verschleiert, nicht nur einzelne Requests

| Anbieter | Preis | CLI-Support | ARM64 |
|----------|-------|-------------|-------|
| **Mullvad** | €5/Monat | ✅ WireGuard CLI | ✅ |
| **ProtonVPN** | Kostenlos/€5/Mo | ✅ CLI | ✅ |
| **Surfshark** | ~€2/Monat | ✅ CLI | ⚠️ (OpenVPN) |
| **NordVPN** | ~€3/Monat | ✅ CLI | ⚠️ (OpenVPN) |

**Integration (WireGuard, am Beispiel Mullvad):**
```bash
# Installation
sudo apt install wireguard
# Config generieren auf mullvad.net
sudo wg-quick up wg0
# Fertig — gesamter Traffic läuft über VPN
```

**Vorteile:**
- Einfach einzurichten
- Gesamter Traffic geschützt
- Fester Monatspreis (egal wie viel Traffic)

**Nachteile:**
- Gesamter Server-Traffic geht über VPN (kann Gateway-Latenz erhöhen)
- VPN-IPs werden auch teilweise erkannt/geblockt
- Weniger zuverlässig als Residential Proxies für YouTube

---

### Option 4: WireGuard Split-Tunnel (Best of Both Worlds)

**Was:** Nur bestimmter Traffic geht über VPN, Rest bleibt direkt
**Warum:** Gateway/Telegram bleiben schnell, nur YouTube/Scraping über VPN

```bash
# WireGuard Config mit AllowedIPs nur für YouTube
[Interface]
PrivateKey = ...
Address = 10.66.66.2/32

[Peer]
PublicKey = ...
Endpoint = vpn.example.com:51820
# Nur YouTube-IP-Ranges über VPN routen
AllowedIPs = 142.250.0.0/15, 172.217.0.0/16, 216.58.0.0/16
```

**Vorteil:** Kein Latenz-Impact auf den normalen Betrieb
**Nachteil:** YouTube-IP-Ranges ändern sich, muss gepflegt werden

---

### Option 5: Apify / SaaS Transcript-Services

**Was:** Transcript als API-Service nutzen, ohne eigene IP
**Warum:** Kein Proxy/VPN nötig, funktioniert sofort

| Service | Preis | Beschreibung |
|---------|-------|------------|
| **Apify YouTube Transcript** | Free Tier + $5/Mo | API für YouTube-Transcripts |
| **Supadata** | Free Tier | YouTube Transcript API |
| **RapidAPI YouTube Transcript** | Free/Paid | Diverse Anbieter |

**Integration:**
```bash
export APIFY_API_TOKEN="dein_token"
# summarize CLI kann Apify als Fallback nutzen
summarize "https://youtube.com/watch?v=..." --youtube auto
```

**Vorteil:** Sofort nutzbar, kein Server-Setup
**Nachteil:** Abhängig von externem Service

---

## Empfehlung für deinen Use Case

**Für YouTube-Transcripts speziell:**

1. **Kurzfristig (sofort):** Apify Free Tier einrichten → `APIFY_API_TOKEN` setzen → funktioniert mit summarize CLI (sobald ARM-Binary gefixt)
2. **Mittelfristig:** Residential Proxy (IPRoyal oder Webshare) → $1-2/GB, Pay-per-Use
3. **Langfristig (wenn mehr Services geblockt werden):** Mullvad WireGuard Split-Tunnel → €5/Mo, alles abgedeckt

**Für allgemeines Web Scraping (Twitter, LinkedIn etc.):**

→ **Residential Proxy** ist die einzig zuverlässige Option. VPNs werden mittlerweile auch von vielen Services erkannt.

**Budget-Empfehlung:**
- Unter €5/Monat: Apify Free + IPRoyal bei Bedarf
- €5/Monat: Mullvad WireGuard
- €10+/Monat: Bright Data oder Oxylabs (Premium, alles funktioniert)

---

## Nächste Schritte (falls gewünscht)

1. **Apify Token holen** (kostenlos) → sofort YouTube-Transcripts
2. **Oder:** Mullvad Account → WireGuard auf Server installieren
3. **Oder:** IPRoyal Account → Proxy in yt-dlp/Tools konfigurieren
