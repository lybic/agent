import base64

import numpy as np

from gui_agents.s2.core.engine import (
    LMMEngineAnthropic,
    LMMEngineAzureOpenAI,
    LMMEngineHuggingFace,
    LMMEngineOpenAI,
    LMMEngineOpenRouter,
    LMMEnginevLLM,
    LMMEngineGemini,
    LMMEngineQwen,
    LMMEngineDoubao,
    LMMEngineDeepSeek,
    LMMEngineZhipu,
    LMMEngineGroq,
    LMMEngineSiliconflow,
    LMMEngineMonica,
    LMMEngineAWSBedrock,
    OpenAIEmbeddingEngine,
    GeminiEmbeddingEngine,
    AzureOpenAIEmbeddingEngine,
    DashScopeEmbeddingEngine,
    DoubaoEmbeddingEngine,
    JinaEmbeddingEngine,
    BochaAISearchEngine,
    ExaResearchEngine,
)

class LMMAgent:
    def __init__(self, engine_params=None, system_prompt=None, engine=None):
        if engine is None:
            if engine_params is not None:
                engine_type = engine_params.get("engine_type")
                if engine_type == "openai":
                    self.engine = LMMEngineOpenAI(**engine_params)
                elif engine_type == "anthropic":
                    self.engine = LMMEngineAnthropic(**engine_params)
                elif engine_type == "azure":
                    self.engine = LMMEngineAzureOpenAI(**engine_params)
                elif engine_type == "vllm":
                    self.engine = LMMEnginevLLM(**engine_params)
                elif engine_type == "huggingface":
                    self.engine = LMMEngineHuggingFace(**engine_params)
                elif engine_type == "gemini":
                    self.engine = LMMEngineGemini(**engine_params)
                elif engine_type == "open_router":
                    self.engine = LMMEngineOpenRouter(**engine_params)
                elif engine_type == "dashscope":
                    self.engine = LMMEngineQwen(**engine_params)
                elif engine_type == "doubao":
                    self.engine = LMMEngineDoubao(**engine_params)
                elif engine_type == "deepseek":
                    self.engine = LMMEngineDeepSeek(**engine_params)
                elif engine_type == "zhipu":
                    self.engine = LMMEngineZhipu(**engine_params)
                elif engine_type == "groq":
                    self.engine = LMMEngineGroq(**engine_params)
                elif engine_type == "siliconflow":
                    self.engine = LMMEngineSiliconflow(**engine_params)
                elif engine_type == "monica":
                    self.engine = LMMEngineMonica(**engine_params)
                elif engine_type == "aws_bedrock":
                    self.engine = LMMEngineAWSBedrock(**engine_params)
                else:
                    raise ValueError("engine_type is not supported")
            else:
                raise ValueError("engine_params must be provided")
        else:
            self.engine = engine

        self.messages = []  # Empty messages

        if system_prompt:
            self.add_system_prompt(system_prompt)
        else:
            self.add_system_prompt("You are a helpful assistant.")

    def encode_image(self, image_content):
        # if image_content is a path to an image file, check type of the image_content to verify
        if isinstance(image_content, str):
            with open(image_content, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        else:
            return base64.b64encode(image_content).decode("utf-8")

    def reset(
        self,
    ):

        self.messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": self.system_prompt}],
            }
        ]

    def add_system_prompt(self, system_prompt):
        self.system_prompt = system_prompt
        if len(self.messages) > 0:
            self.messages[0] = {
                "role": "system",
                "content": [{"type": "text", "text": self.system_prompt}],
            }
        else:
            self.messages.append(
                {
                    "role": "system",
                    "content": [{"type": "text", "text": self.system_prompt}],
                }
            )

    def remove_message_at(self, index):
        """Remove a message at a given index"""
        if index < len(self.messages):
            self.messages.pop(index)

    def replace_message_at(
        self, index, text_content, image_content=None, image_detail="high"
    ):
        """Replace a message at a given index"""
        if index < len(self.messages):
            self.messages[index] = {
                "role": self.messages[index]["role"],
                "content": [{"type": "text", "text": text_content}],
            }
            if image_content:
                base64_image = self.encode_image(image_content)
                self.messages[index]["content"].append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}",
                            "detail": image_detail,
                        },
                    }
                )

    def add_message(
        self,
        text_content,
        image_content=None,
        role=None,
        image_detail="high",
        put_text_last=False,
    ):
        """Add a new message to the list of messages"""

        # API-style inference from OpenAI and similar services
        if isinstance(
            self.engine,
            (
                LMMEngineAnthropic,
                LMMEngineAzureOpenAI,
                LMMEngineHuggingFace,
                LMMEngineOpenAI,
                LMMEngineOpenRouter,
                LMMEnginevLLM,
                LMMEngineGemini,
                LMMEngineQwen,
                LMMEngineDoubao,
                LMMEngineDeepSeek,
                LMMEngineZhipu,
                LMMEngineGroq,
                LMMEngineSiliconflow,
                LMMEngineMonica,
                LMMEngineAWSBedrock,
            ),
        ):
            # infer role from previous message
            if role != "user":
                if self.messages[-1]["role"] == "system":
                    role = "user"
                elif self.messages[-1]["role"] == "user":
                    role = "assistant"
                elif self.messages[-1]["role"] == "assistant":
                    role = "user"

            message = {
                "role": role,
                "content": [{"type": "text", "text": text_content}],
            }

            if isinstance(image_content, np.ndarray) or image_content:
                # Check if image_content is a list or a single image
                if isinstance(image_content, list):
                    # If image_content is a list of images, loop through each image
                    for image in image_content:
                        base64_image = self.encode_image(image)
                        message["content"].append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}",
                                    "detail": image_detail,
                                },
                            }
                        )
                else:
                    # If image_content is a single image, handle it directly
                    base64_image = self.encode_image(image_content)
                    message["content"].append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": image_detail,
                            },
                        }
                    )

            # Rotate text to be the last message if desired
            if put_text_last:
                text_content = message["content"].pop(0)
                message["content"].append(text_content)

            self.messages.append(message)

        # For API-style inference from Anthropic
        elif isinstance(self.engine, (LMMEngineAnthropic, LMMEngineAWSBedrock)):
            # infer role from previous message
            if role != "user":
                if self.messages[-1]["role"] == "system":
                    role = "user"
                elif self.messages[-1]["role"] == "user":
                    role = "assistant"
                elif self.messages[-1]["role"] == "assistant":
                    role = "user"

            message = {
                "role": role,
                "content": [{"type": "text", "text": text_content}],
            }

            if image_content:
                # Check if image_content is a list or a single image
                if isinstance(image_content, list):
                    # If image_content is a list of images, loop through each image
                    for image in image_content:
                        base64_image = self.encode_image(image)
                        message["content"].append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": base64_image,
                                },
                            }
                        )
                else:
                    # If image_content is a single image, handle it directly
                    base64_image = self.encode_image(image_content)
                    message["content"].append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64_image,
                            },
                        }
                    )
            self.messages.append(message)

        # Locally hosted vLLM model inference
        elif isinstance(self.engine, LMMEnginevLLM):
            # infer role from previous message
            if role != "user":
                if self.messages[-1]["role"] == "system":
                    role = "user"
                elif self.messages[-1]["role"] == "user":
                    role = "assistant"
                elif self.messages[-1]["role"] == "assistant":
                    role = "user"

            message = {
                "role": role,
                "content": [{"type": "text", "text": text_content}],
            }

            if image_content:
                # Check if image_content is a list or a single image
                if isinstance(image_content, list):
                    # If image_content is a list of images, loop through each image
                    for image in image_content:
                        base64_image = self.encode_image(image)
                        message["content"].append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image;base64,{base64_image}"
                                },
                            }
                        )
                else:
                    # If image_content is a single image, handle it directly
                    base64_image = self.encode_image(image_content)
                    message["content"].append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image;base64,{base64_image}"},
                        }
                    )

            self.messages.append(message)
        else:
            raise ValueError("engine_type is not supported")

    def get_response(
        self,
        user_message=None,
        messages=None,
        temperature=0.0,
        max_new_tokens=None,
        **kwargs,
    ):
        """Generate the next response based on previous messages"""
        if messages is None:
            messages = self.messages
        if user_message:
            messages.append(
                {"role": "user", "content": [{"type": "text", "text": user_message}]}
            )

        return self.engine.generate(
            messages,
            temperature=temperature,
            max_new_tokens=max_new_tokens,
            **kwargs,
        )

