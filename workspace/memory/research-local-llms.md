# Research: Lokale LLMs als Fallback für OpenClaw

_Erstellt: 2026-03-05 | Maximilian hat gefragt welche lokalen LLMs auf seinem Server laufen könnten falls Claude/Opus nicht mehr verfügbar sind._

## Server-Spezifikationen

| Spec | Wert |
|------|------|
| **CPU** | 2x ARM Neoverse-N1 (aarch64) |
| **RAM** | 3.7 GB total, ~2.5 GB verfügbar |
| **Swap** | 4 GB |
| **GPU** | Keine (Virtio Display Controller = virtuell) |
| **Disk** | 38 GB, 14 GB frei |
| **SIMD** | ARM NEON (asimd), AES, SHA1/SHA2, CRC32 |
| **OS** | Ubuntu, Linux 6.8.0, arm64 |

## Einschränkungen

- **Kein GPU** → nur CPU-Inferenz (langsam bei großen Modellen)
- **3.7 GB RAM** → maximal ~2 GB für das LLM (Gateway + Chromium brauchen ~1.5 GB)
- **2 Cores** → langsame Token-Generierung, besonders bei größeren Modellen
- **ARM64** → nicht alle Modelle/Runtimes unterstützen ARM nativ

## Realistisch nutzbare Modelle (sortiert nach Empfehlung)

### 🥇 Tier 1: Beste Wahl für diesen Server

#### 1. Qwen2.5-1.5B-Instruct (Q4_K_M)
- **RAM:** ~1.2 GB
- **Qualität:** Sehr gut für 1.5B — mehrsprachig (Deutsch!), guter Instruction-Following
- **Speed:** ~8-12 tok/s auf 2x Neoverse-N1
- **Warum:** Bestes Verhältnis Qualität/Ressourcen. Versteht Deutsch gut.

#### 2. Phi-3.5-mini-instruct (3.8B, Q4_K_M)
- **RAM:** ~2.3 GB
- **Qualität:** Sehr stark für seine Größe. Microsoft-Modell, gut bei Reasoning + Code.
- **Speed:** ~3-5 tok/s (knapp, nutzt Swap)
- **Warum:** Deutlich schlauer als 1.5B-Modelle, aber grenzwertig beim RAM.

#### 3. Gemma 2 2B Instruct (Q4_K_M)
- **RAM:** ~1.5 GB
- **Qualität:** Googles kleines Modell. Solide, gutes Deutsch.
- **Speed:** ~6-10 tok/s
- **Warum:** Guter Kompromiss zwischen Qwen 1.5B und Phi-3.5.

### 🥈 Tier 2: Möglich, aber mit Einschränkungen

#### 4. Llama 3.2 3B Instruct (Q4_K_M)
- **RAM:** ~2.0 GB
- **Qualität:** Metas kleinstes brauchbares Modell. Englisch sehr gut, Deutsch okay.
- **Speed:** ~4-6 tok/s
- **Warum:** Solide, aber Qwen/Phi sind in dieser Größe oft besser.

#### 5. TinyLlama 1.1B (Q4_K_M)
- **RAM:** ~0.8 GB
- **Qualität:** Für einfache Tasks (Zusammenfassungen, simple Fragen). Nicht für komplexe Reasoning.
- **Speed:** ~15-20 tok/s
- **Warum:** Extrem schnell und leicht, aber deutlich dümmer.

### 🚫 Tier 3: Nicht empfohlen für diesen Server

| Modell | RAM | Warum nicht |
|--------|-----|-------------|
| Llama 3.1 8B | ~5 GB | Zu viel RAM, würde komplett in Swap laufen → extrem langsam |
| Mistral 7B | ~4.5 GB | Gleicher Grund |
| DeepSeek V2 Lite 16B | ~10 GB | Unmöglich |
| Jedes 13B+ Modell | >8 GB | Unmöglich |

## Empfohlene Runtime: Ollama

**Ollama** ist die beste Wahl:
- ✅ Unterstützt ARM64 nativ
- ✅ Einfache Installation (`curl -fsSL https://ollama.ai/install.sh | sh`)
- ✅ OpenAI-kompatible API (Port 11434)
- ✅ OpenClaw kann Ollama als Provider nutzen
- ✅ Automatische Quantisierung + Modelmanagement
- ✅ Lädt Modelle bei Bedarf und entlädt sie wieder (spart RAM)

**Alternative:** llama.cpp direkt (mehr Kontrolle, weniger komfortabel)

## OpenClaw Integration

Ollama als Provider in `openclaw.json`:
```json
{
  "models": {
    "providers": {
      "ollama": {
        "baseUrl": "http://localhost:11434/v1",
        "apiKey": "ollama",
        "api": "openai-completions",
        "models": [
          {"id": "qwen2.5:1.5b", "name": "Qwen 2.5 1.5B (lokal)"}
        ]
      }
    }
  }
}
```

Dann als Fallback oder für günstige Tasks nutzbar.

## Empfehlung

**Für deinen Server empfehle ich:**

1. **Ollama installieren** + **Qwen2.5-1.5B** als Standard-Lokalmodell
2. **Phi-3.5-mini** als stärkere Option für komplexere Tasks (wenn Gateway gerade nicht läuft)
3. Als **Fallback-Kette** in OpenClaw: Opus → Sonnet → Gemini Flash → Ollama/Qwen lokal

**Ehrliche Einschätzung:** Lokale Modelle auf diesem Server sind ein Notfall-Fallback, kein Ersatz für Claude Opus. Die Qualität ist 10-20x schlechter, die Geschwindigkeit langsam. Für einfache Tasks (Zusammenfassungen, simple Fragen, Formatierung) reicht es. Für komplexe Reasoning, Coding, oder mehrstufige Aufgaben nicht.

**Bessere Alternativen bei Budget-Problemen:**
- Gemini Flash (kostenlos, schnell, gut)
- DeepSeek V3 (sehr günstig, $0.27/M input tokens)
- Guthaben aufladen statt lokal zu rechnen

## Nächste Schritte (falls gewünscht)

1. `curl -fsSL https://ollama.ai/install.sh | sh`
2. `ollama pull qwen2.5:1.5b`
3. Provider in OpenClaw konfigurieren
4. Testen

---
_Recherche basiert auf aktuellem Wissen über lokale LLMs (Stand Q1 2026) und den konkreten Server-Specs._
