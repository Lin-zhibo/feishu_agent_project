```diff
diff --git a/self-intro-service/main.py b/self-intro-service/main.py
new file mode 100644
index 0000000..f3a9b7e
--- /dev/null
+++ b/self-intro-service/main.py
@@ -0,0 +1,101 @@
+import os
+import yaml
+from flask import Flask, request, jsonify
+from handlers.introduction_handler import IntroductionHandler
+from handlers.follow_up_handler import FollowUpHandler
+from services.intent_detector import IntentDetector
+from services.language_detector import LanguageDetector
+
+app = Flask(__name__)
+
+# In-memory configuration cache
+CONFIG_CACHE = {}
+CONFIG_DIR = os.path.join(os.path.dirname(__file__), 'config')
+
+def load_configs():
+    """Load all YAML config files into cache."""
+    global CONFIG_CACHE
+    CONFIG_CACHE.clear()
+    for filename in os.listdir(CONFIG_DIR):
+        if filename.startswith('introduction_') and filename.endswith('.yaml'):
+            lang_code = filename.replace('introduction_', '').replace('.yaml', '')
+            filepath = os.path.join(CONFIG_DIR, filename)
+            with open(filepath, 'r', encoding='utf-8') as f:
+                CONFIG_CACHE[lang_code] = yaml.safe_load(f)
+
+# Load configs at startup
+load_configs()
+
+# Instantiate services
+intent_detector = IntentDetector()
+language_detector = LanguageDetector()
+intro_handler = IntroductionHandler(CONFIG_CACHE)
+follow_up_handler = FollowUpHandler(CONFIG_CACHE)
+
+@app.route('/api/introduction', methods=['POST'])
+def handle_introduction():
+    """Main endpoint for self-introduction requests."""
+    data = request.get_json()
+    if not data or 'message' not in data:
+        return jsonify({'error': 'Missing or empty message field'}), 400
+
+    user_message = data['message'].strip()
+    if not user_message:
+        return jsonify({'error': 'Message cannot be empty'}), 400
+
+    # Determine intent
+    intent = intent_detector.detect(user_message)
+
+    if intent == 'introduction':
+        # Detect language
+        language = language_detector.detect(user_message)
+        try:
+            response_text, follow_up = intro_handler.generate(language)
+            return jsonify({
+                'response': response_text,
+                'language': language,
+                'follow_up_prompt': follow_up
+            })
+        except ValueError as e:
+            return jsonify({'error': str(e)}), 500
+
+    elif intent == 'follow_up':
+        # Use the language of the current request (or default to English)
+        language = language_detector.detect(user_message)
+        try:
+            response_text = follow_up_handler.generate(language)
+            return jsonify({
+                'response': response_text,
+                'language': language,
+                'follow_up_prompt': None
+            })
+        except ValueError as e:
+            return jsonify({'error': str(e)}), 500
+
+    else:
+        # Unknown intent – return a generic help message
+        return jsonify({
+            'response': "I'm here to introduce myself. Try saying 'Introduce yourself'.",
+            'language': 'en',
+            'follow_up_prompt': None
+        })
+
+@app.route('/health', methods=['GET'])
+def health():
+    """Health check endpoint."""
+    return jsonify({'status': 'ok'})
+
+@app.errorhandler(500)
+def internal_error(error):
+    return jsonify({'error': 'Internal server error'}), 500
+
+@app.errorhandler(404)
+def not_found(error):
+    return jsonify({'error': 'Not found'}), 404
+
+if __name__ == '__main__':
+    # For development only
+    app.run(host='0.0.0.0', port=5000, debug=True)
+
+# Background config reload (every 60 seconds)
+import threading
+def reload_config_periodically():
+    threading.Timer(60.0, reload_config_periodically).start()
+    load_configs()
+
+# Start background reload in production (optional)
+# reload_config_periodically()
diff --git a/self-intro-service/handlers/__init__.py b/self-intro-service/handlers/__init__.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/self-intro-service/handlers/__init__.py
@@ -0,0 +1 @@
+# Empty
diff --git a/self-intro-service/handlers/follow_up_handler.py b/self-intro-service/handlers/follow_up_handler.py
new file mode 100644
index 0000000..cffd392
--- /dev/null
+++ b/self-intro-service/handlers/follow_up_handler.py
@@ -0,0 +1,34 @@
+class FollowUpHandler:
+    """Generates follow-up messages for users who want more details."""
+
+    def __init__(self, config_cache):
+        self.config_cache = config_cache
+
+    def generate(self, language):
+        """Return the follow-up text for the given language."""
+        config = self.config_cache.get(language)
+        if not config:
+            # Fallback to English if language config missing
+            config = self.config_cache.get('en', {})
+        follow_up = config.get('follow_up', {})
+        prompt = follow_up.get('prompt', 'Would you like to know more?')
+        details_url = follow_up.get('details_url', '')
+
+        if details_url:
+            response = f"{prompt} More details here: {details_url}"
+        else:
+            response = prompt
+        return response
diff --git a/self-intro-service/handlers/introduction_handler.py b/self-intro-service/handlers/introduction_handler.py
new file mode 100644
index 0000000..ca99613
--- /dev/null
+++ b/self-intro-service/handlers/introduction_handler.py
@@ -0,0 +1,71 @@
+import re
+
+class IntroductionHandler:
+    """Generates self-introduction responses based on language configuration."""
+
+    def __init__(self, config_cache):
+        self.config_cache = config_cache
+
+    def generate(self, language):
+        """
+        Render the introduction template for the given language.
+        Returns (response_text, follow_up_prompt).
+        Raises ValueError if config not found.
+        """
+        config = self.config_cache.get(language)
+        if not config:
+            # Fallback to English
+            config = self.config_cache.get('en')
+            if not config:
+                raise ValueError("No configuration available")
+
+        name = config.get('name', 'AI Assistant')
+        capabilities = config.get('capabilities', '')
+        limitations = config.get('limitations', '')
+        tone = config.get('tone', 'friendly')
+        max_words = config.get('max_words', 100)
+        follow_up = config.get('follow_up', {})
+        follow_up_prompt = follow_up.get('prompt', '')
+
+        # Build the introduction text according to tone
+        if language == 'zh':
+            response = f"你好！我是{name}，一个AI助手。{capabilities}请注意，{limitations}"
+        else:
+            # Default English-like
+            response = f"Hello! I'm {name}, an AI assistant. {capabilities} Please note: {limitations}"
+
+        # Enforce word limit
+        response = self._enforce_word_limit(response, max_words, language)
+
+        return response, follow_up_prompt
+
+    def _enforce_word_limit(self, text, max_words, language):
+        """
+        Truncate text to max_words, preserving last complete sentence.
+        For Chinese, count characters; for others, words (split by whitespace).
+        """
+        if language == 'zh':
+            # Chinese: count characters
+            if len(text) <= max_words:
+                return text
+            # Find last sentence break before limit
+            truncated = text[:max_words]
+            # Ensure we end at a punctuation like 。！？ or cut at char
+            last_punct = max(truncated.rfind('。'), truncated.rfind('！'), truncated.rfind('？'))
+            if last_punct > 0:
+                truncated = truncated[:last_punct+1]
+            return truncated
+        else:
+            # English/other: count words (split)
+            words = text.split()
+            if len(words) <= max_words:
+                return text
+            # Truncate to first max_words words
+            truncated = ' '.join(words[:max_words])
+            # Try to end at the last complete sentence
+            # Simple: find last period, question mark, exclamation within truncated
+            last_punct = max(truncated.rfind('.'), truncated.rfind('?'), truncated.rfind('!'))
+            if last_punct > 0:
+                # Ensure we don't cut off the rest of the sentence
+                # We'll keep only up to the last punctuation +1
+                truncated = truncated[:last_punct+1]
+            return truncated
diff --git a/self-intro-service/services/__init__.py b/self-intro-service/services/__init__.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/self-intro-service/services/__init__.py
@@ -0,0 +1 @@
+# Empty
diff --git a/self-intro-service/services/intent_detector.py b/self-intro-service/services/intent_detector.py
new file mode 100644
index 0000000..b48482c
--- /dev/null
+++ b/self-intro-service/services/intent_detector.py
@@ -0,0 +1,61 @@
+import re
+
+class IntentDetector:
+    """
+    Classifies user input into one of:
+    - 'introduction': user wants a self-introduction
+    - 'follow_up': user wants more details after an introduction
+    - None: other
+    """
+
+    def __init__(self):
+        # Compile keyword patterns for performance
+        self.intro_patterns = [
+            r'\b(introduce\s+yourself|who\s+are\s+you|what\s+are\s+you)\b',
+            r'\b(介绍|你是谁|你是什么|自我介绍一下)\b',
+            r'^请\s*介绍',
+        ]
+        self.follow_up_patterns = [
+            r'\b(more|details|tell\s+me\s+more|learn\s+more)\b',
+            r'\b(更多|详细|告诉我更多|深入)\b',
+        ]
+
+        self.intro_re = [re.compile(p, re.IGNORECASE) for p in self.intro_patterns]
+        self.follow_up_re = [re.compile(p, re.IGNORECASE) for p in self.follow_up_patterns]
+
+    def detect(self, message):
+        """
+        Detect intent of the message.
+        Returns None if not introduction or follow-up.
+        """
+        # First check introduction (priority)
+        for pattern in self.intro_re:
+            if pattern.search(message):
+                return 'introduction'
+
+        # Then check follow-up
+        for pattern in self.follow_up_re:
+            if pattern.search(message):
+                return 'follow_up'
+
+        return None
diff --git a/self-intro-service/services/language_detector.py b/self-intro-service/services/language_detector.py
new file mode 100644
index 0000000..2ef8c88
--- /dev/null
+++ b/self-intro-service/services/language_detector.py
@@ -0,0 +1,34 @@
+import re
+
+class LanguageDetector:
+    """
+    Detect the language of a string.
+    Fast heuristic: Chinese if contains CJK characters; otherwise English.
+    For extensibility, fallback to langdetect for other languages.
+    """
+
+    # Unicode range for CJK Unified Ideographs
+    CJK_PATTERN = re.compile(r'[\u4e00-\u9fff]')
+
+    def __init__(self):
+        # Optionally import langdetect lazily
+        self._langdetect = None
+        self.supported_languages = ['zh', 'en', 'fr']  # Add as needed
+
+    def detect(self, text):
+        """Return language code (e.g., 'zh', 'en', 'fr')."""
+        if self.CJK_PATTERN.search(text):
+            return 'zh'
+        # Default to English for now
+        # For other languages, use langdetect if available
+        # To keep this implementation lightweight, we only support zh and en.
+        # If French keywords appear, we can detect via langdetect.
+        # Check for French hint: accented characters or specific words
+        if re.search(r'[àâçéèêëîïôûùüÿœ]', text, re.IGNORECASE):
+            # Attempt langdetect if installed
+            try:
+                import langdetect
+                return langdetect.detect(text)
+            except:
+                return 'fr'
+        return 'en'
diff --git a/self-intro-service/config/introduction_en.yaml b/self-intro-service/config/introduction_en.yaml
new file mode 100644
index 0000000..bbce7e5
--- /dev/null
+++ b/self-intro-service/config/introduction_en.yaml
@@ -0,0 +1,12 @@
+name: "ChatBot"
+capabilities: "I can help with language understanding, answering questions, and task assistance."
+limitations: "I cannot access real-time data or the internet."
+tone: "friendly and professional"
+max_words: 100
+follow_up:
+  prompt: "Would you like to know more about my features?"
+  details_url: "/help"
diff --git a/self-intro-service/config/introduction_zh.yaml b/self-intro-service/config/introduction_zh.yaml
new file mode 100644
index 0000000..e2882ae
--- /dev/null
+++ b/self-intro-service/config/introduction_zh.yaml
@@ -0,0 +1,12 @@
+name: "ChatBot"
+capabilities: "我可以帮助你理解语言、回答问题以及完成各种任务。"
+limitations: "我无法访问实时数据或互联网。"
+tone: "友好且专业"
+max_words: 100
+follow_up:
+  prompt: "你想了解更多关于我的功能吗？"
+  details_url: "/help"
diff --git a/self-intro-service/config/introduction_fr.yaml b/self-intro-service/config/introduction_fr.yaml
new file mode 100644
index 0000000..b7cb07c
--- /dev/null
+++ b/self-intro-service/config/introduction_fr.yaml
@@ -0,0 +1,12 @@
+name: "ChatBot"
+capabilities: "Je peux vous aider à comprendre le langage, répondre aux questions et effectuer des tâches."
+limitations: "Je n'ai pas accès aux données en temps réel ni à Internet."
+tone: "amical et professionnel"
+max_words: 100
+follow_up:
+  prompt: "Voulez-vous en savoir plus sur mes fonctionnalités ?"
+  details_url: "/help"
diff --git a/self-intro-service/tests/__init__.py b/self-intro-service/tests/__init__.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/self-intro-service/tests/__init__.py
@@ -0,0 +1 @@
+# Empty
diff --git a/self-intro-service/tests/test_intent_detector.py b/self-intro-service/tests/test_intent_detector.py
new file mode 100644
index 0000000..ca20f72
--- /dev/null
+++ b/self-intro-service/tests/test_intent_detector.py
@@ -0,0 +1,49 @@
+import unittest
+from services.intent_detector import IntentDetector
+
+class TestIntentDetector(unittest.TestCase):
+    def setUp(self):
+        self.detector = IntentDetector()
+
+    def test_intro_english(self):
+        self.assertEqual(self.detector.detect("Introduce yourself"), 'introduction')
+        self.assertEqual(self.detector.detect("Who are you?"), 'introduction')
+        self.assertEqual(self.detector.detect("What are you?"), 'introduction')
+
+    def test_intro_chinese(self):
+        self.assertEqual(self.detector.detect("介绍一下你自己"), 'introduction')
+        self.assertEqual(self.detector.detect("你是谁"), 'introduction')
+        self.assertEqual(self.detector.detect("请你介绍一下"), 'introduction')
+
+    def test_follow_up_english(self):
+        self.assertEqual(self.detector.detect("Tell me more"), 'follow_up')
+        self.assertEqual(self.detector.detect("more details"), 'follow_up')
+
+    def test_follow_up_chinese(self):
+        self.assertEqual(self.detector.detect("告诉我更多"), 'follow_up')
+        self.assertEqual(self.detector.detect("详细说说"), 'follow_up')
+
+    def test_no_match(self):
+        self.assertIsNone(self.detector.detect("Hello"))
+        self.assertIsNone(self.detector.detect("What's the weather?"))
+        self.assertIsNone(self.detector.detect(""))
+
+if __name__ == '__main__':
+    unittest.main()
diff --git a/self-intro-service/tests/test_introduction.py b/self-intro-service/tests/test_introduction.py
new file mode 100644
index 0000000..f75e967
--- /dev/null
+++ b/self-intro-service/tests/test_introduction.py
@@ -0,0 +1,77 @@
+import unittest
+import yaml
+import os
+from handlers.introduction_handler import IntroductionHandler
+from handlers.follow_up_handler import FollowUpHandler
+
+class TestIntroductionHandler(unittest.TestCase):
+    def setUp(self):
+        # Load configs for testing
+        self.config_cache = {}
+        config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
+        for fname in os.listdir(config_dir):
+            if fname.startswith('introduction_') and fname.endswith('.yaml'):
+                lang = fname.replace('introduction_', '').replace('.yaml', '')
+                with open(os.path.join(config_dir, fname), 'r', encoding='utf-8') as f:
+                    self.config_cache[lang] = yaml.safe_load(f)
+        self.intro_handler = IntroductionHandler(self.config_cache)
+        self.follow_up_handler = FollowUpHandler(self.config_cache)
+
+    def test_english_introduction_contains_keywords(self):
+        response, _ = self.intro_handler.generate('en')
+        self.assertIn('AI assistant', response)
+        self.assertIn('can help with', response)
+        self.assertIn('cannot access real-time', response)
+        self.assertIn('Hello! I\'m', response)
+
+    def test_chinese_introduction_contains_keywords(self):
+        response, _ = self.intro_handler.generate('zh')
+        self.assertIn('AI助手', response)
+        self.assertIn('帮助', response)
+        self.assertIn('无法访问', response)
+
+    def test_french_introduction_contains_keywords(self):
+        response, _ = self.intro_handler.generate('fr')
+        self.assertIn('Je peux', response)
+        self.assertIn('répondre', response)
+
+    def test_word_limit_enforced_english(self):
+        # Ensure response is within word limit
+        response, _ = self.intro_handler.generate('en')
+        word_count = len(response.split())
+        self.assertLessEqual(word_count, 100)
+
+    def test_word_limit_enforced_chinese(self):
+        response, _ = self.intro_handler.generate('zh')
+        # Chinese: character count
+        char_count = len(response)
+        self.assertLessEqual(char_count, 100)
+
+    def test_follow_up_handler(self):
+        response = self.follow_up_handler.generate('en')
+        self.assertIn('Would you like to know more', response)
+
+    def test_follow_up_handler_chinese(self):
+        response = self.follow_up_handler.generate('zh')
+        self.assertIn('你想了解更多', response)
+
+    def test_consistent_responses(self):
+        # Multiple calls should return same text
+        res1, _ = self.intro_handler.generate('en')
+        res2, _ = self.intro_handler.generate('en')
+        self.assertEqual(res1, res2)
+
+    def test_language_detection_integration(self):
+        # Use services directly
+        from services.language_detector import LanguageDetector
+        detector = LanguageDetector()
+        self.assertEqual(detector.detect("你好"), 'zh')
+        self.assertEqual(detector.detect("Hello"), 'en')
+        self.assertEqual(detector.detect("Bonjour"), 'fr')
+
+if __name__ == '__main__':
+    unittest.main()
diff --git a/self-intro-service/requirements.txt b/self-intro-service/requirements.txt
new file mode 100644
index 0000000..6270cc8
--- /dev/null
+++ b/self-intro-service/requirements.txt
@@ -0,0 +1,4 @@
+flask==2.3.2
+pyyaml==6.0
+langdetect==1.0.9
+# Optional: gunicorn for production
diff --git a/self-intro-service/Dockerfile b/self-intro-service/Dockerfile
new file mode 100644
index 0000000..f63e85f
--- /dev/null
+++ b/self-intro-service/Dockerfile
@@ -0,0 +1,16 @@
+FROM python:3.10-slim
+
+WORKDIR /app
+
+COPY requirements.txt .
+RUN pip install --no-cache-dir -r requirements.txt
+
+COPY . .
+
+# Expose the port the app runs on
+EXPOSE 5000
+
+# Use gunicorn for production with 2 workers
+CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]
+
+# For development, replace with: CMD ["python", "main.py"]
```