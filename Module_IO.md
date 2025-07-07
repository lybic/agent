# Manager
## 输入
 - 叙事记忆（Mn）：
    - 本地文件形式，json格式。Key是与环境观测有关的查询Query，Value是与Query相关的叙事记忆。
    - 示例：
      ```json
      {
      "How to open App Store on Mac?": "The task was successfully executed.\n\n**Successful Plan:**\n1. Open Spotlight Search using `command + space`.\n2. Type \"App Store\" and press enter."
      }
      ```
 - 用户任务指令（Tu）：
    - 文本形式，python字符串
    - 示例：
      ```python
      "Open AppStore"
      ```
 - 全局状态（Global States）：
    - 环境观测（obs）：图片形式， PIL (Pillow) 库的 Image 对象
      - 示例：
        ```python
        # Get screen shot using pyautogui
        screenshot = pyautogui.screenshot()
        screenshot = screenshot.resize((scaled_width, scaled_height), Image.LANCZOS)

        # Save the screenshot to a BytesIO object
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")

        # Get the byte value of the screenshot
        screenshot_bytes = buffered.getvalue()
        # Convert to base64 string.
        obs["screenshot"] = screenshot_bytes
        ```
    - 运行状态标记（running_state）：
      - 文本形式，python字符串，"running" 或 "stopped"
      - 示例：
        ```python
        "running"
        ```
 - 工具调用（Tools）：
   - Python类，参考[engine.py](./gui_agents/s2/core/engine.py)
   - 封装成Tools类，并接受模型名称和是否embedding的参数
   - 示例：
     ```python
     class Tools:
       def __init__(self, model_name, embedding=False):
         self.model_name = model_name
     ```
 - 提示词（Prompt）：
   - 文本形式，python字符串，参考[procedural_memory.py](./gui_agents/s2/memory/procedural_memory.py)
   - 示例：
     ```python
     "You are an expert in graphical user interfaces and Python code. You are responsible for executing the current subtask: `SUBTASK_DESCRIPTION` of the larger goal: `TASK_DESCRIPTION`. IMPORTANT: ** The subtasks: ['DONE_TASKS'] have already been done. The future subtasks ['FUTURE_TASKS'] will be done in the future by me. You must only perform the current subtask: `SUBTASK_DESCRIPTION`. Do not try to do future subtasks. ** You are working in CURRENT_OS. You must only complete the subtask provided and not the larger goal. You are provided with: 1. A screenshot of the current time step. 2. The history of your previous interactions with the UI. 3. Access to the following class and methods to interact with the UI: class Agent: "
     ```
## 输出
 - 子任务（Subtask）：
   - Node对象列表，参考[manager.py](./gui_agents/s2/agents/manager.py)
   - 示例：
     ```python
     [Node(name='Open Finder', info='Click on the Finder icon in the dock to open Finder.')]
     ```
 - Manager信息（Manager Info）：
- 字典形式，python字符串
   - 示例：
     ```python
     {
        'search_query': 'How to open Finder on macOS?', 
        'goal_plan': '1. Click on the Finder icon in the dock to open Finder.',
        'num_input_tokens_plan': 1776, 
        'num_output_tokens_plan': 14, 
        'goal_plan_cost': 0.00909, 
        'dag': '<json>\n{\n  "dag": {\n    "nodes": [\n      {\n        "name": "Open Finder",\n        "info": "Click on the Finder icon in the dock to open Finder."\n      }\n    ],\n    "edges": []\n  }\n}\n</json>', 
        'num_input_tokens_dag': 503, 
        'num_output_tokens_dag': 56, 'dag_cost': 0.0033550000000000003}
     ```

# Tools
## 输入
