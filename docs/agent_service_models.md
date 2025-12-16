# Agent Service Model Support & Configuration

This document explains:

- Which model providers the Agent service supports (LLM / Embedding / Web Search).
- How to configure models via **tools_config.json** and via **Agent service requests** (REST and gRPC).
- Which **environment variables** are required by each provider.
- How to pass additional model/engine parameters to the service.

The information below is based on:

- `gui_agents/tools/`
- `gui_agents/core/mllm.py`, `gui_agents/core/engine.py`
- `gui_agents/grpc_app.py`, `gui_agents/restful_app.py`
- `gui_agents/proto/agent.proto`

---

## 1) Configuration layers (priority)

The Agent service resolves model configuration in this order:

1. **Per-request overrides** (REST `stage_model_config`, gRPC `runningConfig.stageModelConfig`) — highest priority.
2. **Repository tool config**: `gui_agents/tools/tools_config.json` (loaded by `load_config()`).
3. **Provider environment variables** (API keys, endpoints, etc.), loaded from:
   - `gui_agents/.env` if present, otherwise
   - `<repo_root>/.env` if present, otherwise process environment variables.

> Tip: If you want an English baseline config, copy `gui_agents/tools/tools_config_en.json` to `gui_agents/tools/tools_config.json`.

---

## 2) Supported providers

The service routes all tool calls through `gui_agents/core/mllm.py` (for LLM / embeddings / web search), which selects the concrete engine implementation from `gui_agents/core/engine.py` based on the tool config field:

- `provider` (aka `engine_type`)
- `model_name` / `model`

### 2.1 LLM providers (chat / multimodal)

Supported `provider` values (LLM):

- `openai`
- `anthropic`
- `gemini`
- `openrouter`
- `dashscope` (Qwen via DashScope compatible endpoint)
- `doubao` (Volcengine Ark)
- `deepseek`
- `zhipu`
- `groq`
- `siliconflow`
- `monica`
- `azure` (Azure OpenAI)
- `vllm` (local OpenAI-compatible endpoint)
- `huggingface` (TGI / OpenAI-compatible endpoint)
- `aws_bedrock` (AWS Bedrock)

### 2.2 Embedding providers

Supported `provider` values (Embedding):

- `openai`
- `gemini`
- `azure`
- `dashscope`
- `doubao`
- `jina`

### 2.3 Web search providers

Supported `provider` values (WebSearch):

- `exa`
- `bocha`

---

## 3) Required environment variables

Below is a consolidated list of the environment variables used by engines in `gui_agents/core/engine.py`.

### 3.1 LLM

| Provider (`provider`) | Required environment variables | Notes |
|---|---|---|
| `openai` | `OPENAI_API_KEY` | Optional custom base URL via tool config `base_url` / request `apiEndpoint`. |
| `anthropic` | `ANTHROPIC_API_KEY` | Uses Anthropic SDK (not OpenAI-compatible base_url). |
| `gemini` | `GEMINI_API_KEY`, `GEMINI_ENDPOINT_URL` | This implementation uses an OpenAI-compatible endpoint URL. |
| `openrouter` | `OPENROUTER_API_KEY`, `OPEN_ROUTER_ENDPOINT_URL` | OpenAI-compatible endpoint. |
| `dashscope` | `DASHSCOPE_API_KEY` | Default base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`. |
| `doubao` | `ARK_API_KEY` | Default base URL: `https://ark.cn-beijing.volces.com/api/v3`. |
| `deepseek` | `DEEPSEEK_API_KEY` | Default base URL: `https://api.deepseek.com`. |
| `zhipu` | `ZHIPU_API_KEY` | Uses ZhipuAI SDK. |
| `groq` | `GROQ_API_KEY` | Uses Groq SDK. |
| `siliconflow` | `SILICONFLOW_API_KEY` | Default base URL: `https://api.siliconflow.cn/v1`. |
| `monica` | `MONICA_API_KEY` | Default base URL: `https://openapi.monica.im/v1`. |
| `azure` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `OPENAI_API_VERSION` | Azure endpoint/version are required; see section 5. |
| `vllm` | `vLLM_ENDPOINT_URL` | OpenAI-compatible local endpoint URL (note the lowercase `v` in env var name). |
| `huggingface` | `HF_TOKEN` | Also requires a per-tool `base_url` (TGI endpoint) in tool config. |
| `aws_bedrock` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (and optionally `AWS_DEFAULT_REGION`) | Defaults region to `us-west-2` if not set. |

### 3.2 Embeddings

| Provider (`provider`) | Required environment variables |
|---|---|
| `openai` | `OPENAI_API_KEY` |
| `gemini` | `GEMINI_API_KEY` |
| `azure` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `OPENAI_API_VERSION` |
| `dashscope` | `DASHSCOPE_API_KEY` |
| `doubao` | `ARK_API_KEY` |
| `jina` | `JINA_API_KEY` |

