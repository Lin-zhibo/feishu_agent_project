# 微信小程序「微信登录」技术解决方案

## 1. 架构总览 (Architecture Overview)

### 1.1 系统分层架构

```
┌────────────────────────────────────────────────────────────────────┐
│                        用户层                                       │
│             微信客户端 (iOS / Android / 开发者工具)                   │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────────┐
│                   表现层 (Mini Program Frontend)                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ 登录页面      │  │ 首页          │  │ 用户中心                   │   │
│  │ (pages/login) │  │ (pages/home) │  │ (pages/profile)          │   │
│  └──────┬───────┘  └──────────────┘  └──────────────────────────┘   │
│         │                                                            │
│  ┌──────▼───────────────────────────────────────────────────────┐   │
│  │                通用能力层 (Services)                          │   │
│  │  auth.service  │  http.service  │  storage.service           │   │
│  │  network.service│  user.service  │  error.service            │   │
│  └──────┬───────────────────────────────────────────────────────┘   │
└─────────┼───────────────────────────────────────────────────────────┘
          │ HTTPS (TLS 1.2+)         ↑ 微信私有协议
          │                          │
┌─────────▼──────────────────────────┼────────────────────────────────┐
│       接入层 (API Gateway / Nginx)   │                               │
│   ┌─ 速率限制 (Rate Limiting) ────┐ │                               │
│   └─ 安全头 (Security Headers) ───┘ │                               │
└─────────┬───────────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────────┐
│                   服务层 (Backend Service)                          │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              AuthController (登录入口)                       │   │
│  └──────────────┬───────────────────────────────────────────────┘   │
│                 │                                                    │
│  ┌──────────────▼───────────────────────────────────────────────┐   │
│  │              AuthService (核心逻辑)                           │   │
│  │  ┌──────────┐  ┌────────────┐  ┌──────────┐                │   │
│  │  │code2session│  │Token签发   │  │用户注册/   │               │   │
│  │  │           │  │(JWT)      │  │查询      │                │   │
│  │  └──────────┘  └────────────┘  └──────────┘                │   │
│  └────────────────────────────────────────────────────────────┘   │
│                 │                                                    │
│  ┌──────────────▼───────────────────────────────────────────────┐   │
│  │              数据访问层 (Repository)                          │   │
│  │  UserRepository   │   SessionRepository  │  TokenRepository │   │
│  └──────────────┬───────────────────────────────────────────────┘   │
│                 │                                                    │
│  ┌──────────────▼───────────────────────────────────────────────┐   │
│  │              数据源 (Data Sources)                            │   │
│  │  PostgreSQL  │  Redis (会话/速率限制)     │  WeChat API       │   │
│  └──────────────┴────────────────────────────┴──────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心技术栈选型

| 层级 | 技术选型 | 选型理由 |
|------|----------|----------|
| **前端框架** | 微信原生框架 + TypeScript | 原生兼容性最佳，TS 提供类型安全 |
| **后端框架** | Node.js (NestJS) / Go (Gin) | Node.js 适合 I/O 密集场景；Go 适合高并发 |
| **API 网关** | Nginx / Kong | 统一 SSL 终结、限流、日志 |
| **数据库** | PostgreSQL 15+ | 强事务支持，JSONB 存储灵活字段 |
| **缓存** | Redis 7+ | Token 黑名单、速率计数、session_key 缓存 |
| **可观测性** | Prometheus + Grafana + ELK | 全链路监控和日志聚合 |

> **推荐方案**：若团队 Node.js 经验丰富，选择 **NestJS**（装饰器风格、模块化、内置 Throttler/Logger）；若有更高并发需求（>5000 QPS），选择 **Go + Gin**。

### 1.3 核心数据流 (Sequence Diagram)

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ 小程序前端 │    │ Nginx    │    │ 后端服务  │    │ Redis    │    │ 微信服务器│
└─────┬────┘    └─────┬────┘    └─────┬────┘    └─────┬────┘    └─────┬────┘
      │                │                │                │                │
      │ 1. 用户点击     │                │                │                │
      │ "微信登录"      │                │                │                │
      ├────────────────►│                │                │                │
      │                 │                │                │                │
      │ 2. 检查网络状态  │                │                │                │
      │◄────────────────┤                │                │                │
      │                 │                │                │                │
      │ 3. wx.login()   │                │                │                │
      ├───────────────────────────────────────────────────────────────►│
      │                 │                │                │             │
      │ 4. 返回 code    │                │                │             │
      │◄───────────────────────────────────────────────────────────────┤
      │                 │                │                │                │
      │ 5. POST /login  │                │                │                │
      │ {code,device}   │                │                │                │
      ├────────────────►├───────────────►│                │                │
      │                 │                │                │                │
      │                 │                │ 6. 速率检查     │                │
      │                 │                ├───────────────►│                │
      │                 │                │◄───────────────┤                │
      │                 │                │                │                │
      │                 │                │ 7. jscode2session               │
      │                 │                ├────────────────────────────────►│
      │                 │                │                 │               │
      │                 │                │ 8. openid+      │               │
      │                 │                │  session_key    │               │
      │                 │                │◄────────────────────────────────┤
      │                 │                │                 │                │
      │                 │                │ 9. 非空+errcode校验              │
      │                 │                │                 │                │
      │                 │                │ 10. 查/建用户    │               │
      │                 │                ├────────────────►│                │
      │                 │                │◄────────────────┤                │
      │                 │                │                 │                │
      │                 │                │ 11. 加密存       │               │
      │                 │                │  session_key    │                │
      │                 │                ├────────────────►│                │
      │                 │                │                 │                │
      │                 │                │ 12. 生成 JWT    │                │
      │                 │                │ (access+refresh)│                │
      │                 │                │                 │                │
      │ 13. 200 OK     │                │                 │                │
      │ {token,user}   │                │                 │                │
      │◄────────────────├────────────────┤                 │                │
      │                 │                │                 │                │
      │ 14. 存 Token    │                │                 │                │
      │ 到 localStorage │                │                 │                │
      ├────────────────►│                │                 │                │
      │                 │                │                 │                │
      │ 15. 跳转首页    │                │                 │                │
      │                 │                │                 │                │
```

