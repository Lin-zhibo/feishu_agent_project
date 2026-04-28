Below are **pytest** unit and integration tests for a Python backend implementing the WeChat Mini‑Program login flow described in the specification.  
The tests assume a Flask/FastAPI or similar Python web framework, with services, repositories, and middleware structured as in the provided design.  
All tests use mocking for external APIs and databases where appropriate.

---

## Test Strategy

| Test Type        | Scope                                             | Dependencies Mocked / Used                                   |
|------------------|---------------------------------------------------|--------------------------------------------------------------|
| **Unit Tests**   | Individual services, helpers, middleware          | `requests`, `jwt`, database calls, Redis, logger             |
| **Integration Tests** | Full API endpoints with a test database        | Test DB (SQLite in‑memory), mocked WeChat API, Redis (optional) |
| **Security**     | JWT validation, rate‑limiting, PII in logs       | Real JWT signing, mocked time                                |

---

## 1. Unit Tests

### 1.1 WeChatService – `jscode2session`

```python
# tests/unit/test_wechat_service.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.wechat_service import WeChatService
from app.config import Settings
import requests

@pytest.fixture
def wechat_service():
    settings = Settings(
        WECHAT_APPID="test_appid",
        WECHAT_SECRET="test_secret",
        WECHAT_API_URL="https://api.weixin.qq.com/sns/jscode2session"
    )
    return WeChatService(settings)

@patch("app.services.wechat_service.requests.get")
def test_jscode2session_success(mock_get, wechat_service):
    """Verify successful code exchange returns openid and session_key."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "openid": "oTestOpenId",
        "session_key": "testSessionKey",
        "unionid": "unionid_test"
    }
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    result = wechat_service.jscode2session("valid_code")

    assert result["openid"] == "oTestOpenId"
    assert result["session_key"] == "testSessionKey"
    assert result["unionid"] == "unionid_test"
    mock_get.assert_called_once()

@patch("app.services.wechat_service.requests.get")
def test_jscode2session_invalid_code(mock_get, wechat_service):
    """Verify that WeChat API error raises a custom exception."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"errcode": 40029, "errmsg": "invalid code"}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    with pytest.raises(WeChatAPIError) as exc:
        wechat_service.jscode2session("bad_code")
    assert "invalid_code" in str(exc.value)

@patch("app.services.wechat_service.requests.get")
def test_jscode2session_network_failure(mock_get, wechat_service):
    """Verify that a request exception is propagated."""
    mock_get.side_effect = requests.exceptions.ConnectionError("No connection")
    with pytest.raises(WeChatServiceUnavailable) as exc:
        wechat_service.jscode2session("code")
    assert "server_error" in str(exc.value)

def test_mask_code(wechat_service):
    """Ensure code is masked for logging (first 4 chars + ****)."""
    masked = wechat_service.mask_code("abcdefghij")
    assert masked == "abcd******"
```

### 1.2 TokenService – JWT generation / verification / blacklist

```python
# tests/unit/test_token_service.py
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from app.services.token_service import TokenService
from app.config import Settings

@pytest.fixture
def token_service():
    settings = Settings(
        JWT_SECRET="test_secret_key",
        JWT_ALGORITHM="HS256",
        JWT_EXPIRATION_SECONDS=604800,  # 7 days
    )
    redis_client = MagicMock()  # Mock Redis for blacklist
    return TokenService(settings, redis_client)

def test_generate_token_validity(token_service):
    """Verify that generated token contains correct sub and iat/exp."""
    user_id = "123e4567-e89b-12d3-a456-426614174000"
    token = token_service.generate_token(user_id)
    payload = token_service.decode_token(token)

    assert payload["sub"] == user_id
    assert "iat" in payload
    assert "exp" in payload
    # Check expiration is roughly 7 days ahead
    exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert (exp_time - datetime.now(timezone.utc)).days == 6  # within 7 days

def test_verify_valid_token(token_service):
    """Verify that a valid token passes verification and returns sub."""
    user_id = "user123"
    token = token_service.generate_token(user_id)
    result = token_service.verify_token(token)
    assert result == user_id

def test_verify_expired_token(token_service):
    """Verify that an expired token raises TokenExpiredError."""
    with patch("app.services.token_service.datetime") as mock_dt:
        # Simulate token created 8 days ago
        past = datetime(2023, 1, 1, tzinfo=timezone.utc)
        mock_dt.now.return_value = past
        expired_token = token_service.generate_token("user123")

        # Now move time forward
        mock_dt.now.return_value = past + timedelta(days=8)
        mock_dt.fromtimestamp = datetime.fromtimestamp
        mock_dt.utcfromtimestamp = datetime.utcfromtimestamp  # if Python <3.11

        with pytest.raises(TokenExpiredError):
            token_service.verify_token(expired_token)

def test_blacklisted_token_is_rejected(token_service):
    """Verify that tokens added to blacklist are invalidated."""
    token = token_service.generate_token("user123")
    token_service.blacklist_token(token, ttl=3600)
    with pytest.raises(TokenBlacklistedError):
        token_service.verify_token(token)

def test_logout_invalidates_token(token_service):
    """Blacklist token upon logout."""
    token = token_service.generate_token("user123")
    token_service.blacklist_token(token, ttl=3600)
    assert token_service.redis_client.setex.called
```

