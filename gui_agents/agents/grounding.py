import ast
import re
import logging
from collections import defaultdict
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, Union
import time
import pytesseract
from PIL import Image
from pytesseract import Output

from gui_agents.tools.tools import Tools
from gui_agents.utils.common_utils import (
    # call_llm_safe,
    parse_single_code_from_string,
)
from gui_agents.store.registry import Registry
from gui_agents.agents.global_state import GlobalState

logger = logging.getLogger("desktopenv.agent")

class ACI:
    def __init__(self):
        self.notes: List[str] = []


# Agent action decorator
def agent_action(func):
    func.is_agent_action = True
    return func


# ACI primitives are parameterized by description, and coordinate generation uses a pretrained grounding model
class Grounding(ACI):
    def __init__(
        self,
        Tools_dict: Dict,
        platform: str,
        width: int = 1920, # Screenshot width
        height: int = 1080, # Screenshot height
    ):
        self.platform = (
            platform  # Dictates how the switch_applications agent action works.
        )
        self.Tools_dict = Tools_dict

        # Screenshot size
        self.width = width 
        self.height = height

        # Coordinates used during ACI execution
        self.coords1 = None
        self.coords2 = None

        # Configure the visual grounding model responsible for coordinate generation
        self.grounding_model = Tools()
        self.grounding_model.register_tool("grounding", self.Tools_dict["grounding"]["provider"], self.Tools_dict["grounding"]["model"])

        self.grounding_width, self.grounding_height = self.grounding_model.tools["grounding"].get_grounding_wh()
        if self.grounding_width is None or self.grounding_height is None:
            self.grounding_width = self.width
            self.grounding_height = self.height

        # Configure text grounding agent
        self.text_span_agent = Tools()
        self.text_span_agent.register_tool("text_span", self.Tools_dict["text_span"]["provider"], self.Tools_dict["text_span"]["model"])
        
        # 获取GlobalState实例
        self.global_state: GlobalState = Registry.get("GlobalStateStore") # type: ignore

    # Given the state and worker's referring expression, use the grounding model to generate (x,y)
    def generate_coords(self, ref_expr: str, obs: Dict) -> List[int]:
        grounding_start_time = time.time()
        # Reset the grounding model state
        self.grounding_model.tools["grounding"].llm_agent.reset()

        # Configure the context, UI-TARS demo does not use system prompt
        prompt = f"Task: Visual Grounding - Locate and return coordinates\n Query:{ref_expr}\n Instructions: 1. Carefully analyze the provided screenshot image \n 2. Locate the EXACT element/area described in the query \n 3. Return ONLY the pixel coordinates [x, y] of one representative point within the target area \n 4. Choose a point that is clearly inside the described element/region \n 5. Coordinates must be integers representing pixel positions on the image \n 6. If the described element has multiple instances, select the most prominent or central one 7. - If this appears to be for dragging (selecting text, moving items, etc.): * For START points: Position slightly to the LEFT of text/content in empty space  * For END points: Position slightly to the RIGHT of text/content in empty space  * Avoid placing coordinates directly ON text characters to prevent text selection issues  * Keep offset minimal (3-5 pixels) - don't go too far from the target area  * Still return only ONE coordinate as requested \n Output Format: Return only two integers separated by comma, like: (900, 400)\n Important Notes: - Focus on the main descriptive elements in the query (colors, positions, objects) - Ignore any additional context that doesn't help locate the target - The returned point should be clickable/actionable within the target area \n CRITICAL REQUIREMENTS: - MUST return exactly ONE coordinate pair under ALL circumstances - NO explanations, NO multiple coordinates, NO additional text \n"
        response, total_tokens, cost_string = self.grounding_model.execute_tool("grounding", {"str_input": prompt, "img_input": obs["screenshot"]})
        logger.info(f"Grounding model tokens: {total_tokens}, cost: {cost_string}")
        grounding_end_time = time.time()
        grounding_duration = grounding_end_time - grounding_start_time
        logger.info(f"Grounding model execution time: {grounding_duration:.2f} seconds")
        logger.info(f"RAW GROUNDING MODEL RESPONSE: {response}")
        self.global_state.log_operation(
            module="grounding",
            operation="grounding_model_response",
            data={
                "tokens": total_tokens,
                "cost": cost_string,
                "content": response,
                "duration": grounding_duration
            }
        )
        # Generate and parse coordinates
        numericals = re.findall(r"\d+", response)
        assert len(numericals) >= 2
        return [int(numericals[0]), int(numericals[1])]
    
    # Takes a description based action and assigns the coordinates for any coordinate based action
    # Raises an error if function can't be parsed
    def assign_coordinates(self, plan: str, obs: Dict):

        # Reset coords from previous action generation
        self.coords1, self.coords2 = None, None

        try:
            # Extract the function name and args
            action = parse_single_code_from_string(plan.split("Grounded Action")[-1])
            function_name = re.match(r"(\w+\.\w+)\(", action).group(1) # type: ignore
            args = self.parse_function_args(action)
        except Exception as e:
            raise RuntimeError(f"Error in parsing grounded action: {e}") from e

        # arg0 is a description
        if (
            function_name in ["agent.click", "agent.doubleclick", "agent.move", "agent.scroll"]
            and len(args) >= 1
            and args[0] != None
        ):
            self.coords1 = self.generate_coords(args[0], obs)
        # arg0 and arg1 are descriptions
        elif function_name == "agent.drag" and len(args) >= 2:
            self.coords1 = self.generate_coords(args[0], obs)
            self.coords2 = self.generate_coords(args[1], obs)

    def reset_screen_size(self, width: int, height: int):
        self.width = width
        self.height = height
        
    # Resize from grounding model dim into OSWorld dim (1920 * 1080)
    def resize_coordinates(self, coordinates: List[int]) -> List[int]:
        return [
            round(coordinates[0] * self.width / self.grounding_width),
            round(coordinates[1] * self.height / self.grounding_height),
        ]

    # Given a generated ACI function, returns a list of argument values, where descriptions are at the front of the list
    def parse_function_args(self, function: str) -> List[str]:
        if not function or not isinstance(function, str):
            return []
        
        # This regex handles quoted strings and numeric arguments
        pattern = r'(\w+\.\w+)\((?:"([^"]*)")?(?:,\s*(\d+))?\)'
        match = re.match(pattern, function)
        if match:
            args = []
            # Add the string argument if present
            if match.group(2) is not None:
                args.append(match.group(2))
            # Add the numeric argument if present
            if match.group(3) is not None:
                args.append(int(match.group(3)))
            if args:
                return args
        
        # If the special handling didn't work, try the AST approach
        try:
            tree = ast.parse(function)
        except Exception as e:
            print(f"Failed to parse function: {function}")
            print(f"Exception: {e}")
            return []
        
        if not tree.body or not hasattr(tree.body[0], 'value'):
            return []
        
        call_node = tree.body[0].value # type: ignore
        if not isinstance(call_node, ast.Call):
            return []
        
        def safe_eval(node):
            if isinstance(node, ast.Constant):
                return node.value
            elif hasattr(ast, 'Str') and isinstance(node, ast.Str):
                return node.s
            else:
                try:
                    return ast.unparse(node)
                except Exception:
                    return str(node)
        
        positional_args = []
        try:
            positional_args = [safe_eval(arg) for arg in call_node.args]
        except Exception as e:
            print(f"Error processing positional args: {e}")
            positional_args = []
        
        keyword_args = {}
        try:
            keyword_args = {kw.arg: safe_eval(kw.value) for kw in call_node.keywords}
        except Exception as e:
            print(f"Error processing keyword args: {e}")
            keyword_args = {}
        
        res = []
        for key, val in keyword_args.items():
            if key and "description" in key:
                res.append(val)
        for arg in positional_args:
            res.append(arg)
        
        return res

    @agent_action
    def click(
        self,
        element_description: str,
        button: int = 1,
        holdKey: List[str] = [],
    ):
        """One click on the element
        Args:
            element_description:str, a detailed descriptions of which element to click on. This description should be at least a full sentence.
            button:int, which mouse button to press can be 1, 2, 4, 8, or 16, indicates which mouse button to press. 1 for left click, 2 for right click, 4 for middle click, 8 for back and 16 for forward. Add them together to press multiple buttons at once.
            holdKey:List[str], list of keys to hold while clicking.
        """
        x, y = self.resize_coordinates(self.coords1) # type: ignore
        
        actionDict = {
            "type": "Click",
            "x": x, # int
            "y": y, # int
            "element_description": element_description, # str
            "button": button,
            "holdKey": holdKey
        }
        return actionDict

    @agent_action
    def doubleclick(
        self,
        element_description: str,
        button: int = 1,
        holdKey: List[str] = [],
    ):
        """Double click on the element
        Args:
            element_description:str, a detailed descriptions of which element to double click on. This description should be at least a full sentence.
            button:int, which mouse button to press can be 1, 2, 4, 8, or 16, indicates which mouse button to press. 1 for left click, 2 for right click, 4 for middle click, 8 for back and 16 for forward. Add them together to press multiple buttons at once.
            holdKey:List[str], list of keys to hold while double clicking.
        """
        x, y = self.resize_coordinates(self.coords1) # type: ignore
        
        actionDict = {
            "type": "DoubleClick",
            "x": x, # int
            "y": y, # int
            "element_description": element_description, # str
            "button": button,
            "holdKey": holdKey
        }
        return actionDict

    @agent_action
    def move(
        self,
        element_description: str,
        holdKey: List[str] = [],
    ):
        """Move to the element or place
        Args:
            element_description:str, a detailed descriptions of which element or place to move the mouse to. This action only moves the mouse, it does not click. This description should be at least a full sentence.
            holdKey:List[str], list of keys to hold while moving the mouse.
        """
        x, y = self.resize_coordinates(self.coords1) # type: ignore
        
        actionDict = {
            "type": "Move",
            "x": x, # int
            "y": y, # int
            "element_description": element_description, # str
            "holdKey": holdKey
        }
        return actionDict

    @agent_action
    def scroll(
        self, 
        element_description: str, 
        clicks: int, 
        vertical: bool = True,
        holdKey: List[str] = [],
    ):
        """Scroll the element in the specified direction
        Args:
            element_description:str, a very detailed description of which element or where to place the mouse for scrolling. This description should be at least a full sentence.
            clicks:int, the number of clicks to scroll can be positive (for up and left) or negative (for down and right).
            vertical:bool, whether to vertical scrolling.
            holdKey:List[str], list of keys to hold while scrolling.
        """

        x, y = self.resize_coordinates(self.coords1) # type: ignore

        if vertical == True:
            actionDict = {
                "type": "Scroll",
                "x": x, # int
                "y": y, # int
                "element_description": element_description,
                "stepVertical": clicks,
                "holdKey": holdKey
            }
        else:
            actionDict = {
                "type": "Scroll",
                "x": x, # int
                "y": y, # int
                "element_description": element_description,
                "stepHorizontal": clicks,
                "holdKey": holdKey
            }
        return actionDict 

    @agent_action
    def drag(
        self, 
        starting_description: str, 
        ending_description: str, 
        holdKey: List[str] = [],
    ):
        """Drag from the starting description to the ending description
        Args:
            starting_description:str, a very detailed description of where to start the drag action. This description should be at least a full sentence.
            ending_description:str, a very detailed description of where to end the drag action. This description should be at least a full sentence.
            holdKey:List[str], list of keys to hold while dragging.
        """
        x1, y1 = self.resize_coordinates(self.coords1) # type: ignore
        x2, y2 = self.resize_coordinates(self.coords2) # type: ignore

        actionDict = {
            "type": "Drag",
            "startX": x1,
            "startY": y1,
            "endX": x2,
            "endY": y2,
            "holdKey": holdKey,
            "starting_description": starting_description,
            "ending_description": ending_description
        }
        return actionDict

    @agent_action
    def type(
        self,
        text: str = "",
    ):
        """Type text
        Args:
            text:str, the text to type.
        """
        actionDict = {
            "type": "TypeText",
            "text": text,
        }
        
        return actionDict

    
    @agent_action
    def hotkey(
        self, 
        keys: List[str] = [],
        duration: int = 0,
    ):
        """Press a hotkey combination
        Args:
            keys:List[str], the keys to press in combination in a list format. The list can contain multiple modifier keys (e.g. ctrl, alt, shift) but only one non-modifier key (e.g. ['ctrl', 'alt', 'c']).
            duration:int, duration in milliseconds, Range 1 <= value <= 5000. If specified, the hotkey will be held for a while and then released. If 0, the hotkey combination will use the default value in hardware interface.
        """
        # add quotes around the keys
        keys = [f"{key}" for key in keys]
        if 1 <= duration <= 5000:
            actionDict = {
                "type": "Hotkey",
                "keys": keys,
                "duration": duration,
            }
        else:
            actionDict = {
                "type": "Hotkey",
                "keys": keys,
            }

        return actionDict

    @agent_action
    def wait(
        self, 
        duration: int
    ):
        """Wait for a specified amount of time in milliseconds
        Args:
            duration:int the amount of time to wait in milliseconds
        """
        actionDict = {
            "type": "Wait",
            "duration": duration
        }
        return actionDict

    @agent_action
    def done(
        self,
        message: str = '',
    ):
        """End the current task with a success and the return message if needed"""
        self.returned_info = message
        actionDict = {
            "type": "Done",
            "message": message
        }
        return actionDict

    @agent_action
    def fail(
        self,
        message: str = '',
    ):
        """End the current task with a failure message, and replan the whole task."""
        actionDict = {
            "type": "Failed",
            "message": message
        }
        return actionDict
