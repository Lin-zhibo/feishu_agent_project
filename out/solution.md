## Technical Solution: WeChat Mini-Program Login Integration

### 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WeChat Mini‑Program                          │
│  ┌─────────────┐   ┌─────────────┐   ┌───────────────────────────┐ │
│  │  Login Page  │   │   Home Page  │   │  Other Protected Pages   │ │
│  └──────┬───────┘   └─────────────┘   └────────────┬──────────────┘ │
│         │                                            │                │
│         │  wx.login()                                │  Authorization:│
│         │  → code                                    │  Header       │
│         ▼                                            │  Bearer token │
│  ┌─────────────────┐   ┌────────────────────────┐    │                │
│  │   utils/auth.js  │   │  utils/request.js     │◄───┘                │
│  └────────┬─────────┘   └───────────┬────────────┘                     │
│           │                         │ HTTP (HTTPS)                     │
└───────────┼─────────────────────────┼─────────────────────────────────┘
            │                         │
            ▼                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     API Gateway / Load Balancer                       │
│                     (e.g., Nginx, Cloudflare)                         │
└────────────────────────────────────┬──────────────────────────────────┘
                                     │ HTTPS
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          Backend Server                               │
│                                                                       │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐  │
│  │  Auth Router  │   │  User Router  │   │   Middleware (JWT,       │  │
│  │  /api/login   │   │  /api/user    │   │   Rate Limit, Logging)  │  │
│  └──────┬────────┘   └──────┬───────┘   └──────────────────────────┘  │
│         │                    │                                          │
│         ▼                    ▼                                          │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                      Controller Layer                          │   │
│  │  AuthController: exchange code, create/update user, gen token  │   │
│  │  UserController: get user profile (protected)                  │   │
│  └────────────────────────────────────────────────────────────────┘   │
│         │                                                              │
│         ▼                                                              │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                      Service Layer                              │   │
│  │  WeChatService: call jscode2session, verify signature           │   │
│  │  TokenService: generate/verify JWT, manage blacklist            │   │
│  │  UserService: find or create user, update login time            │   │
│  └────────────────────────────────────────────────────────────────┘   │
│         │                                                              │
│         ▼                                                              │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                      Data Access Layer                          │   │
│  │  UserRepository / ORM (e.g., Prisma, Mongoose)                  │   │
│  └────────────────────────────────────────────────────────────────┘   │
│         │                                                              │
│         ▼                                                              │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                         Database                                │   │
│  │  (e.g., PostgreSQL, MySQL, MongoDB)                             │   │
│  └────────────────────────────────────────────────────────────────┘   │
│         │                                                              │
│         ▼                                                              │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │                         Redis (optional)                        │   │
│  │  • Cache session_key (with short TTL)                          │   │
│  │  • Token blacklist / rate limit counters                       │   │
│  └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        WeChat Server                                 │
│  https://api.weixin.qq.com/sns/jscode2session                       │
└──────────────────────────────────────────────────────────────────────┘
```

**Key Flow**  
1. User taps “WeChat Login” → frontend calls `wx.login()` → gets `code`.  
2. Frontend sends `code` to backend via `POST /api/login` (HTTPS).  
3. Backend calls WeChat API with `appid`, `secret`, `code`.  
4. WeChat returns `openid`, `session_key`, (optionally `unionid`).  
5. Backend creates/updates user record in DB, generates JWT token.  
6. Backend returns `{ token, user }` to frontend.  
7. Frontend stores token in `wx.setStorageSync('token')` and redirects to home.  
8. All subsequent API calls include `Authorization: Bearer <token>` header.

---

### 2. File Structure

#### Frontend (WeChat Mini‑Program)

```
miniprogram/
├── app.js                  # App lifecycle, check token validity on launch
├── app.json                # Page registration, global configuration
├── app.wxss                # Global styles
├── utils/
│   ├── request.js          # Axios wrapper with auth interceptor
│   ├── auth.js             # Token management (get, set, clear, verify)
│   └── constants.js        # API base URL, error codes
├── pages/
│   ├── login/
│   │   ├── login.wxml      # UI: WeChat login button, loading, error messages
│   │   ├── login.wxss
│   │   ├── login.js        # Logic: debounce, wx.login, POST to API, error handling
│   │   └── login.json
│   ├── index/              # (Home page) – after successful login
│   │   ├── index.wxml
│   │   ├── index.wxss
│   │   ├── index.js        # OnLoad: check token, if invalid → redirect to login
│   │   └── index.json
│   └── ...                 # Other protected pages
```

#### Backend (Example: Node.js + Express)

```
backend/
├── src/
│   ├── app.js                  # Express app setup, middlewares, route mounting
│   ├── config/
│   │   ├── index.js            # AppID, AppSecret, JWT secret, DB config
│   │   └── environment.js      # Environment-specific overrides
│   ├── middleware/
│   │   ├── auth.js             # JWT verification middleware
│   │   ├── rateLimit.js        # Rate limiting for /api/login
│   │   ├── logger.js           # Request logging (structured)
│   │   └── errorHandler.js     # Global error handler
│   ├── routes/
│   │   ├── auth.routes.js      # POST /api/login, POST /api/logout
│   │   └── user.routes.js      # GET /api/user/me (protected)
│   ├── controllers/
│   │   ├── auth.controller.js  # handleLogin, handleLogout
│   │   └── user.controller.js  # getProfile
│   ├── services/
│   │   ├── wechat.service.js   # jscode2session call, response validation
│   │   ├── token.service.js    # JWT generation/verification, blacklist
│   │   └── user.service.js     # FindOrCreate, update login time
│   ├── models/
│   │   ├── user.model.js       # User schema (Mongoose/Prisma)
│   │   └── session.model.js    # Optional: store session_key (encrypted)
│   ├── repositories/
│   │   └── user.repository.js  # DB queries
│   ├── utils/
│   │   ├── crypto.js           # Encrypt/decrypt session_key if needed
│   │   └── errors.js           # Custom error classes
│   └── logger/
│       └── index.js            # Winston / Pino configuration
├── .env                        # Sensitive config (not committed)
├── package.json
└── Dockerfile                  # For containerized deployment
```

---

### 3. API Design

#### 3.1 Endpoints

| Method | Path              | Auth Required | Description                                     |
|--------|-------------------|---------------|-------------------------------------------------|
| POST   | `/api/login`      | No            | Exchange code for token, create/update user     |
| POST   | `/api/logout`     | Yes           | Invalidate token (optional blacklist)           |
| GET    | `/api/user/me`    | Yes           | Get current user profile                        |
| GET    | `/api/health`     | No            | Health check                                    |

#### 3.2 Detailed API Specifications

**POST /api/login**

- **Request Body**
  ```json
  {
    "code": "wx_code_here"
  }
  ```
- **Success Response (200)**
  ```json
  {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "id": "user_id",
      "openid": "oXXXXX",           // Not exposed to frontend in practice
      "unionid": "uXXXXX",          // If applicable, not exposed
      "nickname": null,
      "avatar_url": null,
      "is_new_user": true
    },
    "expires_in": 604800             // Token TTL (seconds, e.g., 7 days)
  }
  ```
- **Error Responses**
  - `400 Bad Request`: Code missing, expired, or invalid (WeChat returns errcode 40029)
    ```json
    { "error": "invalid_code", "message": "登录已过期，请重新授权" }
    ```
  - `401 Unauthorized` (not used here)
  - `429 Too Many Requests`: Rate limit exceeded
    ```json
    { "error": "rate_limited", "message": "请求过于频繁，请稍后重试" }
    ```
  - `500 Internal Server Error`: WeChat service unavailable, DB error
    ```json
    { "error": "server_error", "message": "登录服务异常，请稍后重试" }
    ```

**POST /api/logout**

- **Headers**: `Authorization: Bearer <token>`
- **Request Body**: (empty)
- **Success Response (200)**: `{ "message": "logged_out" }`
- **Error**: `401` if token invalid or expired.

**GET /api/user/me**

- **Headers**: `Authorization: Bearer <token>`
- **Response (200)**:
  ```json
  {
    "id": "user_id",
    "openid": "oXXXXX",      // Only returned if absolutely necessary; consider omitting
    "nickname": "WeChat nickname",
    "avatar_url": "https://...",
    "created_at": "2024-01-01T00:00:00Z",
    "last_login": "2024-01-10T12:00:00Z"
  }
  ```

#### 3.3 Token Design

- **Algorithm**: HS256 (HMAC with SHA-256)
- **Payload**:
  ```json
  {
    "sub": "user_id",
    "iat": <issued_at>,
    "exp": <expiration>
  }
  ```
- **TTL**: 7 days (configurable), no refresh token for simplicity. For longer sessions, consider a refresh token pattern.
- **Security**: Use a strong, random secret stored in environment variable. Rotate keys periodically.

---

### 4. Key Implementation Notes

#### 4.1 Frontend

- **Debounce**: Prevent multiple rapid clicks on login button – disable button after first click until response received.
- **Loading State**: Show `wx.showLoading()` with “登录中…” while waiting.
- **Error Handling**: Distinguish network error vs. server error vs. code expired. Show user‑friendly toast messages (e.g., “网络异常，请检查后重试”).
- **Auto‑login on App Launch**: In `app.js` `onLaunch`, check if token exists in storage and attempt `GET /api/user/me`. If fails (401), clear token and redirect to login page.
- **Token Expiry Handling**: In the `request.js` interceptor, if server returns 401, clear token and navigate to login page.
- **Privacy**: Never log or display `openid` or `session_key` in frontend.

#### 4.2 Backend

**Code Exchange** (WeChatService)
- Use HTTPS with proper TLS verification.
- Validate WeChat response: check `errcode` and `errmsg`. If `errcode` is non‑zero, log the error and return appropriate HTTP status.
- Do **not** store `session_key` in plaintext; if needed for later decryption (e.g., user data), encrypt it with a server‑side key.
- Rate limit `/api/login` per IP (e.g., 10 requests per minute) to prevent brute force.

**User Management** (UserService)
- `findOrCreate` logic:
  ```js
  async function findOrCreate(openid, unionid, sessionKey) {
    let user = await User.findOne({ openid });
    if (!user) {
      user = await User.create({ openid, unionid, first_login: Date.now() });
    } else {
      user.last_login = Date.now();
      if (unionid) user.unionid = unionid; // update if previously null
      await user.save();
    }
    return user;
  }
  ```
- Ensure `openid` is unique index.

**Security**
- **HTTPS Only**: Enforce HTTPS at load balancer / API gateway.
- **Never Log `code`, `session_key`, `openid`** in plaintext in logs. Log only masked versions (`code` first 4 chars + “****”).
- **JWT**: Do not include `openid` or `session_key` in token payload. Only include `user_id`. Validate signature on every authenticated request.
- **Session Key**: If stored (e.g., for offline message decryption), store encrypted at rest using AES‑256. Use a dedicated encryption key rotated regularly.

**Logging** (Logger)
- Structured JSON logs (e.g., using Winston/Pino).
- For each login request, log:
  - Timestamp
  - Client IP
  - Success/failure
  - Error type (if failure)
  - Response time
  - Masked `code` (optional)
- Ensure logs do not contain PII (personal identifiable information) like full openid.

**Performance**
- Average login response time < 2 seconds: WeChat API typically responds in < 500ms; backend processing < 200ms. Ensure database queries are indexed.
- Use connection pooling for DB.
- Consider caching `session_key` in Redis (TTL = 5 minutes) to avoid re‑requesting WeChat for the same code (though code is one‑time use; caching is for other scenarios).

**Availability**
- Backend deployment behind a load balancer with health checks.
- Retry logic for WeChat API calls (e.g., retry on network timeout, max 2 retries).
- Graceful degradation: if WeChat API is unreachable, return 503 with appropriate message.

**Rate Limiting**
- Apply at API gateway or middleware: 10 requests per minute per IP for `/api/login`.
- Return `429` with `Retry-After` header.

**Error Codes** (consistent across all responses)
```json
{
  "error": "string_code",
  "message": "Human‑readable message"
}
```

Common codes:
- `invalid_code` – code expired or invalid.
- `code_exchanged` – duplicate code (WeChat prevents reuse, but handle edge case).
- `rate_limited` – too many requests.
- `server_error` – internal or WeChat API failure.

#### 4.3 Database Schema (Example: PostgreSQL)

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  openid VARCHAR(64) NOT NULL UNIQUE,
  unionid VARCHAR(64),
  encrypted_session_key BYTEA,  -- encrypted with server key
  nickname VARCHAR(64),
  avatar_url VARCHAR(512),
  first_login TIMESTAMP NOT NULL DEFAULT NOW(),
  last_login TIMESTAMP NOT NULL DEFAULT NOW(),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_openid ON users(openid);
```

