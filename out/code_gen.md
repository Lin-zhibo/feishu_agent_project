```diff
--- /dev/null
+++ b/miniprogram/app.js
@@ -0,0 +1,33 @@
+// app.js
+const auth = require('./utils/auth');
+const request = require('./utils/request');
+
+App({
+  onLaunch: function () {
+    // Check token validity on app launch
+    const token = auth.getToken();
+    if (token) {
+      request.get('/api/user/me')
+        .then(res => {
+          console.log('User already logged in:', res.data.id);
+          wx.switchTab({ url: '/pages/index/index' });
+        })
+        .catch(err => {
+          if (err.status === 401) {
+            auth.clearToken();
+            wx.redirectTo({ url: '/pages/login/login' });
+          }
+        });
+    } else {
+      wx.redirectTo({ url: '/pages/login/login' });
+    }
+  },
+  globalData: {
+    userInfo: null
+  }
+});
--- /dev/null
+++ b/miniprogram/utils/constants.js
@@ -0,0 +1,7 @@
+// constants.js
+const API_BASE_URL = 'https://yourdomain.com/api'; // Replace with actual domain
+const TOKEN_KEY = 'wechat_token';
+const ERROR_CODES = {
+  INVALID_CODE: 'invalid_code',
+  RATE_LIMITED: 'rate_limited',
+  SERVER_ERROR: 'server_error'
+};
+module.exports = { API_BASE_URL, TOKEN_KEY, ERROR_CODES };
--- /dev/null
+++ b/miniprogram/utils/auth.js
@@ -0,0 +1,18 @@
+// auth.js
+const { TOKEN_KEY } = require('./constants');
+
+function getToken() {
+  return wx.getStorageSync(TOKEN_KEY) || null;
+}
+
+function setToken(token) {
+  wx.setStorageSync(TOKEN_KEY, token);
+}
+
+function clearToken() {
+  wx.removeStorageSync(TOKEN_KEY);
+}
+
+module.exports = { getToken, setToken, clearToken };
--- /dev/null
+++ b/miniprogram/utils/request.js
@@ -0,0 +1,67 @@
+// request.js
+const { API_BASE_URL, ERROR_CODES } = require('./constants');
+const auth = require('./auth');
+
+const request = (url, options = {}) => {
+  return new Promise((resolve, reject) => {
+    const token = auth.getToken();
+    const header = {
+      'Content-Type': 'application/json',
+    };
+    if (token) {
+      header['Authorization'] = `Bearer ${token}`;
+    }
+
+    wx.request({
+      url: `${API_BASE_URL}${url}`,
+      method: options.method || 'GET',
+      data: options.data,
+      header,
+      success: (res) => {
+        if (res.statusCode >= 200 && res.statusCode < 300) {
+          resolve(res);
+        } else if (res.statusCode === 401) {
+          // Token expired or invalid – clear and redirect to login
+          auth.clearToken();
+          wx.showToast({ title: '登录已过期，请重新登录', icon: 'none' });
+          setTimeout(() => {
+            wx.redirectTo({ url: '/pages/login/login' });
+          }, 1500);
+          reject(res);
+        } else if (res.statusCode === 429) {
+          wx.showToast({ title: '请求过于频繁，请稍后重试', icon: 'none' });
+          reject(res);
+        } else {
+          // Other errors
+          const errorMsg = res.data && res.data.message ? res.data.message : '服务器错误';
+          wx.showToast({ title: errorMsg, icon: 'none' });
+          reject(res);
+        }
+      },
+      fail: (err) => {
+        wx.showToast({ title: '网络异常，请检查网络后重试', icon: 'none' });
+        reject(err);
+      }
+    });
+  });
+};
+
+// Convenience methods
+request.get = (url, data) => request(url, { method: 'GET', data });
+request.post = (url, data) => request(url, { method: 'POST', data });
+request.put = (url, data) => request(url, { method: 'PUT', data });
+request.delete = (url, data) => request(url, { method: 'DELETE', data });
+
+module.exports = request;
--- /dev/null
+++ b/miniprogram/pages/login/login.js
@@ -0,0 +1,61 @@
+// pages/login/login.js
+const request = require('../../utils/request');
+const auth = require('../../utils/auth');
+
+Page({
+  data: {
+    loading: false,
+    disabled: false
+  },
+
+  onLoad() {
+    // Check if already logged in
+    const token = auth.getToken();
+    if (token) {
+      wx.switchTab({ url: '/pages/index/index' });
+    }
+  },
+
+  handleLogin() {
+    if (this.data.disabled) return; // debounce
+    this.setData({ loading: true, disabled: true });
+
+    wx.showLoading({ title: '登录中…', mask: true });
+
+    // Step 1: Get code from WeChat
+    wx.login({
+      success: (res) => {
+        if (res.code) {
+          // Step 2: Send code to backend
+          this.exchangeCode(res.code);
+        } else {
+          wx.hideLoading();
+          wx.showToast({ title: '获取授权失败', icon: 'none' });
+          this.setData({ loading: false, disabled: false });
+        }
+      },
+      fail: () => {
+        wx.hideLoading();
+        wx.showToast({ title: '网络异常', icon: 'none' });
+        this.setData({ loading: false, disabled: false });
+      }
+    });
+  },
+
+  exchangeCode(code) {
+    request.post('/api/login', { code })
+      .then(res => {
+        const { token, user } = res.data;
+        auth.setToken(token);
+        wx.hideLoading();
+        wx.showToast({ title: '登录成功', icon: 'success' });
+        // Navigate to home page
+        wx.switchTab({ url: '/pages/index/index' });
+      })
+      .catch(err => {
+        wx.hideLoading();
+        const msg = err.data && err.data.message ? err.data.message : '登录失败，请重试';
+        wx.showToast({ title: msg, icon: 'none' });
+        this.setData({ loading: false, disabled: false });
+      });
+  }
+});
--- /dev/null
+++ b/miniprogram/pages/login/login.wxml
@@ -0,0 +1,11 @@
+<!-- pages/login/login.wxml -->
+<view class="login-container">
+  <image class="logo" src="/images/logo.png" mode="aspectFit"></image>
+  <text class="title">欢迎使用</text>
+  <text class="subtitle">请授权登录</text>
+  <button 
+    class="login-btn" 
+    type="primary" 
+    loading="{{loading}}" 
+    disabled="{{disabled}}" 
+    bindtap="handleLogin">微信登录</button>
+</view>
--- /dev/null
+++ b/miniprogram/pages/login/login.wxss
@@ -0,0 +1,42 @@
+/* pages/login/login.wxss */
+.login-container {
+  display: flex;
+  flex-direction: column;
+  align-items: center;
+  padding-top: 120rpx;
+  background-color: #f8f8f8;
+  min-height: 100vh;
+}
+
+.logo {
+  width: 200rpx;
+  height: 200rpx;
+  border-radius: 20rpx;
+  margin-bottom: 40rpx;
+}
+
+.title {
+  font-size: 40rpx;
+  font-weight: bold;
+  color: #333;
+  margin-bottom: 10rpx;
+}
+
+.subtitle {
+  font-size: 28rpx;
+  color: #999;
+  margin-bottom: 80rpx;
+}
+
+.login-btn {
+  width: 70%;
+  height: 90rpx;
+  line-height: 90rpx;
+  border-radius: 45rpx;
+  font-size: 32rpx;
+  background-color: #07c160;
+}
+
+.login-btn[disabled] {
+  background-color: #a0d8b0;
+}
--- /dev/null
+++ b/miniprogram/pages/index/index.js
@@ -0,0 +1,28 @@
+// pages/index/index.js
+const auth = require('../../utils/auth');
+const request = require('../../utils/request');
+
+Page({
+  data: {
+    user: null
+  },
+
+  onLoad() {
+    const token = auth.getToken();
+    if (!token) {
+      wx.redirectTo({ url: '/pages/login/login' });
+      return;
+    }
+    request.get('/api/user/me')
+      .then(res => {
+        this.setData({ user: res.data });
+      })
+      .catch(err => {
+        if (err.status === 401) {
+          auth.clearToken();
+          wx.redirectTo({ url: '/pages/login/login' });
+        }
+      });
+  }
+});
--- /dev/null
+++ b/miniprogram/pages/index/index.wxml
@@ -0,0 +1,13 @@
+<!-- pages/index/index.wxml -->
+<view class="container">
+  <view class="user-card" wx:if="{{user}}">
+    <image class="avatar" src="{{user.avatar_url || '/images/default-avatar.png'}}"></image>
+    <text class="nickname">{{user.nickname || '未设置昵称'}}</text>
+    <text class="login-time">上次登录: {{user.last_login}}</text>
+  </view>
+  <view wx:else>
+    <text>加载中...</text>
+  </view>
+  <button class="logout-btn" bindtap="handleLogout">退出登录</button>
+</view>
+<!-- For brevity, handleLogout logic omitted; would call POST /api/logout -->
--- /dev/null
+++ b/miniprogram/app.json
@@ -0,0 +1,20 @@
+{
+  "pages": [
+    "pages/index/index",
+    "pages/login/login"
+  ],
+  "window": {
+    "navigationBarTitleText": "Demo",
+    "navigationBarBackgroundColor": "#ffffff",
+    "navigationBarTextStyle": "black"
+  },
+  "style": "v2",
+  "sitemapLocation": "sitemap.json",
+  "tabBar": {
+    "list": [{
+      "pagePath": "pages/index/index",
+      "text": "首页"
+    }]
+  }
+}
--- /dev/null
+++ b/backend/package.json
@@ -0,0 +1,16 @@
+{
+  "name": "wechat-miniprogram-backend",
+  "version": "1.0.0",
+  "description": "Backend for WeChat Mini-Program login integration",
+  "main": "src/app.js",
+  "scripts": {
+    "start": "node src/app.js",
+    "dev": "nodemon src/app.js"
+  },
+  "dependencies": {
+    "axios": "^1.6.7",
+    "express": "^4.18.2",
+    "jsonwebtoken": "^9.0.2",
+    "mongoose": "^8.1.1",
+    "winston": "^3.11.0",
+    "express-rate-limit": "^7.1.5",
+    "dotenv": "^16.3.1"
+  },
+  "devDependencies": {
+    "nodemon": "^3.0.2"
+  }
+}
--- /dev/null
+++ b/backend/.env.example
@@ -0,0 +1,8 @@
+WECHAT_APP_ID=your_appid_here
+WECHAT_APP_SECRET=your_appsecret_here
+JWT_SECRET=your_random_jwt_secret_here
+JWT_EXPIRES_IN=7d
+MONGO_URI=mongodb://localhost:27017/wechat_miniprogram
+PORT=3000
+REDIS_URL=redis://localhost:6379 # optional
+ENCRYPTION_KEY=32_byte_random_key_for_session_key_encryption
--- /dev/null
+++ b/backend/src/app.js
@@ -0,0 +1,47 @@
+const express = require('express');
+const mongoose = require('mongoose');
+const dotenv = require('dotenv');
+const { logger } = require('./logger');
+const errorHandler = require('./middleware/errorHandler');
+const authRoutes = require('./routes/auth.routes');
+const userRoutes = require('./routes/user.routes');
+
+dotenv.config();
+
+const app = express();
+
+// Middleware
+app.use(express.json());
+app.use(require('./middleware/rateLimit'));
+app.use(require('./middleware/logger'));
+
+// Routes
+app.use('/api', authRoutes);
+app.use('/api', userRoutes);
+app.get('/api/health', (req, res) => res.json({ status: 'ok' }));
+
+// Global error handler
+app.use(errorHandler);
+
+// Database connection
+mongoose.connect(process.env.MONGO_URI)
+  .then(() => {
+    logger.info('Connected to MongoDB');
+  })
+  .catch(err => {
+    logger.error('MongoDB connection error', { error: err.message });
+    process.exit(1);
+  });
+
+const PORT = process.env.PORT || 3000;
+app.listen(PORT, () => {
+  logger.info(`Server running on port ${PORT}`);
+});
+
+module.exports = app;
--- /dev/null
+++ b/backend/src/config/index.js
@@ -0,0 +1,24 @@
+const dotenv = require('dotenv');
+dotenv.config();
+
+module.exports = {
+  wechat: {
+    appId: process.env.WECHAT_APP_ID,
+    appSecret: process.env.WECHAT_APP_SECRET,
+    jscode2sessionUrl: 'https://api.weixin.qq.com/sns/jscode2session'
+  },
+  jwt: {
+    secret: process.env.JWT_SECRET,
+    expiresIn: process.env.JWT_EXPIRES_IN || '7d'
+  },
+  db: {
+    uri: process.env.MONGO_URI
+  },
+  encryption: {
+    key: process.env.ENCRYPTION_KEY // 32 bytes for AES-256
+  },
+  rateLimit: {
+    windowMs: 60 * 1000, // 1 minute
+    max: 10 // 10 requests per window per IP
+  }
+};
--- /dev/null
+++ b/backend/src/logger/index.js
@@ -0,0 +1,24 @@
+const winston = require('winston');
+
+const logger = winston.createLogger({
+  level: 'info',
+  format: winston.format.json(),
+  defaultMeta: { service: 'wechat-backend' },
+  transports: [
+    new winston.transports.Console({
+      format: winston.format.combine(
+        winston.format.colorize(),
+        winston.format.simple()
+      )
+    }),
+    new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
+    new winston.transports.File({ filename: 'logs/combined.log' })
+  ]
+});
+
+// Middleware for logging requests
+const requestLogger = (req, res, next) => {
+  logger.info('Request', { method: req.method, url: req.url, ip: req.ip });
+  next();
+};
+module.exports = { logger, requestLogger };
--- /dev/null
+++ b/backend/src/middleware/logger.js
@@ -0,0 +1,7 @@
+const { requestLogger } = require('../logger');
+
+module.exports = (req, res, next) => {
+  // Structured logging with masked sensitive fields
+  const logData = { method: req.method, url: req.url, ip: req.ip, body: maskSensitive(req.body) };
+  // For brevity, we use a simple console as placeholder
+  next();
+};
+function maskSensitive(body) {
+  if (!body) return body;
+  const masked = { ...body };
+  if (masked.code) masked.code = masked.code.substring(0, 4) + '****';
+  return masked;
+}
--- /dev/null
+++ b/backend/src/middleware/auth.js
@@ -0,0 +1,22 @@
+const jwt = require('jsonwebtoken');
+const config = require('../config');
+const { tokenBlacklist } = require('../services/token.service');
+
+module.exports = (req, res, next) => {
+  const authHeader = req.headers.authorization;
+  if (!authHeader || !authHeader.startsWith('Bearer ')) {
+    return res.status(401).json({ error: 'unauthorized', message: '缺少认证令牌' });
+  }
+  const token = authHeader.split(' ')[1];
+
+  // Check blacklist (if any)
+  if (tokenBlacklist.has(token)) {
+    return res.status(401).json({ error: 'token_expired', message: '令牌已失效' });
+  }
+
+  jwt.verify(token, config.jwt.secret, (err, decoded) => {
+    if (err) return res.status(401).json({ error: 'invalid_token', message: '令牌无效或已过期' });
+    req.userId = decoded.sub;
+    next();
+  });
+};
--- /dev/null
+++ b/backend/src/middleware/rateLimit.js
@@ -0,0 +1,13 @@
+const rateLimit = require('express-rate-limit');
+const config = require('../config');
+
+const loginLimiter = rateLimit({
+  windowMs: config.rateLimit.windowMs,
+  max: config.rateLimit.max,
+  message: {
+    error: 'rate_limited',
+    message: '请求过于频繁，请稍后重试'
+  }
+});
+
+module.exports = loginLimiter;
--- /dev/null
+++ b/backend/src/middleware/errorHandler.js
@@ -0,0 +1,15 @@
+const { logger } = require('../logger');
+
+module.exports = (err, req, res, next) => {
+  logger.error('Unhandled error', { error: err.message, stack: err.stack });
+
+  const statusCode = err.statusCode || 500;
+  const errorCode = err.errorCode || 'server_error';
+  const message = err.message || '服务器内部错误';
+
+  res.status(statusCode).json({
+    error: errorCode,
+    message
+  });
+};
--- /dev/null
+++ b/backend/src/routes/auth.routes.js
@@ -0,0 +1,11 @@
+const express = require('express');
+const router = express.Router();
+const authController = require('../controllers/auth.controller');
+const authMiddleware = require('../middleware/auth');
+const loginLimiter = require('../middleware/rateLimit');
+
+router.post('/login', loginLimiter, authController.handleLogin);
+router.post('/logout', authMiddleware, authController.handleLogout);
+
+module.exports = router;
--- /dev/null
+++ b/backend/src/routes/user.routes.js
@@ -0,0 +1,9 @@
+const express = require('express');
+const router = express.Router();
+const userController = require('../controllers/user.controller');
+const authMiddleware = require('../middleware/auth');
+
+router.get('/user/me', authMiddleware, userController.getProfile);
+
+module.exports = router;
--- /dev/null
+++ b/backend/src/controllers/auth.controller.js
@@ ... @@
+const wechatService = require('../services/wechat.service');
+const tokenService = require('../services/token.service');
+const userService = require('../services/user.service');
+const { ValidationError } = require('../utils/errors');
+
+exports.handleLogin = async (req, res, next) => {
+  try {
+    const { code } = req.body;
+    if (!code) {
+      throw new ValidationError('缺少授权码', 'invalid_code');
+    }
+
+    // Call WeChat API to get openid and session_key
+    const wechatResult = await wechatService.code2Session(code);
+    const { openid, unionid, session_key } = wechatResult;
+
+    // Find or create user
+    const user = await userService.findOrCreate(openid, unionid, session_key);
+
+    // Generate JWT
+    const token = tokenService.generateToken(user.id);
+
+    res.json({
+      token,
+      user: {
+        id: user.id,
+        openid: user.openid,  // Typically should not expose; but for demo
+        unionid: user.unionid,
+        nickname: user.nickname,
+        avatar_url: user.avatar_url,
+        is_new_user: user.first_login === user.last_login // if first_login equals last_login, it's new
+      },
+      expires_in: tokenService.getExpiresInSeconds()
+    });
+  } catch (err) {
+    next(err);
+  }
+};
+
+exports.handleLogout = async (req, res, next) => {
+  try {
+    const token = req.headers.authorization.split(' ')[1];
+    tokenService.blacklistToken(token);
+    res.json({ message: 'logged_out' });
+  } catch (err) {
+    next(err);
+  }
+};
--- /dev/null
+++ b/backend/src/controllers/user.controller.js
@@ -0,0 +1,20 @@
+const userService = require('../services/user.service');
+
+exports.getProfile = async (req, res, next) => {
+  try {
+    const userId = req.userId;
+    const user = await userService.findById(userId);
+    if (!user) {
+      return res.status(404).json({ error: 'user_not_found', message: '用户不存在' });
+    }
+    res.json({
+      id: user.id,
+      openid: user.openid,  // Consider omitting for privacy
+      nickname: user.nickname,
+      avatar_url: user.avatar_url,
+      created_at: user.created_at,
+      last_login: user.last_login
+    });
+  } catch (err) {
+    next(err);
+  }
+};
--- /dev/null
+++ b/backend/src/services/wechat.service.js
@@ -0,0 +1,42 @@
+const axios = require('axios');
+const config = require('../config');
+const { ExternalServiceError, ValidationError } = require('../utils/errors');
+const { logger } = require('../logger');
+
+exports.code2Session = async (code) => {
+  try {
+    const response = await axios.get(config.wechat.jscode2sessionUrl, {
+      params: {
+        appid: config.wechat.appId,
+        secret: config.wechat.appSecret,
+        js_code: code,
+        grant_type: 'authorization_code'
+      },
+      timeout: 5000
+    });
+
+    const data = response.data;
+
+    // Check WeChat error
+    if (data.errcode && data.errcode !== 0) {
+      logger.error('WeChat API error', { errcode: data.errcode, errmsg: data.errmsg });
+      // Map common errors
+      if (data.errcode === 40029) {
+        throw new ValidationError('授权码无效或已过期', 'invalid_code');
+      } else if (data.errcode === 45011) {
+        throw new ValidationError('API 频率超限', 'rate_limited');
+      } else {
+        throw new ExternalServiceError('微信服务异常', 'wechat_error');
+      }
+    }
+
+    if (!data.openid) {
+      throw new ExternalServiceError('微信返回缺失 openid', 'wechat_error');
+    }
+
+    // Return openid, unionid (if any), session_key
+    return { openid: data.openid, unionid: data.unionid || null, session_key: data.session_key };
+  } catch (err) {
+    if (err.isCustom) throw err;
+    throw new ExternalServiceError('微信服务不可达', 'wechat_unreachable');
+  }
+};
--- /dev/null
+++ b/backend/src/services/token.service.js
@@ ... @@
+const jwt = require('jsonwebtoken');
+const config = require('../config');
+
+// Simple in-memory blacklist (for production use Redis)
+const tokenBlacklist = new Set();
+
+exports.generateToken = (userId) => {
+  return jwt.sign(
+    { sub: userId },
+    config.jwt.secret,
+    { expiresIn: config.jwt.expiresIn }
+  );
+};
+
+exports.verifyToken = (token) => {
+  return jwt.verify(token, config.jwt.secret);
+};
+
+exports.blacklistToken = (token) => {
+  tokenBlacklist.add(token);
+  // For production, set TTL based on remaining token expiry
+};
+
+exports.getExpiresInSeconds = () => {
+  // Parse expiresIn string to seconds
+  const match = config.jwt.expiresIn.match(/^(\d+)(d|h|m|s)?$/);
+  if (!match) return 604800; // default 7 days
+  const value = parseInt(match[1]);
+  const unit = match[2] || 'd';
+  const multipliers = { d: 86400, h: 3600, m: 60, s: 1 };
+  return value * (multipliers[unit] || 86400);
+};
+
+exports.tokenBlacklist = tokenBlacklist;
--- /dev/null
+++ b/backend/src/services/user.service.js
@@ -0,0 +1,49 @@
+const userRepository = require('../repositories/user.repository');
+const crypto = require('../utils/crypto');
+const { logger } = require('../logger');
+
+exports.findOrCreate = async (openid, unionid, sessionKey) => {
+  let user = await userRepository.findByOpenid(openid);
+  const now = new Date();
+
+  if (!user) {
+    // New user
+    const encryptedSessionKey = crypto.encrypt(sessionKey);
+    user = await userRepository.create({
+      openid,
+      unionid: unionid || undefined,
+      encrypted_session_key: encryptedSessionKey,
+      first_login: now,
+      last_login: now
+    });
+    logger.info('New user created', { openid: maskOpenid(openid) });
+  } else {
+    // Existing user: update login time and unionid if missing
+    const updateData = { last_login: now };
+    if (unionid && !user.unionid) {
+      updateData.unionid = unionid;
+    }
+    // Optionally re-encrypt session_key if needed
+    // For now we do not store updated session_key (WeChat session_key may change)
+    user = await userRepository.update(user.id, updateData);
+    logger.info('User login updated', { openid: maskOpenid(openid) });
+  }
+  return user;
+};
+
+exports.findById = async (id) => {
+  return userRepository.findById(id);
+};
+
+exports.updateProfile = async (id, profileData) => {
+  // For setting nickname, avatar after obtaining from WeChat userinfo (not covered here)
+  return userRepository.update(id, profileData);
+};
+
+function maskOpenid(openid) {
+  if (!openid) return 'unknown';
+  return openid.substring(0, 4) + '****';
+}
+
+// Export for repository
+exports.maskOpenid = maskOpenid;
--- /dev/null
+++ b/backend/src/repositories/user.repository.js
@@ -0,0 +1,42 @@
+const User = require('../models/user.model');
+
+exports.findByOpenid = async (openid) => {
+  try {
+    return await User.findOne({ openid });
+  } catch (err) {
+    throw err;
+  }
+};
+
+exports.findById = async (id) => {
+  try {
+    return await User.findById(id);
+  } catch (err) {
+    throw err;
+  }
+};
+
+exports.create = async (userData) => {
+  try {
+    const user = new User(userData);
+    return await user.save();
+  } catch (err) {
+    throw err;
+  }
+};
+
+exports.update = async (id, updateData) => {
+  try {
+    return await User.findByIdAndUpdate(id, updateData, { new: true });
+  } catch (err) {
+    throw err;
+  }
+};
+
+exports.delete = async (id) => {
+  try {
+    return await User.findByIdAndDelete(id);
+  } catch (err) {
+    throw err;
+  }
+};
--- /dev/null
+++ b/backend/src/models/user.model.js
@@ -0,0 +1,31 @@
+const mongoose = require('mongoose');
+
+const userSchema = new mongoose.Schema({
+  openid: {
+    type: String,
+    required: true,
+    unique: true,
+    index: true
+  },
+  unionid: {
+    type: String,
+    default: null
+  },
+  encrypted_session_key: {
+    type: Buffer,
+    default: null
+  },
+  nickname: String,
+  avatar_url: String,
+  first_login: { type: Date, default: Date.now },
+  last_login: { type: Date, default: Date.now },
+  created_at: { type: Date, default: Date.now },
+  updated_at: { type: Date, default: Date.now }
+});
+
+userSchema.pre('save', function(next) {
+  this.updated_at = Date.now();
+  next();
+});
+
+module.exports = mongoose.model('User', userSchema);
--- /dev/null
+++ b/backend/src/utils/crypto.js
@@ -0,0 +1,28 @@
+const crypto = require('crypto');
+const config = require('../config');
+
+const ALGORITHM = 'aes-256-cbc';
+const IV_LENGTH = 16;
+
+function encrypt(text) {
+  const key = Buffer.from(config.encryption.key, 'hex');
+  const iv = crypto.randomBytes(IV_LENGTH);
+  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
+  let encrypted = cipher.update(text, 'utf8', 'hex');
+  encrypted += cipher.final('hex');
+  return iv.toString('hex') + ':' + encrypted;
+}
+
+function decrypt(encryptedText) {
+  const key = Buffer.from(config.encryption.key, 'hex');
+  const parts = encryptedText.split(':');
+  const iv = Buffer.from(parts.shift(), 'hex');
+  const encrypted = parts.join(':');
+  const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
+  let decrypted = decipher.update(encrypted, 'hex', 'utf8');
+  decrypted += decipher.final('utf8');
+  return decrypted;
+}
+
+module.exports = { encrypt, decrypt };
--- /dev/null
+++ b/backend/src/utils/errors.js
@@ -0,0 +1,24 @@
+class CustomError extends Error {
+  constructor(message, errorCode, statusCode = 500) {
+    super(message);
+    this.name = this.constructor.name;
+    this.errorCode = errorCode;
+    this.statusCode = statusCode;
+    this.isCustom = true;
+  }
+}
+
+class ValidationError extends CustomError {
+  constructor(message, errorCode = 'validation_error', statusCode = 400) {
+    super(message, errorCode, statusCode);
+  }
+}
+
+class ExternalServiceError extends CustomError {
+  constructor(message, errorCode = 'external_error', statusCode = 502) {
+    super(message, errorCode, statusCode);
+  }
+}
+
+module.exports = { CustomError, ValidationError, ExternalServiceError };
--- /dev/null
+++ b/backend/Dockerfile
@@ -0,0 +1,15 @@
+FROM node:18-alpine
+WORKDIR /app
+COPY package*.json ./
+RUN npm install --production
+COPY . .
+EXPOSE 3000
+CMD ["node", "src/app.js"]
+```
+
+**Note:** 
+- The above diff assumes an empty repository and creates all files. It covers the core components: frontend login page, token management, HTTP request wrapper; backend Express server with JWT, WeChat code exchange, user management, encryption, rate limiting, error handling.
+- Omitted files for brevity include the `login.json`, `index.json`, full `index.wxss`, `index.js` logout logic, `sitemap.json`, `app.wxss`, and some utility functions (e.g., Redis integration). These can be added following the same pattern.
+- Environment variables must be set in a `.env` file (copy from `.env.example`).
- The MongoDB model uses Mongoose; adapt schema for PostgreSQL if needed.