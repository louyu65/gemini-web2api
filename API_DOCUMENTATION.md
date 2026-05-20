# Gemini API Wrapper - 接口文档

## 概述

基于 [Gemini-API](tests/Gemini-API-master) 的 FastAPI 封装，提供 **OpenAI 兼容**的 REST API。

**Base URL:** `http://localhost:8000/v1`

**特点：**
- 完全兼容 OpenAI API 格式
- 无需 OpenAI API Key，使用 Google Cookie 认证
- 支持 SSE 流式输出
- 支持对话、生图、识图

---

## 目录

1. [认证](#认证)
2. [模型列表](#模型列表)
3. [对话补全](#对话补全)
4. [图像生成](#图像生成)
5. [图像下载代理](#图像下载代理)
6. [健康检查](#健康检查)
7. [Cookie 刷新](#cookie-刷新)
8. [错误码](#错误码)
9. [第三方客户端对接](#第三方客户端对接)

---

## 认证

本服务使用 Google Cookie 进行认证，不需要 API Key。

### 获取 Cookie

1. 浏览器访问 [gemini.google.com](https://gemini.google.com) 并登录
2. 按 `F12` → `Application/应用` → `Cookies` → `https://gemini.google.com`
3. 复制以下字段：
   - `__Secure-1PSID`
   - `__Secure-1PSIDTS`
4. 填入 `tests/cookie.json`

```json
{
  "__Secure-1PSID": "g.a000xxxx...",
  "__Secure-1PSIDTS": "sidts-CjcBxxxx..."
}
```

### Cookie 缓存问题

如果确认 Cookie 有效但仍提示 `UNAUTHENTICATED`，请清除缓存：

```bash
# Windows
rmdir /s /q gemini_cookies && mkdir gemini_cookies

# Linux/Mac
rm -rf gemini_cookies && mkdir gemini_cookies
```

---

## 模型列表

### 获取可用模型

**Endpoint:** `GET /v1/models`

**请求示例：**
```bash
curl http://localhost:8000/v1/models
```

**响应示例：**
```json
{
  "object": "list",
  "data": [
    {
      "id": "gemini",
      "object": "model",
      "created": 0,
      "owned_by": "google"
    },
    {
      "id": "gemini-vision",
      "object": "model",
      "created": 0,
      "owned_by": "google"
    }
  ]
}
```

| 模型 | 说明 |
|------|------|
| `gemini` | 默认对话模型 |
| `gemini-vision` | 支持图片识别的多模态模型 |

---

## 对话补全

### 非流式对话

**Endpoint:** `POST /v1/chat/completions`

**请求头：**
```
Content-Type: application/json
```

**请求体：**
```json
{
  "model": "gemini",
  "messages": [
    {"role": "user", "content": "你好，请介绍一下自己"}
  ],
  "stream": false
}
```

**参数说明：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `model` | string | 是 | - | 模型 ID，`gemini` 或 `gemini-vision` |
| `messages` | array | 是 | - | 消息列表 |
| `messages[].role` | string | 是 | - | `system`/`user`/`assistant` |
| `messages[].content` | string/array | 是 | - | 文本内容或图片数组 |
| `stream` | boolean | 否 | false | 是否使用 SSE 流式输出 |
| `temperature` | float | 否 | null | 温度参数（当前忽略） |
| `max_tokens` | integer | 否 | null | 最大 token 数（当前忽略） |

**响应示例：**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1716123456,
  "model": "gemini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！我是 Gemini，由 Google 开发的多模态 AI 助手..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

### 流式对话（SSE）

**请求体：**
```json
{
  "model": "gemini",
  "messages": [{"role": "user", "content": "讲个故事"}],
  "stream": true
}
```

**响应格式：**
```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1716123456,"model":"gemini","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1716123456,"model":"gemini","choices":[{"index":0,"delta":{"content":"从前"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1716123456,"model":"gemini","choices":[{"index":0,"delta":{"content":"有座山"},"finish_reason":null}]}

data: [DONE]
```

### 识图（Vision）

支持三种方式传图：`base64` 内联、`file://` 本地路径、`http://` 远程 URL。

**请求体：**
```json
{
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
}
```

**content 数组格式：**

| 类型 | 格式 | 示例 |
|------|------|------|
| text | `{"type": "text", "text": "描述图片"}` | 文字提示 |
| base64 | `{"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}` | base64 编码图片 |
| 本地文件 | `{"type": "image_url", "image_url": {"url": "file:///C:/Users/xxx/cat.png"}}` | 绝对路径 |
| 远程 URL | `{"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}}` | HTTP 图片地址 |

---

## 图像生成

**Endpoint:** `POST /v1/images/generations`

### 默认返回 base64（推荐）

**请求体：**
```json
{
  "model": "gemini",
  "prompt": "一只穿着宇航服的猫在月球上",
  "n": 1
}
```

**响应示例：**
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

### 返回本地 URL

**请求体：**
```json
{
  "model": "gemini",
  "prompt": "一只穿着宇航服的猫在月球上",
  "n": 1,
  "response_format": "url"
}
```

**响应示例：**
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

**参数说明：**

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `model` | string | 是 | - | 固定为 `gemini` |
| `prompt` | string | 是 | - | 图片描述文本 |
| `n` | integer | 否 | 1 | 生成数量（当前忽略，由 Gemini 决定） |
| `size` | string | 否 | `1024x1024` | 图片尺寸（当前忽略） |
| `response_format` | string | 否 | `b64_json` | `b64_json` 或 `url` |

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `created` | integer | 时间戳 |
| `data` | array | 图片列表 |
| `data[].b64_json` | string | base64 编码的图片数据（`response_format=b64_json` 时） |
| `data[].url` | string | 本地图片 URL（`response_format=url` 时） |
| `data[].revised_prompt` | string | 实际使用的 prompt 或错误提示 |

> **注意：** 如果 `b64_json` 和 `url` 都为 null，且 `revised_prompt` 包含 "signed in" 等字样，说明 Cookie 过期，需要重新导出。

---

## 图像下载代理

**Endpoint:** `POST /v1/images/download`

用于下载需要 Google Cookie 认证的图片 URL（如 `lh3.googleusercontent.com`）。

**请求体：**
```json
{
  "url": "https://lh3.googleusercontent.com/xxxx"
}
```

**响应：**
- 成功：`200 OK`，返回图片二进制流，附带 `Content-Type`
- 失败：`502 Bad Gateway` 或 `503 Service Unavailable`

**curl 示例：**
```bash
curl http://localhost:8000/v1/images/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://lh3.googleusercontent.com/xxxx"}' \
  --output image.png
```

---

## 健康检查

**Endpoint:** `GET /health`

**响应示例：**
```json
{
  "status": "ok",
  "account_status": "AVAILABLE (1000)",
  "note": "UNAUTHENTICATED means cookies expired; image generation and advanced features will be unavailable."
}
```

| status | account_status | 说明 |
|--------|----------------|------|
| `ok` | `AVAILABLE (1000)` | 正常，所有功能可用 |
| `degraded` | `UNAUTHENTICATED (1016)` | Cookie 过期，仅基础对话可用 |

---

## Cookie 刷新

### 运行时刷新 Cookie（无需重启）

**Endpoint:** `POST /v1/admin/refresh-cookie`

用于在不重启服务的情况下更新 Cookie，新 Cookie 会自动持久化到本地文件。

**请求体：**
```json
{
  "cookies": {
    "__Secure-1PSID": "g.a000xxxx...",
    "__Secure-1PSIDTS": "sidts-CjcBxxxx..."
  }
}
```

**响应示例（成功）：**
```json
{
  "success": true,
  "account_status": "AVAILABLE (1000)",
  "description": "Account is authorized and has normal access.",
  "message": "Cookie refreshed and persisted successfully."
}
```

**响应示例（失败）：**
```json
{
  "error": {
    "message": "Failed to refresh cookie: ...",
    "type": "upstream_error",
    "code": "bad_gateway"
  }
}
```

**curl 示例：**
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

> **注意**：调用此接口后会重建 `GeminiClient` 并自动清除旧连接。无需手动重启服务或清除缓存。

---

## 错误码

### HTTP 状态码

| 状态码 | 场景 | 响应格式 |
|--------|------|----------|
| `200` | 请求成功 | OpenAI 标准格式 |
| `502` | Gemini 上游错误 | `{"error": {"message": "...", "type": "upstream_error", "code": "bad_gateway"}}` |
| `503` | 服务未初始化 | `{"error": "Gemini client not initialized"}` |

### 常见业务错误

| 现象 | 原因 | 解决 |
|------|------|------|
| `revised_prompt`: "You might be signed out" | Cookie 过期 | 重新导出 Cookie，清除 `gemini_cookies/` 缓存 |
| `revised_prompt`: "image creation isn't available" | 地区/账号限制 | 确认浏览器端可正常生图 |
| Vision 返回 502 | 文件上传失败（Windows curl-cffi 不稳定） | 使用 Docker 部署，或换用 base64 传图 |
| `TLS connect error` | curl-cffi 版本不兼容 | `pip install -U "curl-cffi~=0.15.0"` |

---

## 第三方客户端对接

由于接口格式与 OpenAI 完全兼容，可直接填入支持自定义 Base URL 的客户端。

### Python (openai SDK)

```python
from openai import OpenAI

client = OpenAI(api_key="dummy", base_url="http://localhost:8000/v1")

# 对话
resp = client.chat.completions.create(
    model="gemini",
    messages=[{"role": "user", "content": "你好"}]
)
print(resp.choices[0].message.content)

# 生图
images = client.images.generate(
    model="gemini",
    prompt="一只猫",
    response_format="b64_json"
)
import base64
with open("cat.png", "wb") as f:
    f.write(base64.b64decode(images.data[0].b64_json))
```

### ChatGPT-Next-Web / LobeChat

- **API Key**: 任意填写（如 `dummy`）
- **Base URL**: `http://localhost:8000/v1`

---

## Docker 部署

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

**docker-compose.yml 关键配置：**
- 挂载 `./tests/cookie.json`：Cookie 文件
- 挂载 `./gemini_cookies/`：Cookie 缓存持久化
- 挂载 `./generated_images/`：生成的图片持久化

---

## 附录：完整请求示例

### 生图 + base64

```bash
curl -s http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini",
    "prompt": "A beautiful sunset over the ocean",
    "n": 1
  }' | python -m json.tool
```

### 生图 + URL

```bash
curl -s http://localhost:8000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini",
    "prompt": "A beautiful sunset over the ocean",
    "n": 1,
    "response_format": "url"
  }' | python -m json.tool
```

### 流式对话

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini",
    "messages": [{"role": "user", "content": "讲个故事"}],
    "stream": true
  }'
```

### 识图 base64

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-vision",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "描述这张图片"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgoAAAA..."}}
      ]
    }]
  }'
```
