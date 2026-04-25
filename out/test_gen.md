We'll generate a comprehensive test suite using `pytest` for the described user login system. The tests cover both unit-level logic (auth service) and integration-level API endpoints, with mocking for external dependencies (database, Redis, token blacklist, captcha verification).

## Test Files Overview

- **`tests/unit/test_auth_service.py`**: Unit tests for `auth.service.py` functions: password verification, lockout logic, JWT generation/validation, captcha requirement after failures.
- **`tests/integration/test_auth_api.py`**: Integration tests for `POST /api/v1/auth/login`, `POST /refresh`, `POST /logout`, `GET /user`, etc., using an in-memory database and mocked external services.

We assume a Python backend using Flask/FastAPI, with `bcrypt`, `PyJWT`, and an ORM (e.g., SQLAlchemy). Tests are structured to be run with `pytest`.

---

## `tests/unit/test_auth_service.py`

```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import bcrypt
import jwt
from auth.auth_service import AuthService
from auth.user_model import User
from common.errors import InvalidCredentials, AccountLocked, CaptchaRequired

class TestAuthService:
    """Unit tests for AuthService methods."""

    @pytest.fixture
    def auth_service(self):
        """Create an AuthService instance with mocked dependencies."""
        config = {
            'JWT_SECRET': 'test_secret',
            'JWT_ALGORITHM': 'HS256',
            'ACCESS_TOKEN_EXPIRE_MINUTES': 15,
            'REFRESH_TOKEN_EXPIRE_DAYS': 7,
            'BCRYPT_COST': 12,
            'MAX_FAILED_ATTEMPTS': 5,
            'LOCKOUT_DURATION_MINUTES': 15,
            'CAPTCHA_ATTEMPT_THRESHOLD': 3,
            'CAPTCHA_ENABLED': True
        }
        # Mock database session and redis
        db = MagicMock()
        redis = MagicMock()
        return AuthService(config, db, redis)

    # ------------- Password Verification -------------
    def test_verify_password_correct(self, auth_service):
        password = "StrongPass123!"
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        assert auth_service.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self, auth_service):
        hashed = bcrypt.hashpw(b"wrong_hash", bcrypt.gensalt())
        assert auth_service.verify_password("RealPass", hashed) is False

    # ------------- User Lookup -------------
    def test_find_user_by_username(self, auth_service):
        mock_user = Mock(spec=User, username="john_doe")
        auth_service.db.query.return_value.filter.return_value.first.return_value = mock_user
        user = auth_service.find_user_by_login("john_doe")
        assert user == mock_user
        # Verify query was called with username filter
        auth_service.db.query.assert_called_with(User)

    def test_find_user_by_email(self, auth_service):
        mock_user = Mock(spec=User, email="john@example.com")
        auth_service.db.query.return_value.filter.return_value.first.return_value = mock_user
        user = auth_service.find_user_by_login("john@example.com")
        assert user == mock_user

    def test_find_user_not_found(self, auth_service):
        auth_service.db.query.return_value.filter.return_value.first.return_value = None
        user = auth_service.find_user_by_login("nonexistent")
        assert user is None

    # ------------- Lockout Logic -------------
    def test_is_account_locked_no_lock(self, auth_service):
        mock_user = Mock(locked_until=None)
        assert auth_service.is_account_locked(mock_user) is False

    def test_is_account_locked_future_time(self, auth_service):
        future = datetime.utcnow() + timedelta(minutes=10)
        mock_user = Mock(locked_until=future)
        assert auth_service.is_account_locked(mock_user) is True

    def test_is_account_locked_past_time(self, auth_service):
        past = datetime.utcnow() - timedelta(minutes=10)
        mock_user = Mock(locked_until=past)
        assert auth_service.is_account_locked(mock_user) is False

    def test_lock_account_reaches_threshold(self, auth_service):
        # After 5 failed attempts, should lock
        mock_user = Mock(failed_attempts=4, locked_until=None)
        result = auth_service.handle_failed_login(mock_user)
        assert mock_user.failed_attempts == 5
        assert mock_user.locked_until is not None
        assert result['action'] == 'locked'

    def test_lock_account_not_reached(self, auth_service):
        mock_user = Mock(failed_attempts=2, locked_until=None)
        result = auth_service.handle_failed_login(mock_user)
        assert mock_user.failed_attempts == 3
        assert mock_user.locked_until is None
        assert result['action'] == 'increment'

    # ------------- Captcha Requirement -------------
    def test_captcha_required_after_3_failures(self, auth_service):
        mock_user = Mock(failed_attempts=2, locked_until=None)
        assert auth_service.is_captcha_required(mock_user) is True

    def test_captcha_not_required_below_threshold(self, auth_service):
        mock_user = Mock(failed_attempts=0, locked_until=None)
        assert auth_service.is_captcha_required(mock_user) is False

    def test_captcha_not_required_when_captcha_disabled(self, auth_service):
        auth_service.config['CAPTCHA_ENABLED'] = False
        mock_user = Mock(failed_attempts=10)
        assert auth_service.is_captcha_required(mock_user) is False

    # ------------- JWT Generation -------------
    def test_generate_access_token_with_remember_me(self, auth_service):
        token = auth_service.generate_token(user_id=1, username="test", remember_me=True)
        payload = jwt.decode(token, auth_service.config['JWT_SECRET'], algorithms=[auth_service.config['JWT_ALGORITHM']])
        assert payload['remember_me'] is True
        # Check expiry: should be 7 days
        exp = datetime.utcfromtimestamp(payload['exp'])
        assert (exp - datetime.utcnow()).days == 7

    def test_generate_access_token_without_remember_me(self, auth_service):
        token = auth_service.generate_token(user_id=1, username="test", remember_me=False)
        payload = jwt.decode(token, auth_service.config['JWT_SECRET'], algorithms=[auth_service.config['JWT_ALGORITHM']])
        assert payload['remember_me'] is False
        # Check expiry: should be 15 minutes (configured)
        exp = datetime.utcfromtimestamp(payload['exp'])
        delta = exp - datetime.utcnow()
        assert delta.total_seconds() // 60 == 15

    # ------------- Token Blacklisting (Logout) -------------
    def test_blacklist_token(self, auth_service):
        token = "some_token"
        auth_service.blacklist_token(token, ttl=3600)
        auth_service.redis.setex.assert_called_once_with(f"blacklist:{token}", 3600, True)

    def test_is_token_blacklisted_true(self, auth_service):
        auth_service.redis.get.return_value = b'1'
        assert auth_service.is_token_blacklisted("blacklisted_token") is True

    def test_is_token_blacklisted_false(self, auth_service):
        auth_service.redis.get.return_value = None
        assert auth_service.is_token_blacklisted("valid_token") is False

    # ------------- Full Login Flow (unit test with mock user) -------------
    def test_login_successful(self, auth_service):
        # Mock user with no lockout and correct password
        mock_user = Mock(
            id=1,
            username="john_doe",
            email="john@example.com",
            password_hash=bcrypt.hashpw(b"CorrectPassword", bcrypt.gensalt()),
            failed_attempts=0,
            locked_until=None,
            token_version=1
        )
        auth_service.find_user_by_login = Mock(return_value=mock_user)
        auth_service.is_account_locked = Mock(return_value=False)
        auth_service.verify_password = Mock(return_value=True)
        auth_service.generate_token = Mock(return_value="access_token")

        result = auth_service.login("john_doe", "CorrectPassword")
        assert result['access_token'] == "access_token"
        assert result['user']['id'] == 1
        assert mock_user.failed_attempts == 0  # reset
        assert mock_user.locked_until is None

    def test_login_incorrect_password(self, auth_service):
        mock_user = Mock(
            id=1,
            username="john_doe",
            password_hash=b'$2b$12$...',
            failed_attempts=0,
            locked_until=None
        )
        auth_service.find_user_by_login = Mock(return_value=mock_user)
        auth_service.is_account_locked = Mock(return_value=False)
        auth_service.verify_password = Mock(return_value=False)
        auth_service.is_captcha_required = Mock(return_value=False)

        with pytest.raises(InvalidCredentials):
            auth_service.login("john_doe", "WrongPassword")
        assert mock_user.failed_attempts == 1

    def test_login_account_locked(self, auth_service):
        mock_user = Mock(locked_until=datetime.utcnow() + timedelta(minutes=10))
        auth_service.find_user_by_login = Mock(return_value=mock_user)
        auth_service.is_account_locked = Mock(return_value=True)

        with pytest.raises(AccountLocked):
            auth_service.login("john_doe", "anypassword")

    def test_login_captcha_required_but_not_provided(self, auth_service):
        mock_user = Mock(failed_attempts=2, locked_until=None, password_hash=b'hash')
        auth_service.find_user_by_login = Mock(return_value=mock_user)
        auth_service.is_account_locked = Mock(return_value=False)
        # Simulate that captcha is needed but not sent
        auth_service.is_captcha_required = Mock(return_value=True)

        with pytest.raises(CaptchaRequired):
            auth_service.login("john_doe", "anypassword", captcha=None)

    def test_login_captcha_valid(self, auth_service):
        mock_user = Mock(
            id=1,
            username="john_doe",
            password_hash=bcrypt.hashpw(b"CorrectPassword", bcrypt.gensalt()),
            failed_attempts=2,
            locked_until=None,
            token_version=1
        )
        auth_service.find_user_by_login = Mock(return_value=mock_user)
        auth_service.is_account_locked = Mock(return_value=False)
        auth_service.verify_password = Mock(return_value=True)
        auth_service.generate_token = Mock(return_value="access_token")
        auth_service.is_captcha_required = Mock(return_value=True)
        auth_service.verify_captcha = Mock(return_value=True)

        result = auth_service.login("john_doe", "CorrectPassword", captcha="valid_token")
        assert result['access_token'] == "access_token"

    def test_login_captcha_invalid(self, auth_service):
        mock_user = Mock(failed_attempts=2, locked_until=None)
        auth_service.find_user_by_login = Mock(return_value=mock_user)
        auth_service.is_account_locked = Mock(return_value=False)
        auth_service.is_captcha_required = Mock(return_value=True)
        auth_service.verify_captcha = Mock(return_value=False)

        with pytest.raises(InvalidCredentials):
            auth_service.login("john_doe", "anypassword", captcha="wrong")

    # ------------- Token Refresh -------------
    def test_refresh_token_valid(self, auth_service):
        # Assume refresh token is a special token that we can validate
        auth_service.validate_refresh_token = Mock(return_value={'user_id': 1, 'username': 'test'})
        auth_service.generate_token = Mock(return_value="new_access_token")
        result = auth_service.refresh("valid_refresh_token")
        assert result['access_token'] == "new_access_token"

    def test_refresh_token_invalid(self, auth_service):
        auth_service.validate_refresh_token = Mock(side_effect=jwt.InvalidTokenError)
        with pytest.raises(InvalidCredentials):
            auth_service.refresh("invalid_refresh_token")

    # ------------- Multi-device (Token Version) -------------
    def test_token_version_mismatch(self, auth_service):
        mock_user = Mock(token_version=2)
        # Create a token with version=1
        payload = {'user_id': 1, 'version': 1}
        token = jwt.encode(payload, auth_service.config['JWT_SECRET'], algorithm='HS256')
        # In service, verify_token checks version against DB
        auth_service.verify_token_version(token, mock_user)
        # Assert that if versions differ, token is considered invalid
        with pytest.raises(InvalidCredentials):
            auth_service.verify_token(token)  # This should check version

    def test_token_version_match(self, auth_service):
        mock_user = Mock(token_version=1)
        payload = {'user_id': 1, 'version': 1}
        token = jwt.encode(payload, auth_service.config['JWT_SECRET'], algorithm='HS256')
        # Should not raise
        auth_service.verify_token_version(token, mock_user)
```

