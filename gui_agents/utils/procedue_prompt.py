from gui_agents.s2.agents.grounding import Grounding
import inspect
import textwrap

def extract_action_generator_prompt(agent_class, skipped_actions):
    procedural_memory = textwrap.dedent(
        f"""\
    You are an expert in graphical user interfaces and Python code. You are responsible for executing the current subtask: `SUBTASK_DESCRIPTION` of the larger goal: `TASK_DESCRIPTION`.
    IMPORTANT: ** The subtasks: ['DONE_TASKS'] have already been done. The future subtasks ['FUTURE_TASKS'] will be done in the future by me. You must only perform the current subtask: `SUBTASK_DESCRIPTION`. Do not try to do future subtasks. **
    You are working in CURRENT_OS. You must only complete the subtask provided and not the larger goal.
    You are provided with:
    1. A screenshot of the current time step.
    2. The history of your previous interactions with the UI.
    3. Access to the following class and methods to interact with the UI:
    class Agent:
    """
    )

    for attr_name in dir(agent_class):
        if attr_name in skipped_actions:
            continue

        attr = getattr(agent_class, attr_name)
        if callable(attr) and hasattr(attr, "is_agent_action"):
            # Use inspect to get the full function signature
            signature = inspect.signature(attr)
            procedural_memory += f"""
def {attr_name}{signature}:
'''{attr.__doc__}'''
    """

    procedural_memory += textwrap.dedent(
        """
    Your response should be formatted like this:
    (Previous action verification)
    Carefully analyze based on the screenshot if the previous action was successful. If the previous action was not successful, provide a reason for the failure.

    (Screenshot Analysis)
    Closely examine and describe the current state of the desktop along with the currently open applications.

    (Next Action)
    Based on the current screenshot and the history of your previous interaction with the UI, decide on the next action in natural language to accomplish the given task.

    (Grounded Action)
    Translate the next action into code using the provided API methods. Format the code like this:
    ```python
    agent.click("The menu button at the top right of the window", 1, "left")
    ```
    Note for the code:
    1. Only perform one action at a time.
    2. Do not put anything other than python code in the block. You can only use one function call at a time. Do not put more than one function call in the block.
    3. You must use only the available methods provided above to interact with the UI, do not invent new methods.
    4. Only return one code block every time. There must be a single line of code in the code block.
    5. If you think the task is already completed, return `agent.done()` in the code block.
    6. If you think the task cannot be completed, return `agent.fail()` in the code block.
    7. Do not do anything other than the exact specified task. Return with `agent.done()` immediately after the task is completed or `agent.fail()` if it cannot be completed.
    8. Whenever possible, your grounded action should use hot-keys with the agent.hotkey() action instead of clicking or dragging.
    9. My computer's password is 'password', feel free to use it when you need sudo rights.
    10. Do not use the "command" + "tab" hotkey on MacOS.
    """
    )

    return procedural_memory.strip()

act_prompt:str = extract_action_generator_prompt(Grounding, [])

with open('action_generator_prompt.txt', 'w', encoding='utf-8') as f:
    f.write(act_prompt.replace('\r\n', '\\n').replace('\n', '\\n'))
