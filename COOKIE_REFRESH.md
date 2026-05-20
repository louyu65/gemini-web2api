# Cookie 刷新与维护指南

## 一、Cookie 失效的表现

| 现象 | 可能原因 |
|------|---------|
| `/health` 返回 `UNAUTHENTICATED (1016)` | `__Secure-1PSIDTS` 过期或缓存中有旧 cookie |
| 生图返回 "You might be signed out" | 会话未认证 |
| CLI 报 `Authentication failed` | `__Secure-1PSID` 本身过期 |

---

## 二、自动刷新（推荐日常维护）

`gemini_webapi` 内置了 `__Secure-1PSIDTS` 的自动刷新机制。

### 2.1 刷新原理

- **触发条件**：`client.init(auto_refresh=True)`（服务默认已开启）
- **刷新间隔**：每 600 秒（10分钟）后台自动刷新一次
- **刷新对象**：`__Secure-1PSIDTS`（短效 token）
- **限制**：如果 `__Secure-1PSID`（长效 token）过期，自动刷新会失败

### 2.2 确保自动刷新生效

检查 `api/gemini_service.py` 中的初始化代码：

```python
await self.client.init(auto_refresh=True, verbose=False)
```

确保 `auto_refresh=True`。

### 2.3 查看刷新日志

启动服务时观察日志，如果看到类似以下内容，说明自动刷新在工作：

```
Saved cookies to cache successfully (5 cookies).
```

如果看到：

```
AuthError: Failed to refresh cookies.
```

说明 `__Secure-1PSID` 已过期，需要手动重新导出。

---

## 三、手动重新导出 Cookie（彻底解决方案）

当自动刷新失败时，必须从浏览器重新导出最新的 Cookie。

### 3.1 步骤

1. **浏览器访问** [gemini.google.com](https://gemini.google.com)
2. **确认网页端可正常使用 Gemini**（测试发个消息或生图）
3. **打开开发者工具**：`F12` → `Application/应用` → `Cookies`
4. **选择域名**：`https://gemini.google.com`
5. **复制以下字段的值**：
   - `__Secure-1PSID`
   - `__Secure-1PSIDTS`
6. **更新 `tests/cookie.json`**：

```json
{
  "__Secure-1PSID": "g.a000xxxx...",
  "__Secure-1PSIDTS": "sidts-CjcBxxxx..."
}
```

### 3.2 推荐工具

使用浏览器扩展导出更可靠：

- **Chrome/Edge**: [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkefkgcdmdfiggmhkfcej)
- **Firefox**: [Cookie-Editor](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/)

导出时选择 `JSON` 格式，直接复制到 `tests/cookie.json`。

---

## 四、清除缓存（关键步骤）

`gemini_webapi` 会缓存 cookie 到本地文件，即使更新了 `cookie.json`，库可能仍在使用缓存中的旧 cookie。

### 4.1 本地运行（不使用 Docker）

缓存目录通常在系统临时目录：

```bash
# Windows - 命令提示符
rmdir /s /q %TEMP%\gemini_webapi 2>nul

# Windows - PowerShell
Remove-Item -Recurse -Force $env:TEMP\gemini_webapi -ErrorAction SilentlyContinue

# Linux/Mac
rm -rf /tmp/gemini_webapi
```

### 4.2 Docker 运行

Docker 挂载了本地 `./gemini_cookies` 到容器的 `/tmp/gemini_webapi`：

```bash
# 在项目根目录执行
rmdir /s /q gemini_cookies 2>nul && mkdir gemini_cookies

# 然后重启容器
docker-compose restart
```

### 4.3 为什么要清除缓存？

`gemini_webapi` 的 `get_access_token()` 会优先从缓存加载 cookie（日志显示 `Init attempt (1) from Cache succeeded`）。如果缓存中有旧的过期 cookie，即使 `tests/cookie.json` 已更新，服务仍会使用旧缓存。

---

## 五、完整刷新流程（按顺序执行）

```bash
# Step 1: 停止服务
# (Ctrl+C 或 docker-compose down)

# Step 2: 清除缓存
rmdir /s /q gemini_cookies 2>nul && mkdir gemini_cookies
rmdir /s /q %TEMP%\gemini_webapi 2>nul

# Step 3: 更新 tests/cookie.json（从浏览器导出最新 cookie）

# Step 4: 重新启动服务
python run.py
# 或
docker-compose up -d

# Step 5: 检查健康状态
curl http://localhost:8000/health
# 期望返回: "account_status": "AVAILABLE (1000)"
```

---

## 六、诊断命令

### 6.1 检查账号状态

```bash
curl http://localhost:8000/health
```

### 6.2 CLI 深度诊断

```bash
cd tests/Gemini-API-master
python cli.py --cookies-json ../../tests/cookie.json inspect
```

输出示例（正常）：
```
Account status: AVAILABLE - Account is authorized and has normal access.
All probes passed.
```

输出示例（异常）：
```
Account status: UNAUTHENTICATED - Session is not authenticated...
Rejected: activity, model_state, quota, caps
```

### 6.3 测试生图

```bash
python tests/test_image_gen_only.py
```

---

## 七、常见问题

### Q: 为什么刚导出的 cookie 很快就失效？

A: 可能原因：
1. 浏览器中登出了 Google 账号
2. 使用了无痕/隐私模式的 cookie（会话级，关闭即失效）
3. Google 检测到异常活动，强制重置了会话
4. IP 地址/地区变化触发了安全验证

**建议**：使用主浏览器的 cookie，不要频繁切换 IP。

### Q: Cookie 刷新后还需要重启服务吗？

A: **不需要**。调用 `POST /v1/admin/refresh-cookie` 接口即可在运行时刷新 Cookie，服务会自动重建 `GeminiClient` 并持久化新 Cookie 到本地文件。

如果无法调用 API，仍然可以手动更新 `tests/cookie.json` 后重启服务。

### Q: 可以只刷新 `__Secure-1PSIDTS` 吗？

A: 如果 `__Secure-1PSID` 还有效，库的自动刷新会处理 `__Secure-1PSIDTS`。但如果 `__Secure-1PSID` 过期，必须重新导出两个值。

### Q: Docker 中如何自动刷新？

A: Docker Compose 已配置 `auto_refresh=True`，容器内每 10 分钟自动刷新一次。只要 `__Secure-1PSID` 有效，`__Secure-1PSIDTS` 会自动更新并持久化到 `./gemini_cookies/`。

---

## 八、飞书告警监控（可选）

服务内置了 Cookie 健康监控，当 Cookie 失效时会自动发送飞书机器人消息。

### 配置方式

#### 方式一：环境变量（推荐 Docker）

编辑 `docker-compose.yml`：

```yaml
environment:
  - FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
  - COOKIE_CHECK_INTERVAL=300  # 检查间隔，单位秒，默认 300
```

#### 方式二：直接运行

```bash
# Windows
set FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
set COOKIE_CHECK_INTERVAL=300
python run.py

# Linux/Mac
export FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
export COOKIE_CHECK_INTERVAL=300
python run.py
```

### 告警效果

当 `/health` 检测到 `UNAUTHENTICATED` 时，会推送如下卡片消息：

- **标题**: 🚨 Gemini Cookie 已失效
- **内容**: 账号状态 + 建议操作步骤

> 注意：监控采用状态变更触发机制，只在"从有效变为失效"时发送一次，避免重复刷屏。
