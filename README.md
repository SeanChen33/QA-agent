## QA Agent（React 前端 + Python 后端）

一个简洁易用的问答（QA）Agent，前端使用 React，后端使用 Python，支持主流大模型服务对接，便于本地开发与生产部署。

> 说明：本 README 面向“React 作为前端，Python 作为后端”的通用 QA Agent 项目。若你的实现与本文的默认技术选型不同（例如 Flask 而非 FastAPI、Next.js 而非 Vite），请按你的实际代码轻微调整命令与目录。

---

### 特性

- **前后端分离**：React SPA 前端，Python RESTful/SSE 后端
- **多模型适配**：可接入 OpenAI/Anthropic/Google/本地 Ollama 等（按需配置）
- **可选 RAG**：支持检索增强（向量库/本地文件检索），便于企业内知识库接入
- **流式响应**：后端可选 SSE 流式输出，前端边生成边渲染
- **易部署**：本地一键启动，支持 Docker / Docker Compose

---

### 架构示意

- **Frontend（React）**：
  - UI、会话管理、消息渲染（支持流式）
  - 与后端交互：`/api/qa/ask`（JSON 或 SSE）

- **Backend（Python / FastAPI 推荐）**：
  - API 路由：`/api/health` 健康检查，`/api/qa/ask` 发起问答
  - LLM Provider 封装：OpenAI、Anthropic、Ollama、…
  - 可选检索：嵌入、向量库（FAISS/PGVector），文档加载、分块

---

### 目录结构（示例）

```
QA-agent/
├─ frontend/                     # React 前端（Vite 或 Next.js 均可）
│  ├─ src/
│  │  ├─ components/
│  │  ├─ pages/
│  │  ├─ hooks/
│  │  └─ api/
│  ├─ index.html
│  ├─ package.json
│  └─ .env.local                 # VITE_API_BASE_URL=...
│
└─ backend/                      # Python 后端（FastAPI 示例）
   ├─ main.py
   ├─ requirements.txt           # 或 pyproject.toml
   └─ .env                       # API KEY 等
```

---

### 快速开始

#### 1) 前置依赖

- Node.js 18+，pnpm/npm/yarn 其一
- Python 3.10+
- 可选：Docker / Docker Compose

#### 2) 后端启动（FastAPI 示例）

在 `backend/` 下：

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt

# 设置环境变量（或在 backend/.env 中配置）
export OPENAI_API_KEY=your_key_here
export PROVIDER=openai          # openai|anthropic|ollama|...
export MODEL=gpt-4o-mini        # 依实际可用模型而定
export PORT=8000

# 启动服务（自动重载）
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --reload
```

#### 3) 前端启动（Vite + React 示例）

在 `frontend/` 下：

```bash
npm install

# 若后端运行在 http://localhost:8000
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local

npm run dev
```

访问开发地址（一般为 `http://localhost:5173` 或控制台提示的端口）。

---

### 环境变量与配置

- `backend/.env`（示例）：

```
# 基础
PORT=8000

# LLM Provider 选择与凭证
PROVIDER=openai          # openai|anthropic|ollama|vertex|...
MODEL=gpt-4o-mini        # 目标模型名称
OPENAI_API_KEY=xxxx      # 若使用 OpenAI
ANTHROPIC_API_KEY=xxxx   # 若使用 Anthropic
GOOGLE_API_KEY=xxxx      # 若使用 Gemini/Vertex 需另配

# 可选 RAG
ENABLE_RAG=false
EMBEDDING_MODEL=text-embedding-3-small
VECTOR_STORE=faiss       # faiss|pgvector|...
```

- `frontend/.env.local`（示例）：

```
VITE_API_BASE_URL=http://localhost:8000
```

---

### API 说明

- `GET /api/health`
  - 返回服务健康状态

- `POST /api/qa/ask`
  - 发起问答请求（JSON 请求），也可支持 `text/event-stream` 流式响应（可选）

请求示例（JSON）：

```bash
curl -X POST "http://localhost:8000/api/qa/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "介绍一下 RAG 的基本思路",
    "context": "",                  
    "session_id": "demo-001",      
    "stream": false                 
  }'
```

响应示例：

```json
{
  "answer": "RAG（Retrieval-Augmented Generation）通过先检索相关文档，再结合生成模型…",
  "usage": { "prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168 },
  "session_id": "demo-001"
}
```

流式（SSE）示例（可选）：

```bash
curl -N -X POST "http://localhost:8000/api/qa/ask?stream=true" \
  -H "Content-Type: application/json" \
  -d '{"question": "什么是向量数据库？"}'
```

---

### 前端要点（示例做法）

- 使用 `fetch` 调用后端 REST API；若启用流式，则使用 `EventSource`/`ReadableStream` 渲染增量 token。
- 建议抽象 `useChat`/`useStream` hook，管理消息队列、loading 状态、错误展示与自动滚动。
- 统一在 `frontend/src/api/client.ts` 中读取 `VITE_API_BASE_URL`，避免硬编码。

---

### 后端要点（示例做法）

- FastAPI 路由拆分在 `app/routers/qa.py`；将模型调用封装在 `app/services/llm_provider.py`。
- 为每个 Provider 做统一接口（`generate`/`stream_generate`）。
- 若开启 RAG：在 `app/services/rag.py` 中实现文档加载、分块、嵌入、索引与检索。
- 开启 CORS 以允许前端本地开发访问：

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### 部署建议

#### Docker Compose（示例）

```yaml
version: "3.9"
services:
  backend:
    build: ./backend
    env_file:
      - ./backend/.env
    ports:
      - "8000:8000"
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  frontend:
    build: ./frontend
    environment:
      - VITE_API_BASE_URL=http://backend:8000
    ports:
      - "5173:5173"
    command: npm run dev -- --host 0.0.0.0
```

> 生产环境可使用 Nginx 反向代理与静态资源构建产物（`npm run build`），并在后端启用进程管理（如 `gunicorn`）。

---

### 开发与质量

- 代码风格：前端建议 ESLint + Prettier；后端使用 Ruff/Black。
- 类型：前端 TypeScript；后端使用 `pydantic` 定义请求/响应模型。
- 测试：前端 Vitest/Playwright；后端 Pytest。

---

### 常见问题（FAQ）

- 前端跨域请求被拦截？请确认后端已配置 CORS，且 `VITE_API_BASE_URL` 指向后端可访问地址。
- 模型报鉴权失败？请确认环境变量中的 API Key 与所选 Provider 一致，且账单/配额正常。
- 流式不生效？确认请求是否带上 `stream=true`，后端是否返回 `text/event-stream`，以及前端是否按流式读取。

---

### 许可证

本项目使用 MIT License。详见 `LICENSE`。

---

### 致谢

- FastAPI、Pydantic、Uvicorn
- React、Vite、TypeScript
- 各大模型与开源社区的贡献者
