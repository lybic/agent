import json
import re
import tiktoken
import numpy as np

from typing import Tuple, List, Union, Dict

from pydantic import BaseModel, ValidationError

import pickle


class Node(BaseModel):
    name: str
    info: str


class Dag(BaseModel):
    nodes: List[Node]
    edges: List[List[Node]]


NUM_IMAGE_TOKEN = 1105  # Value set of screen of size 1920x1080 for openai vision

def calculate_tokens(messages, num_image_token=NUM_IMAGE_TOKEN) -> Tuple[int, int]:

    num_input_images = 0
    output_message = messages[-1]

    input_message = messages[:-1]

    input_string = """"""
    for message in input_message:
        input_string += message["content"][0]["text"] + "\n"
        if len(message["content"]) > 1:
            num_input_images += 1

    input_text_tokens = get_input_token_length(input_string)

    input_image_tokens = num_image_token * num_input_images

    output_tokens = get_input_token_length(output_message["content"][0]["text"])

    return (input_text_tokens + input_image_tokens), output_tokens

def parse_dag(text):
    """
    Try extracting JSON from <json>…</json> tags first;
    if not found, try ```json … ``` Markdown fences.
    If both fail, try to parse the entire text as JSON.
    """
    import logging
    logger = logging.getLogger("desktopenv.agent")

    def _extract(pattern):
        m = re.search(pattern, text, re.DOTALL)
        return m.group(1).strip() if m else None

    # 1) look for <json>…</json>
    json_str = _extract(r"<json>(.*?)</json>")
    # 2) fallback to ```json … ```
    if json_str is None:
        json_str = _extract(r"```json\s*(.*?)\s*```")
        if json_str is None:
            # 3) try other possible code block formats
            json_str = _extract(r"```\s*(.*?)\s*```")

    # 4) if still not found, try to parse the entire text
    if json_str is None:
        logger.warning("JSON markers not found, attempting to parse entire text")
        json_str = text.strip()

    # Log the extracted JSON string
    logger.debug(f"Extracted JSON string: {json_str[:100]}...")

    try:
        # Try to parse as JSON directly
        payload = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        
        # Try to fix common JSON format issues
        try:
            # Replace single quotes with double quotes
            fixed_json = json_str.replace("'", "\"")
            payload = json.loads(fixed_json)
            logger.info("Successfully fixed JSON by replacing single quotes with double quotes")
        except json.JSONDecodeError:
            # Try to find and extract possible JSON objects
            try:
                # Look for content between { and }
                match = re.search(r"\{(.*)\}", json_str, re.DOTALL)
                if match:
                    fixed_json = "{" + match.group(1) + "}"
                    payload = json.loads(fixed_json)
                    logger.info("Successfully fixed JSON by extracting JSON object")
                else:
                    logger.error("Unable to fix JSON format")
                    return None
            except Exception:
                logger.error("All JSON fixing attempts failed")
        return None

    # Check if payload contains dag key
    if "dag" not in payload:
        logger.warning("'dag' key not found in JSON, attempting to use entire JSON object")
        # If no dag key, try to use the entire payload
        try:
            # Check if payload directly conforms to Dag structure
            if "nodes" in payload and "edges" in payload:
                return Dag(**payload)
            else:
                # Iterate through top-level keys to find possible dag structure
                for key, value in payload.items():
                    if isinstance(value, dict) and "nodes" in value and "edges" in value:
                        logger.info(f"Found DAG structure in key '{key}'")
                        return Dag(**value)
                
                logger.error("Could not find valid DAG structure in JSON")
                return None
        except ValidationError as e:
            logger.error(f"Data structure validation error: {e}")
        return None

    # Normal case, use value of dag key
    try:
        return Dag(**payload["dag"])
    except ValidationError as e:
        logger.error(f"DAG data structure validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unknown error parsing DAG: {e}")
        return None


