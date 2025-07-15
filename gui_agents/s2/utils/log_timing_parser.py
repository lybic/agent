import re
import sys
from typing import List, Dict, Optional

# Regular expressions for timing lines
TIMING_PATTERN = re.compile(r"\[(Timing|Step Timing)\] ([^:]+):? ?([\w\. ]*)execution time: ([\d\.]+) seconds")

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    
    @staticmethod
    def get_duration_color(duration: float) -> str:
        """Return color based on duration."""
        if duration > 50:
            return Colors.RED
        elif duration > 20:
            return Colors.YELLOW
        elif duration > 5:
            return Colors.GREEN
        else:
            return Colors.CYAN

class TimingEvent:
    def __init__(self, timestamp: str, timing_type: str, step: str, detail: str, duration: float, raw_line: str):
        self.timestamp = timestamp
        self.timing_type = timing_type  # Timing or Step Timing
        self.step = step.strip()
        self.detail = detail.strip()
        self.duration = duration
        self.raw_line = raw_line

    def __repr__(self):
        return f"[{self.timestamp}] [{self.timing_type}] {self.step} {self.detail} - {self.duration:.2f}s"

def parse_log_file(filepath: str) -> List[TimingEvent]:
    events = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '[Timing]' in line or '[Step Timing]' in line:
                # Extract timestamp (first [....])
                ts_match = re.match(r"\x1b\[1;33m\[(.*?) ", line)
                timestamp = ts_match.group(1) if ts_match else "UNKNOWN"
                timing = TIMING_PATTERN.search(line)
                if timing:
                    timing_type, step, detail, duration = timing.groups()
                    try:
                        duration = float(duration)
                    except Exception:
                        duration = -1
                    events.append(TimingEvent(timestamp, timing_type, step, detail, duration, line.strip()))
    return events

def get_step_level(step_name: str) -> int:
    """Return the indentation level for a step based on its name."""
    if step_name in ["agent.predict", "hwi.dispatchDict"]:
        return 0  # First level (root)
    elif step_name in ["manager.get_action_queue", "Worker.generate_next_action total"]:
        return 1  # Second level
    elif step_name in ["Manager._generate_step_by_step_plan", "Manager._generate_dag", 
                      "Worker.retrieve_episodic_experience", "Worker.traj_reflector", 
                      "Worker.action_generator"]:
        return 2  # Third level
    elif step_name in ["Manager.retrieve_narrative_experience", "Manager.retrieve_knowledge", 
                      "Manager.knowledge_fusion", "Manager.subtask_planner"]:
        return 3  # Fourth level - children of _generate_step_by_step_plan
    return 0  # Default to root level

def get_parent_step(step_name: str) -> Optional[str]:
    """Return the parent step name for a given step."""
    if step_name in ["manager.get_action_queue", "Worker.generate_next_action total"]:
        return "agent.predict"
    elif step_name in ["Manager._generate_step_by_step_plan", "Manager._generate_dag"]:
        return "manager.get_action_queue"
    elif step_name in ["Worker.retrieve_episodic_experience", "Worker.traj_reflector", "Worker.action_generator"]:
        return "Worker.generate_next_action total"
    elif step_name in ["Manager.retrieve_narrative_experience", "Manager.retrieve_knowledge", 
                      "Manager.knowledge_fusion", "Manager.subtask_planner"]:
        return "Manager._generate_step_by_step_plan"
    return None  # No parent

def get_step_color(step_name: str) -> str:
    """Return color for a step based on its name."""
    if step_name.startswith("agent"):
        return Colors.MAGENTA
    elif step_name.startswith("manager") or step_name.startswith("Manager"):
        return Colors.BLUE
    elif step_name.startswith("Worker"):
        return Colors.GREEN
    elif step_name.startswith("hwi"):
        return Colors.CYAN
    else:
        return Colors.RESET

