import os
import json
import backoff
import requests
from typing import List, Dict, Any, Optional, Union
import numpy as np
from anthropic import Anthropic
from openai import (
    AzureOpenAI,
    APIConnectionError,
    APIError,
    AzureOpenAI,
    OpenAI,
    RateLimitError,
)
from google import genai
from google.genai import types
from zhipuai import ZhipuAI
from groq import Groq
import boto3
import exa_py


class LMMEngine:
    pass

# ==================== LLM ====================

class LMMEngineOpenAI(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named OPENAI_API_KEY"
            )

        self.base_url = base_url

        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        if not self.base_url:
            self.llm_client = OpenAI(api_key=self.api_key)
        else:
            self.llm_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        return (
            self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_new_tokens if max_new_tokens else 4096,
                temperature=temperature,
                **kwargs,
            )
            .choices[0]
            .message.content
        )


class LMMEngineQwen(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, enable_thinking=False, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model
        self.enable_thinking = enable_thinking

        api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named DASHSCOPE_API_KEY"
            )

        self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        self.llm_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        # For Qwen3 models, we need to handle thinking mode
        extra_body = {}
        if self.model.startswith("qwen3") and not self.enable_thinking:
            extra_body["enable_thinking"] = False

        return (
            self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_new_tokens if max_new_tokens else 4096,
                temperature=temperature,
                extra_body=extra_body if extra_body else None,
                **kwargs,
            )
            .choices[0]
            .message.content
        )


class LMMEngineDoubao(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        api_key = api_key or os.getenv("ARK_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named ARK_API_KEY"
            )

        self.base_url = base_url or "https://ark.cn-beijing.volces.com/api/v3"
        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        self.llm_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        return (
            self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_new_tokens if max_new_tokens else 4096,
                temperature=temperature,
                **kwargs,
            )
            .choices[0]
            .message.content
        )


class LMMEngineAnthropic(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, thinking=False, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model
        self.thinking = thinking

        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named ANTHROPIC_API_KEY"
            )

        self.api_key = api_key

        self.llm_client = Anthropic(api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        if self.thinking:
            full_response = self.llm_client.messages.create(
                system=messages[0]["content"][0]["text"],
                model=self.model,
                messages=messages[1:],
                max_tokens=8192,
                thinking={"type": "enabled", "budget_tokens": 4096},
                **kwargs,
            )

            thoughts = full_response.content[0].thinking
            print("CLAUDE 3.7 THOUGHTS:", thoughts)
            return full_response.content[1].text

        return (
            self.llm_client.messages.create(
                system=messages[0]["content"][0]["text"],
                model=self.model,
                messages=messages[1:],
                max_tokens=max_new_tokens if max_new_tokens else 4096,
                temperature=temperature,
                **kwargs,
            )
            .content[0]
            .text
        )


class LMMEngineGemini(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named GEMINI_API_KEY"
            )

        self.base_url = base_url or os.getenv("GEMINI_ENDPOINT_URL")
        if self.base_url is None:
            raise ValueError(
                "An endpoint URL needs to be provided in either the endpoint_url parameter or as an environment variable named GEMINI_ENDPOINT_URL"
            )

        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        self.llm_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        return (
            self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_new_tokens if max_new_tokens else 4096,
                temperature=temperature,
                **kwargs,
            )
            .choices[0]
            .message.content
        )


class LMMEngineOpenRouter(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named OPENROUTER_API_KEY"
            )

        self.base_url = base_url or os.getenv("OPEN_ROUTER_ENDPOINT_URL")
        if self.base_url is None:
            raise ValueError(
                "An endpoint URL needs to be provided in either the endpoint_url parameter or as an environment variable named OPEN_ROUTER_ENDPOINT_URL"
            )

        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        self.llm_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        return (
            self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_new_tokens if max_new_tokens else 4096,
                temperature=temperature,
                **kwargs,
            )
            .choices[0]
            .message.content
        )


