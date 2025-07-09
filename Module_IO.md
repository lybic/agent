# Manager
## 输入

| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| Mn_dict | Dict | 由叙事记忆Mn类的readout方法得到的字典 | 
| Tu | String | 用户任务指令，文本形式 |
| Screenshot | PIL (Pillow) 库的 Image 对象 | 由全局状态类Global_Instance的get_screenshot方法得到的图片对象|
| Running_state | String | 运行状态标记，文本形式，"running" 或 "stopped"。由全局状态类Global_Instance的get_running_state方法得到 |
| Tools_dict | Dict | 工具字典配置参照Tools类的创建属性，应包含“memory_retrival”、“websearch”、“context_fusion”和“subtask_planner” |


- 叙事记忆（Mn_dict）：
  - 示例：
      ```python
      {
        "How to open App Store on Mac?": "The task was successfully executed.\n\n**Successful Plan:**\n1. Open Spotlight Search using `command + space`.\n2. Type \"App Store\" and press enter."
      }
      ```
- 用户任务指令（Tu）：
  - 文本形式，python字符串
  - 示例：
    ```
    "Open AppStore"
    ```
- 全局状态（Global Instance）：
  - 环境观测（obs）里的截屏（Screenshot）：
    - 图片形式， PIL (Pillow) 库的 Image 对象
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
- 工具调用（Tools_dict）：
  - 用Dict的key做工具匹配，value选择工具使用的模型名称
  - 示例：
     ```python
     class Tools:
       def __init__(self, tool_name, model_name):
         self.model_name = model_name
         self.tool_name = tool_name
     ```
## 输出
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| Subtasks | List[Node] | 子任务列表，Node对象列表，类定义参考[common_utils.py](./gui_agents/s2/utils/common_utils.py) |
| Manager_info | Dict | Manager信息，字典形式，python字符串 |