class EmbeddingAgent:
    def __init__(self, engine_params=None, engine=None):
        if engine is None:
            if engine_params is not None:
                engine_type = engine_params.get("engine_type")
                if engine_type == "openai":
                    self.engine = OpenAIEmbeddingEngine(**engine_params)
                elif engine_type == "gemini":
                    self.engine = GeminiEmbeddingEngine(**engine_params)
                elif engine_type == "azure":
                    self.engine = AzureOpenAIEmbeddingEngine(**engine_params)
                elif engine_type == "dashscope":
                    self.engine = DashScopeEmbeddingEngine(**engine_params)
                elif engine_type == "doubao":
                    self.engine = DoubaoEmbeddingEngine(**engine_params)
                elif engine_type == "jina":
                    self.engine = JinaEmbeddingEngine(**engine_params)
                else:
                    raise ValueError(f"Embedding engine type '{engine_type}' is not supported")
            else:
                raise ValueError("engine_params must be provided")
        else:
            self.engine = engine

    def get_embeddings(self, text):
        """Get embeddings for the given text
        
        Args:
            text (str): The text to get embeddings for
            
        Returns:
            numpy.ndarray: The embeddings for the text
        """
        return self.engine.get_embeddings(text)
    
    def get_similarity(self, text1, text2):
        """Calculate the cosine similarity between two texts
        
        Args:
            text1 (str): First text
            text2 (str): Second text
            
        Returns:
            float: Cosine similarity score between the two texts
        """
        embedding1 = self.get_embeddings(text1)[0]
        embedding2 = self.get_embeddings(text2)[0]
        
        # Calculate cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        return dot_product / (norm1 * norm2)
    
    def batch_get_embeddings(self, texts):
        """Get embeddings for multiple texts
        
        Args:
            texts (List[str]): List of texts to get embeddings for
            
        Returns:
            List[numpy.ndarray]: List of embeddings for each text
        """
        embeddings = []
        for text in texts:
            embedding = self.get_embeddings(text)
            embeddings.append(embedding[0])
        return embeddings
    
    def find_most_similar(self, query_text, candidate_texts):
        """Find the most similar text from a list of candidates
        
        Args:
            query_text (str): The query text
            candidate_texts (List[str]): List of candidate texts to compare against
            
        Returns:
            Tuple[int, float, str]: Index, similarity score, and content of the most similar text
        """
        query_embedding = self.get_embeddings(query_text)[0]
        
        max_similarity = -1
        max_index = -1
        
        for i, text in enumerate(candidate_texts):
            candidate_embedding = self.get_embeddings(text)[0]
            
            # Calculate cosine similarity
            dot_product = np.dot(query_embedding, candidate_embedding)
            norm1 = np.linalg.norm(query_embedding)
            norm2 = np.linalg.norm(candidate_embedding)
            
            similarity = dot_product / (norm1 * norm2)
            
            if similarity > max_similarity:
                max_similarity = similarity
                max_index = i
        
        if max_index >= 0:
            return max_index, max_similarity, candidate_texts[max_index]
        else:
            return None, None, None