class LMMEngineAzureOpenAI(LMMEngine):
    def __init__(
        self,
        base_url=None,
        api_key=None,
        azure_endpoint=None,
        model=None,
        api_version=None,
        rate_limit=-1,
        **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        assert api_version is not None, "api_version must be provided"
        self.api_version = api_version

        api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named AZURE_OPENAI_API_KEY"
            )

        self.api_key = api_key

        azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        if azure_endpoint is None:
            raise ValueError(
                "An Azure API endpoint needs to be provided in either the azure_endpoint parameter or as an environment variable named AZURE_OPENAI_ENDPOINT"
            )

        self.azure_endpoint = azure_endpoint
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        self.llm_client = AzureOpenAI(
            azure_endpoint=self.azure_endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
        )
        self.cost = 0.0

    # @backoff.on_exception(backoff.expo, (APIConnectionError, APIError, RateLimitError), max_tries=10)
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        completion = self.llm_client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_new_tokens if max_new_tokens else 4096,
            temperature=temperature,
            **kwargs,
        )
        total_tokens = completion.usage.total_tokens
        self.cost += 0.02 * ((total_tokens + 500) / 1000)
        return completion.choices[0].message.content


class LMMEnginevLLM(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model
        self.api_key = api_key

        self.base_url = base_url or os.getenv("vLLM_ENDPOINT_URL")
        if self.base_url is None:
            raise ValueError(
                "An endpoint URL needs to be provided in either the endpoint_url parameter or as an environment variable named vLLM_ENDPOINT_URL"
            )

        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        self.llm_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    # @backoff.on_exception(backoff.expo, (APIConnectionError, APIError, RateLimitError), max_tries=10)
    # TODO: Default params chosen for the Qwen model
    def generate(
        self,
        messages,
        temperature=0.0,
        top_p=0.8,
        repetition_penalty=1.05,
        max_new_tokens=512,
        **kwargs
    ):
        """Generate the next message based on previous messages"""
        completion = self.llm_client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_new_tokens if max_new_tokens else 4096,
            temperature=temperature,
            top_p=top_p,
            extra_body={"repetition_penalty": repetition_penalty},
        )
        return completion.choices[0].message.content


class LMMEngineHuggingFace(LMMEngine):
    def __init__(self, base_url=None, api_key=None, rate_limit=-1, **kwargs):
        assert base_url is not None, "HuggingFace endpoint must be provided"
        self.base_url = base_url

        api_key = api_key or os.getenv("HF_TOKEN")
        if api_key is None:
            raise ValueError(
                "A HuggingFace token needs to be provided in either the api_key parameter or as an environment variable named HF_TOKEN"
            )

        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        self.llm_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        return (
            self.llm_client.chat.completions.create(
                model="tgi",
                messages=messages,
                max_tokens=max_new_tokens if max_new_tokens else 4096,
                temperature=temperature,
                **kwargs,
            )
            .choices[0]
            .message.content
        )


# ==================== NEW ENGINE CLASSES ====================

class LMMEngineDeepSeek(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named DEEPSEEK_API_KEY"
            )

        self.base_url = base_url or "https://api.deepseek.com"
        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        self.llm_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        return (
            self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_new_tokens if max_new_tokens else 4096,
                temperature=temperature,
                **kwargs,
            )
            .choices[0]
            .message.content
        )


