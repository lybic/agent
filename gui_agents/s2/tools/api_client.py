"""
API client module for interacting with different API providers.

This module provides client classes for interacting with various API providers
such as OpenAI, Anthropic, Google (Gemini), etc.
"""

import os
import json
import base64
import requests
from typing import Dict, Any, Optional, List, Union
import logging

logger = logging.getLogger(__name__)

class BaseAPIClient:
    """Base class for API clients."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the base API client.
        
        Args:
            api_key: API key for authentication
        """
        self.api_key = api_key or self._get_api_key_from_env()
        
    def _get_api_key_from_env(self) -> Optional[str]:
        """
        Get API key from environment variables.
        
        Returns:
            API key as a string or None if not found
        """
        return None
    
    def _handle_error(self, response: requests.Response) -> Dict[str, Any]:
        """
        Handle error responses from the API.
        
        Args:
            response: Response object from the API
            
        Returns:
            Error information as a dictionary
        """
        try:
            error_data = response.json()
        except json.JSONDecodeError:
            error_data = {"error": response.text}
        
        logger.error(f"API error: {response.status_code} - {error_data}")
        return {
            "status_code": response.status_code,
            "error": error_data
        }


class OpenAIClient(BaseAPIClient):
    """Client for interacting with OpenAI API."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the OpenAI client.
        
        Args:
            api_key: OpenAI API key
            base_url: Base URL for the API
        """
        super().__init__(api_key)
        self.base_url = base_url or "https://api.openai.com/v1"
        
    def _get_api_key_from_env(self) -> Optional[str]:
        """
        Get OpenAI API key from environment variables.
        
        Returns:
            OpenAI API key as a string or None if not found
        """
        return os.environ.get("OPENAI_API_KEY")
    
    def text_completion(self, prompt: str, model: str = "gpt-4o") -> Dict[str, Any]:
        """
        Generate text completion using OpenAI API.
        
        Args:
            prompt: Prompt text
            model: Model name
            
        Returns:
            Response from the API
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return self._handle_error(response)
    
    def multimodal_completion(self, prompt: str, image_data: bytes, model: str = "gpt-4o") -> Dict[str, Any]:
        """
        Generate multimodal completion using OpenAI API.
        
        Args:
            prompt: Prompt text
            image_data: Image data as bytes
            model: Model name
            
        Returns:
            Response from the API
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Convert image to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }
            ],
            "temperature": 0.7
        }
        
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return self._handle_error(response)


class AnthropicClient(BaseAPIClient):
    """Client for interacting with Anthropic API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Anthropic client.
        
        Args:
            api_key: Anthropic API key
        """
        super().__init__(api_key)
        self.base_url = "https://api.anthropic.com/v1"
        
    def _get_api_key_from_env(self) -> Optional[str]:
        """
        Get Anthropic API key from environment variables.
        
        Returns:
            Anthropic API key as a string or None if not found
        """
        return os.environ.get("ANTHROPIC_API_KEY")
    
    def text_completion(self, prompt: str, model: str = "claude-3-5-sonnet") -> Dict[str, Any]:
        """
        Generate text completion using Anthropic API.
        
        Args:
            prompt: Prompt text
            model: Model name
            
        Returns:
            Response from the API
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1024
        }
        
        response = requests.post(
            f"{self.base_url}/messages",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return self._handle_error(response)
    
    def multimodal_completion(self, prompt: str, image_data: bytes, model: str = "claude-3-5-sonnet") -> Dict[str, Any]:
        """
        Generate multimodal completion using Anthropic API.
        
        Args:
            prompt: Prompt text
            image_data: Image data as bytes
            model: Model name
            
        Returns:
            Response from the API
        """
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        # Convert image to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64_image}}
                    ]
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1024
        }
        
        response = requests.post(
            f"{self.base_url}/messages",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return self._handle_error(response)


class GeminiClient(BaseAPIClient):
    """Client for interacting with Google Gemini API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gemini client.
        
        Args:
            api_key: Gemini API key
        """
        super().__init__(api_key)
        self.base_url = "https://generativelanguage.googleapis.com/v1"
        
    def _get_api_key_from_env(self) -> Optional[str]:
        """
        Get Gemini API key from environment variables.
        
        Returns:
            Gemini API key as a string or None if not found
        """
        return os.environ.get("GEMINI_API_KEY")
    
    def text_completion(self, prompt: str, model: str = "gemini-2.5-pro") -> Dict[str, Any]:
        """
        Generate text completion using Gemini API.
        
        Args:
            prompt: Prompt text
            model: Model name
            
        Returns:
            Response from the API
        """
        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            return response.json()
        else:
            return self._handle_error(response)
    
    def multimodal_completion(self, prompt: str, image_data: bytes, model: str = "gemini-2.5-pro") -> Dict[str, Any]:
        """
        Generate multimodal completion using Gemini API.
        
        Args:
            prompt: Prompt text
            image_data: Image data as bytes
            model: Model name
            
        Returns:
            Response from the API
        """
        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Convert image to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1024
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            return response.json()
        else:
            return self._handle_error(response)


class SerperClient(BaseAPIClient):
    """Client for interacting with Serper API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Serper client.
        
        Args:
            api_key: Serper API key
        """
        super().__init__(api_key)
        self.base_url = "https://google.serper.dev/search"
        
    def _get_api_key_from_env(self) -> Optional[str]:
        """
        Get Serper API key from environment variables.
        
        Returns:
            Serper API key as a string or None if not found
        """
        return os.environ.get("SERPER_API_KEY")
    
    def search(self, query: str, num_results: int = 10) -> Dict[str, Any]:
        """
        Perform a web search using Serper API.
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            Search results as a dictionary
        """
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "q": query,
            "num": num_results
        }
        
        response = requests.post(
            self.base_url,
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return self._handle_error(response)


class SerpAPIClient(BaseAPIClient):
    """Client for interacting with SerpAPI."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the SerpAPI client.
        
        Args:
            api_key: SerpAPI key
        """
        super().__init__(api_key)
        self.base_url = "https://serpapi.com/search"
        
    def _get_api_key_from_env(self) -> Optional[str]:
        """
        Get SerpAPI key from environment variables.
        
        Returns:
            SerpAPI key as a string or None if not found
        """
        return os.environ.get("SERPAPI_API_KEY")
    
    def search(self, query: str, num_results: int = 10) -> Dict[str, Any]:
        """
        Perform a web search using SerpAPI.
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            Search results as a dictionary
        """
        params = {
            "q": query,
            "num": num_results,
            "api_key": self.api_key
        }
        
        response = requests.get(self.base_url, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            return self._handle_error(response)


class APIClientFactory:
    """Factory class for creating API clients."""
    
    @staticmethod
    def create_client(provider: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> BaseAPIClient:
        """
        Create an API client based on the provider.
        
        Args:
            provider: API provider name
            api_key: API key for authentication
            base_url: Base URL for the API
            
        Returns:
            An instance of the appropriate API client
            
        Raises:
            ValueError: If the provider is not recognized
        """
        if provider.lower() == "openai":
            return OpenAIClient(api_key, base_url)
        elif provider.lower() == "anthropic":
            return AnthropicClient(api_key)
        elif provider.lower() == "gemini":
            return GeminiClient(api_key)
        elif provider.lower() == "serper":
            return SerperClient(api_key)
        elif provider.lower() == "serpapi":
            return SerpAPIClient(api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}") 