---

## 2. 文件结构 (File Structure)

### 2.1 小程序前端 (Mini Program Frontend)

```
miniprogram/
├── app.json                          # 全局配置(页面路径、window、tabBar)
├── app.ts                            # 应用入口(生命周期、全局数据)
├── app.wxss                          # 全局样式
├── project.config.json               # 项目配置文件
├── sitemap.json                      # 搜索索引配置
│
├── pages/
│   ├── login/
│   │   ├── index.wxml                 # 登录页面模板
│   │   ├── index.wxss                 # 登录页面样式
│   │   ├── index.ts                   # 登录页面逻辑
│   │   └── index.json                 # 页面配置
│   ├── home/
│   │   ├── index.wxml
│   │   ├── index.wxss
│   │   ├── index.ts
│   │   └── index.json
│   └── profile/
│       ├── index.wxml
│       ├── index.wxss
│       ├── index.ts
│       └── index.json
│
├── services/                         # 业务服务层
│   ├── auth.service.ts               # 认证服务(wx.login, 登录请求, Token管理)
│   ├── http.service.ts               # HTTP 请求封装(拦截器、重试、超时)
│   ├── user.service.ts               # 用户信息服务
│   ├── storage.service.ts            # 本地存储封装(wx.get/set/removeStorageSync)
│   └── network.service.ts            # 网络状态检测
│
├── utils/
│   ├── constants.ts                  # 常量定义(API_BASE_URL, TOKEN_KEY等)
│   ├── helpers.ts                    # 工具函数(格式化、校验)
│   ├── error-codes.ts                # 错误码与提示文案映射
│   └── logger.ts                     # 前端日志工具
│
├── types/
│   ├── api.d.ts                      # API 请求/响应类型定义
│   ├── user.d.ts                     # 用户相关类型
│   └── auth.d.ts                     # 认证相关类型
│
├── components/
│   ├── login-button/
│   │   ├── index.wxml
│   │   ├── index.wxss
│   │   ├── index.ts
│   │   └── index.json
│   ├── error-toast/
│   │   ├── index.wxml
│   │   ├── index.wxss
│   │   ├── index.ts
│   │   └── index.json
│   └── loading-overlay/
│       ├── index.wxml
│       ├── index.wxss
│       ├── index.ts
│       └── index.json
│
├── interceptors/
│   └── token.interceptor.ts          # Token 过期自动刷新 & 请求注入
│
└── __tests__/                        # 单元测试
    ├── services/
    │   ├── auth.service.test.ts
    │   └── http.service.test.ts
    └── pages/
        └── login.test.ts
```

### 2.2 后端服务 (Backend Service — NestJS 示例)