def display_timing_tree(events: List[TimingEvent]):
    """Display events in chronological order with proper indentation to show relationships."""
    print("\n==== Timing Tree (in execution order) ====")
    
    # Track active parents at each level to know where to attach child nodes
    active_parents = {}
    
    # For each event, determine its level and display with appropriate indentation
    for event in events:
        level = get_step_level(event.step)
        parent = get_parent_step(event.step)
        
        # Mark this step as the active parent for its level
        if level >= 0:
            active_parents[level] = event.step
            
        # Create the indentation and connector based on level
        indent = "  " * level
        connector = "├─" if level > 0 else ""
        
        # Get colors for step name and duration
        step_color = get_step_color(event.step)
        duration_color = Colors.get_duration_color(event.duration)
        
        # Display the event with proper indentation and colors
        print(f"{indent}{connector} {step_color}{event.step}{Colors.RESET} ({duration_color}{event.duration:.2f}s{Colors.RESET})")

def group_and_display(events: List[TimingEvent]):
    """Display timing events in a tree structure following execution order."""
    display_timing_tree(events)

def main():
    if len(sys.argv) < 2:
        print("Usage: python log_timing_parser.py <logfile>")
        return
    filepath = sys.argv[1]
    events = parse_log_file(filepath)
    group_and_display(events)

if __name__ == "__main__":
    """
    python gui_agents/s2/utils/log_timing_parser.py logs/normal-20250715@164749.log
    """
    main()

"""
[2025-07-15] [Timing] Manager._generate_step_by_step_plan  - 96.23s
[2025-07-15] [Timing] Manager._generate_dag  - 12.49s
[2025-07-15] [Timing] manager.get_action_queue  - 108.82s
[2025-07-15] [Timing] Worker.retrieve_episodic_experience  - 0.00s
[2025-07-15] [Timing] Worker.action_generator  - 14.79s
[2025-07-15] [Timing] Worker.generate_next_action total  - 14.80s
[2025-07-15] [Step Timing] agent.predict  - 133.39s
[2025-07-15] [Step Timing] hwi.dispatchDict  - 0.17s
[2025-07-15] [Timing] manager.get_action_queue  - 0.00s
[2025-07-15] [Timing] Worker.traj_reflector  - 18.39s
[2025-07-15] [Timing] Worker.action_generator  - 15.05s
[2025-07-15] [Timing] Worker.generate_next_action total  - 33.45s
[2025-07-15] [Step Timing] agent.predict  - 41.22s
[2025-07-15] [Step Timing] hwi.dispatchDict  - 0.12s
[2025-07-15] [Timing] manager.get_action_queue  - 0.00s
[2025-07-15] [Timing] Worker.traj_reflector  - 28.50s
[2025-07-15] [Timing] Worker.action_generator  - 22.63s
[2025-07-15] [Timing] Worker.generate_next_action total  - 51.13s
[2025-07-15] [Step Timing] agent.predict  - 51.13s

==== Timing Events (tree view) ====
agent.predict (133.39s)
├─ manager.get_action_queue (108.82s)
│  ├─ Manager._generate_step_by_step_plan (96.23s)
│  └─ Manager._generate_dag (12.49s)
├─ Worker.generate_next_action total (14.80s)
│  ├─ Worker.retrieve_episodic_experience (0.00s)
│  ├─ Worker.action_generator (14.79s)
├─ hwi.dispatchDict (0.17s)

agent.predict (41.22s)
├─ manager.get_action_queue (0.00s)
├─ Worker.generate_next_action total (33.45s)
│  ├─ Worker.traj_reflector (18.39s)
│  ├─ Worker.action_generator (15.05s)
└─ hwi.dispatchDict (0.12s)

agent.predict (51.13s)
├─ manager.get_action_queue (0.00s)
├─ Worker.generate_next_action total (51.13s)
│  ├─ Worker.traj_reflector (28.50s)
│  └─ Worker.action_generator (22.63s)

"""