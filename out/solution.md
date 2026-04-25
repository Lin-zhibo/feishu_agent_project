## Technical Solution for User Login System

### 1. Architecture Overview

The solution follows a **stateless, modular** architecture with separate frontend and backend, communicating over HTTPS. The backend is horizontally scalable and uses JWT for authentication.

```
[Browser/Client] 
       ↕ HTTPS (REST API)
[Load Balancer] 
       ↕ 
[Web Server / API Gateway] (Nginx, Kong, etc.)
       ↕ 
[Auth Service] (Stateless, handles login, token validation, lockout logic)
       ↕ 
[User Database] (PostgreSQL, MySQL) – stores hashed passwords, lockout info
[Redis] (Optional, for token blacklist & rate limiting)
[Third-party OAuth] (Future: plugin)
```

**Key principles:**
- All authentication is JWT-based. Tokens are issued, validated, and optionally revoked.
- Forget password is a separate flow (only entry point defined here).
- CAPTCHA service (e.g., reCAPTCHA) integrated after 3 consecutive failures.
- Lockout data stored in the user database (or Redis for TTL).
- Frontend stores JWT in `httpOnly` cookie for security (`SameSite=Strict`), or in localStorage with careful CSRF protection. We recommend **httpOnly + Secure cookie** to mitigate XSS.

**Security measures:**
- HTTPS enforced (HSTS header).
- Password hashed with bcrypt (cost factor 12).
- JWT signed with RS256 (asymmetric) for easy key rotation.
- CSRF token if using cookie-based token transport.
- Rate limiting per IP and per username at API gateway.

### 2. File Structure

**Frontend (React/Vue – example React)**

```
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── LoginForm.jsx
│   │   ├── PasswordInput.jsx
│   │   └── CaptchaWidget.jsx
│   ├── pages/
│   │   └── LoginPage.jsx
│   ├── services/
│   │   └── authApi.js          (API calls)
│   ├── hooks/
│   │   └── useAuth.js          (context/auth state)
│   ├── utils/
│   │   └── storage.js          (cookie/token helpers)
│   ├── App.js
│   └── index.js
└── package.json
```

**Backend (Node.js/Express example)**

```
backend/
├── src/
│   ├── auth/
│   │   ├── auth.controller.js
│   │   ├── auth.service.js
│   │   ├── auth.validation.js
│   │   └── auth.middleware.js
│   ├── user/
│   │   ├── user.model.js
│   │   ├── user.service.js
│   │   └── user.validation.js
│   ├── common/
│   │   ├── errors.js
│   │   ├── logger.js
│   │   ├── rateLimiter.js
│   │   └── captcha.js
│   ├── config/
│   │   └── index.js
│   ├── routes/
│   │   └── auth.routes.js
│   └── app.js
├── migrations/
├── tests/
└── package.json
```

**Database migrations** (e.g., Knex or Prisma)

```
migrations/
└── 001_create_users.sql
```

User table:
```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(50) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE,
  phone VARCHAR(20) UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  failed_attempts INT DEFAULT 0,
  locked_until TIMESTAMP NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### 3. API Design

All endpoints are prefixed with `/api/v1/auth`.

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| POST | `/login` | Authenticate user | `{ login: string (username/email/phone), password: string, captcha?: string, rememberMe?: boolean }` | 200: `{ accessToken, refreshToken?, user: { id, username, email, avatar } }`<br>401: error message |
| POST | `/refresh` | Refresh access token (optional) | `{ refreshToken: string }` | 200: `{ accessToken, refreshToken? }` |
| POST | `/logout` | Invalidate current token | `{ token?: string }` (or from cookie) | 200: success |
| GET | `/user` | Get current user info | – | 200: user object |
| GET | `/captcha` | Get captcha challenge (if needed) | – | 200: challenge data (e.g., reCAPTCHA site key) |
| POST | `/password-reset-request` | Initiate password reset (separate flow) | `{ email, phone }` | 200: success |

**Error responses** (uniform):
```json
{
  "error": {
    "code": "INVALID_CREDENTIALS",
    "message": "Username or password is incorrect"
  }
}
```

**Authentication header**: `Authorization: Bearer <accessToken>`

**Token expiry settings:**
- Access token: 15 minutes (short-lived)
- Refresh token (if used with `rememberMe`): 7 days; without rememberMe: session-only (no refresh token stored)
- Alternatively, use a single token with long expiry based on `rememberMe` – simpler but less secure. We'll use **single long-lived token** with `rememberMe` flag encoded inside.

### 4. Key Implementation Notes

#### 4.1 Login Flow (high-level pseudocode)

```
POST /login:
1. Validate input (login, password, captcha if present)
2. Check rate limit by IP & username (if >3 failed attempts: require captcha)
3. Find user by login (search username, email, phone)
4. If user not found => return 401 "Invalid credentials"
5. If user.locked_until > now => return 429 "Account locked for X minutes"
6. Verify password with bcrypt
7. If password failed:
   a. Increment failed_attempts
   b. If failed_attempts >= 5 => set locked_until = now + 15 min
   c. Return 401 "Invalid credentials"