```
backend/
├── package.json
├── tsconfig.json
├── nest-cli.json
├── .env                               # 环境变量(APPID, SECRET, DB_URL, REDIS_URL)
├── .env.example                       # 环境变量模板
├── Dockerfile
├── docker-compose.yml                 # 本地开发编排(PostgreSQL + Redis + App)
│
├── src/
│   ├── main.ts                        # 应用入口(启动、全局管道、过滤器)
│   ├── app.module.ts                  # 根模块
│   │
│   ├── modules/
│   │   ├── auth/
│   │   │   ├── auth.module.ts         # 认证模块
│   │   │   ├── auth.controller.ts     # 登录/刷新/登出接口
│   │   │   ├── auth.service.ts        # 核心认证逻辑
│   │   │   ├── auth.service.spec.ts   # 单元测试
│   │   │   ├── dto/
│   │   │   │   ├── wechat-login.dto.ts      # 登录请求DTO(含class-validator)
│   │   │   │   ├── refresh-token.dto.ts     # 刷新Token请求DTO
│   │   │   │   └── login-response.dto.ts    # 登录响应DTO
│   │   │   ├── guards/
│   │   │   │   └── wechat-auth.guard.ts     # JWT 校验守卫
│   │   │   ├── strategies/
│   │   │   │   └── jwt.strategy.ts          # Passport JWT 策略
│   │   │   └── interfaces/
│   │   │       └── auth.interface.ts        # 认证相关接口
│   │   │
│   │   ├── user/
│   │   │   ├── user.module.ts
│   │   │   ├── user.controller.ts
│   │   │   ├── user.service.ts
│   │   │   ├── user.service.spec.ts
│   │   │   ├── entities/
│   │   │   │   └── user.entity.ts           # TypeORM 用户实体
│   │   │   └── dto/
│   │   │       └── user-profile.dto.ts
│   │   │
│   │   ├── wechat/
│   │   │   ├── wechat.module.ts
│   │   │   ├── wechat.service.ts            # 封装微信API调用
│   │   │   ├── wechat.service.spec.ts
│   │   │   ├── interfaces/
│   │   │   │   └── wechat.interface.ts      # 微信响应类型
│   │   │   └── constants/
│   │   │       └── error-codes.ts           # 微信错误码映射
│   │   │
│   │   ├── token/
│   │   │   ├── token.module.ts
│   │   │   ├── token.service.ts             # JWT 签发/验证/刷新
│   │   │   └── token.service.spec.ts
│   │   │
│   │   └── security/
│   │       ├── security.module.ts
│   │       ├── rate-limiter.service.ts      # Redis 速率限制
│   │       └── encryption.service.ts        # session_key 加密/解密
│   │
│   ├── common/
│   │   ├── filters/
│   │   │   ├── http-exception.filter.ts     # 全局异常过滤器
│   │   │   └── wechat-exception.filter.ts   # 微信异常处理
│   │   ├── interceptors/
│   │   │   ├── logging.interceptor.ts       # 请求日志记录(脱敏)
│   │   │   ├── timeout.interceptor.ts       # 超时控制拦截器
│   │   │   └── transform.interceptor.ts     # 统一响应格式
│   │   ├── pipes/
│   │   │   └── validation.pipe.ts           # 参数校验管道
│   │   ├── middlewares/
│   │   │   └── device-info.middleware.ts    # 设备信息提取
│   │   ├── constants/
│   │   │   └── error-codes.ts               # 业务错误码枚举
│   │   └── helpers/
│   │       ├── retry.helper.ts              # 指数退避重试工具
│   │       └── logger.helper.ts             # 结构化日志(脱敏)
│   │
│   └── config/
│       ├── database.config.ts               # 数据库配置
│       ├── redis.config.ts                  # Redis 配置
│       ├── jwt.config.ts                    # JWT 配置
│       └── wechat.config.ts                 # 微信配置
│
├── migrations/                             # 数据库迁移文件
│   └── 20250101_create_users_table.ts
│
├── test/
│   ├── e2e/
│   │   └── auth.e2e-spec.ts                # 端到端测试
│   └── jest-e2e.json
│
└── docs/
    └── api-spec.yaml                       # OpenAPI 3.0 规范文档
```

---

## 3. API 设计 (API Design)

### 3.1 接口总览

| 方法 | 路径 | 描述 | 认证 | 限流 |
|------|------|------|------|------|
| POST | `/api/v1/auth/wechat-login` | 微信登录（code 换 Token） | 无 | 60/min/IP |
| POST | `/api/v1/auth/refresh` | 刷新 Token | Refresh Token | 30/min/IP |
| POST | `/api/v1/auth/logout` | 登出（Token 加入黑名单） | Bearer Token | 30/min/IP |
| GET  | `/api/v1/user/profile` | 获取用户信息 | Bearer Token | 120/min/User |

### 3.2 接口详细定义

#### 3.2.1 微信登录接口

```
POST /api/v1/auth/wechat-login
Content-Type: application/json
User-Agent: <设备UA>

Request:
{
  "code": "033J8j0000sX6a1Nfd000a9Z8b3J8j0e",
  "deviceInfo": {
    "platform": "ios",
    "model": "iPhone15,2",
    "system": "17.1",
    "version": "8.0.44",
    "sdkVersion": "3.2.0"
  }
}

Response 200 (成功):
{
  "code": 0,
  "message": "success",
  "requestId": "req_20250101_a1b2c3d4",
  "timestamp": 1704110400000,
  "data": {
    "accessToken": "eyJhbGciOiJIUzI1NiIs...",
    "refreshToken": "dGhpcyBpcyBhIHJlZnJl...",
    "expiresIn": 604800,
    "tokenType": "Bearer",
    "user": {
      "openId": "oHwFz5vP8abc...",
      "unionId": "o6_bmasdasdsad...",
      "avatarUrl": "https://thirdwx.qlogo.cn/...",
      "nickName": "张三",
      "createdAt": "2025-01-01T10:00:00Z"
    }
  }
}

Response 400 (参数校验失败):
{
  "code": 40000,
  "message": "请求参数错误",
  "details": [
    { "field": "code", "error": "code 不能为空" }
  ],
  "requestId": "req_20250101_a1b2c3d4"
}

Response 401 (code 无效/过期):
{
  "code": 40101,
  "message": "登录凭证已过期，请重新登录",
  "errorType": "TOKEN_EXPIRED",
  "requestId": "req_20250101_a1b2c3d4"
}

Response 429 (频率超限):
{
  "code": 42900,
  "message": "请求过于频繁，请稍后再试",
  "retryAfter": 60,
  "requestId": "req_20250101_a1b2c3d4"
}
```

