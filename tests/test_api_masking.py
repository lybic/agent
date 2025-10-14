#!/usr/bin/env python3
"""
Test script to verify API key masking functionality in grpc_app.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui_agents.proto.pb import agent_pb2
from gui_agents.grpc_app import AgentServicer

def test_api_key_masking():
    """
    Verify that API keys in CommonConfig and LLMConfig objects are replaced with "********" while non-sensitive fields remain unchanged.
    
    Constructs a CommonConfig populated with multiple sensitive apiKey fields and an LLMConfig with an apiKey, invokes AgentServicer._mask_config_secrets and _mask_llm_config_secrets, and asserts that every apiKey is replaced with "********" and that non-sensitive fields (e.g., id, orgID, modelName, provider) are preserved.
    """
    print("Testing API key masking functionality...")

    # Create a test servicer
    servicer = AgentServicer()

    # Create a test config with sensitive information
    test_config = agent_pb2.CommonConfig()
    test_config.id = "test"

    # Add authorization info with API key
    test_config.authorizationInfo.orgID = "test_org"
    test_config.authorizationInfo.apiKey = "super_secret_api_key_123"
    test_config.authorizationInfo.apiEndpoint = "https://api.test.com"

    # Add stage model config with multiple LLM configs containing API keys
    test_config.stageModelConfig.embeddingModel.modelName = "text-embedding-ada-002"
    test_config.stageModelConfig.embeddingModel.provider = "openai"
    test_config.stageModelConfig.embeddingModel.apiKey = "sk-openai-secret-key"

    test_config.stageModelConfig.groundingModel.modelName = "gpt-4"
    test_config.stageModelConfig.groundingModel.provider = "openai"
    test_config.stageModelConfig.groundingModel.apiKey = "sk-gpt4-secret-key"

    test_config.stageModelConfig.actionGeneratorModel.modelName = "claude-3"
    test_config.stageModelConfig.actionGeneratorModel.provider = "anthropic"
    test_config.stageModelConfig.actionGeneratorModel.apiKey = "sk-ant-secret-key"

    # Test all LLM config fields
    test_config.stageModelConfig.contextFusionModel.apiKey = "sk-context-secret"
    test_config.stageModelConfig.subtaskPlannerModel.apiKey = "sk-subtask-secret"
    test_config.stageModelConfig.trajReflectorModel.apiKey = "sk-traj-secret"
    test_config.stageModelConfig.memoryRetrivalModel.apiKey = "sk-memory-secret"
    test_config.stageModelConfig.taskEvaluatorModel.apiKey = "sk-evaluator-secret"
    test_config.stageModelConfig.actionGeneratorWithTakeoverModel.apiKey = "sk-takeover-secret"
    test_config.stageModelConfig.fastActionGeneratorModel.apiKey = "sk-fast-secret"
    test_config.stageModelConfig.fastActionGeneratorWithTakeoverModel.apiKey = "sk-fast-takeover-secret"
    test_config.stageModelConfig.dagTranslatorModel.apiKey = "sk-dag-secret"
    test_config.stageModelConfig.queryFormulatorModel.apiKey = "sk-query-secret"
    test_config.stageModelConfig.narrativeSummarizationModel.apiKey = "sk-narrative-secret"
    test_config.stageModelConfig.textSpanModel.apiKey = "sk-text-secret"
    test_config.stageModelConfig.episodeSummarizationModel.apiKey = "sk-episode-secret"

    print("Original config has API keys:")
    print(f"  Authorization API key: {test_config.authorizationInfo.apiKey}")
    print(f"  Embedding API key: {test_config.stageModelConfig.embeddingModel.apiKey}")
    print(f"  Grounding API key: {test_config.stageModelConfig.groundingModel.apiKey}")
    print(f"  Action Generator API key: {test_config.stageModelConfig.actionGeneratorModel.apiKey}")

    # Apply masking
    masked_config = servicer._mask_config_secrets(test_config)

    print("\nMasked config should have API keys replaced:")
    print(f"  Authorization API key: {masked_config.authorizationInfo.apiKey}")
    print(f"  Embedding API key: {masked_config.stageModelConfig.embeddingModel.apiKey}")
    print(f"  Grounding API key: {masked_config.stageModelConfig.groundingModel.apiKey}")
    print(f"  Action Generator API key: {masked_config.stageModelConfig.actionGeneratorModel.apiKey}")

    # Verify all API keys are masked
    assert masked_config.authorizationInfo.apiKey == "********", f"Authorization API key not masked: {masked_config.authorizationInfo.apiKey}"
    assert masked_config.stageModelConfig.embeddingModel.apiKey == "********", f"Embedding API key not masked: {masked_config.stageModelConfig.embeddingModel.apiKey}"
    assert masked_config.stageModelConfig.groundingModel.apiKey == "********", f"Grounding API key not masked: {masked_config.stageModelConfig.groundingModel.apiKey}"
    assert masked_config.stageModelConfig.actionGeneratorModel.apiKey == "********", f"Action Generator API key not masked: {masked_config.stageModelConfig.actionGeneratorModel.apiKey}"
    assert masked_config.stageModelConfig.contextFusionModel.apiKey == "********", f"Context Fusion API key not masked: {masked_config.stageModelConfig.contextFusionModel.apiKey}"
    assert masked_config.stageModelConfig.subtaskPlannerModel.apiKey == "********", f"Subtask Planner API key not masked: {masked_config.stageModelConfig.subtaskPlannerModel.apiKey}"
    assert masked_config.stageModelConfig.trajReflectorModel.apiKey == "********", f"Traj Reflector API key not masked: {masked_config.stageModelConfig.trajReflectorModel.apiKey}"
    assert masked_config.stageModelConfig.memoryRetrivalModel.apiKey == "********", f"Memory Retrieval API key not masked: {masked_config.stageModelConfig.memoryRetrivalModel.apiKey}"
    assert masked_config.stageModelConfig.taskEvaluatorModel.apiKey == "********", f"Task Evaluator API key not masked: {masked_config.stageModelConfig.taskEvaluatorModel.apiKey}"
    assert masked_config.stageModelConfig.actionGeneratorWithTakeoverModel.apiKey == "********", f"Action Generator With Takeover API key not masked: {masked_config.stageModelConfig.actionGeneratorWithTakeoverModel.apiKey}"
    assert masked_config.stageModelConfig.fastActionGeneratorModel.apiKey == "********", f"Fast Action Generator API key not masked: {masked_config.stageModelConfig.fastActionGeneratorModel.apiKey}"
    assert masked_config.stageModelConfig.fastActionGeneratorWithTakeoverModel.apiKey == "********", f"Fast Action Generator With Takeover API key not masked: {masked_config.stageModelConfig.fastActionGeneratorWithTakeoverModel.apiKey}"
    assert masked_config.stageModelConfig.dagTranslatorModel.apiKey == "********", f"DAG Translator API key not masked: {masked_config.stageModelConfig.dagTranslatorModel.apiKey}"
    assert masked_config.stageModelConfig.queryFormulatorModel.apiKey == "********", f"Query Formulator API key not masked: {masked_config.stageModelConfig.queryFormulatorModel.apiKey}"
    assert masked_config.stageModelConfig.narrativeSummarizationModel.apiKey == "********", f"Narrative Summarization API key not masked: {masked_config.stageModelConfig.narrativeSummarizationModel.apiKey}"
    assert masked_config.stageModelConfig.textSpanModel.apiKey == "********", f"Text Span API key not masked: {masked_config.stageModelConfig.textSpanModel.apiKey}"
    assert masked_config.stageModelConfig.episodeSummarizationModel.apiKey == "********", f"Episode Summarization API key not masked: {masked_config.stageModelConfig.episodeSummarizationModel.apiKey}"

    # Verify non-sensitive fields are not changed
    assert masked_config.id == test_config.id, "Non-sensitive field 'id' was modified"
    assert masked_config.authorizationInfo.orgID == test_config.authorizationInfo.orgID, "Non-sensitive field 'orgID' was modified"
    assert masked_config.stageModelConfig.embeddingModel.modelName == test_config.stageModelConfig.embeddingModel.modelName, "Non-sensitive field 'modelName' was modified"

    print("\n✅ All API keys properly masked!")
    print("✅ Non-sensitive fields preserved!")

    # Test individual LLM config masking
    print("\nTesting individual LLM config masking...")
    test_llm_config = agent_pb2.LLMConfig()
    test_llm_config.modelName = "gpt-4"
    test_llm_config.provider = "openai"
    test_llm_config.apiKey = "sk-secret-key"
    test_llm_config.apiEndpoint = "https://api.openai.com"

    print(f"Original LLM config API key: {test_llm_config.apiKey}")
    masked_llm_config = servicer._mask_llm_config_secrets(test_llm_config)
    print(f"Masked LLM config API key: {masked_llm_config.apiKey}")

    assert masked_llm_config.apiKey == "********", f"LLM API key not masked: {masked_llm_config.apiKey}"
    assert masked_llm_config.modelName == test_llm_config.modelName, "Non-sensitive LLM field was modified"
    assert masked_llm_config.provider == test_llm_config.provider, "Non-sensitive LLM field was modified"

    print("✅ Individual LLM config masking works correctly!")

    print("\n🔒 Security test passed! All API keys are properly masked.")

if __name__ == "__main__":
    test_api_key_masking()