#!/usr/bin/env python3
"""
测试 gRPC 服务中 LLM 配置传递的脚本
"""

import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config_flow():
    """
    Verifies that a gRPC-provided LLM configuration is propagated into a registered tool's engine parameters.
    
    Simulates a gRPC configuration, applies it to the "action_generator" tool configuration loaded from the application's config, registers the tool, and asserts that the resulting engine parameters contain the expected api_key, base_url, and model values. Prints progress and diagnostic information; on failure, prints the exception and stack trace.
    """

    print("=" * 80)
    print("测试 LLM 配置传递流程")
    print("=" * 80)

    # 模拟 gRPC 请求中的配置
    mock_grpc_config = {
        "provider": "openai",
        "modelName": "gpt-4",
        "apiKey": "test-api-key-12345",
        "apiEndpoint": "https://api.openai.com/v1"
    }

    print(f"1. 模拟 gRPC 配置: {json.dumps(mock_grpc_config, indent=2)}")

    # 测试 load_config 函数
     from gui_agents.agents.agent_s import load_config
    _tools_config, tools_dict = load_config()

     print(f"2. 加载了 {len(tools_dict)} 个工具配置")

     # 模拟应用配置
     if "action_generator" in tools_dict:
         original_config = tools_dict["action_generator"].copy()
         print(f"3. action_generator 原始配置: {json.dumps(original_config, indent=2)}")

         # 应用 gRPC 配置
         tools_dict["action_generator"]["provider"] = mock_grpc_config["provider"]
         tools_dict["action_generator"]["model_name"] = mock_grpc_config["modelName"]
         tools_dict["action_generator"]["model"] = mock_grpc_config["modelName"]
         tools_dict["action_generator"]["api_key"] = mock_grpc_config["apiKey"]
         tools_dict["action_generator"]["base_url"] = mock_grpc_config["apiEndpoint"]

         updated_config = tools_dict["action_generator"]
         print(f"4. action_generator 更新后配置: {json.dumps(updated_config, indent=2)}")

         # 测试工具注册
         from gui_agents.tools.tools import Tools
         test_tools = Tools()
         test_tools.register_tool(
             "action_generator",
             updated_config["provider"],
             updated_config["model"],
             **updated_config
         )

         # 检查 LLMAgent 的引擎参数
         action_tool = test_tools.tools["action_generator"]
         engine_params = action_tool.engine_params

         print(f"5. LLMAgent 引擎参数: {json.dumps(engine_params, indent=2)}")

         # 验证关键参数
         assert engine_params.get("api_key") == mock_grpc_config["apiKey"], "API key 未正确传递"
         assert engine_params.get("base_url") == mock_grpc_config["apiEndpoint"], "Base URL 未正确传递"
         assert engine_params.get("model") == mock_grpc_config["modelName"], "Model name 未正确传递"

-    except Exception as e:
-        print(f"❌ 测试失败: {e}")
-        import traceback
    print("✅ 所有关键参数已正确传递到 LLMAgent")
def test_different_providers():
    """
    Runs registration checks for multiple LLM providers and prints per-provider pass/fail results.
    
    For each predefined provider case, registers a tool using the provider's configuration and prints a masked API key indicator and the resolved base URL; any exceptions encountered during registration or inspection are printed as failures.
    """
    print("\n" + "=" * 80)
    print("测试不同提供商的配置传递")
    print("=" * 80)

    test_cases = [
        {
            "name": "OpenAI",
            "config": {
                "provider": "openai",
                "modelName": "gpt-4",
                "apiKey": "sk-test-key",
                "apiEndpoint": "https://api.openai.com/v1"
            }
        },
        {
            "name": "Gemini",
            "config": {
                "provider": "gemini",
                "modelName": "gemini-2.0-flash-exp",
                "apiKey": "gemini-test-key",
                "apiEndpoint": "https://generativelanguage.googleapis.com/v1beta"
            }
        },
        {
            "name": "Qwen",
            "config": {
                "provider": "dashscope",
                "modelName": "qwen-turbo",
                "apiKey": "dashscope-test-key",
                "apiEndpoint": "https://dashscope.aliyuncs.com/compatible-mode/v1"
            }
        }
    ]

    for test_case in test_cases:
        print(f"\n测试 {test_case['name']} 配置传递:")
        try:
            from gui_agents.tools.tools import Tools

            config = test_case["config"].copy()
            test_tools = Tools()
            test_tools.register_tool(
                "test_tool",
                config["provider"],
                config["modelName"],
                api_key=config["apiKey"],
                base_url=config["apiEndpoint"]
            )

            tool = test_tools.tools["test_tool"]
            engine_params = tool.engine_params

            print(f"  ✅ {test_case['name']}: API key={'*' * len(engine_params.get('api_key', ''))}")
            print(f"  ✅ {test_case['name']}: Base URL={engine_params.get('base_url', 'N/A')}")

        except Exception as e:
            print(f"  ❌ {test_case['name']}: {e}")

if __name__ == "__main__":
    test_config_flow()
    test_different_providers()

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)