#### 3.2.2 Token 刷新接口

```
POST /api/v1/auth/refresh
Content-Type: application/json
Authorization: Bearer <refresh_token>

Request:
{
  "refreshToken": "dGhpcyBpcyBhIHJlZnJl..."
}

Response 200:
{
  "code": 0,
  "message": "success",
  "data": {
    "accessToken": "eyJhbGciOiJIUzI1NiIs...",
    "refreshToken": "bmV3IHJlZnJl...",
    "expiresIn": 604800
  }
}

Response 401 (Refresh Token 过期/无效):
{
  "code": 40103,
  "message": "登录已过期，请重新登录",
  "errorType": "REFRESH_EXPIRED"
}
```

#### 3.2.3 用户信息接口

```
GET /api/v1/user/profile
Authorization: Bearer <access_token>

Response 200:
{
  "code": 0,
  "message": "success",
  "data": {
    "openId": "oHwFz5vP8abc...",
    "unionId": "o6_bmasdasdsad...",
    "avatarUrl": "https://thirdwx.qlogo.cn/...",
    "nickName": "张三",
    "mobile": "138****1234",        // 已授权则返回脱敏手机号
    "createdAt": "2025-01-01T10:00:00Z",
    "lastLoginAt": "2025-01-15T14:30:00Z"
  }
}
```

### 3.3 错误码定义

| 错误码 | 错误类型 | 说明 | HTTP 状态码 |
|--------|----------|------|-------------|
| 0 | SUCCESS | 成功 | 200 |
| 40000 | BAD_REQUEST | 请求参数错误 | 400 |
| 40100 | UNAUTHORIZED | Token 缺失/无效 | 401 |
| 40101 | TOKEN_EXPIRED | `code` 已过期 (微信 40029) | 401 |
| 40102 | CODE_USED | `code` 已被使用 (幂等性) | 401 |
| 40103 | REFRESH_EXPIRED | Refresh Token 过期 | 401 |
| 40104 | TOKEN_BLACKLISTED | Token 已被登出 | 401 |
| 50000 | WECHAT_API_ERROR | 微信接口异常 (errcode=-1) | 502 |
| 50001 | NETWORK_TIMEOUT | 微信接口超时 | 504 |
| 50002 | WECHAT_FREQ_LIMIT | 微信接口频率限制 (45011) | 502 |
| 42900 | RATE_LIMITED | 请求频率超限 | 429 |
| 50010 | INTERNAL_ERROR | 服务器内部错误 | 500 |

---

## 4. 关键实现说明 (Key Implementation Notes)

### 4.1 前端关键实现

#### 4.1.1 登录流程控制器 (`auth.service.ts` 核心逻辑)

```
登录按钮点击
    │
    ├──[网络检测]──> networkService.checkNetwork()
    │                   ├── 可用 ──> 继续
    │                   └── 不可用 ──> showToast("网络不可用，请检查后重试")
    │
    ├──[登录]──> wx.login()
    │               ├── success ──> 获取 code
    │               └── fail ──> showError("登录失败", 提供重试按钮)
    │
    ├──[请求]──> httpService.post('/auth/wechat-login', { code, deviceInfo })
    │               ├── 200 ──> 解析响应
    │               ├── 401(code过期) ──> 递归重试 wx.login()
    │               └── 5xx ──> showError("服务繁忙")
    │
    ├──[存储]──> storageService.set('accessToken', accessToken)
    │            storageService.set('refreshToken', refreshToken)
    │
    └──[跳转]──> navigateTo('/pages/home/index')
```

**关键代码片段 — 登录服务：**

```typescript
// services/auth.service.ts
import { NetworkService } from './network.service';
import { HttpService } from './http.service';
import { StorageService } from './storage.service';

const MAX_RETRY = 1;  // code 过期后最多重试获取 1 次

export class AuthService {
  private networkService = new NetworkService();
  private httpService = new HttpService();
  private storageService = new StorageService();

  async wechatLogin(retryCount = 0): Promise<LoginResult> {
    // 1. 网络检测
    const isConnected = await this.networkService.checkNetwork();
    if (!isConnected) {
      throw new LoginError('NETWORK_UNAVAILABLE', '网络不可用，请检查后重试');
    }

    // 2. 获取 code
    const loginResult = await wx.login();
    if (loginResult.errMsg !== 'login:ok') {
      throw new LoginError('LOGIN_FAILED', '登录失败，请重试');
    }
    const { code } = loginResult;

    // 3. 发送到后端
    try {
      const response = await this.httpService.post<LoginResponse>(
        '/api/v1/auth/wechat-login',
        {
          code,
          deviceInfo: this.getDeviceInfo()
        }
      );
      
      // 4. 存储 Token
      this.storageService.set('accessToken', response.data.accessToken);
      this.storageService.set('refreshToken', response.data.refreshToken);
      
      return response.data;
    } catch (error) {
      if (error instanceof HttpError && error.code === 40101) {
        // code 过期，重新获取
        if (retryCount < MAX_RETRY) {
          return this.wechatLogin(retryCount + 1);
        }
        throw new LoginError('LOGIN_EXPIRED', '登录失效，请重新尝试');
      }
      throw error;
    }
  }

  private getDeviceInfo(): DeviceInfo {
    const info = wx.getSystemInfoSync();
    const accountInfo = wx.getAccountInfoSync();
    return {
      platform: info.platform,
      model: info.model,
      system: info.system,
      version: info.version,
      sdkVersion: accountInfo.miniProgram?.sdkVersion || ''
    };
  }
}
```