### 3.3 Web search

| Provider (`provider`) | Required environment variables |
|---|---|
| `exa` | `EXA_API_KEY` |
| `bocha` | `BOCHA_API_KEY` |

### 3.4 Lybic backend (sandbox)

The service itself runs the UI agent inside a Lybic sandbox by default.

- `LYBIC_API_KEY`
- `LYBIC_ORG_ID`
- Optional: `LYBIC_API_ENDPOINT` (defaults to `https://api.lybic.cn/` in REST server)

---

## 4) Configuring models in service requests

### 4.1 REST: `stage_model_config` (FastAPI)

REST requests accept a `stage_model_config` object (see `gui_agents/restful_app.py`):

- `web_search_engine`: string (`"exa"` or `"bocha"`)
- For each stage/tool: an `LLMConfig` object:
  - `model_name`
  - `provider` (optional)
  - `api_key` (optional)
  - `api_endpoint` (optional)

API keys can be provided in two ways:

- **Environment variables** (recommended for single-tenant deployments)
- **Request parameters** (`stage_model_config.*.api_key`) — when present, the service injects it into the tool config as `api_key` and it takes precedence over environment variables

Stage fields (REST) map to tool names in `tools_config.json`:

- `context_fusion_model` → `context_fusion`
- `subtask_planner_model` → `subtask_planner`
- `traj_reflector_model` → `traj_reflector`
- `memory_retrival_model` → `memory_retrival`
- `grounding_model` → `grounding`
- `task_evaluator_model` → `evaluator`
- `action_generator_model` → `action_generator`
- `action_generator_with_takeover_model` → `action_generator_with_takeover`
- `fast_action_generator_model` → `fast_action_generator`
- `fast_action_generator_with_takeover_model` → `fast_action_generator_with_takeover`
- `dag_translator_model` → `dag_translator`
- `embedding_model` → `embedding`
- `query_formulator_model` → `query_formulator`
- `narrative_summarization_model` → `narrative_summarization`
- `text_span_model` → `text_span`
- `episode_summarization_model` → `episode_summarization`

In addition, if `action_generator_model` is provided, the service will use it as a **common default** for all LLM-based tools **except**: `websearch`, `embedding`, `grounding`.

### 4.2 gRPC: `runningConfig.stageModelConfig` (proto)

The gRPC proto defines:

- `RunAgentInstructionRequest.runningConfig.stageModelConfig` (`StageModelConfig`)
- `StageModelConfig.webSearchEngine` (string: `"exa"` or `"bocha"`)
- Stage model fields (LLMConfig):
  - `modelName`
  - `provider` (optional)
  - `apiKey` (optional)
  - `apiEndpoint` (optional)

Mapping is equivalent to REST (same tool names as `tools_config.json`).

API keys can be provided in two ways:

- **Environment variables**
- **Request parameters** (`runningConfig.stageModelConfig.*.apiKey`) — when present, the service injects it into the tool config as `api_key` and it takes precedence over environment variables

> Important: For gRPC, `provider` is `optional` in proto. If you omit it, the server will keep the tool’s existing provider from `tools_config.json`.

---

## 5) Passing additional model/engine parameters

The service request schema (REST / proto) only exposes these per-model override fields:

- model name
- provider
- api key
- api endpoint

For other parameters (Azure API version, Qwen thinking toggle, rate limit, etc.), you should configure them in `gui_agents/tools/tools_config.json` **inside each tool entry**.

All extra key/value fields under a tool entry are passed into the underlying engine as init kwargs (see `gui_agents/tools/tools.py`). Common examples:

- `api_version` (required for provider `azure`)
- `azure_endpoint` (required for provider `azure`)
- `rate_limit`
- `enable_thinking` (Qwen)
- `thinking` (Anthropic)

---

## 6) Examples

### 6.1 REST example: configure Gemini (LLM) + Doubao grounding + Gemini embedding

Request body example for `POST /run_agent` (or `POST /submit_task`):

```json
{
  "instruction": "Open the calculator and compute 123*456",
  "platform": "Windows",
  "mode": "fast",
  "max_steps": 50,
  "authentication": {
    "org_id": "${LYBIC_ORG_ID}",
    "api_key": "${LYBIC_API_KEY}",
    "api_endpoint": "https://api.lybic.cn/"
  },
  "stage_model_config": {
    "web_search_engine": "exa",
    "action_generator_model": {
      "provider": "gemini",
      "model_name": "gemini-2.5-pro"
    },
    "grounding_model": {
      "provider": "doubao",
      "model_name": "doubao-1-5-ui-tars-250428"
    },
    "embedding_model": {
      "provider": "gemini",
      "model_name": "text-embedding-004"
    }
  }
}
```

Environment variables needed for this example:

