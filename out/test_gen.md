Below are the pytest unit and integration tests covering the self‑introduction service as described. They verify each component (intent detection, language detection, introduction rendering, follow‑up handling) and the full `/api/introduction` endpoint, including edge cases and error conditions.

---

```python
# tests/conftest.py
import pytest
from unittest.mock import Mock, patch
import yaml
from fastapi.testclient import TestClient
from main import app  # assume FastAPI app in main.py

# Sample configs for testing
SAMPLE_CONFIG_EN = {
    "name": "ChatBot",
    "capabilities": "I can help with language understanding, answering questions, and task assistance.",
    "limitations": "I cannot access real-time data or the internet.",
    "tone": "friendly and professional",
    "max_words": 100,
    "follow_up": {
        "prompt": "Would you like to know more about my features?",
        "details_url": "/help"
    }
}

SAMPLE_CONFIG_ZH = {
    "name": "ChatBot",
    "capabilities": "我可以帮助你理解语言、回答问题以及完成各种任务。",
    "limitations": "我无法访问实时数据或互联网。",
    "tone": "友好且专业",
    "max_words": 100,
    "follow_up": {
        "prompt": "你想了解更多关于我的功能吗？",
        "details_url": "/help"
    }
}

SAMPLE_CONFIG_FR = {
    "name": "ChatBot",
    "capabilities": "Je peux vous aider à comprendre le langage, répondre aux questions et effectuer des tâches.",
    "limitations": "Je ne peux pas accéder aux données en temps réel ni à Internet.",
    "tone": "amical et professionnel",
    "max_words": 100,
    "follow_up": {
        "prompt": "Souhaitez-vous en savoir plus sur mes fonctionnalités?",
        "details_url": "/aide"
    }
}

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)

@pytest.fixture
def mock_config_loader():
    """Mock loading of YAML configs."""
    def _mock_load(language):
        configs = {"en": SAMPLE_CONFIG_EN, "zh": SAMPLE_CONFIG_ZH, "fr": SAMPLE_CONFIG_FR}
        return configs.get(language, None)
    return _mock_load

@pytest.fixture
def mock_intent_detector():
    """Fixture to mock intent detector."""
    with patch("services.intent_detector.IntentDetector") as mock:
        detector = mock.return_value
        # Default: classify as initial intro
        detector.classify.return_value = "initial_intro"
        yield detector

@pytest.fixture
def mock_language_detector():
    """Fixture to mock language detector."""
    with patch("services.language_detector.LanguageDetector") as mock:
        detector = mock.return_value
        detector.detect.return_value = "en"
        yield detector
```

---

```python
# tests/test_intent_detector.py
import pytest
from unittest.mock import patch
from services.intent_detector import IntentDetector

# We assume IntentDetector has a method classify(message) -> str
# Possible returns: "initial_intro", "follow_up", "other"

@pytest.mark.unit
class TestIntentDetector:
    """Unit tests for IntentDetector."""

    def setup_method(self):
        self.detector = IntentDetector()

    @patch("services.intent_detector.load_keywords")
    def test_initial_intro_chinese(self, mock_keywords):
        """AC-07: Chinese 'introduce yourself' triggers initial_intro."""
        mock_keywords.return_value = {"initial": ["介绍", "你是谁", "自我介绍"]}
        result = self.detector.classify("请你介绍一下你自己")
        assert result == "initial_intro"

    @patch("services.intent_detector.load_keywords")
    def test_follow_up_english(self, mock_keywords):
        """AC-07: 'tell me more' triggers follow_up."""
        mock_keywords.return_value = {"follow_up": ["more", "tell me more", "details"]}
        result = self.detector.classify("tell me more")
        assert result == "follow_up"

    @patch("services.intent_detector.load_keywords")
    def test_non_intro_message(self, mock_keywords):
        """Random message triggers 'other'."""
        mock_keywords.return_value = {"initial": ["介绍"], "follow_up": ["more"]}
        result = self.detector.classify("What is the weather?")
        assert result == "other"

    @patch("services.intent_detector.load_keywords")
    def test_empty_message(self, mock_keywords):
        """Empty message returns 'other' (not an error)."""
        mock_keywords.return_value = {"initial": [], "follow_up": []}
        result = self.detector.classify("")
        assert result == "other"
```

---

```python
# tests/test_language_detector.py
import pytest
from services.language_detector import LanguageDetector

# Assume detect(message) -> str (language code)

@pytest.mark.unit
class TestLanguageDetector:
    """Unit tests for LanguageDetector."""

    def setup_method(self):
        self.detector = LanguageDetector()

    def test_detect_chinese(self):
        """CJK characters → 'zh'."""
        result = self.detector.detect("请你介绍一下你自己")
        assert result == "zh"

    def test_detect_english(self):
        """ASCII without CJK → 'en'."""
        result = self.detector.detect("Please introduce yourself")
        assert result == "en"

    def test_detect_french(self):
        """French text (Latin with accents) → 'fr' using langdetect fallback."""
        # Assume langdetect works; we can simulate with a mock if needed
        result = self.detector.detect("Présentez-vous, s'il vous plaît")
        assert result == "fr"

    def test_detect_empty_message(self):
        """Empty string → default 'en'."""
        result = self.detector.detect("")
        assert result == "en"

    def test_detect_mixed_languages(self):
        """Mixed Chinese and English → prefer Chinese (first CJK)."""
        result = self.detector.detect("Hello 世界")
        assert result == "zh"
```