class LMMEngineZhipu(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        api_key = api_key or os.getenv("ZHIPU_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named ZHIPU_API_KEY"
            )

        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        # Use ZhipuAI client directly instead of OpenAI compatibility layer
        self.llm_client = ZhipuAI(api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        response = self.llm_client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_new_tokens if max_new_tokens else 4096,
            temperature=temperature,
            **kwargs,
        )
        return response.choices[0].message.content # type: ignore


class LMMEngineGroq(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        api_key = api_key or os.getenv("GROQ_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named GROQ_API_KEY"
            )

        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        # Use Groq client directly
        self.llm_client = Groq(api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        response = self.llm_client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_new_tokens if max_new_tokens else 4096,
            temperature=temperature,
            **kwargs,
        )
        return response.choices[0].message.content # type: ignore


class LMMEngineSiliconflow(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named SILICONFLOW_API_KEY"
            )

        self.base_url = base_url or "https://api.siliconflow.cn/v1"
        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        self.llm_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        return (
            self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_new_tokens if max_new_tokens else 4096,
                temperature=temperature,
                **kwargs,
            )
            .choices[0]
            .message.content
        )


class LMMEngineMonica(LMMEngine):
    def __init__(
        self, base_url=None, api_key=None, model=None, rate_limit=-1, **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        api_key = api_key or os.getenv("MONICA_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named MONICA_API_KEY"
            )

        self.base_url = base_url or "https://openapi.monica.im/v1"
        self.api_key = api_key
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        self.llm_client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""
        return (
            self.llm_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_new_tokens if max_new_tokens else 4096,
                temperature=temperature,
                **kwargs,
            )
            .choices[0]
            .message.content
        )


class LMMEngineAWSBedrock(LMMEngine):
    def __init__(
        self,
        aws_access_key=None,
        aws_secret_key=None,
        aws_region=None,
        model=None,
        rate_limit=-1,
        **kwargs
    ):
        assert model is not None, "model must be provided"
        self.model = model

        # Claude model mapping for AWS Bedrock
        self.claude_model_map = {
            "claude-opus-4": "anthropic.claude-opus-4-20250514-v1:0",
            "claude-sonnet-4": "anthropic.claude-sonnet-4-20250514-v1:0",
            "claude-3-7-sonnet": "anthropic.claude-3-7-sonnet-20250219-v1:0",
            "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "claude-3-5-sonnet-20241022": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "claude-3-5-sonnet-20240620": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "claude-3-5-haiku": "anthropic.claude-3-5-haiku-20241022-v1:0",
            "claude-3-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
            "claude-3-sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
            "claude-3-opus": "anthropic.claude-3-opus-20240229-v1:0",
        }

        # Get the actual Bedrock model ID
        self.bedrock_model_id = self.claude_model_map.get(model, model)

        # AWS credentials
        aws_access_key = aws_access_key or os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = aws_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_region = aws_region or os.getenv("AWS_DEFAULT_REGION") or "us-west-2"

        if aws_access_key is None:
            raise ValueError(
                "AWS Access Key needs to be provided in either the aws_access_key parameter or as an environment variable named AWS_ACCESS_KEY_ID"
            )
        if aws_secret_key is None:
            raise ValueError(
                "AWS Secret Key needs to be provided in either the aws_secret_key parameter or as an environment variable named AWS_SECRET_ACCESS_KEY"
            )

        self.aws_region = aws_region
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        # Initialize Bedrock client
        self.bedrock_client = boto3.client(
            service_name="bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )

    @backoff.on_exception(
        backoff.expo, (APIConnectionError, APIError, RateLimitError), max_time=60
    )
    def generate(self, messages, temperature=0.0, max_new_tokens=None, **kwargs):
        """Generate the next message based on previous messages"""

        # Convert messages to Bedrock format
        # Extract system message if present
        system_message = None
        user_messages = []

        for message in messages:
            if message["role"] == "system":
                if isinstance(message["content"], list):
                    system_message = message["content"][0]["text"]
                else:
                    system_message = message["content"]
            else:
                # Handle both list and string content formats
                if isinstance(message["content"], list):
                    content = message["content"][0]["text"] if message["content"] else ""
                else:
                    content = message["content"]

                user_messages.append({
                    "role": message["role"],
                    "content": content
                })

        # Prepare the body for Bedrock
        body = {
            "max_tokens": max_new_tokens if max_new_tokens else 4096,
            "messages": user_messages,
            "anthropic_version": "bedrock-2023-05-31"
        }

        if temperature > 0:
            body["temperature"] = temperature

        if system_message:
            body["system"] = system_message

        try:
            response = self.bedrock_client.invoke_model(
                body=json.dumps(body),
                modelId=self.bedrock_model_id
            )

            response_body = json.loads(response.get("body").read())

            # Extract the text response
            if "content" in response_body and response_body["content"]:
                return response_body["content"][0]["text"]
            else:
                raise ValueError("No content in response")

        except Exception as e:
            print(f"AWS Bedrock error: {e}")
            raise

# ==================== Embedding ====================

class OpenAIEmbeddingEngine(LMMEngine):
    def __init__(
        self,
        embedding_model: str = "text-embedding-3-small",
        api_key=None,
        **kwargs
    ):
        """Init an OpenAI Embedding engine

        Args:
            embedding_model (str, optional): Model name. Defaults to "text-embedding-3-small".
            api_key (_type_, optional): Auth key from OpenAI. Defaults to None.
        """
        self.model = embedding_model

        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named OPENAI_API_KEY"
            )
        self.api_key = api_key

    @backoff.on_exception(
        backoff.expo,
        (
            APIError,
            RateLimitError,
            APIConnectionError,
        ),
    )
    def get_embeddings(self, text: str) -> np.ndarray:
        client = OpenAI(api_key=self.api_key)
        response = client.embeddings.create(model=self.model, input=text)
        return np.array([data.embedding for data in response.data])


class GeminiEmbeddingEngine(LMMEngine):
    def __init__(
        self,
        embedding_model: str = "text-embedding-004",
        api_key=None,
        **kwargs
    ):
        """Init an Gemini Embedding engine

        Args:
            embedding_model (str, optional): Model name. Defaults to "text-embedding-004".
            api_key (_type_, optional): Auth key from Gemini. Defaults to None.
        """
        self.model = embedding_model

        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named GEMINI_API_KEY"
            )
        self.api_key = api_key

    @backoff.on_exception(
        backoff.expo,
        (
            APIError,
            RateLimitError,
            APIConnectionError,
        ),
    )
    def get_embeddings(self, text: str) -> np.ndarray:
        client = genai.Client(api_key=self.api_key)

        result = client.models.embed_content(
            model=self.model,
            contents=text,
            config=types.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY"),
        )

        return np.array([i.values for i in result.embeddings]) # type: ignore


