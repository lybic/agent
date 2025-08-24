# Module IO

## Manager

### Manager Input

| Field | Type | Description |
|-----|-----|-----|
| local_kb_path | String | File path to local narrative memory and episodic memory |
| Tu | String | User task instruction, as text |
| observation | Dict | Contains key "screenshot"; value is the image object returned by Global_Instance.get_screenshot |
| Running_state | String | Run-state flag, "running" or "stopped" |
| Tools_dict | Dict | Tool dictionary per the Tools class configuration; should include "memory_retrival", "websearch", "context_fusion", and "subtask_planner" |
| Failed_subtask | Node | Failed subtask, a Node object |
| Completed_subtasks_list | List[Node] | List of completed subtasks, list of Node objects |
| Remaining_subtasks_list | List[Node] | List of remaining subtasks, list of Node objects |

### Manager Output

| Field | Type | Description |
|-----|-----|-----|
| Subtasks | List[Node] | List of subtasks, list of Node objects; class defined in [common_utils.py](./gui_agents/s2/utils/common_utils.py) |
| Manager_info | Dict | Manager information, dictionary serialized as a Python string |

- Subtask:
  - List of Node objects; class defined in [common_utils.py](./gui_agents/s2/utils/common_utils.py)
  - Example:

```python
[Node(name='Open Finder', info='Click on the Finder icon in the dock to open Finder.')]
```

- Manager Info:
  - Dictionary serialized as a Python string
  - Example:

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

## GlobalState

| Field | Type | Description |
|-----|-----|-----|
| screenshot_dir | String | Screenshot folder path |
| tu_path | String | User task instruction file path |
| search_query_path | String | Environment-related task summary query file path |
| failed_subtasks_path | String | Failed subtask file path |
| completed_subtasks_path | String | Completed subtask file path |
| remaining_subtasks_path | String | Remaining subtask file path |
| termination_flag_path | String | Termination flag file path |
| running_state_path | String | Running state flag file path |

### Stored Objects

- Observation (obs):
  - Screenshot: A folder containing PNG images named by timestamp, corresponding to subtasks; returned as a PIL (Pillow) library Image object by method
  - User task instruction (Tu): Stored in JSON format, read from file and returned as text by method
  - Environment-related task summary query (search_query): Stored in JSON format, read from file and returned as text by method
  - Completed subtask (Completed_subtask): Stored in JSON format, read and returned as a list of Node objects by method; only stores subtasks actually executed in the current task, not future planned tasks
  - Remaining subtask (Remaining_subtask): Stored in JSON format, read and returned as a list of Node objects by method; only stores future planned tasks in the current task, not subtasks actually executed
  - Failed subtask (Failed_subtask): Stored in JSON format, read and returned as a list of Node objects by method; only stores subtasks actually executed in the current task, not future planned tasks
  - Termination flag (termination_flag): Stored in JSON format, read and returned as text by method; "terminated" or "not_terminated", used as a termination button flag
- Running state flag (running_state): Stored in JSON format, read and returned as text by method; "running" or "stopped", used as a pause button flag

### Read Methods

| Method Name | Parameters | Return Value | Description |
|-----|-----|-----|-----|
| get_screenshot | None | PIL (Pillow) library Image object | Get the latest screenshot from the ```Screenshot_dir``` folder |
| get_Tu | None | String | Get the user task instruction from the ```Tu_path``` file |
| get_search_query | None | String | Get the environment-related task summary query from the ```Search_query_path``` file |
| get_failed_subtasks | None | List[Node] | Get the failed subtasks from the ```Failed_subtask_path``` file |
| get_completed_subtasks | None | List[Node] | Get the completed subtasks from the ```Completed_subtask_path``` file |
| get_remaining_subtasks | None | List[Node] | Get the remaining subtasks from the ```Remaining_subtask_path``` file |
| get_termination_flag | None | String | Get the termination flag from the ```Termination_flag_path``` file |
| get_running_state | None | String | Get the running state flag from the ```Running_state_path``` file |

### Write Methods