**关键代码片段 — HTTP 拦截器（Token 注入 + 自动刷新）：**

```typescript
// interceptors/token.interceptor.ts
// 在 http.service.ts 中集成

async request<T>(config: RequestConfig): Promise<T> {
  // 注入 Token
  const token = this.storageService.get('accessToken');
  if (token) {
    config.header = {
      ...config.header,
      'Authorization': `Bearer ${token}`
    };
  }
  
  try {
    return await this._request(config);
  } catch (error) {
    // Token 过期 -> 尝试刷新
    if (error.statusCode === 401 && error.data?.errorType === 'TOKEN_EXPIRED') {
      const refreshed = await this.refreshToken();
      if (refreshed) {
        config.header['Authorization'] = `Bearer ${this.storageService.get('accessToken')}`;
        return await this._request(config);  // 重放原始请求
      }
      // 刷新失败 -> 跳转登录页
      this.redirectToLogin();
    }
    throw error;
  }
}

private async refreshToken(): Promise<boolean> {
  const refreshToken = this.storageService.get('refreshToken');
  if (!refreshToken) return false;
  
  try {
    const res = await this._request({
      url: '/api/v1/auth/refresh',
      method: 'POST',
      data: { refreshToken }
    });
    this.storageService.set('accessToken', res.data.accessToken);
    this.storageService.set('refreshToken', res.data.refreshToken);
    return true;
  } catch {
    return false;
  }
}
```

#### 4.1.2 静默登录（自动恢复会话）

```typescript
// app.ts
import { AuthService } from './services/auth.service';

App({
  async onLaunch() {
    const authService = new AuthService();
    
    // 尝试静默登录
    const accessToken = wx.getStorageSync('accessToken');
    if (accessToken) {
      try {
        const user = await authService.validateToken();
        // Token 有效，直接进入首页
        this.globalData.user = user;
        wx.reLaunch({ url: '/pages/home/index' });
      } catch {
        // Token 无效/过期，留在当前页等待用户手动登录
        console.log('Session expired, user needs to re-login');
      }
    }
  }
});
```

### 4.2 后端关键实现

#### 4.2.1 AuthController — 登录入口

```typescript
// modules/auth/auth.controller.ts
import { Controller, Post, Body, Headers, HttpCode } from '@nestjs/common';
import { AuthService } from './auth.service';
import { WechatLoginDto } from './dto/wechat-login.dto';
import { Throttle } from '@nestjs/throttler';
import { SkipThrottle } from '@nestjs/throttler';

@Controller('api/v1/auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('wechat-login')
  @HttpCode(200)
  @Throttle({ default: { limit: 60, ttl: 60000 } })  // 60次/分钟/IP
  async wechatLogin(
    @Body() dto: WechatLoginDto,
    @Headers('user-agent') userAgent: string,
    @Headers('x-real-ip') ip: string,
  ) {
    const result = await this.authService.login({
      code: dto.code,
      deviceInfo: dto.deviceInfo,
      userAgent,
      ip,
    });
    return {
      code: 0,
      message: 'success',
      requestId: this.generateRequestId(),
      timestamp: Date.now(),
      data: result,
    };
  }

  private generateRequestId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}
```

#### 4.2.2 AuthService — 核心业务逻辑

```typescript
// modules/auth/auth.service.ts
import { Injectable } from '@nestjs/common';
import { WechatService } from '../wechat/wechat.service';
import { UserService } from '../user/user.service';
import { TokenService } from '../token/token.service';
import { EncryptionService } from '../security/encryption.service';

@Injectable()
export class AuthService {
  constructor(
    private readonly wechatService: WechatService,
    private readonly userService: UserService,
    private readonly tokenService: TokenService,
    private readonly encryptionService: EncryptionService,
  ) {}

  async login(params: LoginParams): Promise<LoginResult> {
    // 1. 调用微信 jscode2session
    const wechatRes = await this.wechatService.code2Session(params.code);
    
    // 2. 开启数据库事务
    return await this.dataSource.transaction(async (manager) => {
      // 3. 查询或创建用户
      let user = await this.userService.findByOpenId(wechatRes.openid);
      if (!user) {
        user = await this.userService.createUser({
          openId: wechatRes.openid,
          unionId: wechatRes.unionid || null,
        });
      }
      
      // 4. 加密存储 session_key
      const encryptedSessionKey = this.encryptionService.encrypt(
        wechatRes.session_key
      );
      await this.userService.updateSessionKey(
        user.id, 
        encryptedSessionKey,
        manager
      );
      
      // 5. 生成 JWT (双 Token 机制)
      const accessToken = await this.tokenService.generateAccessToken({
        userId: user.id,
        openId: user.openId,
        unionId: user.unionId,
      });
      const refreshToken = await this.tokenService.generateRefreshToken({
        userId: user.id,
      });
      
      return {
        accessToken,
        refreshToken,
        expiresIn: 604800,  // 7天
        tokenType: 'Bearer',
        user: this.sanitizeUser(user),
      };
    });
  }

  private sanitizeUser(user: User): SanitizedUser {
    return {
      openId: user.openId,
      unionId: user.unionId,
      avatarUrl: user.avatarUrl,
      nickName: user.nickName,
      createdAt: user.createdAt,
    };
  }
}
```

