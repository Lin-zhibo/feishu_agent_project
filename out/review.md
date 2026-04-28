# Code Review Report — 微信小程序登录技术解决方案

## Executive Summary

This is a **well-structured and thorough** design document covering architecture, API design, security considerations, and observability. However, I found **several critical runtime bugs** that would prevent the code from working, **security violations** against WeChat's official recommendations, and **design flaws** in token/encryption handling.

---

## 1️⃣ CRITICAL Issues

### CRITICAL-1: `session_key` Stored in Database (Violates WeChat Security Model)

**File:** `src/modules/security/encryption.service.ts` + `backend/src/modules/auth/auth.service.ts`

```sql
encrypted_session_key TEXT,              -- AES-256-GCM 加密存储
session_key_iv  VARCHAR(64),
```

**Problem:**  
Per [WeChat Official Documentation](https://developers.weixin.qq.com/miniprogram/dev/framework/open-ability/login.html):
> "Session key 是数据解密的关键，**开发者不应该在本地或数据库中以明文或加密形式存储 session_key**。"

Storing `session_key` — even encrypted in AES-256-GCM — violates WeChat's security guidelines. The `session_key` has **no guaranteed validity period** and can be refreshed by WeChat at any time. If the encryption key is compromised, all historical `session_key` values are exposed.

**Fix:**  
- Store `session_key` in **Redis only** with a short TTL (e.g., 5 minutes) for the immediate login session
- If you need to decrypt user data later (e.g., phone number), re-invoke `code2session` to get a fresh key
- Alternatively, encrypt/decrypt data immediately during the login flow and discard the key

```typescript
// ✅ Correct approach: Redis cache with TTL
await this.redisService.set(
  `session_key:${user.id}`,
  wechatRes.session_key,
  300  // 5 minutes TTL only
);
```

---

### CRITICAL-2: `dataSource` Not Injected in AuthService → Runtime Crash

**File:** `src/modules/auth/auth.service.ts` (line ~48)

```typescript
@Injectable()
export class AuthService {
  constructor(
    private readonly wechatService: WechatService,
    private readonly userService: UserService,
    private readonly tokenService: TokenService,
    private readonly encryptionService: EncryptionService,
  ) {}  // ⚠️ DataSource NOT injected!

  async login(params: LoginParams): Promise<LoginResult> {
    // ...
    return await this.dataSource.transaction(async (manager) => {
      // ^^^^ TypeError: Cannot read properties of undefined (reading 'transaction')
```

**Problem:**  
`this.dataSource` is used but never injected. This will throw a **runtime `TypeError`** on every login attempt.

**Fix:**
```typescript
constructor(
  private readonly dataSource: DataSource,  // ✅ Must inject
  private readonly wechatService: WechatService,
  // ...
) {}
```

---

### CRITICAL-3: AES-256-GCM Auth Tag Not Persisted → Decryption Always Fails

**File:** `src/modules/security/encryption.service.ts` vs Database Schema

```typescript
// encrypt() returns: { ciphertext: string; iv: string; tag: string }
// But database stores only:
encrypted_session_key TEXT,    // stores ciphertext only
session_key_iv  VARCHAR(64),  // stores iv only
// ⚠️ NO column for 'tag'!
```

**Problem:**  
AES-256-GCM **requires** the authentication tag for decryption. The `tag` is returned by `encrypt()` but the database schema has no column to store it. When `decrypt(ciphertext, ivHex, tagHex)` is called later, `tagHex` cannot be retrieved → **decryption always throws**.

**Fix:**
```sql
encrypted_session_key TEXT,              -- AES-256-GCM encrypted data
session_key_iv  VARCHAR(64),             -- Initialization Vector
session_key_tag VARCHAR(64),             -- ✅ Authentication Tag (GCM)
```

Or combine them:
```typescript
// Store combined: iv:tag:ciphertext (base64)
const combined = `${iv.toString('hex')}:${tag}:${encrypted}`;
```

---

### CRITICAL-4: `checkCodeReuse()` Queries Wrong Table / Missing Repository Injection

**File:** `src/modules/wechat/wechat.service.ts` (shown in section 4.4.2)

```typescript
async checkCodeReuse(code: string): Promise<void> {
  const codeHash = crypto.createHash('sha256').update(code).digest('hex');
  
  const exists = await this.userRepository.findOne({  // ⚠️ Not injected!
    where: { codeHash },  // ⚠️ Not a column on users table!
    select: ['id'],
  });
```

**Problems:**  
1. `this.userRepository` is **not injected** into `WechatService`  
2. `codeHash` is a column in `login_audits`, **not** in `users`  
3. This method is **never called** in the login flow shown in `AuthService`  

**Fix:**
```typescript
// Move to a dedicated audit service with proper injection
@Injectable()
export class AuditService {
  constructor(
    @InjectRepository(LoginAudit)
    private readonly auditRepository: Repository<LoginAudit>,  // ✅ login_audits
  ) {}

  async checkCodeReuse(code: string): Promise<void> {
    const codeHash = crypto.createHash('sha256').update(code).digest('hex');
    const exists = await this.auditRepository.findOne({
      where: { codeHash },
      select: ['id'],
    });
    if (exists) throw new UnauthorizedException({ code: 40102, ... });
  }
}
```

---

### CRITICAL-5: Refresh Token API Call in Interceptor Missing Authorization Header

**File:** `miniprogram/interceptors/token.interceptor.ts`

```typescript
private async refreshToken(): Promise<boolean> {
  const refreshToken = this.storageService.get('refreshToken');
  if (!refreshToken) return false;
  
  const res = await this._request({
    url: '/api/v1/auth/refresh',
    method: 'POST',
    data: { refreshToken }
    // ⚠️ Missing Authorization header!
  });
```

**Problem:**  
The API spec (section 3.2.2) requires:
```
Authorization: Bearer <refresh_token>
```
But the interceptor only sends `data: { refreshToken }` in the body. The backend likely checks the header → **refresh always fails**.

**Fix:**
```typescript
const res = await this._request({
  url: '/api/v1/auth/refresh',
  method: 'POST',
  header: { 'Authorization': `Bearer ${refreshToken}` },  // ✅
  data: { refreshToken }
});
```

---

## 2️⃣ HIGH Issues

### HIGH-1: Race Condition in Concurrent Login — No Implementation

**File:** Section 4.7 (Boundary Conditions table)

| 场景 | 预期行为 |
|------|----------|
| 并发重复登录 | 后一次请求覆盖前一次 Token，旧 Token 加入黑名单 |

**Problem:**  
The boundary table describes correct behavior, but **no code implements this**. When two login requests arrive simultaneously:
- Both call `code2session` — one will get `CODE_USED` (40102)
- Both may try to `createUser` if user doesn't exist — potential unique constraint violation
- Both generate different token pairs — last write wins, but no blacklisting of the overwritten token

**Fix:**  
Add pessimistic locking or application-level locks:
```typescript
async login(params: LoginParams): Promise<LoginResult> {
  const wechatRes = await this.wechatService.code2Session(params.code);
  
  // ✅ Distributed lock to prevent concurrent registration
  const lockKey = `login:${wechatRes.openid}`;
  const acquired = await this.redisService.setnx(lockKey, '1', 10); // 10s TTL
  if (!acquired) {
    // Retry or queue
  }
  
  try {
    return await this.dataSource.transaction(async (manager) => {
      // ... login logic
    });
  } finally {
    await this.redisService.del(lockKey);
  }
}
```

---

### HIGH-2: Rate Limiter `incr` + `expire` Is Not Atomic

**File:** `src/modules/security/rate-limiter.service.ts`

```typescript
const current = await this.redisService.incr(windowKey);
if (current === 1) {
  await this.redisService.expire(windowKey, windowSeconds);  // ⚠️ Race condition
}
```

**Problem:**  
If Redis crashes or the server restarts between `incr` and `expire`, the key persists **without an expiry**, permanently blocking that client.

**Fix:** Use Redis `SET` with `NX` + `EX` or a Lua script:
```typescript
// ✅ Option 1: SET with NX and EX
const result = await this.redisService.set(
  windowKey, 1, 'NX', 'EX', windowSeconds
);
if (result) { /* first request */ }

// ✅ Option 2: Lua script (atomic)
const luaScript = `
  local current = redis.call('INCR', KEYS[1])
  if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
  end
  return current
`;
```

---

### HIGH-3: `Throttle` Decorator Requires Guard — Not Registered

**File:** `src/modules/auth/auth.controller.ts`

```typescript
@Throttle({ default: { limit: 60, ttl: 60000 } })
```

**Problem:**  
`@Throttle()` from `@nestjs/throttler` only defines metadata. It **requires** `ThrottlerGuard` to be applied (globally or at controller level). Without registration, the decorator is a **no-op**.

**Fix:**
```typescript
// In app.module.ts or auth.module.ts
import { APP_GUARD } from '@nestjs/core';
import { ThrottlerGuard } from '@nestjs/throttler';

@Module({
  providers: [
    {
      provide: APP_GUARD,
      useClass: ThrottlerGuard,  // ✅ Register globally
    },
  ],
})
```

---

### HIGH-4: `Math.random()` for RequestId — Not Cryptographically Secure

**File:** `src/modules/auth/auth.controller.ts`

```typescript
return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
```

**Problem:**  
`Math.random()` is **not cryptographically secure** and can be predicted. For `requestId` this is more about collision risk and audit integrity — a collision would break request tracing.

**Fix:**
```typescript
import { randomUUID } from 'crypto';

return `req_${randomUUID()}`;
// or: nanoId / uuid v4
```

---

### HIGH-5: No JWT Secret Rotation or Key Management Strategy

**File:** `src/config/jwt.config.ts` / `.env`

```
JWT_SECRET=your-256-bit-jwt-secret-in-base64
```

**Problem:**  
The document mentions no key rotation strategy. If the JWT secret is compromised:
- All existing tokens (access + refresh, up to 30d validity) can be forged
- No mention of `kid` (key ID) header to support multiple signing keys

**Fix:**
```typescript
// Use JWKS or at minimum support key rotation:
const jwtConfig = {
  secret: process.env.JWT_SECRET,
  signOptions: {
    keyid: process.env.JWT_KID || 'v1',  // ✅ key ID for rotation
    expiresIn: '7d',
  },
};

// When rotating: add new key as 'v2', old tokens with 'v1' still validate
```

---

## 3️⃣ MEDIUM Issues

### MEDIUM-1: AuthService Not Injectable in `checkCodeReuse` — Dead Code

`checkCodeReuse` is defined but **never invoked** in the login flow. The `AuthService.login()` method goes directly to `code2Session` without calling `checkCodeReuse` first. This means code reuse protection (idempotency) is **not actually enforced**.

### MEDIUM-2: `SkipThrottle` Imported But Unused

```typescript
import { SkipThrottle } from '@nestjs/throttler';  // Unused import
```

### MEDIUM-3: `getDeviceInfo()` Calls Synchronous Blocking APIs

```typescript
private getDeviceInfo(): DeviceInfo {
  const info = wx.getSystemInfoSync();      // Blocks
  const accountInfo = wx.getAccountInfoSync();  // Blocks
```

On every login, two synchronous native calls block the main thread. For better UX:
```typescript
// Pre-fetch in app.ts onLaunch and cache
async getDeviceInfo(): Promise<DeviceInfo> {
  const [info, accountInfo] = await Promise.all([
    wx.getSystemInfoAsync(),      // ✅ Async version
    wx.getAccountInfoSync(),      // No async alternative, but cache it
  ]);
}
```

### MEDIUM-4: `reLaunch` in `app.ts` — May Cause Loop on Deep Links

```typescript
wx.reLaunch({ url: '/pages/home/index' });
```

If the user opened a **deep link** to `/pages/profile/index`, auto-navigating to `/pages/home/index` breaks that intent. Consider:
```typescript
// Only navigate if user is on the login page
const pages = getCurrentPages();
if (pages.length === 1 && pages[0].route === 'pages/login/index') {
  wx.reLaunch({ url: '/pages/home/index' });
}
```

### MEDIUM-5: No Validation on `deviceInfo` Fields

```typescript
// DTO validation
export class WechatLoginDto {
  @IsString()
  @IsNotEmpty()
  code: string;
  
  deviceInfo: DeviceInfo;  // ⚠️ No @ValidateNested() or inner validation
}
```

**Fix:**
```typescript
export class DeviceInfoDto {
  @IsString()
  @IsOptional()
  platform?: string;
  // ...
}

export class WechatLoginDto {
  @IsString()
  @IsNotEmpty()
  code: string;
  
  @ValidateNested()
  @Type(() => DeviceInfoDto)
  deviceInfo: DeviceInfoDto;
}
```

---

## 4️⃣ LOW Issues

### LOW-1: Private `sanitizeUser()` Harder to Unit Test

```typescript
private sanitizeUser(user: User): SanitizedUser {
```

Make it `public` or extract to a pure function for testability.

### LOW-2: Index on `login_audits.created_at` Without Query Pattern

```sql
CREATE INDEX idx_login_audits_created_at ON login_audits(created_at);
```

If queries typically filter `WHERE user_id = ? AND created_at > ?`, consider a **composite index**:
```sql
CREATE INDEX idx_login_audits_user_created ON login_audits(user_id, created_at);
```

### LOW-3: `code_hash` Unique Index Allows NULLs (Defeats Uniqueness)

```sql
CREATE UNIQUE INDEX idx_login_audits_code_hash ON login_audits(code_hash) 
    WHERE code_hash IS NOT NULL;
```

PostgreSQL allows multiple NULL values in a unique index. If `code_hash` is nullable, the uniqueness constraint is effectively **bypassed** for any row where code_hash is NULL. Consider making `code_hash` NOT NULL.

### LOW-4: Missing `Crypto` Import in `checkCodeReuse` Snippet

```typescript
const codeHash = crypto.createHash('sha256').update(code).digest('hex');
```

The `crypto` module is imported in `encryption.service.ts` but **not shown** in the `checkCodeReuse` code snippet.

---

## 5️⃣ Suggestions for Improvement

### Suggestion 1: Token Family / Rotation Chain

**Current:** When refreshing, both access + refresh tokens are replaced. Old refresh tokens remain valid until expiry.

**Better:** Implement **refresh token rotation** — invalidate the old refresh token when issuing a new one. This detects token theft (if a stolen refresh token is used after rotation).

```typescript
// On refresh:
await this.redisService.del(`refresh:${oldJti}`);  // Invalidate old
await this.redisService.set(`refresh:${newJti}`, userId, 30 * 86400);  // New
```

### Suggestion 2: Circuit Breaker State Persistence

The `CircuitBreaker` is in-memory. In a multi-instance deployment, one instance might be open while others keep hammering the failing WeChat API. Consider using Redis for circuit breaker state.

### Suggestion 3: Structured Logging — Add Trace ID Propagation

The `requestId` is generated per request but not propagated to **downstream calls** (e.g., WeChat API calls). Add it as a correlation ID in all service log entries for full traceability.

### Suggestion 4: Graceful Degradation for WeChat API Outage

Add a **fallback mechanism**: if the WeChat API is unreachable for extended periods, consider allowing previously authenticated users to continue using cached tokens without re-validation (with appropriate warnings).

### Suggestion 5: Add Security Headers

In the Nginx layer, add:
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
```

---

## Summary Table

| # | Severity | Category | Issue |
|---|----------|----------|-------|
| CR-1 | **CRITICAL** | Security | `session_key` stored in DB violates WeChat policy |
| CR-2 | **CRITICAL** | Runtime Error | `dataSource` not injected → `TypeError` on login |
| CR-3 | **CRITICAL** | Bug | GCM auth tag not persisted → decryption always fails |
| CR-4 | **CRITICAL** | Runtime Error | `checkCodeReuse()` uses wrong repo/table, never called |
| CR-5 | **CRITICAL** | API Contract | Refresh call missing `Authorization` header |
| H-1 | **HIGH** | Race Condition | Concurrent login not handled in code |
| H-2 | **HIGH** | Reliability | Rate limiter `incr`+`expire` not atomic |
| H-3 | **HIGH** | Configuration | `@Throttle` guard not registered → no rate limiting |
| H-4 | **HIGH** | Security | `Math.random()` for request ID not crypto-safe |
| H-5 | **HIGH** | Security | No JWT key rotation strategy |
| M-1 | **MEDIUM** | Dead Code | `checkCodeReuse` defined but never invoked |
| M-2 | **MEDIUM** | Code Quality | Unused import `SkipThrottle` |
| M-3 | **MEDIUM** | Performance | Synchronous blocking calls in `getDeviceInfo` |
| M-4 | **MEDIUM** | UX | `reLaunch` breaks deep linking |
| M-5 | **MEDIUM** | Validation | Missing `@ValidateNested` on `deviceInfo` |
| L-1 | **LOW** | Testability | Private method `sanitizeUser` |
| L-2 | **LOW** | Performance | Suboptimal index on `login_audits` |
| L-3 | **LOW** | Data Integrity | Unique index allows NULL code_hash |
| L-4 | **LOW** | Documentation | Missing `crypto` import in code snippet |

---

**Overall Assessment:** The architecture is sound and well-documented, but **CRITICAL-2, CRITICAL-3, and CRITICAL-4 are production-blocking bugs** that would crash the service. **CRITICAL-1** requires an architectural decision to align with WeChat's security model. I recommend addressing all Critical and High issues before merging this design into development.