# Gemini API Wrapper

基于 [Gemini-API](tests/Gemini-API-master) 的 FastAPI 封装，提供 **OpenAI 兼容**的 REST API，支持：

- 💬 对话（Chat Completions）
- 🖼️ 识图（Vision，支持 base64 / URL / 本地文件）
- 🎨 生图（Image Generations，依赖 Gemini 的图像生成能力）
- ⚡ 流式输出（SSE Streaming）
- 🔔 Cookie 健康监控与飞书告警

---

## 目录结构

```
.
├── api/
│   ├── __init__.py
│   ├── config.py          # 全局配置（路径、环境变量等）
│   ├── models.py          # OpenAI 兼容的请求/响应 Pydantic 模型
│   ├── utils.py           # 通用工具函数（ID 生成、图片下载/保存等）
│   ├── gemini_service.py  # GeminiClient 单例封装
│   ├── monitor.py         # Cookie 健康监控与飞书告警
│   └── main.py            # FastAPI 路由与业务逻辑
├── run.py                 # 启动入口
├── tests/
│   ├── cookie.json        # 你的 Google Cookie
│   └── Gemini-API-master/ # 原始逆向库源码
└── README.md              # 本文件
```

---

## 前置准备

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

`gemini_webapi` 无需 pip 安装，代码已通过 `sys.path` 指向本地 `tests/Gemini-API-master/src`。

### 2. 准备 Cookie

打开浏览器访问 [gemini.google.com](https://gemini.google.com) 并登录，按 `F12` → `Network` → 刷新页面 → 复制请求中的：
抓这个链接的cookie
`https://analytics.google.com/g/collect`
- `__Secure-1PSID`
- `__Secure-1PSIDTS`

填入 `tests/cookie.json`：

```json
{
  "__Secure-1PSID": "g.a000xxxx...",
  "__Secure-1PSIDTS": "sidts-CjcBxxxx..."
}
```

> ⚠️ 如果运行中出现 `UNAUTHENTICATED`，说明 Cookie 已过期，请重新导出。

---

## 启动服务

### 方式一：直接运行

```bash
python run.py
```

### 方式二：使用 uvicorn（推荐生产环境）

```bash
uvicorn run:app --host 0.0.0.0 --port 8000
```

### 方式三：Docker

```bash
docker-compose up -d
```

---

## API 使用示例

### 1. 普通对话

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini",
    "messages": [{"role": "user", "content": "你好，请介绍一下自己"}]
  }'
```

### 2. 流式对话

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini",
    "messages": [{"role": "user", "content": "讲个故事"}],
    "stream": true
  }'
```

### 3. 识图（Vision）

支持三种方式传图：

#### A. base64 内联

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-vision",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "描述这张图片"},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAA..."}}
        ]
      }
    ]
  }'
```

#### B. 本地文件路径

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-vision",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "描述这张图片"},
          {"type": "image_url", "image_url": {"url": "file:///C:/Users/xxx/Pictures/cat.png"}}
        ]
      }
    ]
  }'
```

#### C. HTTP URL

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-vision",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "描述这张图片"},
          {"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}}
        ]
      }
    ]
  }'
```

### 4. 生图

默认返回 **base64** 编码的图片（`b64_json`），客户端无需额外请求即可直接嵌入使用。你也可以通过 `response_format` 参数显式选择返回格式。

#### A. 默认返回 base64（推荐）

```bash
curl http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini",
    "prompt": "一只穿着宇航服的猫在月球上",
    "n": 1
  }'
```

返回示例：

```json
{
  "created": 1716123456,
  "data": [
    {
      "b64_json": "iVBORw0KGgoAAAANSUhEUgAAAAE...",
      "revised_prompt": "一只穿着宇航服的猫在月球上"
    }
  ]
}
```

#### B. 返回本地 URL

若希望获得可访问的图片链接，可指定 `response_format: url`。服务会自动将图片下载到本地并返回静态文件地址。

```bash
curl http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini",
    "prompt": "一只穿着宇航服的猫在月球上",
    "n": 1,
    "response_format": "url"
  }'