#### 4.2.3 WechatService — 微信 API 封装（含重试和熔断）

```typescript
// modules/wechat/wechat.service.ts
import { Injectable } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';
import { ConfigService } from '@nestjs/config';
import { RetryHelper } from '../../common/helpers/retry.helper';
import { CircuitBreaker } from '../../common/helpers/circuit-breaker.helper';

@Injectable()
export class WechatService {
  private readonly appId: string;
  private readonly appSecret: string;
  private readonly wechatApiBase = 'https://api.weixin.qq.com';
  private readonly circuitBreaker = new CircuitBreaker(5, 30000); // 5次失败后熔断30s

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
  ) {
    this.appId = this.configService.get<string>('WECHAT_APPID');
    this.appSecret = this.configService.get<string>('WECHAT_SECRET');
  }

  async code2Session(jsCode: string): Promise<WechatSessionResponse> {
    if (this.circuitBreaker.isOpen()) {
      throw new CircuitBreakerOpenException('微信接口熔断中');
    }

    return await RetryHelper.retry(
      async () => {
        const url = `${this.wechatApiBase}/sns/jscode2session`;
        const response = await firstValueFrom(
          this.httpService.get(url, {
            params: {
              appid: this.appId,
              secret: this.appSecret,
              js_code: jsCode,
              grant_type: 'authorization_code',
            },
            timeout: 5000,  // ⏱ 5秒超时
          })
        );

        const data = response.data;

        // 非空校验
        if (!data.openid || !data.session_key) {
          throw new WechatApiException('微信返回缺少必要字段');
        }

        // 错误码校验
        if (data.errcode && data.errcode !== 0) {
          throw new WechatErrorException(
            data.errcode,
            data.errmsg || '未知微信错误'
          );
        }

        this.circuitBreaker.recordSuccess();
        return data;
      },
      {
        maxRetries: 2,
        baseDelay: 500,      // 500ms
        maxDelay: 2000,      // 2s
        factor: 2,           // 指数退避: 500ms -> 1s -> 2s
        retryableErrors: ['ECONNRESET', 'ETIMEDOUT', 'ECONNREFUSED'],
      }
    ).catch((err) => {
      if (err instanceof WechatErrorException) {
        this.circuitBreaker.recordFailure();
      }
      throw err;
    });
  }
}
```

#### 4.2.4 TokenService — JWT 双 Token 机制

```typescript
// modules/token/token.service.ts
import { Injectable } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { RedisService } from '../redis/redis.service';
import { v4 as uuidv4 } from 'uuid';

@Injectable()
export class TokenService {
  private readonly accessTokenExpiry = '7d';
  private readonly refreshTokenExpiry = '30d';

  constructor(
    private readonly jwtService: JwtService,
    private readonly redisService: RedisService,
  ) {}

  async generateAccessToken(payload: AccessTokenPayload): Promise<string> {
    const jti = uuidv4();
    return this.jwtService.signAsync(
      {
        sub: payload.userId,
        openId: payload.openId,
        unionId: payload.unionId,
        type: 'access',
        jti,
      },
      { expiresIn: this.accessTokenExpiry }
    );
  }

  async generateRefreshToken(payload: RefreshTokenPayload): Promise<string> {
    const jti = uuidv4();
    const token = await this.jwtService.signAsync(
      {
        sub: payload.userId,
        type: 'refresh',
        jti,
      },
      { expiresIn: this.refreshTokenExpiry }
    );
    
    // 存储 refresh_token jti 到 Redis (用于校验和吊销)
    await this.redisService.set(
      `refresh:${jti}`,
      payload.userId,
      30 * 24 * 60 * 60  // 30天
    );
    
    return token;
  }

  async validateAccessToken(token: string): Promise<AccessTokenPayload> {
    try {
      const payload = await this.jwtService.verifyAsync(token);
      
      // 检查是否在黑名单中（登出操作）
      const isBlacklisted = await this.redisService.get(`blacklist:${payload.jti}`);
      if (isBlacklisted) {
        throw new TokenBlacklistedException();
      }
      
      return payload;
    } catch (err) {
      if (err instanceof TokenBlacklistedException) throw err;
      throw new TokenInvalidException('Token 无效或已过期');
    }
  }

  async revokeToken(jti: string, expiry: number): Promise<void> {
    // 将 jti 加入黑名单，TTL 设为 Token 剩余有效期
    await this.redisService.set(`blacklist:${jti}`, '1', expiry);
  }
}
```