---

```python
# tests/test_introduction_handler.py
import pytest
from unittest.mock import patch, MagicMock
from handlers.introduction_handler import IntroductionHandler
from config.loader import ConfigLoader  # assume exists

@pytest.mark.unit
class TestIntroductionHandler:
    """Unit tests for IntroductionHandler (intro rendering)."""

    def setup_method(self):
        self.handler = IntroductionHandler()

    @patch.object(ConfigLoader, "get_config")
    def test_render_introduction_english(self, mock_get_config):
        """Verify template placeholders are replaced correctly."""
        config = {
            "name": "ChatBot",
            "capabilities": "I can help with language understanding.",
            "limitations": "I cannot access real-time data.",
            "max_words": 100,
            "follow_up": {}
        }
        mock_get_config.return_value = config
        rendered = self.handler.render_introduction("en")
        expected = "I am ChatBot, an AI assistant. I can help with language understanding. Please note, I cannot access real-time data."
        assert rendered == expected

    @patch.object(ConfigLoader, "get_config")
    def test_word_count_truncation(self, mock_get_config):
        """Words > max_words should be truncated to last complete sentence under limit."""
        config = {
            "name": "ChatBot",
            "capabilities": "A " * 50,   # 50 words
            "limitations": "B " * 60,   # 60 words
            "max_words": 100,           # total would be >100
            "follow_up": {}
        }
        mock_get_config.return_value = config
        rendered = self.handler.render_introduction("en")
        word_count = len(rendered.split())
        assert word_count <= 100
        # Ensure it ends with a period (complete sentence)
        assert rendered.rstrip().endswith(".")
        # Verify it contains the beginning of the capabilities
        assert "A" in rendered

    @patch.object(ConfigLoader, "get_config")
    def test_word_count_within_limit(self, mock_get_config):
        """Short text stays unchanged."""
        config = {
            "name": "Bot",
            "capabilities": "Short.",
            "limitations": "None.",
            "max_words": 100,
            "follow_up": {}
        }
        mock_get_config.return_value = config
        rendered = self.handler.render_introduction("en")
        assert len(rendered.split()) <= 100
        assert "Short." in rendered

    @patch.object(ConfigLoader, "get_config")
    def test_config_loaded_per_language(self, mock_get_config):
        """Handler calls ConfigLoader with correct language."""
        mock_get_config.return_value = {}
        self.handler.render_introduction("fr")
        mock_get_config.assert_called_with("fr")
```

---

```python
# tests/test_follow_up_handler.py
import pytest
from unittest.mock import patch
from handlers.follow_up_handler import FollowUpHandler
from config.loader import ConfigLoader

@pytest.mark.unit
class TestFollowUpHandler:
    """Unit tests for FollowUpHandler."""

    def setup_method(self):
        self.handler = FollowUpHandler()

    @patch.object(ConfigLoader, "get_config")
    def test_follow_up_returns_prompt_and_url(self, mock_get_config):
        """Handler returns follow-up object from config."""
        mock_get_config.return_value = {
            "follow_up": {
                "prompt": "Want more?",
                "details_url": "/help"
            }
        }
        result = self.handler.get_follow_up("en")
        assert result == {"prompt": "Want more?", "details_url": "/help"}

    @patch.object(ConfigLoader, "get_config")
    def test_no_follow_up_for_initial_intro(self, mock_get_config):
        """When intent is initial_intro, follow_up should not be returned."""
        # In the real handler, this might return None or empty
        result = self.handler.get_follow_up("en", is_initial=True)
        assert result is None or result == {}
```

---