```

返回示例：

```json
{
  "created": 1716123456,
  "data": [
    {
      "url": "http://localhost:8000/images/a1b2c3d4.png",
      "revised_prompt": "一只穿着宇航服的猫在月球上"
    }
  ]
}
```

> 本地图片通过 `StaticFiles` 挂载在 `/images` 路径下，可直接浏览器访问。

### 5. 下载远程图片（代理接口）

如果你手头有一个 Google 图片地址（如 `https://lh3.googleusercontent.com/...`）且需要携带认证 Cookie 访问，可调用代理下载接口：

```bash
curl http://localhost:8000/v1/images/download \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://lh3.googleusercontent.com/xxxx"
  }' \
  --output generated_image.png
```

**说明：**

- `url`：需要代理下载的原始图片地址。
- 响应直接返回图片二进制流，并附带正确的 `Content-Type`。
- 若服务未初始化或上游访问失败，会返回 `503`/`502` 错误及 JSON 详情。

---

## 在第三方客户端中使用

由于接口格式与 OpenAI 兼容，你可以把 `http://localhost:8000` 填入任何支持自定义 API Base URL 的客户端：

- **ChatGPT-Next-Web / LobeChat**：API Key 随便填（目前未做鉴权），Base URL 填 `http://localhost:8000/v1`
- **Python openai SDK**：

```python
from openai import OpenAI

client = OpenAI(api_key="dummy", base_url="http://localhost:8000/v1")
resp = client.chat.completions.create(
    model="gemini",
    messages=[{"role": "user", "content": "你好"}]
)
print(resp.choices[0].message.content)
```

---

### 6. 运行时刷新 Cookie

无需重启服务即可更新 Cookie。支持两种输入方式：

#### A. JSON 字符串（推荐，从浏览器控制台直接复制）

```bash
curl http://localhost:8000/v1/admin/refresh-cookie \
  -H "Content-Type: application/json" \
  -d '{
    "cookies": "{\"__Secure-1PSID\": \"g.a000xxxx...\", \"__Secure-1PSIDTS\": \"sidts-CjcBxxxx...\"}"
  }'
```

#### B. JSON 对象

```bash
curl http://localhost:8000/v1/admin/refresh-cookie \
  -H "Content-Type: application/json" \
  -d '{
    "cookies": {
      "__Secure-1PSID": "g.a000xxxx...",
      "__Secure-1PSIDTS": "sidts-CjcBxxxx..."
    }
  }'
```

响应：
```json
{
  "success": true,
  "account_status": "AVAILABLE (1000)",
  "description": "Account is authorized and has normal access.",
  "message": "Cookie refreshed and persisted successfully."
}
```

> 调用后会自动重建 GeminiClient 并持久化到 `tests/cookie.json`，无需重启。

---

## 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `UNAUTHENTICATED` | Cookie 过期 | 重新从浏览器导出 `__Secure-1PSID` 和 `__Secure-1PSIDTS` |
| `TLS connect error` | `curl-cffi` 版本不兼容 | `pip install -U "curl-cffi~=0.15.0"` |
| 返回空内容 | Gemini 风控或模型未响应 | 检查 `cookie.json` 是否有效，或尝试更换模型 |
| 图片下载失败 | 本地 session Cookie 失效 | 先调用 `/v1/admin/refresh-cookie` 刷新 Cookie |

---

## 进阶配置

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `FEISHU_WEBHOOK` | 飞书机器人 Webhook URL，用于 Cookie 失效告警 | `""` |
| `COOKIE_CHECK_INTERVAL` | Cookie 健康检查间隔（秒） | `300` |
| `PORT` | 服务监听端口 | `8000` |

### 修改 Cookie 路径

编辑 [`api/config.py`](api/config.py) 中的 `DEFAULT_COOKIE_PATH`，或启动时指定：

```python
# api/config.py
DEFAULT_COOKIE_PATH = BASE_DIR / "tests" / "cookie.json"
```

### 添加代理

在 `GeminiClient` 初始化时传入 `proxy` 参数（位于 [`api/gemini_service.py`](api/gemini_service.py)）：

```python
self.client = GeminiClient(
    secure_1psid=psid,
    secure_1psidts=psidts,
    proxy="http://127.0.0.1:7890"
)
```

---

## 许可证

遵循原项目 [Gemini-API](tests/Gemini-API-master/LICENSE) 许可证。