| Method Name | Parameters | Description |
|-----|-----|-----|
| set_screenshot | PIL (Pillow) library Image object | Save the screenshot to the ```Screenshot_dir``` folder with a timestamp as the name |
| set_Tu | String | Save the user task instruction to the ```Tu_path``` file |
| set_search_query | String | Save the environment-related task summary query to the ```Search_query_path``` file |
| set_failed_subtasks | List[Node] | Save the failed subtasks to the ```Failed_subtask_path``` file |
| add_failed_subtask | Node | Save the failed subtask to the ```Failed_subtask_path``` file |
| set_completed_subtasks | List[Node] | Save the completed subtasks to the ```Completed_subtask_path``` file |
| add_completed_subtask | Node | Save the completed subtask to the ```Completed_subtask_path``` file |
| set_remaining_subtasks | List[Node] | Save the remaining subtasks to the ```Remaining_subtask_path``` file |
| add_remaining_subtask | Node | Save the remaining subtask to the ```Remaining_subtask_path``` file |
| set_termination_flag | String | Save the termination flag to the ```Termination_flag_path``` file |
| set_running_state | String | Save the running state flag to the ```Running_state_path``` file |

- Manager:
  - Environment-related task summary query (search_query) in observation (obs)
- HardwareInterface:
  - Screenshot (Screenshot) in observation (obs)
- Evaluator:
  - Termination flag (termination_flag) in observation (obs)

## Tools

### Properties

| Field | Type | Description |
|-----|-----|-----|
| tool_name | String | Tool name, including: "websearch", "context_fusion", "subtask_planner", "traj_reflector", "memory_retrival", "grounding", "evaluator", "action_generator", "fast_action_generator", "dag_translator", "embedding", "query_formulator", "text_span", "narrative_summarization", "episode_summarization" |
| provider | String | API provider name, such as "gemini" |
| model_name | String | Model name used by the tool, such as "gemini-2.5-pro" |
| prompt_path | String | Prompt file path, text format, Python string; select the prompt file based on the tool_name from a fixed path |

### Tools Input

| Field | Type | Description |
|-----|-----|-----|
| tool_input | Dict | Observation, dictionary format, Python string, containing str_input and img_input keys; str_input is text input, img_input is image input |

### Tools Output

| Field | Type | Description |
|-----|-----|-----|
| tool_output | String | Tool output, text format, Python string |

## KnowledgeBase

### Tools Stored Objects

| Field | Type | Description |
|-----|-----|-----|
| local_kb_path | String | File path to local narrative memory and episodic memory |
| embedding_engine | Tools | Embedding engine, Tools object |
| Tools_dict | Dict | Tool dictionary per the Tools class configuration; should include "query_formulator", "narrative_summarization", "context_fusion", and "episode_summarization" |

### Methods

| Method Name | Parameters | Return Value | Description |
|-----|-----|-----|-----|
| formulate_query | String | String | Generate environment-related task summary query based on user task instruction and environment-related task summary query |
| retrieve_narrative_experience | String | String | Generate narrative memory based on user task instruction |
| retrieve_episode_experience | String | String | Generate episodic memory based on user task instruction |
| retrieve_knowledge | String | String | Generate knowledge based on user task instruction and environment-related task summary query |

## Worker

### Input

| Field | Type | Description |
|-----|-----|-----|
| local_kb_path | String | File path to local narrative memory and episodic memory |
| Tu | String | User task instruction, text format |
| Search_query | String | Environment-related task summary query, text format, obtained by Global_Instance.get_search_query method |
| subtask | String | Current subtask, text format |
| subtask_info | Dict | Context description of the current subtask, dictionary format, Python string |
| future_tasks | List[Node] | List of future subtasks, list of Node objects |
| done_task | List[Node] | List of completed subtasks, list of Node objects |
| obs | Dict | Contains key "screenshot"; value is the image object returned by Global_Instance.get_screenshot |
| Running_state | String | Run-state flag, "running" or "stopped"; obtained by Global_Instance.get_running_state method |
| Tools_dict | Dict | Tool dictionary per the Tools class configuration; should include "memory_retrival", "traj_reflector", and "action_generator" |

### Output

| Field | Type | Description |
|-----|-----|-----|
| worker_plan | String | Plan, text format, Python string |