8. If password ok:
   a. Reset failed_attempts = 0, locked_until = null
   b. Generate JWT:
      - Payload: userId, username, role, rememberMe (boolean), iat, exp
      - Sign with RS256 private key
   c. Set expiry: if rememberMe => 7 days, else => session (e.g., 1 day)
   d. Return token & user info
   e. Optionally log audit trail
```

#### 4.2 Token Storage & CSRF

- **Recommended**: Store JWT in a **httpOnly, Secure, SameSite=Strict** cookie. This prevents XSS theft and provides CSRF protection.
- **Alternative**: Store in memory + refresh token in httpOnly cookie.
- If using cookie, an additional CSRF token (double-submit cookie pattern) is unnecessary with SameSite=Strict, but ensure all dashboard forms include a anti-CSRF token for protected actions.

#### 4.3 Multi-device Policy

- **Single sign-on**: On login, blacklist any existing valid tokens for that user (store user's token version in DB or Redis). Invalidate by incrementing a `token_version` column. JWT includes `version` claim; if version does not match, reject.
- **Multiple sessions allowed**: No special handling (default). Each login creates a new token. Server-side may track active sessions.

#### 4.4 Lockout & CAPTCHA

- After **3 consecutive failed attempts** (per username), frontend should show CAPTCHA (can be checked via a separate endpoint or via response header).
- To avoid race conditions, use atomic increment in DB or Redis with expiring keys.
- Lockout is based on IP + username combination? Requirement says "IP或账号". We'll lock **username** globally to prevent distributed attacks.

#### 4.5 Password Reset Link

- This endpoint is not defined in detail, but we must provide the entry point: `POST /password-reset-request`. The service sends an email/SMS with a time-limited token to reset password. This is a separate feature.

#### 4.6 Logout

- Invalidate token by adding it to a **blacklist** (Redis with TTL matching token expiry) or by clearing the cookie.
- For better security, maintain a token version or a revocation list.

#### 4.7 Audit Logging

- All login attempts (success/fail) are logged asynchronously to a logging service (e.g., ELK stack) with: timestamp, userId (if identified), IP, user-agent, result.
- Retention: 180 days.

#### 4.8 Performance & Scalability

- Auth service is stateless (JWT), so scale horizontally.
- Use Redis for lockout counters and token blacklist to avoid DB load.
- Rate limiting at API gateway (e.g., Nginx limit_req, Kong rate-limiting plugin).
- For 1000 concurrent login requests, each request should be under 2s (mostly DB lookup + bcrypt). Bcrypt cost factor should be tuned (10–12). Optionally use async worker threads for password hashing.

#### 4.9 Frontend Implementation Notes

- Use a state management (Redux, Context) to hold auth state.
- On login success, store token in cookie and redirect.
- On 401 response, redirect to login page (or show a modal).
- For "remember me", send boolean in request; backend sets appropriate expiry.
- Password visibility toggle: local state only, no server impact.
- Client-side validation: required fields, min password length.
- After 3 failed attempts, fetch a captcha challenge and show widget.

#### 4.10 Testing Considerations

- Unit tests for auth service (password validation, lockout, token generation).
- Integration tests for API endpoints with mocked DB.
- Security tests: OWASP scan, brute force simulation, CSRF checks.
- Performance load test with 1000 concurrent logins.

This solution meets all functional and non-functional requirements while remaining extensible for third-party OAuth (via plugin pattern) and future enhancements.