# LLM Models

## 1. OpenAI

**支持的模型：**

- `gpt-4o` - 最新多模态模型
- `gpt-4o-mini` - 轻量版
- `gpt-4-turbo` - GPT-4 Turbo
- `gpt-4` - GPT-4 标准版
- `gpt-3.5-turbo` - GPT-3.5

## 2. Anthropic Claude

**支持的模型：**

- `claude-opus-4` - Claude Opus 4
- `claude-sonnet-4` - Claude Sonnet 4
- `claude-3-5-sonnet` - Claude 3.5 Sonnet
- `claude-3-5-haiku` - Claude 3.5 Haiku
- `claude-3-opus` - Claude 3 Opus
- `claude-3-sonnet` - Claude 3 Sonnet
- `claude-3-haiku` - Claude 3 Haiku

### 3. 阿里云 Qwen

**支持的模型：**
- `qwen-max` - 通义千问最大模型
- `qwen-plus` - 通义千问增强版
- `qwen-turbo` - 通义千问标准版
- `qwen2.5-72b-instruct` - Qwen2.5 72B
- `qwen2.5-32b-instruct` - Qwen2.5 32B
- `qwen2.5-14b-instruct` - Qwen2.5 14B
- `qwen2.5-7b-instruct` - Qwen2.5 7B

```python
from engine import LMMEngineQwen

# 初始化
qwen = LMMEngineQwen(
    model="qwen-max",
    enable_thinking=False  # 是否启用思考模式
)

# 生成文本
messages = [{"role": "user", "content": "写一首关于春天的诗"}]
response = qwen.generate(messages, temperature=0.8)
```

### 4. 字节跳动 Doubao

**支持的模型：**
- `Doubao-1.5-thinking-vision-pro` - 豆包模型（需要替换为实际模型）
- 具体模型名称需要在火山引擎控制台查看

```python
from engine import LMMEngineDoubao

# 初始化
doubao = LMMEngineDoubao(model="Doubao-1.5-thinking-vision-pro")

# 生成文本
messages = [{"role": "user", "content": "介绍人工智能"}]
response = doubao.generate(messages)
```

### 5. Google Gemini

**支持的模型：**
- `gemini-2.5-pro` - Gemini 2.5 Pro
- `gemini-2.5-flash` - Gemini 2.5 Flash


```python
from engine import LMMEngineGemini

# 初始化
gemini = LMMEngineGemini(model="gemini-2.5-pro")

# 生成文本
messages = [{"role": "user", "content": "解释相对论"}]
response = gemini.generate(messages)
```

### 6. DeepSeek

**支持的模型：**
- `deepseek-chat` - DeepSeek Chat
- `deepseek-reasoner` - DeepSeek Reasoner

```python
from engine import LMMEngineDeepSeek

# 初始化
deepseek = LMMEngineDeepSeek(model="deepseek-chat")

# 生成文本
messages = [{"role": "user", "content": "编写Python快速排序"}]
response = deepseek.generate(messages)
```

### 7. 智谱 GLM

**支持的模型：**
- `glm-4-plus` - GLM-4 Plus
- `glm-4-0520` - GLM-4 
- `glm-4-air` - GLM-4 Air
- `glm-4-airx` - GLM-4 AirX
- `glm-4-flash` - GLM-4 Flash

```python
from engine import LMMEngineZhipu

# 初始化
zhipu = LMMEngineZhipu(model="glm-4-plus")

# 生成文本
messages = [{"role": "user", "content": "分析经济形势"}]
response = zhipu.generate(messages)
```

### 8. Groq

**支持的模型：**
- `llama-3.1-405b-reasoning` - Llama 3.1 405B
- `llama-3.1-70b-versatile` - Llama 3.1 70B
- `llama-3.1-8b-instant` - Llama 3.1 8B
- `mixtral-8x7b-32768` - Mixtral 8x7B
- `gemma2-9b-it` - Gemma 2 9B

```python
from engine import LMMEngineGroq

# 初始化
groq = LMMEngineGroq(model="llama-3.1-70b-versatile")

# 生成文本
messages = [{"role": "user", "content": "什么是机器学习？"}]
response = groq.generate(messages)
```

### 9. AWS Bedrock