```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch, MagicMock

@pytest.mark.integration
class TestIntroductionAPI:
    """Integration tests for POST /api/introduction."""

    def test_intro_zh(self, client, mock_intent_detector, mock_language_detector, mock_config_loader):
        """AC-02 & AC-03: Chinese request returns correct response and language."""
        mock_intent_detector.classify.return_value = "initial_intro"
        mock_language_detector.detect.return_value = "zh"
        # Patch the introduction_handler to use mock config
        with patch("handlers.introduction_handler.ConfigLoader.get_config", return_value=SAMPLE_CONFIG_ZH):
            response = client.post("/api/introduction", json={"message": "请你介绍一下你自己"})
            assert response.status_code == 200
            data = response.json()
            assert data["language"] == "zh"
            assert "ChatBot" in data["response"]
            assert "可以帮助" in data["response"]
            assert "无法访问" in data["response"]

    def test_intro_en(self, client, mock_intent_detector, mock_language_detector):
        """AC-02 & AC-03: English request returns correct response and language."""
        # Reset mocks if needed
        mock_intent_detector.classify.return_value = "initial_intro"
        mock_language_detector.detect.return_value = "en"
        with patch("handlers.introduction_handler.ConfigLoader.get_config", return_value=SAMPLE_CONFIG_EN):
            response = client.post("/api/introduction", json={"message": "Introduce yourself"})
            assert response.status_code == 200
            data = response.json()
            assert data["language"] == "en"
            assert "AI assistant" in data["response"]
            assert "cannot access real-time" in data["response"]

    def test_intro_fr(self, client, mock_intent_detector, mock_language_detector):
        """AC-03: French request returns French response and language code."""
        mock_intent_detector.classify.return_value = "initial_intro"
        mock_language_detector.detect.return_value = "fr"
        with patch("handlers.introduction_handler.ConfigLoader.get_config", return_value=SAMPLE_CONFIG_FR):
            response = client.post("/api/introduction", json={"message": "Présentez-vous"})
            assert response.status_code == 200
            data = response.json()
            assert data["language"] == "fr"
            assert "ChatBot" in data["response"]
            assert "Je peux" in data["response"]

    def test_follow_up_request(self, client, mock_intent_detector, mock_language_detector):
        """AC-07: Follow-up request returns follow_up_prompt."""
        mock_intent_detector.classify.return_value = "follow_up"
        mock_language_detector.detect.return_value = "en"
        with patch("handlers.introduction_handler.ConfigLoader.get_config", return_value=SAMPLE_CONFIG_EN):
            response = client.post("/api/introduction", json={"message": "tell me more"})
            assert response.status_code == 200
            data = response.json()
            assert data["follow_up_prompt"] == SAMPLE_CONFIG_EN["follow_up"]["prompt"]
            # Optionally check details_url if included in response (spec says it may)
            # The spec example shows follow_up_prompt, not details_url in response

    def test_empty_message_error(self, client):
        """Empty message → 400 Bad Request."""
        response = client.post("/api/introduction", json={"message": ""})
        assert response.status_code == 400
        assert "detail" in response.json()  # FastAPI error detail

    def test_missing_message_field(self, client):
        """Missing 'message' field → 400 Bad Request."""
        response = client.post("/api/introduction", json={})
        assert response.status_code == 400

    def test_server_error_on_config_fail(self, client, mock_intent_detector, mock_language_detector):
        """Config load failure → 500 Internal Server Error."""
        mock_intent_detector.classify.return_value = "initial_intro"
        mock_language_detector.detect.return_value = "en"
        with patch("handlers.introduction_handler.ConfigLoader.get_config", side_effect=FileNotFoundError):
            response = client.post("/api/introduction", json={"message": "Hi"})
            assert response.status_code == 500

    def test_word_count_enforcement_integration(self, client, mock_intent_detector, mock_language_detector):
        """AC-04: Response word count ≤ 100."""
        # Use a config that would produce a long response
        long_config = SAMPLE_CONFIG_EN.copy()
        long_config["capabilities"] = "word " * 200
        mock_intent_detector.classify.return_value = "initial_intro"
        mock_language_detector.detect.return_value = "en"
        with patch("handlers.introduction_handler.ConfigLoader.get_config", return_value=long_config):
            response = client.post("/api/introduction", json={"message": "Introduce yourself"})
            assert response.status_code == 200
            word_count = len(response.json()["response"].split())
            assert word_count <= 100

    def test_response_consistency(self, client, mock_intent_detector, mock_language_detector):
        """AC-06: Ten identical requests return identical responses (ignoring exact whitespace)."""
        mock_intent_detector.classify.return_value = "initial_intro"
        mock_language_detector.detect.return_value = "en"
        with patch("handlers.introduction_handler.ConfigLoader.get_config", return_value=SAMPLE_CONFIG_EN):
            responses = []
            for _ in range(10):
                resp = client.post("/api/introduction", json={"message": "Introduce yourself"})
                responses.append(resp.json()["response"])
            # All responses should be identical
            assert all(r == responses[0] for r in responses)
```

---

**Notes for the QA team:**

- The tests above assume the existence of modules and classes matching the description (`IntentDetector`, `LanguageDetector`, `IntroductionHandler`, `FollowUpHandler`, `ConfigLoader`, and the FastAPI app in `main.py` with a `POST /api/introduction` endpoint). Adjust imports and patching targets according to the actual implementation.
- Mocking is used for external dependencies (config loading, keyword lists) to isolate unit tests.
- The integration tests use a `TestClient` and patches to simulate a full request/response lifecycle, verifying correctness, error handling, performance constraints (word count), and consistency.
- To run the tests, place them inside the `tests/` directory as shown in the file structure and execute `pytest tests/` from the project root.