- 子任务（Subtask）：
  - Node对象列表，类定义参考[common_utils.py](./gui_agents/s2/utils/common_utils.py)
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
        'num_output_tokens_dag': 56, 'dag_cost': 0.0033550000000000003
    }
     ```

# Global_Instance
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| Screenshot_dir | String | 截图文件夹路径 |
| Tu_path | String | 用户任务指令文件路径 |
| Search_query_path | String | 环境相关的任务总结查询文件路径 |
| Failed_subtask_path | String | 失败子任务文件路径 |
| Completed_subtask_path | String | 已完成子任务文件路径 |
| Remaining_subtask_path | String | 剩余子任务文件路径 |
| Termination_flag_path | String | 终止标记文件路径 |
| Running_state_path | String | 运行状态标记文件路径 |

## 存储对象
- 环境观测（obs）：
  - 截屏（Screenshot）：一个文件夹内，以时间戳命名的PNG图片形式，对应subtask，即图像-子任务配对。通过方法返回PIL (Pillow) 库的 Image 对象
  - 用户任务指令（Tu）：json格式存储，通过方法读取文件并返回文本形式，python字符串
  - 环境相关的任务总结查询（search_query）：json格式存储，通过方法读取文件并返回文本形式，python字符串
  - 已完成子任务（Completed_subtask）：json格式存储，Node对象列表，通过方法读取并返回Node对象列表。仅存储当前任务真正执行过的子任务，不存储未来规划中的任务。
  - 终止标记（termination_flag）：json格式存储，通过方法读取并返回文本形式，python字符串，"terminated" 或 "not_terminated"，作为终止按钮的标记。
- 运行状态标记（running_state）：json格式存储，通过方法读取并返回文本形式，python字符串，"running" 或 "stopped"，作为暂停按钮的标记。

## 读取方法
| 方法名 | 参数 | 返回值 | 描述 |
|-----|-----|-----|-----|
| get_screenshot | 无 | PIL (Pillow) 库的 Image 对象 | 从```Screenshot_dir```文件夹中获取当前最新时间戳的截图 |
| get_Tu | 无 | String | 从```Tu_path```文件中获取用户任务指令 |
| get_search_query | 无 | String | 从```Search_query_path```文件中获取环境相关的任务总结查询 |
| get_failed_subtask | 无 | List[Node] | 从```Failed_subtask_path```文件中获取失败子任务 |
| get_completed_subtask | 无 | List[Node] | 从```Completed_subtask_path```文件中获取已完成子任务 |
| get_remaining_subtask | 无 | List[Node] | 从```Remaining_subtask_path```文件中获取剩余子任务 |
| get_termination_flag | 无 | String | 从```Termination_flag_path```文件中获取终止标记 |
| get_running_state | 无 | String | 从```Running_state_path```文件中获取运行状态标记 |

- Manager：
  - 环境观测（obs）中的截屏（Screenshot）
  - 环境观测（obs）中的终止标记（termination_flag）
- Grounding：
  - 环境观测（obs）中的截屏（Screenshot）
- Evaluator：
  - 环境观测（obs）中的环境相关的任务总结查询（search_query）、子任务（Subtask）和截屏（Screenshot）

## 写入方法
| 方法名 | 参数 | 描述 |
|-----|-----|-----|
| set_screenshot | PIL (Pillow) 库的 Image 对象 | 将截图保存到```Screenshot_dir```文件夹中，以时间戳命名 |
| set_Tu | String | 将用户任务指令保存到```Tu_path```文件中 |
| set_search_query | String | 将环境相关的任务总结查询保存到```Search_query_path```文件中 |
| set_failed_subtask | List[Node] | 将失败子任务保存到```Failed_subtask_path```文件中 |
| set_completed_subtask | List[Node] | 将已完成子任务保存到```Completed_subtask_path```文件中 |
| set_remaining_subtask | List[Node] | 将剩余子任务保存到```Remaining_subtask_path```文件中 |
| set_termination_flag | String | 将终止标记保存到```Termination_flag_path```文件中 |
| set_running_state | String | 将运行状态标记保存到```Running_state_path```文件中 |

- Manager：
  - 环境观测（obs）中的环境相关的任务总结查询（search_query）
- HardwareInterface：
  - 环境观测（obs）中的截屏（Screenshot）
- Evaluator：
  - 环境观测（obs）中的终止标记（termination_flag）

# Tools
## 属性
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| tool_name | String | 工具名称，有X种：“websearch”、“context_fusion”、“subtask_planner”、“traj_reflector”、“memory_retrival”、“grounding”、“summarizer”、 “action_generator”|
| provider | String | API供应商名称，如“gemini” |
| model_name | String | 工具调用的模型名称，如“gemini-2.5-pro” |
| prompt_path | String | 提示词文件路径，文本形式，python字符串。选定tool_name后，根据tool_name选择固定路径下的提示词文件 |

## 输入
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| tool_input | Dict | 环境观测，字典形式，python字符串，包含str_input和img_input两个key，str_input是文本输入，img_input是图像输入 |

## 输出
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| tool_output | String | 工具输出，文本形式，python字符串 |

# Mn/Me
## 存储对象
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| Mn_path | String | 叙事记忆文件路径 |

- 叙事记忆（Mn）：
  - 本地文件形式，json格式。Key是与环境观测有关的查询Query，Value是与Query相关的叙事记忆。
  - 示例：{"How to open Finder on Mac?": "The task was successfully executed.\n\n**Successful Plan:**\n1. Open Spotlight Search using `command + space`.\n2. Type \"Finder\" into the Spotlight search bar.\n3. Press `enter` to launch Finder."}

- 情景记忆（Me）：
  - 本地文件形式，json格式。Key任务与子任务的描述；Value是与子任务的执行过程，包含Action自然语言描述与Grounded Action伪代码形式。
  - 示例：{"Task:\nHow to open Finder on Mac?\n\nSubtask: Open Spotlight\nSubtask Instruction: Press `command + space` to open Spotlight.": "Action: Click the Spotlight icon in the menu bar to open Spotlight.\nGrounded Action: agent.click(\"element1_description\", 1, \"left\")"}

## 读取方法
| 方法名 | 参数 | 返回值 | 描述 |
|-----|-----|-----|-----|
| get_Mn_dict | 无 | Dict | 从```Mn_path```文件中获取当前所有叙事记忆形成的字典 |

## 写入方法
| 方法名 | 参数 | 描述 |
|-----|-----|-----|
| set_Mn_dict | Dict | 将叙事记忆保存到```Mn_path```文件中 |

# Worker
## 输入
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| Me_dict | Dict | 由叙事记忆Me类的readout方法得到的字典 | 
| Tu | String | 用户任务指令，文本形式 |
| Search_query | String | 环境相关的任务总结查询，文本形式，由全局状态类Global_Instance的get_search_query方法得到 |
| Screenshot | PIL (Pillow) 库的 Image 对象 | 由全局状态类Global_Instance的get_screenshot方法得到的图片对象|
| Running_state | String | 运行状态标记，文本形式，"running" 或 "stopped"。由全局状态类Global_Instance的get_running_state方法得到 |
| Tools_dict | Dict | 工具字典配置参照Tools类的创建属性，应包含“memory_retrival”、“traj_reflector”和“action_generator” |


## 输出
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| worker_plan | String | 计划，文本形式，python字符串 |

- 示例1：
(Previous action verification)\nThe previous action was to open Spotlight Search. However, the screenshot does not show Spotlight Search open. It shows the VS Code application and the dock. The previous action was likely not successful, or the screenshot was taken before the Spotlight Search appeared. Given the current state, I will proceed assuming Spotlight Search is not visible.\n\n(Screenshot Analysis)\nThe current screenshot displays the VS Code application as the active window. At the bottom of the screen, the macOS Dock is visible, showing various application icons. The Maps application icon, which is a blue icon with a white map symbol, is visible in the Dock.\n\n(Next Action)\nClick the Maps application icon in the dock to open it.\n\n(Grounded Action)\n```python\nagent.click("The Maps application icon in the dock, which is a blue icon with a white map symbol", 1, "left")\n```

- 示例2：
(Previous action verification)\nThe previous action `agent.open("Finder")` did not successfully open the Finder application. The screenshot shows the desktop without any open Finder windows.\n\n
(Screenshot Analysis)\nThe current screenshot shows the macOS desktop. No applications are open in the foreground. The dock is visible at the bottom. WeChat is not open. Given that multiple attempts to open or click the WeChat icon using various methods (direct click, dock click, and Spotlight search) have failed, and even opening Finder has failed, it indicates that the subtask cannot be completed in the current environment.\n\n(Next Action)\nSince all attempts to open WeChat have failed, and even opening other applications like Finder is not working, it indicates that the environment is not allowing applications to be launched. Therefore, I must report failure.\n\n(Grounded Action)\n```python\nagent.fail()\n```

- 示例3：
(Previous action verification)\nThe previous action of typing "App Store" into Spotlight and pressing enter was successful, as the App Store application is now open on the screen.\n\n(Screenshot Analysis)\nThe current screenshot shows the App Store application open. The window displays a sidebar on the left with options like "搜索" (Search), "探索" (Explore), "创作" (Create), "工作" (Work), "游戏" (Games), "开发" (Develop), "类别" (Categories), and "更新" (Updates). The main content area is currently showing "探索" (Explore). The dock is still visible at the bottom of the screen.\n\n(Next Action)\nThe subtask was to "Click App Store icon". The App Store is now open. Therefore, the subtask is complete.\n\n(Grounded Action)\n```python\nagent.done()\n```

# Grounding
## 输入
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| grounding_input | Dict | 环境观测，字典形式，python字符串，包含str_input和img_input两个key，str_input是文本输入，即为Worker输出的worker_plan全文，img_input是图像输入，即为全局状态类Global_Instance的get_screenshot方法得到的图片对象 |
| Tools_dict | Dict | 工具字典配置参照Tools类的创建属性，应包含“grounding” |

## 输出
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| grounding_output | String | 与具体硬件环境无关的指令输出，统一成python代码形式。文本形式，python字符串 |
- 示例1：
  "import pyautogui; import pyautogui; pyautogui.click(769, 1006, clicks=1, button='left'); "

# Evaluator
## 输入
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| evaluator_worker_plan_input | String | 由Worker模块得出的worker_plan全文，文本形式，python字符串。需解析成Grounded Action伪代码形式，解析方式参考[worker.py](./gui_agents/s2/agents/worker.py)第225行的实现 |

## 输出
无输出。每次执行完Worker模块后，调用Evaluator模块，更新情景记忆Me。当解析出当前任务已完成后，调用Evaluator模块，更新叙事记忆Mn。

# HardwareInterface
## 输入
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| hardware_input | String | 由Grounding输出的与具体硬件环境无关的指令输出，统一成python代码形式。文本形式，python字符串 |

## 输出
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| hardware_output | String | 适配Lybic硬件环境相关的指令输出，文本形式，python字符串 |
- 示例："XXX"