### 1.3 UserService – `find_or_create`

```python
# tests/unit/test_user_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.user_service import UserService
from app.repositories.user_repository import UserRepository
from app.models.user import User

@pytest.fixture
def user_repo():
    return MagicMock(spec=UserRepository)

@pytest.fixture
def user_service(user_repo):
    return UserService(repository=user_repo)

@pytest.mark.asyncio
async def test_find_or_create_user_new(user_service, user_repo):
    """When user does not exist, create a new record."""
    openid = "new_openid"
    unionid = "unionid_new"
    session_key = "key"

    user_repo.find_by_openid.return_value = None  # user not found
    new_user = User(id="new_id", openid=openid, unionid=unionid,
                    first_login=datetime.now())
    user_repo.create.return_value = new_user

    result = await user_service.find_or_create(openid, unionid, session_key)
    assert result.id == "new_id"
    assert result.is_new is True
    user_repo.create.assert_called_once_with(openid=openid, unionid=unionid,
                                             session_key=session_key)

@pytest.mark.asyncio
async def test_find_or_create_user_existing(user_service, user_repo):
    """When user exists, update last_login and return existing."""
    existing_user = User(id="existing_id", openid="existing_openid",
                         last_login=datetime(2023,1,1))
    user_repo.find_by_openid.return_value = existing_user
    user_repo.save = MagicMock()

    result = await user_service.find_or_create("existing_openid", None, None)
    assert result.id == "existing_id"
    assert result.is_new is False
    user_repo.save.assert_called_once()
    # last_login should be updated to now
    assert result.last_login > datetime(2023,1,1)
```

### 1.4 Error Handling & Logging

```python
# tests/unit/test_error_handler.py
from app.middleware.error_handler import error_handler
from app.utils.errors import WeChatAPIError, TokenExpiredError
import json

def test_wechat_api_error_formats_response():
    """Verify that WeChatAPIError returns proper JSON with error code."""
    exc = WeChatAPIError("invalid_code", "登录已过期，请重新授权")
    response, status = error_handler(exc)
    assert status == 400
    body = json.loads(response.data)
    assert body["error"] == "invalid_code"
    assert body["message"] == "登录已过期，请重新授权"
```

---

## 2. Integration Tests

### 2.1 Test Configuration & Fixtures

```python
# tests/conftest.py
import pytest
from flask import Flask
from app import create_app
from app.config import TestingConfig
from app.models.user import User, db
from app.models.user import User as UserModel
import os

@pytest.fixture(scope="module")
def app():
    app = create_app(config_class=TestingConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    with app.test_client() as client:
        with app.app_context():
            db.session.begin_nested()  # rollback after each test
            yield client
            db.session.rollback()

@pytest.fixture
def mock_wechat_api(monkeypatch):
    """Override WeChatService to return a fixed response."""
    def mock_jscode2session(code):
        if code == "valid_code":
            return {"openid": "integration_test_openid",
                    "session_key": "fake_key",
                    "unionid": None}
        elif code == "invalid_code":
            raise WeChatAPIError("invalid_code", "bad code")
        else:
            raise WeChatAPIError("server_error", "WeChat server down")
    monkeypatch.setattr("app.services.wechat_service.WeChatService.jscode2session",
                        mock_jscode2session)
```

### 2.2 POST /api/login