---

## `tests/integration/test_auth_api.py`

```python
import pytest
import json
from flask import Flask
from flask.testing import FlaskClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app import create_app  # Assuming application factory
from config import TestConfig

@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        # Setup database (e.g., in-memory SQLite)
        from models import db
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

# Helper to create a user in test DB
def create_user(db_session, username="testuser", email="test@example.com", password="TestPass123!"):
    from models import User
    import bcrypt
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    user = User(username=username, email=email, password_hash=hashed)
    db_session.add(user)
    db_session.commit()
    return user

class TestLoginEndpoint:
    """Integration tests for POST /api/v1/auth/login"""

    def test_login_successful(self, client, db_session):
        user = create_user(db_session, username="johndoe", password="CorrectP@ss1")
        response = client.post("/api/v1/auth/login", 
                               json={"login": "johndoe", "password": "CorrectP@ss1"})
        assert response.status_code == 200
        data = response.get_json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["username"] == "johndoe"
        # Check that user's failed_attempts reset to 0
        db_session.refresh(user)
        assert user.failed_attempts == 0
        assert user.locked_until is None

    def test_login_wrong_password(self, client, db_session):
        user = create_user(db_session, username="johndoe", password="CorrectP@ss1")
        response = client.post("/api/v1/auth/login",
                               json={"login": "johndoe", "password": "WrongP@ss"})
        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_CREDENTIALS"
        # Check failed_attempts incremented
        db_session.refresh(user)
        assert user.failed_attempts == 1

    def test_login_user_not_found(self, client):
        response = client.post("/api/v1/auth/login",
                               json={"login": "nonexistent", "password": "any"})
        assert response.status_code == 401
        # Should not disclose that user doesn't exist; same generic error
        data = response.get_json()
        assert data["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_account_locked(self, client, db_session):
        # Create user with lockout
        from models import User
        user = create_user(db_session, username="lockeduser")
        user.locked_until = datetime.utcnow() + timedelta(minutes=15)
        db_session.commit()
        response = client.post("/api/v1/auth/login",
                               json={"login": "lockeduser", "password": "any"})
        assert response.status_code == 429
        data = response.get_json()
        assert "Account locked" in data["error"]["message"]

    def test_login_with_remember_me(self, client, db_session):
        create_user(db_session, username="rememberme", password="Pass123!")
        response = client.post("/api/v1/auth/login",
                               json={"login": "rememberme", "password": "Pass123!", "rememberMe": True})
        assert response.status_code == 200
        data = response.get_json()
        token = data["access_token"]
        # Decode to verify remember_me claim (if using JWT)
        import jwt
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["remember_me"] is True

    def test_login_captcha_required_after_3_failures(self, client, db_session):
        # Create user with 2 failed attempts already
        user = create_user(db_session, username="captchauser", password="Pass123!")
        user.failed_attempts = 2
        db_session.commit()
        # Third attempt without captcha should require it
        response = client.post("/api/v1/auth/login",
                               json={"login": "captchauser", "password": "wrong"})
        assert response.status_code == 400  # or 401 with captcha required
        data = response.get_json()
        # The exact code depends on implementation; assume captcha_required error
        # We'll check for "CAPTCHA_REQUIRED" error code
        assert data["error"]["code"] == "CAPTCHA_REQUIRED"

    def test_login_with_valid_captcha(self, client, db_session, mocker):
        # Mock captcha verification to succeed
        mocker.patch('services.auth_service.verify_captcha', return_value=True)
        user = create_user(db_session, username="captchauser2", password="Pass123!")
        user.failed_attempts = 3
        db_session.commit()
        response = client.post("/api/v1/auth/login",
                               json={"login": "captchauser2", "password": "Pass123!", "captcha": "valid_token"})
        assert response.status_code == 200

    def test_login_with_invalid_captcha(self, client, db_session, mocker):
        mocker.patch('services.auth_service.verify_captcha', return_value=False)
        user = create_user(db_session, username="captchauser3", password="Pass123!")
        user.failed_attempts = 3
        db_session.commit()
        response = client.post("/api/v1/auth/login",
                               json={"login": "captchauser3", "password": "Pass123!", "captcha": "invalid_token"})
        assert response.status_code == 401

    def test_login_input_validation_missing_fields(self, client):
        response = client.post("/api/v1/auth/login", json={"login": "test"})
        assert response.status_code == 400
        data = response.get_json()
        assert "password" in data["error"]["message"]  # validation error

class TestRefreshEndpoint:
    @pytest.fixture(autouse=True)
    def setup(self, client, db_session):
        self.user = create_user(db_session, username="refreshtest", password="Pass123!")

    def test_refresh_successful(self, client, db_session, mocker):
        # First login to get refresh token (assuming implementation uses refresh tokens)
        login_resp = client.post("/api/v1/auth/login", 
                                 json={"login": "refreshtest", "password": "Pass123!"})
        assert login_resp.status_code == 200
        login_data = login_resp.get_json()
        refresh_token = login_data.get("refresh_token")
        # Mock refresh token validation
        mocker.patch('services.auth_service.validate_refresh_token', 
                     return_value={'user_id': self.user.id, 'username': 'refreshtest'})
        response = client.post("/api/v1/auth/refresh", json={"refreshToken": refresh_token})
        assert response.status_code == 200
        data = response.get_json()
        assert "access_token" in data

    def test_refresh_with_expired_token(self, client, mocker):
        mocker.patch('services.auth_service.validate_refresh_token', side_effect=jwt.ExpiredSignatureError)
        response = client.post("/api/v1/auth/refresh", json={"refreshToken": "expired_token"})
        assert response.status_code == 401

class TestLogoutEndpoint:
    def test_logout_successful(self, client, mocker):
        # Mock token blacklisting
        mocker.patch('services.auth_service.blacklist_token', return_value=None)
        # Need a valid token in header; we can create one
        headers = {'Authorization': 'Bearer some_valid_token'}
        response = client.post("/api/v1/auth/logout", headers=headers)
        assert response.status_code == 200

class TestUserInfoEndpoint:
    def test_get_user_info_authenticated(self, client, db_session, mocker):
        user = create_user(db_session, username="userinfo")
        # Simulate token validation and user retrieval
        mocker.patch('auth.middleware.decode_token', return_value={'user_id': user.id})
        headers = {'Authorization': 'Bearer valid_token'}
        response = client.get("/api/v1/auth/user", headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["username"] == "userinfo"

    def test_get_user_info_unauthenticated(self, client):
        response = client.get("/api/v1/auth/user")
        assert response.status_code == 401

# Note: Additional tests can be added for rate limiting, multi-device token version, etc.
```

---

## Running the Tests

```bash
pip install pytest pytest-mock pytest-flask
pytest tests/ -v
```

These tests cover the core behaviors described in the technical solution, ensuring both correct functionality and error handling. The unit tests verify business logic in isolation, while integration tests confirm that endpoints behave as expected with a realistic (mocked) stack.