- `LYBIC_API_KEY`, `LYBIC_ORG_ID`
- `GEMINI_API_KEY`, `GEMINI_ENDPOINT_URL`
- `ARK_API_KEY` (for Doubao grounding)
- `EXA_API_KEY` (for Exa web search)

### 6.1a REST example: pass LLM API keys via request parameters

If you do not want to rely on server-side environment variables (e.g., multi-tenant usage), you can pass provider keys in the request:

```json
{
  "instruction": "Open the calculator and compute 123*456",
  "platform": "Windows",
  "mode": "fast",
  "max_steps": 50,
  "authentication": {
    "org_id": "${LYBIC_ORG_ID}",
    "api_key": "${LYBIC_API_KEY}",
    "api_endpoint": "https://api.lybic.cn/"
  },
  "stage_model_config": {
    "action_generator_model": {
      "provider": "gemini",
      "model_name": "gemini-2.5-pro",
      "api_key": "<YOUR_GEMINI_API_KEY>",
      "api_endpoint": "<YOUR_GEMINI_ENDPOINT_URL>"
    },
    "grounding_model": {
      "provider": "doubao",
      "model_name": "doubao-1-5-ui-tars-250428",
      "api_key": "<YOUR_ARK_API_KEY>"
    }
  }
}
```

In this case you do **not** need `GEMINI_API_KEY` / `ARK_API_KEY` in the server environment.

### 6.2 gRPC example: JSON-form of `RunAgentInstructionRequest`

```json
{
  "instruction": "Open the calculator and compute 123*456",
  "destroySandbox": false,
  "runningConfig": {
    "backend": "lybic",
    "mode": "FAST",
    "steps": 50,
    "authorizationInfo": {
      "orgID": "${LYBIC_ORG_ID}",
      "apiKey": "${LYBIC_API_KEY}",
      "apiEndpoint": "https://api.lybic.cn/"
    },
    "stageModelConfig": {
      "webSearchEngine": "exa",
      "actionGeneratorModel": {
        "provider": "gemini",
        "modelName": "gemini-2.5-pro"
      },
      "groundingModel": {
        "provider": "doubao",
        "modelName": "doubao-1-5-ui-tars-250428"
      },
      "embeddingModel": {
        "provider": "gemini",
        "modelName": "text-embedding-004"
      }
    }
  }
}
```

### 6.2a gRPC example: pass LLM API keys via request parameters

```json
{
  "instruction": "Open the calculator and compute 123*456",
  "runningConfig": {
    "backend": "lybic",
    "mode": "FAST",
    "steps": 50,
    "authorizationInfo": {
      "orgID": "${LYBIC_ORG_ID}",
      "apiKey": "${LYBIC_API_KEY}",
      "apiEndpoint": "https://api.lybic.cn/"
    },
    "stageModelConfig": {
      "actionGeneratorModel": {
        "provider": "gemini",
        "modelName": "gemini-2.5-pro",
        "apiKey": "<YOUR_GEMINI_API_KEY>",
        "apiEndpoint": "<YOUR_GEMINI_ENDPOINT_URL>"
      },
      "groundingModel": {
        "provider": "doubao",
        "modelName": "doubao-1-5-ui-tars-250428",
        "apiKey": "<YOUR_ARK_API_KEY>"
      }
    }
  }
}
```

In this case you do **not** need `GEMINI_API_KEY` / `ARK_API_KEY` in the server environment.

### 6.3 tools_config.json example: Azure OpenAI (LLM + embeddings)

Azure requires `api_version` and `azure_endpoint`. Because the service request does not expose these fields, configure them in `tools_config.json`:

```json
{
  "tool_name": "action_generator",
  "provider": "azure",
  "model_name": "gpt-4o",
  "api_version": "2024-10-21",
  "azure_endpoint": "https://<your-resource-name>.openai.azure.com",
  "rate_limit": 60
}
```

Environment variables:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `OPENAI_API_VERSION`

> Note: You can choose either env vars or tool config for endpoint/version, but they must be available at runtime.

### 6.4 tools_config.json example: local vLLM

```json
{
  "tool_name": "action_generator",
  "provider": "vllm",
  "model_name": "qwen2.5-vl",
  "base_url": "http://127.0.0.1:8000/v1"
}
```

Alternatively, set `vLLM_ENDPOINT_URL=http://127.0.0.1:8000/v1`.

---

## 7) Notes & troubleshooting

- If you see errors like `engine_type is not supported`, the `provider` string likely does not match the supported values listed in section 2.
- If you see missing key errors, confirm the provider’s environment variables in section 3 are set (and that `.env` is being loaded).
- For gRPC: global config mutation endpoints (`SetGlobalCommonConfig`, `SetGlobalCommonLLMConfig`, etc.) require `ALLOW_SET_GLOBAL_CONFIG=1`.