#### 4.4 Testing & QA Verification

- **Unit Tests**: Mock WeChat API, test `findOrCreate`, token generation.
- **Integration Tests**: Spin up test DB, call `/api/login` with mock code (simulate WeChat response), verify token and user record.
- **Load Tests**: Ensure login endpoint handles 1000 req/min with acceptable latency.
- **Security Scans**: Use SAST/DAST tools to detect JWT vulnerabilities, injection, etc.
- **E2E Tests**: Use WeChat developer tools to simulate real login flow.

---

### 5. Summary of Decisions

| Aspect                | Decision                                     | Rationale                                                                 |
|-----------------------|----------------------------------------------|---------------------------------------------------------------------------|
| Token Type            | JWT (stateless)                              | No server‑side session storage, easy to scale horizontally                 |
| Token Refresh         | Not implemented (optional future)            | 7‑day TTL is sufficient for most mini‑programs; refresh adds complexity   |
| Storage of session_key| Encrypted at rest (only if needed)           | Privacy compliance; most apps do not need it after login                   |
| Error Communication   | Consistent JSON error codes                  | Simplifies frontend error handling                                        |
| Rate Limiting         | Per IP on /api/login                         | Mitigates brute‑force and abuse                                           |
| Logging               | Structured, no PII                           | Compliance with privacy laws (PIPL, GDPR)                                 |
| Frontend Token Check  | On app launch + API interceptor              | Seamless auto‑login and token lifecycle management                        |

This solution satisfies all functional and non‑functional requirements, with emphasis on security, performance, and user experience.