class WebSearchAgent:
    def __init__(self, engine_params=None, engine=None):
        if engine is None:
            if engine_params is not None:
                engine_type = engine_params.get("engine_type")
                if engine_type == "bocha":
                    self.engine = BochaAISearchEngine(**engine_params)
                elif engine_type == "exa":
                    self.engine = ExaResearchEngine(**engine_params)
                else:
                    raise ValueError(f"Web search engine type '{engine_type}' is not supported")
            else:
                raise ValueError("engine_params must be provided")
        else:
            self.engine = engine

    def search(self, query, **kwargs):
        """Perform a web search with the given query
        
        Args:
            query (str): The search query
            **kwargs: Additional arguments to pass to the search engine
            
        Returns:
            Dict or Any: Search results from the engine
        """
        return self.engine.search(query, **kwargs)
    
    def get_answer(self, query, **kwargs):
        """Get a direct answer for the query
        
        Args:
            query (str): The search query
            **kwargs: Additional arguments to pass to the search engine
            
        Returns:
            str: The answer text
        """
        if isinstance(self.engine, BochaAISearchEngine):
            return self.engine.get_answer(query, **kwargs)
        elif isinstance(self.engine, ExaResearchEngine):
            # For Exa, we'll use the chat_research method which returns a complete answer
            return self.engine.chat_research(query, **kwargs)
        else:
            # Generic fallback
            results = self.search(query, **kwargs)
            if isinstance(results, dict) and "messages" in results:
                for message in results.get("messages", []):
                    if message.get("type") == "answer":
                        return message.get("content", "")
            return str(results)
    
    def get_sources(self, query, **kwargs):
        """Get source materials for the query
        
        Args:
            query (str): The search query
            **kwargs: Additional arguments to pass to the search engine
            
        Returns:
            List: Source materials
        """
        if isinstance(self.engine, BochaAISearchEngine):
            return self.engine.get_sources(query, **kwargs)
        elif isinstance(self.engine, ExaResearchEngine):
            # For Exa, we need to extract sources from the research results
            results = self.search(query, **kwargs)
            if isinstance(results, dict) and "sources" in results:
                return results.get("sources", [])
            return []
        else:
            # Generic fallback
            results = self.search(query, **kwargs)
            if isinstance(results, dict) and "sources" in results:
                return results.get("sources", [])
            return []
    
    def research(self, query, detailed=False, **kwargs):
        """Perform comprehensive research on a topic
        
        Args:
            query (str): The research query
            detailed (bool): Whether to return detailed results
            **kwargs: Additional arguments to pass to the search engine
            
        Returns:
            Dict: Research results with answer and sources
        """
        if isinstance(self.engine, ExaResearchEngine):
            if hasattr(self.engine, "research"):
                return self.engine.research(instructions=query, **kwargs)
            else:
                return self.engine.chat_research(query, **kwargs)
        else:
            # For other engines, combine answer and sources
            answer = self.get_answer(query, **kwargs)
            sources = self.get_sources(query, **kwargs)
            
            if detailed:
                return {
                    "answer": answer,
                    "sources": sources
                }
            else:
                return answer
