# Manager
## 输入

| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| local_kb_path | String | 本地叙事记忆和情景记忆的文件路径 | 
| Tu | String | 用户任务指令，文本形式 |
| observation | Dict | 其中包含key“screenshot”，value为全局状态类Global_Instance的get_screenshot方法得到的图片对象 |
| Running_state | String | 运行状态标记，文本形式，"running" 或 "stopped" |
| Tools_dict | Dict | 工具字典配置参照Tools类的创建属性，应包含“memory_retrival”、“websearch”、“context_fusion”和“subtask_planner” |
| Failed_subtask | Node | 失败子任务，Node对象 |
| Completed_subtasks_list | List[Node] | 已完成子任务列表，Node对象列表 |
| Remaining_subtasks_list | List[Node] | 剩余子任务列表，Node对象列表 |


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

# GlobalState
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| screenshot_dir | String | 截图文件夹路径 |
| tu_path | String | 用户任务指令文件路径 |
| search_query_path | String | 环境相关的任务总结查询文件路径 |
| failed_subtasks_path | String | 失败子任务文件路径 |
| completed_subtasks_path | String | 已完成子任务文件路径 |
| remaining_subtasks_path | String | 剩余子任务文件路径 |
| termination_flag_path | String | 终止标记文件路径 |
| running_state_path | String | 运行状态标记文件路径 |

## 存储对象
- 环境观测（obs）：
  - 截屏（Screenshot）：一个文件夹内，以时间戳命名的PNG图片形式，对应subtask，即图像-子任务配对。通过方法返回PIL (Pillow) 库的 Image 对象
  - 用户任务指令（Tu）：json格式存储，通过方法读取文件并返回文本形式，python字符串
  - 环境相关的任务总结查询（search_query）：json格式存储，通过方法读取文件并返回文本形式，python字符串
  - 已完成子任务（Completed_subtask）：json格式存储，Node对象列表，通过方法读取并返回Node对象列表。仅存储当前任务真正执行过的子任务，不存储未来规划中的任务。
  - 剩余子任务（Remaining_subtask）：json格式存储，Node对象列表，通过方法读取并返回Node对象列表。仅存储当前任务未来规划中的任务，不存储真正执行过的子任务。
  - 失败子任务（Failed_subtask）：json格式存储，Node对象列表，通过方法读取并返回Node对象列表。仅存储当前任务真正执行过的子任务，不存储未来规划中的任务。
  - 终止标记（termination_flag）：json格式存储，通过方法读取并返回文本形式，python字符串，"terminated" 或 "not_terminated"，作为终止按钮的标记。
- 运行状态标记（running_state）：json格式存储，通过方法读取并返回文本形式，python字符串，"running" 或 "stopped"，作为暂停按钮的标记。

## 读取方法
| 方法名 | 参数 | 返回值 | 描述 |
|-----|-----|-----|-----|
| get_screenshot | 无 | PIL (Pillow) 库的 Image 对象 | 从```Screenshot_dir```文件夹中获取当前最新时间戳的截图 |
| get_Tu | 无 | String | 从```Tu_path```文件中获取用户任务指令 |
| get_search_query | 无 | String | 从```Search_query_path```文件中获取环境相关的任务总结查询 |
| get_failed_subtasks | 无 | List[Node] | 从```Failed_subtask_path```文件中获取失败子任务 |
| get_completed_subtasks | 无 | List[Node] | 从```Completed_subtask_path```文件中获取已完成子任务 |
| get_remaining_subtasks | 无 | List[Node] | 从```Remaining_subtask_path```文件中获取剩余子任务 |
| get_termination_flag | 无 | String | 从```Termination_flag_path```文件中获取终止标记 |
| get_running_state | 无 | String | 从```Running_state_path```文件中获取运行状态标记 |



## 写入方法
| 方法名 | 参数 | 描述 |
|-----|-----|-----|
| set_screenshot | PIL (Pillow) 库的 Image 对象 | 将截图保存到```Screenshot_dir```文件夹中，以时间戳命名 |
| set_Tu | String | 将用户任务指令保存到```Tu_path```文件中 |
| set_search_query | String | 将环境相关的任务总结查询保存到```Search_query_path```文件中 |
| set_failed_subtasks | List[Node] | 将失败子任务保存到```Failed_subtask_path```文件中 |
| add_failed_subtask | Node | 将失败子任务保存到```Failed_subtask_path```文件中 |
| set_completed_subtasks | List[Node] | 将已完成子任务保存到```Completed_subtask_path```文件中 |
| add_completed_subtask | Node | 将已完成子任务保存到```Completed_subtask_path```文件中 |
| set_remaining_subtasks | List[Node] | 将剩余子任务保存到```Remaining_subtask_path```文件中 |
| add_remaining_subtask | Node | 将剩余子任务保存到```Remaining_subtask_path```文件中 |
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
| tool_name | String | 工具名称，有种：“websearch”、“context_fusion”、“subtask_planner”、“traj_reflector”、"memory_retrival"、“grounding”、"evaluator"、“action_generator”、“fast_action_generator”、“dag_translator”、“embedding”、"query_formulator"、“text_span”、“narrative_summarization”、“episode_summarization”|
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