- Example 1:
(Previous action verification)\nThe previous action was to open Spotlight Search. However, the screenshot does not show Spotlight Search open. It shows the VS Code application and the dock. The previous action was likely not successful, or the screenshot was taken before the Spotlight Search appeared. Given the current state, I will proceed assuming Spotlight Search is not visible.\n\n(Screenshot Analysis)\nThe current screenshot displays the VS Code application as the active window. At the bottom of the screen, the macOS Dock is visible, showing various application icons. The Maps application icon, which is a blue icon with a white map symbol, is visible in the Dock.\n\n(Next Action)\nClick the Maps application icon in the dock to open it.\n\n(Grounded Action)\n```python\nagent.click("The Maps application icon in the dock, which is a blue icon with a white map symbol", 1, "left")\n```

- Example 2:
(Previous action verification)\nThe previous action `agent.open("Finder")` did not successfully open the Finder application. The screenshot shows the desktop without any open Finder windows.\n\n
(Screenshot Analysis)\nThe current screenshot shows the macOS desktop. No applications are open in the foreground. The dock is visible at the bottom. WeChat is not open. Given that multiple attempts to open or click the WeChat icon using various methods (direct click, dock click, and Spotlight search) have failed, and even opening Finder has failed, it indicates that the subtask cannot be completed in the current environment.\n\n(Next Action)\nSince all attempts to open WeChat have failed, and even opening other applications like Finder is not working, it indicates that the environment is not allowing applications to be launched. Therefore, I must report failure.\n\n(Grounded Action)\n```python\nagent.fail()\n```

- Example 3:
(Previous action verification)\nThe previous action of typing "App Store" into Spotlight and pressing enter was successful, as the App Store application is now open on the screen.\n\n(Screenshot Analysis)\nThe current screenshot shows the App Store application open. The window displays a sidebar on the left with options like Search, Explore, Create, Work, Games, Develop, Categories, and Updates. The main content area is currently showing Explore. The dock is still visible at the bottom of the screen.\n\n(Next Action)\nThe subtask was to "Click App Store icon". The App Store is now open. Therefore, the subtask is complete.\n\n(Grounded Action)\n```python\nagent.done()\n```

## Grounding

### Grounding Input

| Field | Type | Description |
|-----|-----|-----|
| grounding_input | Dict | Observation, dictionary format, Python string, containing str_input and img_input keys; str_input is text input, which is the full text of Worker's worker_plan output, img_input is image input, which is the image object returned by Global_Instance.get_screenshot |
| Tools_dict | Dict | Tool dictionary per the Tools class configuration; should include "grounding" and "text_span" |

### Grounding Output

| Field | Type | Description |
|-----|-----|-----|
| grounding_output | Dict | Instruction output unrelated to specific hardware environment, dictionary format |

- Example 1:
  {'type': 'Click', 'xy': [10, 20]}

### action schema

| Field | Type | Description |
|-----|-----|-----|
| type | String | Required. Action, text format, including "Click", "SwitchApp", "Open", "TypeText", "Drag", "Scroll", "Hotkey", "HoldAndPress", "Wait", "Fail", "Done" |
| xy | List[int] | Coordinates, list format, containing x and y elements |
| num_clicks | int | Number of clicks, integer format |
| clicks | int | Number of clicks for scrolling, can be positive (up) or negative (down), integer format |
| button_type | String | Button type, text format, including "left", "middle", "right" |
| hold_keys | List[str] | Keys to hold down during the operation, list format, containing key names |
| press_keys | List[str] | Keys to press in sequence during the operation, list format, containing key names |
| keys | List[str] | Combination keys, list format, containing key names |
| app_code | String | Code name of the application to switch to from the provided list of open applications, Python string |
| app_or_filename | String | Application name or file name, text format, Python string |
| text | String | Text, text format, Python string |
| overwrite | bool | Overwrite flag, boolean format |
| enter | bool | Enter key press flag, boolean format |
| start | List[int] | Starting coordinates, list format, containing x and y elements |
| end | List[int] | Ending coordinates, list format, containing x and y elements |
| vertical | bool | Vertical scroll flag, boolean format, default True |
| seconds | float | Wait time, float format |
| return_value | Any | Return value, Any type |

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

## HardwareInterface

### HardwareInterface Input

| Field | Type | Description |
|-----|-----|-----|
| hardware_input | Dict | Instruction output unrelated to specific hardware environment, dictionary format, output by Grounding |

### HardwareInterface Output

| Field | Type | Description |
|-----|-----|-----|
| hardware_output | String | Instruction output related to Lybic hardware environment, text format, Python string |

- Example: "XXX"