#### 4.2.5 速率限制实现

```typescript
// modules/security/rate-limiter.service.ts
import { Injectable } from '@nestjs/common';
import { RedisService } from '../redis/redis.service';

@Injectable()
export class RateLimiterService {
  constructor(private readonly redisService: RedisService) {}

  async checkLimit(
    key: string,
    maxRequests: number,
    windowSeconds: number
  ): Promise<{ allowed: boolean; remaining: number; resetAt: number }> {
    const now = Math.floor(Date.now() / 1000);
    const windowKey = `rate_limit:${key}:${Math.floor(now / windowSeconds)}`;
    
    const current = await this.redisService.incr(windowKey);
    
    if (current === 1) {
      // 首次访问，设置过期时间
      await this.redisService.expire(windowKey, windowSeconds);
    }
    
    const ttl = await this.redisService.ttl(windowKey);
    
    return {
      allowed: current <= maxRequests,
      remaining: Math.max(0, maxRequests - current),
      resetAt: now + ttl,
    };
  }
}
```

### 4.3 数据库设计

#### 4.3.1 用户表 (Users)

```sql
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    open_id         VARCHAR(64) NOT NULL UNIQUE,
    union_id        VARCHAR(64),             -- 可选，开放平台绑定后才有
    encrypted_session_key TEXT,              -- AES-256-GCM 加密存储
    session_key_iv  VARCHAR(64),             -- 加密 IV
    avatar_url      VARCHAR(512),
    nick_name       VARCHAR(64),
    mobile          VARCHAR(20),             -- 脱敏存储
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          SMALLINT NOT NULL DEFAULT 1  -- 1=正常, 0=禁用
);

CREATE INDEX idx_users_open_id ON users(open_id);
CREATE INDEX idx_users_union_id ON users(union_id) WHERE union_id IS NOT NULL;
```

#### 4.3.2 登录日志表 (Login Audits)

```sql
CREATE TABLE login_audits (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT REFERENCES users(id),
    open_id         VARCHAR(64),
    code_hash       VARCHAR(128),           -- code 的 SHA-256 哈希（幂等性校验）
    ip_address      INET,
    user_agent      VARCHAR(512),
    device_info     JSONB,
    login_type      VARCHAR(32),            -- 'wechat_code', 'refresh_token'
    result          VARCHAR(32),            -- 'success', 'failed'
    fail_reason     VARCHAR(256),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_login_audits_user_id ON login_audits(user_id);
CREATE INDEX idx_login_audits_created_at ON login_audits(created_at);
CREATE UNIQUE INDEX idx_login_audits_code_hash ON login_audits(code_hash) 
    WHERE code_hash IS NOT NULL;  -- 确保 code 只能被使用一次
```

### 4.4 安全实现要点

#### 4.4.1 session_key 加密存储

```typescript
// modules/security/encryption.service.ts
import { Injectable } from '@nestjs/common';
import * as crypto from 'crypto';

@Injectable()
export class EncryptionService {
  private readonly algorithm = 'aes-256-gcm';
  private readonly key: Buffer;  // 从环境变量或 KMS 获取

  constructor() {
    // 256-bit key, 从环境变量读取 hex 字符串
    const hexKey = process.env.SESSION_KEY_ENCRYPT_KEY;
    if (!hexKey || hexKey.length !== 64) {
      throw new Error('SESSION_KEY_ENCRYPT_KEY must be a 32-byte hex string');
    }
    this.key = Buffer.from(hexKey, 'hex');
  }

  encrypt(plaintext: string): { ciphertext: string; iv: string; tag: string } {
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv(this.algorithm, this.key, iv);
    
    let encrypted = cipher.update(plaintext, 'utf8', 'hex');
    encrypted += cipher.final('hex');
    const tag = cipher.getAuthTag().toString('hex');
    
    return {
      ciphertext: encrypted,
      iv: iv.toString('hex'),
      tag,
    };
  }

  decrypt(ciphertext: string, ivHex: string, tagHex: string): string {
    const decipher = crypto.createDecipheriv(
      this.algorithm,
      this.key,
      Buffer.from(ivHex, 'hex')
    );
    decipher.setAuthTag(Buffer.from(tagHex, 'hex'));
    
    let decrypted = decipher.update(ciphertext, 'hex', 'utf8');
    decrypted += decipher.final('utf8');
    return decrypted;
  }
}
```

#### 4.4.2 Code 幂等性校验

```typescript
// 在 code2Session 之前，先检查 code 是否已被使用
async checkCodeReuse(code: string): Promise<void> {
  const codeHash = crypto.createHash('sha256').update(code).digest('hex');
  
  const exists = await this.userRepository.findOne({
    where: { codeHash },
    select: ['id'],
  });
  
  if (exists) {
    throw new UnauthorizedException({
      code: 40102,
      message: '登录凭证已被使用',
      errorType: 'CODE_USED',
    });
  }
}
```