class AzureOpenAIEmbeddingEngine(LMMEngine):
    def __init__(
        self,
        embedding_model: str = "text-embedding-3-small",
        api_key=None,
        api_version=None,
        endpoint_url=None,
        **kwargs
    ):
        """Init an Azure OpenAI Embedding engine

        Args:
            embedding_model (str, optional): Model name. Defaults to "text-embedding-3-small".
            api_key (_type_, optional): Auth key from Azure OpenAI. Defaults to None.
            api_version (_type_, optional): API version. Defaults to None.
            endpoint_url (_type_, optional): Endpoint URL. Defaults to None.
        """
        self.model = embedding_model

        api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named AZURE_OPENAI_API_KEY"
            )
        self.api_key = api_key

        api_version = api_version or os.getenv("OPENAI_API_VERSION")
        if api_version is None:
            raise ValueError(
                "An API Version needs to be provided in either the api_version parameter or as an environment variable named OPENAI_API_VERSION"
            )
        self.api_version = api_version

        endpoint_url = endpoint_url or os.getenv("AZURE_OPENAI_ENDPOINT")
        if endpoint_url is None:
            raise ValueError(
                "An Endpoint URL needs to be provided in either the endpoint_url parameter or as an environment variable named AZURE_OPENAI_ENDPOINT"
            )
        self.endpoint_url = endpoint_url

    @backoff.on_exception(
        backoff.expo,
        (
            APIError,
            RateLimitError,
            APIConnectionError,
        ),
    )
    def get_embeddings(self, text: str) -> np.ndarray:
        client = AzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.endpoint_url,
        )
        response = client.embeddings.create(input=text, model=self.model)
        return np.array([data.embedding for data in response.data])

class DashScopeEmbeddingEngine(LMMEngine):
    def __init__(
        self,
        embedding_model: str = "text-embedding-v4",
        api_key=None,
        dimensions: int = 1024,
        **kwargs
    ):
        """Init a DashScope (阿里云百炼) Embedding engine

        Args:
            embedding_model (str, optional): Model name. Defaults to "text-embedding-v4".
            api_key (_type_, optional): Auth key from DashScope. Defaults to None.
            dimensions (int, optional): Embedding dimensions. Defaults to 1024.
        """
        self.model = embedding_model
        self.dimensions = dimensions

        api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named DASHSCOPE_API_KEY"
            )
        self.api_key = api_key

        # Initialize OpenAI client with DashScope base URL
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    @backoff.on_exception(
        backoff.expo,
        (
                APIError,
                RateLimitError,
                APIConnectionError,
        ),
    )
    def get_embeddings(self, text: str) -> np.ndarray:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,
            encoding_format="float"
        )
        return np.array([data.embedding for data in response.data])


class DoubaoEmbeddingEngine(LMMEngine):
    def __init__(
        self,
        embedding_model: str = "doubao-embedding-256",
        api_key=None,
        **kwargs
    ):
        """Init a Doubao (字节跳动豆包) Embedding engine

        Args:
            embedding_model (str, optional): Model name. Defaults to "doubao-embedding-256".
            api_key (_type_, optional): Auth key from Doubao. Defaults to None.
        """
        self.model = embedding_model

        api_key = api_key or os.getenv("ARK_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named ARK_API_KEY"
            )
        self.api_key = api_key
        self.base_url = "https://ark.cn-beijing.volces.com/api/v3"

        # Use OpenAI-compatible client for text embeddings
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    @backoff.on_exception(
        backoff.expo,
        (
                APIError,
                RateLimitError,
                APIConnectionError,
        ),
    )
    def get_embeddings(self, text: str) -> np.ndarray:
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            encoding_format="float"
        )
        return np.array([data.embedding for data in response.data])