def parse_single_code_from_string(input_string):
    input_string = input_string.strip()
    if input_string.strip() in ["WAIT", "DONE", "FAIL"]:
        return input_string.strip()

    pattern = r"```(?:\w+\s+)?(.*?)```"
    matches = re.findall(pattern, input_string, re.DOTALL)
    codes = []
    for match in matches:
        match = match.strip()
        commands = ["WAIT", "DONE", "FAIL"]
        if match in commands:
            codes.append(match.strip())
        elif match.split("\n")[-1] in commands:
            if len(match.split("\n")) > 1:
                codes.append("\n".join(match.split("\n")[:-1]))
            codes.append(match.split("\n")[-1])
        else:
            codes.append(match)
    if len(codes) > 0:
        return codes[0]
    # The pattern matches function calls with balanced parentheses and quotes
    code_match = re.search(r"(\w+\.\w+\((?:[^()]*|\([^()]*\))*\))", input_string)
    if code_match:
        return code_match.group(1)
    lines = [line.strip() for line in input_string.splitlines() if line.strip()]
    if lines:
        return lines[0]
    return "fail"


def get_input_token_length(input_string):
    enc = tiktoken.encoding_for_model("gpt-4")
    tokens = enc.encode(input_string)
    return len(tokens)


def sanitize_code(code):
    # This pattern captures the outermost double-quoted text
    if "\n" in code:
        pattern = r'(".*?")'
        # Find all matches in the text
        matches = re.findall(pattern, code, flags=re.DOTALL)
        if matches:
            # Replace the first occurrence only
            first_match = matches[0]
            code = code.replace(first_match, f'"""{first_match[1:-1]}"""', 1)
    return code


def extract_first_agent_function(code_string):
    # Regular expression pattern to match 'agent' functions with any arguments, including nested parentheses
    pattern = r'agent\.[a-zA-Z_]+\((?:[^()\'"]|\'[^\']*\'|"[^"]*")*\)'

    # Find all matches in the string
    matches = re.findall(pattern, code_string)

    # Return the first match if found, otherwise return None
    return matches[0] if matches else None


def load_knowledge_base(kb_path: str) -> Dict:
    try:
        with open(kb_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading knowledge base: {e}")
        return {}


def clean_empty_embeddings(embeddings: Dict) -> Dict:
    to_delete = []
    for k, v in embeddings.items():
        arr = np.array(v)
        if arr.size == 0 or arr.shape == () or (
            isinstance(v, list) and v and isinstance(v[0], str) and v[0].startswith('Error:')
        ) or (isinstance(v, str) and v.startswith('Error:')):
            to_delete.append(k)
    for k in to_delete:
        del embeddings[k]
    return embeddings


def load_embeddings(embeddings_path: str) -> Dict:
    try:
        with open(embeddings_path, "rb") as f:
            embeddings = pickle.load(f)
        embeddings = clean_empty_embeddings(embeddings)
        return embeddings
    except Exception as e:
        # print(f"Error loading embeddings: {e}")
        print(f"Empty embeddings file: {embeddings_path}")
        return {}


def save_embeddings(embeddings_path: str, embeddings: Dict):
    try:
        import os
        os.makedirs(os.path.dirname(embeddings_path), exist_ok=True)
        with open(embeddings_path, "wb") as f:
            pickle.dump(embeddings, f)
    except Exception as e:
        print(f"Error saving embeddings: {e}")


def agent_log_to_string(agent_log: List[Dict]) -> str:
    """
    Converts a list of agent log entries into a single string for LLM consumption.

    Args:
        agent_log: A list of dictionaries, where each dictionary is an agent log entry.

    Returns:
        A formatted string representing the agent log.
    """
    if not agent_log:
        return "No agent log entries yet."

    log_strings = ["[AGENT LOG]"]
    for entry in agent_log:
        entry_id = entry.get("id", "N/A")
        entry_type = entry.get("type", "N/A").capitalize()
        content = entry.get("content", "")
        log_strings.append(f"[Entry {entry_id} - {entry_type}] {content}")

    return "\n".join(log_strings)