### 4.5 可观测性实现

#### 4.5.1 结构化日志（脱敏）

```typescript
// common/helpers/logger.helper.ts
export function sanitizeLogData(data: Record<string, any>): Record<string, any> {
  const sensitiveFields = ['session_key', 'secret', 'password', 'token'];
  const sanitized = { ...data };
  
  for (const field of sensitiveFields) {
    if (sanitized[field]) {
      sanitized[field] = '***REDACTED***';
    }
  }
  
  return sanitized;
}

// 在 AuthService 中使用
this.logger.log({
  event: 'wechat_login.success',
  userId: user.id,
  openId: user.openId,     // openId 可记录（非敏感）
  ip: params.ip,
  duration: Date.now() - startTime,
  // ⚠️ 不记录 code, session_key, secret
});
```

#### 4.5.2 监控指标 (Prometheus)

```
# 定义指标
wechat_login_total{status="success|failed"}      # 登录请求总数
wechat_login_duration_ms{quantile="0.5|0.95|0.99"} # 登录耗时分布
wechat_code2session_duration_ms                    # 微信接口调用耗时
wechat_code2session_errors_total{error_code="..."} # 微信接口错误计数
wechat_circuit_breaker_state{state="open|closed|half"} # 熔断器状态
```

### 4.6 部署架构

```
                        ┌─────────────────────┐
                        │   负载均衡器 (SLB)    │
                        │    SSL 终结 + 健康检查 │
                        └──────┬──────────────┘
                               │
               ┌───────────────┼───────────────┐
               │               │               │
        ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
        │  Nginx 节点1 │ │  Nginx 节点2 │ │  Nginx 节点3 │
        │  速率限制     │ │  速率限制     │ │  速率限制     │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
        ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
        │  后端实例1   │ │  后端实例2   │ │  后端实例3   │
        │  NestJS     │ │  NestJS     │ │  NestJS     │
        └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
               │               │               │
               └───────────────┼───────────────┘
                               │
                    ┌──────────▼──────────┐
                    │    Redis 集群        │
                    │  (会话/限流/黑名单)   │
                    └─────────────────────┘
                    
                    ┌──────────▼──────────┐
                    │    PostgreSQL 集群    │
                    │  (读写分离 + 主从)    │
                    └─────────────────────┘
```

### 4.7 边界条件与异常处理矩阵

| 场景 | 预期行为 | 错误码/提示 |
|------|----------|-------------|
| 用户拒绝授权弹窗 | 停留在登录页，不做任何请求 | 前端: "需要授权才能登录" |
| code 被重复使用 | 后端返回 40102 | `CODE_USED`，前端重新调用 `wx.login()` |
| 微信接口返回 -1 (系统繁忙) | 重试 2 次（指数退避），仍失败则返回 502 | `WECHAT_API_ERROR` |
| 微信接口返回 40029 (code 无效) | 不重试，直接返回 40101 | `TOKEN_EXPIRED` |
| 微信接口返回 45011 (频率限制) | 不重试，返回 429 | 前端: "登录人数过多，请稍后再试" |
| access_token 过期 | 前端自动用 refresh_token 刷新 | 静默处理，用户无感知 |
| refresh_token 过期 | 前端清除所有 Token，跳转登录页 | 用户需重新登录 |
| 并发重复登录（同一用户两次点击） | 后一次请求覆盖前一次 Token，旧 Token 加入黑名单 | 无冲突，正常处理 |
| 数据库连接失败 | 返回 50010，前端提示"服务维护中" | 日志告警 |
| 恶意高频调用登录接口 | 速率限制，返回 429 | 60s 后自动恢复 |

---

### 附录：环境变量配置模板

```bash
# .env 文件

# 微信小程序配置
WECHAT_APPID=wx_xxxxxxxxxxxxxxxx
WECHAT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 服务器配置
NODE_ENV=production
PORT=3000

# 数据库配置
DB_HOST=postgres.internal
DB_PORT=5432
DB_USER=wechat_app
DB_PASSWORD=strong_password
DB_NAME=wechat_login

# Redis 配置
REDIS_HOST=redis.internal
REDIS_PORT=6379
REDIS_PASSWORD=strong_redis_password

# JWT 配置
JWT_SECRET=your-256-bit-jwt-secret-in-base64
JWT_ACCESS_EXPIRY=7d
JWT_REFRESH_EXPIRY=30d

# session_key 加密密钥 (32字节 hex)
SESSION_KEY_ENCRYPT_KEY=aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899

# 日志级别
LOG_LEVEL=info
```

---

本设计方案覆盖了需求文档中全部 6 项功能需求（FR-1~FR-6）和 5 项非功能需求（NFR-1~NFR-5），并针对每个验收条件（AC-1~AC-5）提供了实现级别的保障措施。代码示例均包含完整的错误处理、输入校验和安全防护，可直接作为开发团队的实现参考。