# KnowledgeBase
## 存储对象
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| local_kb_path | String | 本地叙事记忆和情景记忆的文件路径 |
| embedding_engine | Tools | 嵌入引擎，Tools对象 |
| Tools_dict | Dict | 工具字典配置参照Tools类的创建属性，应包含“query_formulator”、“narrative_summarization”、“context_fusion”和“episode_summarization” |


## 方法
| 方法名 | 参数 | 返回值 | 描述 |
|-----|-----|-----|-----|
| formulate_query | String | String | 根据用户任务指令和环境相关的任务总结查询，生成环境相关的任务总结查询 |
| retrieve_narrative_experience | String | String | 根据用户任务指令，生成叙事记忆 |
| retrieve_episode_experience | String | String | 根据用户任务指令，生成情景记忆 |
| retrieve_knowledge | String | String | 根据用户任务指令和环境相关的任务总结查询，生成知识 |



# Worker
## 输入
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| local_kb_path | String | 本地叙事记忆和情景记忆的文件路径 | 
| Tu | String | 用户任务指令，文本形式 |
| Search_query | String | 环境相关的任务总结查询，文本形式，由全局状态类Global_Instance的get_search_query方法得到 |
| subtask | String | 当前子任务，文本形式 |
| subtask_info | Dict | 当前子任务的情境描述，字典形式，python字符串 |
| future_tasks | List[Node] | 未来子任务列表，Node对象列表 |
| done_task | List[Node] | 已完成子任务列表，Node对象列表 |
| obs | Dict | 其中包含key“screenshot”，value为全局状态类Global_Instance的get_screenshot方法得到的图片对象 |
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
| Tools_dict | Dict | 工具字典配置参照Tools类的创建属性，应包含“grounding”、“text_span” |

## 输出
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| grounding_output | Dict | 与具体硬件环境无关的指令输出，字典形式|
- 示例1：
  {'type': 'Click', 'xy': [10, 20]}

## action schema
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| type | String | 必须项。动作，文本形式，包含“Click”、“SwitchApp”、“Open”、“TypeText”、“Drag”、“Scroll”、“Hotkey”、“HoldAndPress”、“Wait”、“Fail”、“Done” |
| xy | List[int] | 坐标，列表形式，包含x和y两个元素 |
| num_clicks | int | 点击次数，整数形式 |
| clicks | int | 滚动的点击次数，可以是正数（向上）或负数（向下），整数形式 |
| button_type | String | 按钮类型，文本形式，包含“left”、“middle”、“right” |
| hold_keys | List[str] | 在操作中需要按住的按键，列表形式，包含按键名称 |
| press_keys | List[str] | 在操作中需要依次按下的按键，列表形式，包含按键名称 |
| keys | List[str] | 组合键，列表形式，包含按键名称 |
| app_code | String | 从提供的打开的应用程序列表中切换到的应用程序的代码名称，python字符串 |
| app_or_filename | String | 应用名称或文件名，文本形式，python字符串 |
| text | String | 文本，文本形式，python字符串 |
| overwrite | bool | 是否覆盖，布尔形式 |
| enter | bool | 是否按下回车键，布尔形式 |
| start | List[int] | 开始坐标，列表形式，包含x和y两个元素 |
| end | List[int] | 结束坐标，列表形式，包含x和y两个元素 |
| vertical | bool | 是否进行纵向滚动，布尔形式，默认True |
| seconds | float | 等待时间，浮点数形式 |
| return_value | Any | 返回值，Any类型 |

```python
# --------------------------------------
#  Concrete Action subclasses
# --------------------------------------
@dataclass(slots=True)
class Click(Action):
    xy: Tuple[int, int]
    element_description: str
    num_clicks: int = 1
    button_type: MouseButton = MouseButton.LEFT
    hold_keys: List[str] | None = None


@dataclass(slots=True)
class SwitchApp(Action):
    app_code: str


@dataclass(slots=True)
class Open(Action):
    app_or_filename: str


@dataclass(slots=True)
class TypeText(Action):
    text: str
    element_description: str
    xy: Tuple[int, int] | None = None
    overwrite: bool = False
    enter: bool = False


@dataclass(slots=True)
class SaveToKnowledge(Action):
    text: List[str]
    

@dataclass(slots=True)
class Drag(Action):
    start: Tuple[int, int]
    end: Tuple[int, int]
    hold_keys: List[str]
    starting_description: str
    ending_description: str


@dataclass(slots=True)
class HighlightTextSpan(Action):
    start: Tuple[int, int]
    end: Tuple[int, int]
    starting_phrase: str
    ending_phrase: str


@dataclass(slots=True)
class Scroll(Action):
    xy: Tuple[int, int]
    element_description: str
    clicks: int
    vertical: bool = True


@dataclass(slots=True)
class Hotkey(Action):
    keys: List[str]


@dataclass(slots=True)
class HoldAndPress(Action):
    hold_keys: List[str]
    press_keys: List[str]


@dataclass(slots=True)
class Wait(Action):
    seconds: float


@dataclass(slots=True)
class Done(Action):
    return_value: Any | None = None


@dataclass(slots=True)
class Fail(Action):
    pass
```

# HardwareInterface
## 输入
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| hardware_input | Dict | 由Grounding输出的与具体硬件环境无关的指令输出，字典形式 |

## 输出
| 字段名 | 类型 | 描述 |
|-----|-----|-----|
| hardware_output | String | 适配Lybic硬件环境相关的指令输出，文本形式，python字符串 |
- 示例："XXX"