**支持的模型：**
- `claude-opus-4` - Claude Opus 4
- `claude-sonnet-4` - Claude Sonnet 4
- `claude-3-5-sonnet` - Claude 3.5 Sonnet
- `claude-3-5-haiku` - Claude 3.5 Haiku
- `claude-3-opus` - Claude 3 Opus
- `claude-3-sonnet` - Claude 3 Sonnet
- `claude-3-haiku` - Claude 3 Haiku

```python
from engine import LMMEngineAWSBedrock

# 初始化
bedrock = LMMEngineAWSBedrock(model="claude-3-5-sonnet")

# 生成文本
messages = [{"role": "user", "content": "介绍云计算"}]
response = bedrock.generate(messages)
```

## 🔤 Embedding 引擎

### 1. OpenAI Embeddings

**支持的模型：**
- `text-embedding-3-large` - 最大模型 (3072维)
- `text-embedding-3-small` - 小模型 (1536维)
- `text-embedding-ada-002` - 经典模型 (1536维)

```python
from engine import OpenAIEmbeddingEngine

# 初始化
embedder = OpenAIEmbeddingEngine(embedding_model="text-embedding-3-small")

# 获取向量
text = "这是一段需要向量化的文本"
embeddings = embedder.get_embeddings(text)
print(f"向量维度: {embeddings.shape}")  # (1, 1536)
```

### 2. Google Gemini Embeddings

**支持的模型：**
- `text-embedding-004` - Gemini 最新嵌入模型

```python
from engine import GeminiEmbeddingEngine

# 初始化
gemini_embedder = GeminiEmbeddingEngine(embedding_model="text-embedding-004")

# 获取向量
text = "人工智能是计算机科学的分支"
embeddings = gemini_embedder.get_embeddings(text)
```

### 3. 阿里云 DashScope Embeddings

**支持的模型：**
- `text-embedding-v4` - 最新版本
- `text-embedding-v3` - 标准版本
- `text-embedding-v2` - 经典版本

```python
from engine import DashScopeEmbeddingEngine

# 初始化
dashscope_embedder = DashScopeEmbeddingEngine(
    embedding_model="text-embedding-v4",
    dimensions=1024  # 可选：512, 768, 1024, 1536
)

# 获取向量
text = "深度学习是机器学习的子集"
embeddings = dashscope_embedder.get_embeddings(text)
```

### 4. 字节跳动 Doubao Embeddings

**支持的模型：**

doubao-embedding-vision-250615 ：input 支持不限数量的 文本信息、图片信息和 视频信息混排输入。传入的信息作为1个整体进行向量化。

doubao-embedding-vision-250328/doubao-embedding-vision-241215 : input 当前仅支持3种组合， 1段文本信息、1段图片信息、 1段图片信息+1段文本信息。


```python
from engine import DoubaoEmbeddingEngine

# 初始化
doubao_embedder = DoubaoEmbeddingEngine(embedding_model="doubao-embedding-vision-250615")

# 获取向量
text = "自然语言处理技术发展"
embeddings = doubao_embedder.get_embeddings(text)
```

### 5. Jina AI Embeddings

**支持的模型：**
- `jina-embeddings-v4` - 最新版本
- `jina-embeddings-v3` - 第三代
- `jina-clip-v2` - 多模态嵌入

```python
from engine import JinaEmbeddingEngine

# 初始化
jina_embedder = JinaEmbeddingEngine(
    embedding_model="jina-embeddings-v4",
    task="retrieval.query"  # "retrieval.passage", "text-matching"
)

# 获取向量
text = "信息检索是计算机科学重要领域"
embeddings = jina_embedder.get_embeddings(text)
```

## 🔍 搜索引擎

### 1. Bocha AI Search

智能搜索引擎，返回AI分析后的答案和参考来源。

```python
from engine import BochaAISearchEngine

# 初始化
bocha_search = BochaAISearchEngine()

# 基本搜索
result = bocha_search.search(
    query="西瓜的功效与作用",
    freshness="noLimit",  # "day", "week", "month", "year", "noLimit"
    answer=True,          # 是否返回AI答案
    stream=False          # 是否使用流式响应
)

# 快捷方法
answer = bocha_search.get_answer("西瓜的功效与作用")
sources = bocha_search.get_sources("西瓜的功效与作用")
follow_ups = bocha_search.get_follow_up_questions("西瓜的功效与作用")

# 流式搜索
for chunk in bocha_search.search("天空为什么是蓝色", stream=True):
    print(chunk)
```

### 2. Exa Research

深度研究引擎，适合复杂主题的学术研究。

**支持的模型：**
- `exa-research` - 专业研究模型
