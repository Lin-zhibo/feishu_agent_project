## Technical Solution: Self-Introduction Feature

### 1. Architecture Overview

The self‑introduction feature is implemented as a lightweight, stateless microservice within the larger AI assistant ecosystem. The architecture follows a pipeline pattern optimized for low latency and high availability.

**Components:**

- **Intent Detector** – Identifies whether the user input is a self‑introduction request (e.g., “请你介绍一下你自己”) or a follow‑up request (e.g., “tell me more”). Supports both keyword matching and, optionally, a lightweight ML classifier for extensibility.
- **Language Detector** – Determines the language of the user input. Uses a fast heuristic (character Unicode ranges) for Chinese/English, with fallback to a library like `langdetect` for other supported languages.
- **Introduction Service** – Core logic: loads the appropriate content template from a configuration file, renders it (e.g., inserts the system name), enforces the 100‑word limit, and returns the response. Caches configuration to avoid repeated disk I/O.
- **Follow‑up Handler** – If the user shows further interest, returns additional details (e.g., a link to a help page) as defined in the configuration.
- **Response Pipeline** – Ensures friendly, professional tone by applying a deterministic template with no randomness.

**Data Flow:**

1. User sends message to the chat interface.
2. HTTP request reaches the Introduction Service endpoint.
3. Intent Detector classifies the message.
4. If intro request → Language Detector processes the input.
5. Introduction Service loads the configuration for that language, renders the template.
6. Response is returned as JSON.

The service is deployed behind a load balancer with at least two instances to achieve 99.9% availability. Caching (e.g., Redis) can be added for the configuration, but in‑memory caching suffices given the small footprint.

---

### 2. File Structure

```
self-intro-service/
├── main.py                          # Entry point (Flask/FastAPI app)
├── config/
│   ├── introduction_zh.yaml         # Chinese introduction template
│   ├── introduction_en.yaml         # English introduction template
│   └── introduction_fr.yaml         # French example (extensible)
├── handlers/
│   ├── introduction_handler.py      # Core logic for intro generation
│   └── follow_up_handler.py         # Handles "tell me more" requests
├── services/
│   ├── intent_detector.py           # Classifies user input intent
│   └── language_detector.py         # Detects user language
├── tests/
│   ├── test_introduction.py
│   └── test_intent_detector.py
├── requirements.txt                 # Dependencies
└── Dockerfile                       # Container definition
```

**YAML Configuration Example (introduction_en.yaml):**
```yaml
name: "ChatBot"
capabilities: "I can help with language understanding, answering questions, and task assistance."
limitations: "I cannot access real-time data or the internet."
tone: "friendly and professional"
max_words: 100
follow_up:
  prompt: "Would you like to know more about my features?"
  details_url: "/help"
```

The template is rendered by replacing placeholders (e.g., `{name}`, `{capabilities}`, `{limitations}`) with the values from the YAML. The final string is automatically word‑counted and truncated if necessary.

---

### 3. API Design

**Endpoint:** `POST /api/introduction`

**Request Body:**
```json
{
  "message": "请你介绍一下你自己"
}
```

**Response (200 OK):**
```json
{
  "response": "你好！我是ChatBot，一个AI助手。我可以帮助你理解语言、回答问题以及完成各种任务。请注意，我无法访问实时数据或互联网。",
  "language": "zh",
  "follow_up_prompt": "你想了解更多关于我的功能吗？"
}
```

**Error Responses:**
- `400 Bad Request` – Missing or empty `message` field.
- `500 Internal Server Error` – Configuration load failure.

**Design Notes:**
- The endpoint is stateless – no session or authentication required for this single feature.
- Response time is measured from receipt of request to sending the response; the handler must complete within 500ms to allow for network latency.
- For follow‑up requests, the same endpoint is used; the **Intent Detector** differentiates between an initial introduction and a follow‑up by matching keywords like “更多” / “more” / “tell me more”.

---

### 4. Key Implementation Notes

#### 4.1 Intent Detection
- **Primary method:** Keyword‑based matching against a set of phrases (e.g., “介绍”, “你是谁”, “introduce yourself”). This is extremely fast (<1ms).
- **Secondary method (optional):** Use a small regex or a pre‑trained text classifier (e.g., fastText) for better generalization. The model would be loaded once at startup.
- **Follow‑up detection:** After an introduction, if the user sends a message containing “更多”, “more”, “details”, the system returns the `follow_up` content from the config.

#### 4.2 Language Detection
- **Chinese detection:** Check if the input contains any CJK Unified Ideographs (U+4E00–U+9FFF). If yes, treat as Chinese.
- **English detection:** Otherwise, default to English. For other languages, use `langdetect` library with a timeout (500ms max). The result is cached per request.
- To meet the 2‑second end‑to‑end SLA, language detection must complete within 100ms.

#### 4.3 Configuration Management
- Config files are loaded into memory at service startup. Any update to a config file triggers a graceful reload via a `SIGHUP` signal or a periodic check (every 60 seconds) without user‑visible downtime.
- The configuration contains the exact text for capabilities and limitations, ensuring consistency across sessions. No dynamic generation is used.

#### 4.4 Word Count & Tone
- The handler counts words using a simple tokenizer (split on spaces for English, character count for Chinese). If the rendered text exceeds 100 words, it truncates at the last full sentence before the limit.
- Tone is enforced by the template itself – every intro begins with a greeting, states the name, lists capabilities, then limitations, and ends with a positive offer. No slang or overly casual language is allowed.

#### 4.5 Performance & Availability
- **Caching:** Config is held in a Python dictionary; no external cache is required for a single instance. For multi‑instance deployments, a shared Redis can keep configs in sync.
- **Response time budget:** intent detection (5ms) + language detection (50ms) + config load (1ms, cached) + template rendering (5ms) = ~61ms. The rest of the 2‑second SLA is allocated to network and queueing.
- **Availability:** Deploy at least two instances behind a load balancer with health checks. Use a container orchestrator (Kubernetes) that restarts failed containers automatically.

#### 4.6 Testing & Verification
- **AC-01:** Use an automated script that sends “请你介绍一下你自己” and measures round‑trip time with a stopwatch. Log response times to a monitoring system.
- **AC-02:** Unit test verifies that the response contains keywords like “AI assistant”, “can help with”, “cannot access real‑time”.
- **AC-03:** Send inputs in Chinese, English, and French – verify the `language` field in the response matches.
- **AC-04:** Word‑count check in integration tests.
- **AC-05:** Human QA reviews the templates once per release.
- **AC-06:** Run 10 successive identical requests; compare responses programmatically (ignoring timestamps, if any).
- **AC-07:** Send “tell me more” after an introduction; verify that the follow‑up prompt appears and that the system returns a help link.

#### 4.7 Extensibility
- Adding a new language requires only: 1) creating a new YAML file (e.g., `introduction_ja.yaml`), 2) adding the language code to the language detector’s supported list, and 3) reloading configuration. No code changes are needed.
- Changing the introduction text (e.g., updating capabilities) is done by editing the YAML file – the service automatically picks up the change on the next config reload.

---

*This design satisfies all functional and non‑functional requirements while keeping the implementation simple, testable, and maintainable.*