class JinaEmbeddingEngine(LMMEngine):
    def __init__(
        self,
        embedding_model: str = "jina-embeddings-v4",
        api_key=None,
        task: str = "retrieval.query",
        **kwargs
    ):
        """Init a Jina AI Embedding engine

        Args:
            embedding_model (str, optional): Model name. Defaults to "jina-embeddings-v4".
            api_key (_type_, optional): Auth key from Jina AI. Defaults to None.
            task (str, optional): Task type. Options: "retrieval.query", "retrieval.passage", "text-matching". Defaults to "retrieval.query".
        """
        self.model = embedding_model
        self.task = task

        api_key = api_key or os.getenv("JINA_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named JINA_API_KEY"
            )
        self.api_key = api_key
        self.base_url = "https://api.jina.ai/v1"

    @backoff.on_exception(
        backoff.expo,
        (
                APIError,
                RateLimitError,
                APIConnectionError,
        ),
    )
    def get_embeddings(self, text: str) -> np.ndarray:
        import requests

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        data = {
            "model": self.model,
            "task": self.task,
            "input": [
                {
                    "text": text
                }
            ]
        }

        response = requests.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json=data
        )

        if response.status_code != 200:
            raise Exception(f"Jina AI API error: {response.text}")

        result = response.json()
        return np.array([data["embedding"] for data in result["data"]])

# ==================== webSearch ====================
class SearchEngine:
    """Base class for search engines"""
    pass