```python
# tests/integration/test_auth_login.py

class TestLogin:
    def test_successful_login(self, client, mock_wechat_api):
        """Verify that a valid code returns token and user."""
        response = client.post("/api/login", json={"code": "valid_code"})
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["is_new_user"] is True
        # Check token is JWT
        import jwt
        payload = jwt.decode(data["token"], options={"verify_signature": False})
        assert payload["sub"] == data["user"]["id"]

    def test_duplicate_code_returns_error(self, client, mock_wechat_api):
        """WeChat API might return error for reused code."""
        response = client.post("/api/login", json={"code": "invalid_code"})
        assert response.status_code == 400
        assert response.json["error"] == "invalid_code"

    def test_missing_code_returns_400(self, client):
        """Request without 'code' field."""
        response = client.post("/api/login", json={})
        assert response.status_code == 400

    def test_rate_limiting(self, client):
        """If rate limiter enabled, 10 requests per minute per IP."""
        for _ in range(10):
            response = client.post("/api/login", json={"code": "some_code"})
        # 11th request should be throttled
        response = client.post("/api/login", json={"code": "some_code"})
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    def test_logging_masks_code(self, client, caplog, mock_wechat_api):
        """Verify that code is masked in logs (first 4 chars + ****)."""
        import logging
        caplog.set_level(logging.INFO)
        client.post("/api/login", json={"code": "abcdefgh"})
        # Search for the masked version in log output
        assert "abcd****" in caplog.text
        # Ensure full code is not present
        assert "abcdefgh" not in caplog.text
```

### 2.3 POST /api/logout

```python
# tests/integration/test_auth_logout.py

def test_logout_blacklists_token(client, mock_wechat_api):
    """After logout, same token should be rejected for protected endpoints."""
    # Login first
    login_resp = client.post("/api/login", json={"code": "valid_code"})
    token = login_resp.json["token"]

    # Logout
    logout_resp = client.post("/api/logout",
                              headers={"Authorization": f"Bearer {token}"})
    assert logout_resp.status_code == 200
    assert logout_resp.json["message"] == "logged_out"

    # Try to access protected endpoint with same token
    profile_resp = client.get("/api/user/me",
                              headers={"Authorization": f"Bearer {token}"})
    assert profile_resp.status_code == 401
```

### 2.4 GET /api/user/me

```python
# tests/integration/test_user_profile.py

def test_get_profile_success(client, mock_wechat_api):
    """Retrieve authenticated user profile."""
    # Login
    login_resp = client.post("/api/login", json={"code": "valid_code"})
    token = login_resp.json["token"]
    user_id = login_resp.json["user"]["id"]

    # Get profile
    profile_resp = client.get("/api/user/me",
                              headers={"Authorization": f"Bearer {token}"})
    assert profile_resp.status_code == 200
    data = profile_resp.json
    assert data["id"] == user_id
    assert "openid" not in data  # openid should not be exposed

def test_get_profile_no_token_returns_401(client):
    """Request without Authorization header."""
    resp = client.get("/api/user/me")
    assert resp.status_code == 401

def test_get_profile_expired_token_returns_401(client):
    """Simulate expired token."""
    import jwt, time
    # Manually create expired token
    expired_payload = {"sub": "test_user", "exp": int(time.time()) - 3600}
    expired_token = jwt.encode(expired_payload, "test_secret_key", algorithm="HS256")
    resp = client.get("/api/user/me",
                      headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
```

### 2.5 Health Check

```python
# tests/integration/test_health.py

def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json == {"status": "ok"}
```

---

## 3. Additional Considerations

- **Mocked Redis**: For token blacklist and rate‑limiting, use a fake Redis or in‑memory dictionary in tests.
- **Database**: Use SQLite in‑memory for integration tests to avoid external dependencies.
- **Async vs Sync**: The tests above show `@pytest.mark.asyncio` for services; adjust based on your framework.
- **Security**: Include tests for CSRF (if applicable) and ensure `openid` is never leaked via API responses.
- **Frontend**: Not covered here (pytest is backend). Frontend unit tests would be in Jest/Mocha.

---

Run the tests with:

```bash
pytest tests/ --cov=app --cov-report=term-missing
```

This suite covers the critical paths described in the specification, including success, failure, rate‑limiting, token lifecycle, and logging hygiene.