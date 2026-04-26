## Review Report: Self-Introduction Feature (Design Document)

No actual source code was provided for review. The following analysis is based solely on the provided technical solution description and addresses design decisions, potential gaps, and risks that should be verified or implemented in the code.

---

### 1. Issues Found

| # | Severity | Issue | Details |
|---|----------|-------|---------|
| 1 | **CRITICAL** | No input validation or sanitization described for the `message` field. | The API accepts arbitrary user input. Without validation, the system is vulnerable to injection attacks if any component processes the input unsafely (e.g., YAML template injection, log injection, XSS if responses are rendered in a UI). The design mentions keyword matching and language detection but does not specify any sanitisation or encoding. |
| 2 | **HIGH** | Language detection heuristic may misclassify mixed or CJK-only input. | Using CJK Unicode range as sole Chinese detection will fail for Chinese text that contains only non‑CJK characters (e.g., pinyin, Chinese punctuation, emoji). It will also misclassify Japanese kanji as Chinese. The fallback to `langdetect` is only for “other supported languages”, but the initial routing to Chinese/English is purely heuristic and may produce incorrect output. |
| 3 | **HIGH** | Word count truncation logic is insufficiently specified. | The design states “truncates at the last full sentence before the limit”. In practice, identifying a “full sentence” reliably across languages (especially CJK where punctuation differs) is non‑trivial. If truncation fails, the response may exceed the 100‑word limit or cut off mid‑sentence, violating AC‑04. |
| 4 | **MEDIUM** | Follow‑up detection is ambiguous and may cause unintended matches. | follow‑up keywords like “更多”, “more”, “tell me more” are very generic. If a user asks “请告诉我更多关于天气的信息” after an unrelated introduction, the system might return the intro follow‑up instead of answering the weather question. The design does not mention any context tracking or session state to avoid false positives. |
| 5 | **MEDIUM** | No error handling for YAML parsing or missing keys. | Configuration files are assumed to be correct. If a YAML is malformed or a required key is missing (e.g., `follow_up.details_url`), the service will crash or behave unexpectedly. A graceful fallback or validation at startup is needed. |
| 6 | **MEDIUM** | “language” field in response could be misleading. | The response includes a `language` field (e.g., “zh”), but the actual response text could be auto‑translated or improperly detected. The field might not match the user’s language, causing confusion for downstream systems. |
| 7 | **LOW** | Configuration reload mechanism (SIGHUP) is fragile in containerised environments. | In Docker/Kubernetes, sending signals is unusual and often unsupported by orchestrators. A periodic poll (60s) is mentioned as an alternative, but the design should default to that and make SIGHUP optional. |
| 8 | **LOW** | Response time budget of 500ms for the endpoint seems overly tight. | The design allocates ~61ms for processing, leaving >400ms for network/queueing. That’s conservative, but the hand‑written timing (5ms for intent detection etc.) is likely optimistic. Real‑world performance should be measured. |
| 9 | **LOW** | Test AC‑01 uses a stopwatch, which is unreliable for automation. | Automated performance testing requires tools like `ab` or `locust`. A human stopwatch is not repeatable and cannot be part of a CI pipeline. |

---

### 2. Suggestions for Improvement

- **Input sanitisation:** Implement strict validation of the `message` field (length limit, reject binary content, escape HTML/control characters). For YAML template rendering, ensure placeholder substitution does not evaluate arbitrary expressions (use `string.replace()` or safe templating like `jinja2` with sandbox).
- **Robust language detection:** Use a dedicated language detection library (e.g., `fastText`, `langdetect`, `spacy‑langdetect`) as the primary method rather than a heuristic. Cache the result per request. The CJK heuristic can be a fast path for known‑dominant languages, but always confirm with the library.
- **Word count and truncation:** For sentence‑aware truncation, implement a language‑specific sentence splitter (e.g., using `nltk` for English, `jieba` for Chinese, or a simple regex that respects punctuation `. ! ? 。！？`). Alternatively, enforce the word limit strictly by truncating at the last space before the 100th token, and append an ellipsis.
- **Context handling for follow‑up:** Use a lightweight session store (e.g., in‑memory dict with TTL) to track whether the last interaction was an introduction. Only respond to “tell me more” if the session flag is set. This prevents false positives.
- **YAML validation:** Add a configuration validator (e.g., using `jsonschema` or `pydantic`) that runs at startup and on reload. If validation fails, log the error and continue with the last successful configuration.
- **Response language consistency:** Verify that the `language` field always matches the language used in the response. If a user sends input in a mix of languages, choose the most confident detection and optionally note uncertainty.
- **Config reload:** Prefer file‑watching (e.g., `watchfiles`) or a periodic check with a configurable interval. SIGHUP should remain an option but not the primary mechanism. Containerise with a health endpoint that forces reload.
- **Performance testing:** Replace stopwatch‑based AC‑01 with automated load generation and store latency percentiles in a monitoring system.
- **Extensibility documentation:** The design claims no code changes are needed for new languages, but the language detector must be updated in code to support a new language code. Clarify that adding a language means adding a YAML file **and** updating the supported list in `language_detector.py`.
- **Security:** Consider that YAML files could be attacked if an attacker can write to the config directory. Validate YAML source integrity (checksum, read‑only permissions). Also ensure the `details_url` from config is not used unsafely in redirects or user‑facing links without validation.

---

### Summary

The design is well‑structured and covers many operational aspects. The most critical gaps are the lack of input validation and the ambiguity of language detection and follow‑up handling. Implementing the suggestions above will improve correctness, security, and maintainability before moving to implementation.

*Reviewed by: AI Code Reviewer*  
*Date: 2025‑02‑25*