class BochaAISearchEngine(SearchEngine):
    def __init__(
            self,
            api_key: str|None = None,
            base_url: str = "https://api.bochaai.com/v1",
            rate_limit: int = -1,
            **kwargs
    ):
        """Init a Bocha AI Search engine

        Args:
            api_key (str, optional): Auth key from Bocha AI. Defaults to None.
            base_url (str, optional): Base URL for the API. Defaults to "https://api.bochaai.com/v1".
            rate_limit (int, optional): Rate limit per minute. Defaults to -1 (no limit).
        """
        api_key = api_key or os.getenv("BOCHA_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named BOCHA_API_KEY"
            )

        self.api_key = api_key
        self.base_url = base_url
        self.endpoint = f"{base_url}/ai-search"
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

    @backoff.on_exception(
        backoff.expo,
        (
                APIConnectionError,
                APIError,
                RateLimitError,
                requests.exceptions.RequestException,
        ),
        max_time=60
    )
    def search(
            self,
            query: str,
            freshness: str = "noLimit",
            answer: bool = True,
            stream: bool = False,
            **kwargs
    ) -> Union[Dict[str, Any], Any]:
        """Search with AI and return intelligent answer

        Args:
            query (str): Search query
            freshness (str, optional): Freshness filter. Defaults to "noLimit".
            answer (bool, optional): Whether to return answer. Defaults to True.
            stream (bool, optional): Whether to stream response. Defaults to False.

        Returns:
            Union[Dict[str, Any], Any]: AI search results with sources and answer
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            "query": query,
            "freshness": freshness,
            "answer": answer,
            "stream": stream,
            **kwargs
        }

        if stream:
            return self._stream_search(headers, payload)
        else:
            return self._regular_search(headers, payload)

    def _regular_search(self, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Regular non-streaming search"""
        response = requests.post(
            self.endpoint,
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            raise APIError(f"Bocha AI Search API error: {response.text}") # type: ignore

        return response.json()

    def _stream_search(self, headers: Dict[str, str], payload: Dict[str, Any]):
        """Streaming search response"""
        response = requests.post(
            self.endpoint,
            headers=headers,
            json=payload,
            stream=True
        )

        if response.status_code != 200:
            raise APIError(f"Bocha AI Search API error: {response.text}") # type: ignore

        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data:'):
                    data = line[5:].strip()
                    if data and data != '{"event":"done"}':
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue

    def get_answer(self, query: str, **kwargs) -> str:
        """Get AI generated answer only"""
        result = self.search(query, answer=True, **kwargs)

        # Extract answer from messages
        messages = result.get("messages", [])
        for message in messages:
            if message.get("type") == "answer":
                return message.get("content", "")

        return ""

    def get_sources(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Get source materials only"""
        result = self.search(query, **kwargs)

        # Extract sources from messages
        sources = []
        messages = result.get("messages", [])
        for message in messages:
            if message.get("type") == "source":
                content_type = message.get("content_type", "")
                if content_type in ["webpage", "image", "video", "baike_pro", "medical_common"]:
                    sources.append({
                        "type": content_type,
                        "content": json.loads(message.get("content", "{}"))
                    })

        return sources

    def get_follow_up_questions(self, query: str, **kwargs) -> List[str]:
        """Get follow-up questions"""
        result = self.search(query, **kwargs)

        # Extract follow-up questions from messages
        follow_ups = []
        messages = result.get("messages", [])
        for message in messages:
            if message.get("type") == "follow_up":
                follow_ups.append(message.get("content", ""))

        return follow_ups


class ExaResearchEngine(SearchEngine):
    def __init__(
            self,
            api_key: str|None = None,
            base_url: str = "https://api.exa.ai",
            rate_limit: int = -1,
            **kwargs
    ):
        """Init an Exa Research engine

        Args:
            api_key (str, optional): Auth key from Exa AI. Defaults to None.
            base_url (str, optional): Base URL for the API. Defaults to "https://api.exa.ai".
            rate_limit (int, optional): Rate limit per minute. Defaults to -1 (no limit).
        """
        api_key = api_key or os.getenv("EXA_API_KEY")
        if api_key is None:
            raise ValueError(
                "An API Key needs to be provided in either the api_key parameter or as an environment variable named EXA_API_KEY"
            )

        self.api_key = api_key
        self.base_url = base_url
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit

        # Initialize OpenAI-compatible client for chat completions
        self.chat_client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )

        # Initialize Exa client for research tasks
        try:
            from exa_py import Exa
            self.exa_client = Exa(api_key=api_key)
        except ImportError:
            self.exa_client = None
            print("Warning: exa_py not installed. Research tasks will not be available.")

    @backoff.on_exception(
        backoff.expo,
        (
                APIConnectionError,
                APIError,
                RateLimitError,
        ),
        max_time=60
    )
    def chat_research(
            self,
            query: str,
            model: str = "exa",
            stream: bool = False,
            **kwargs
    ) -> Union[str, Any]:
        """Research using chat completions interface

        Args:
            query (str): Research query
            model (str, optional): Model name. Defaults to "exa".
            stream (bool, optional): Whether to stream response. Defaults to False.

        Returns:
            Union[str, Any]: Research result or stream
        """
        messages = [
            {"role": "user", "content": query}
        ]

        if stream:
            completion = self.chat_client.chat.completions.create(
                model=model,
                messages=messages, # type: ignore
                stream=True,
                **kwargs
            )
            return completion
        else:
            completion = self.chat_client.chat.completions.create(
                model=model,
                messages=messages, # type: ignore
                **kwargs
            )
            return completion.choices[0].message.content # type: ignore

    def create_research_task(
            self,
            instructions: str,
            model: str = "exa-research",
            output_infer_schema: bool = True,
            **kwargs
    ) -> Optional[Any]:
        """Create a research task using Exa SDK

        Args:
            instructions (str): Research instructions
            model (str, optional): Model name. Defaults to "exa-research".
            output_infer_schema (bool, optional): Whether to infer output schema. Defaults to True.

        Returns:
            Optional[Any]: Task stub or None if SDK not available
        """
        if self.exa_client is None:
            raise ImportError("exa_py SDK is required for research tasks. Install with: pip install exa_py")

        try:
            task_stub = self.exa_client.research.create_task(
                instructions=instructions,
                model=model, # type: ignore
                output_infer_schema=output_infer_schema,
                **kwargs
            )
            return task_stub
        except Exception as e:
            raise APIError(f"Exa Research API error: {str(e)}") # type: ignore

    def poll_research_task(self, task_id: str) -> Optional[Any]:
        """Poll a research task for completion

        Args:
            task_id (str): Task ID to poll

        Returns:
            Optional[Any]: Task result or None if SDK not available
        """
        if self.exa_client is None:
            raise ImportError("exa_py SDK is required for research tasks. Install with: pip install exa_py")

        try:
            task = self.exa_client.research.poll_task(task_id)
            return task
        except Exception as e:
            raise APIError(f"Exa Research API error: {str(e)}") # type: ignore

    def research(
            self,
            instructions: str,
            model: str = "exa-research",
            output_infer_schema: bool = True,
            **kwargs
    ) -> Optional[Any]:
        """Complete research task (create and poll until completion)

        Args:
            instructions (str): Research instructions
            model (str, optional): Model name. Defaults to "exa-research".
            output_infer_schema (bool, optional): Whether to infer output schema. Defaults to True.

        Returns:
            Optional[Any]: Research result or None if SDK not available
        """
        task_stub = self.create_research_task(
            instructions=instructions,
            model=model,
            output_infer_schema=output_infer_schema,
            **kwargs
        )

        if task_stub:
            return self.poll_research_task(task_stub.id)

        return None
