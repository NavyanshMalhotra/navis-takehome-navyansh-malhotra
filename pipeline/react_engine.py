"""
ReAct Multi-Agent Engine for the Nevis Onboarding Platform.
Provides a structured Thought -> Action -> Observation -> Reflection loop
with deterministic tool dispatch and inter-agent communication channels.
"""

import json
import re
import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, List, Optional, Union
from pipeline.llm_client import llm_client, LLMClient

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., Any]
    args_schema: Optional[Dict[str, str]] = None

    def execute(self, **kwargs) -> str:
        try:
            res = self.func(**kwargs)
            if isinstance(res, (dict, list)):
                return json.dumps(res, indent=2, default=str)
            return str(res)
        except Exception as e:
            return f"Error executing tool '{self.name}': {e}"


@dataclass
class Agent:
    name: str
    aim: str
    system_prompt: str
    tools: List[Tool] = field(default_factory=list)

    def get_tool(self, name: str) -> Optional[Tool]:
        for t in self.tools:
            if t.name.lower() == name.lower():
                return t
        return None


@dataclass
class ReActStep:
    thought: str
    action: str
    tool_args: Dict[str, Any]
    observation: str


@dataclass
class ReActResult:
    agent_name: str
    final_answer: Any
    steps: List[ReActStep] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


class ReActEngine:
    def __init__(self, client: Optional[LLMClient] = None, max_steps: int = 5):
        self.client = client or llm_client
        self.max_steps = max_steps

    def run(self, agent: Agent, task_prompt: str, context: Optional[Dict[str, Any]] = None) -> ReActResult:
        """
        Executes a ReAct reasoning loop for the specified agent on a task.
        """
        tools_doc = []
        for t in agent.tools:
            args_str = json.dumps(t.args_schema) if t.args_schema else "{}"
            tools_doc.append(f"- {t.name}: {t.description}\n  Expected JSON Arguments: {args_str}")
        tools_text = "\n".join(tools_doc)

        system_instruction = (
            f"You are the {agent.name} in the Nevis wealth management onboarding platform.\n"
            f"Aim: {agent.aim}\n\n"
            f"Agent System Guidance:\n{agent.system_prompt}\n\n"
            f"Available Tools:\n{tools_text}\n\n"
            f"Execution Protocol:\n"
            f"Think step-by-step. In each step, provide:\n"
            f"Thought: <your rationale for what information is needed next>\n"
            f"Action: <tool_name>(<json_arguments>)\n\n"
            f"When you have resolved the task or have sufficient confidence:\n"
            f"Thought: <reflection on observations>\n"
            f"Final Answer: <your concluded answer or JSON structure>\n"
        )

        history: List[str] = []
        if context:
            history.append(f"Task Context:\n{json.dumps(context, indent=2, default=str)}")
        history.append(f"Task Prompt: {task_prompt}")

        steps: List[ReActStep] = []

        for step_idx in range(self.max_steps):
            full_prompt = "\n\n".join(history)
            try:
                response = self.client.generate_text(full_prompt, system_prompt=system_instruction)
            except Exception as e:
                logger.error("Agent %s LLM reasoning failed: %s", agent.name, e)
                return ReActResult(
                    agent_name=agent.name,
                    final_answer=None,
                    steps=steps,
                    success=False,
                    error=str(e),
                )

            # Check for Final Answer
            if "Final Answer:" in response:
                parts = response.split("Final Answer:", 1)
                thought = parts[0].replace("Thought:", "").strip() if "Thought:" in parts[0] else ""
                final_answer_text = parts[1].strip()

                # Try parsing JSON if final answer looks like JSON
                final_val = final_answer_text
                if final_answer_text.startswith("{") or final_answer_text.startswith("["):
                    try:
                        final_val = json.loads(final_answer_text)
                    except Exception:
                        pass

                steps.append(ReActStep(
                    thought=thought,
                    action="finish",
                    tool_args={},
                    observation="Task finalized by agent.",
                ))
                return ReActResult(
                    agent_name=agent.name,
                    final_answer=final_val,
                    steps=steps,
                    success=True,
                )

            # Parse Thought and Action
            thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|$)", response, re.DOTALL)
            thought = thought_match.group(1).strip() if thought_match else ""

            action_match = re.search(r"Action:\s*(\w+)\((.*?)\)", response, re.DOTALL)
            if not action_match:
                # No structured action found, look for plain Action: tool_name
                plain_action = re.search(r"Action:\s*(\w+)", response)
                if plain_action:
                    tool_name = plain_action.group(1).strip()
                    tool_args = {}
                else:
                    # Treat raw text as final answer if model spoke directly
                    return ReActResult(
                        agent_name=agent.name,
                        final_answer=response.strip(),
                        steps=steps,
                        success=True,
                    )
            else:
                tool_name = action_match.group(1).strip()
                raw_args = action_match.group(2).strip()
                try:
                    tool_args = json.loads(raw_args) if raw_args else {}
                except Exception:
                    # Fallback key-value extraction or treat as single query string
                    tool_args = {"query": raw_args}

            # Execute tool
            tool = agent.get_tool(tool_name)
            if tool:
                observation = tool.execute(**tool_args)
            else:
                observation = f"Tool '{tool_name}' not recognized. Available tools: {[t.name for t in agent.tools]}"

            steps.append(ReActStep(
                thought=thought,
                action=tool_name,
                tool_args=tool_args,
                observation=observation,
            ))

            history.append(f"Thought: {thought}\nAction: {tool_name}({json.dumps(tool_args)})\nObservation: {observation}")

        # If loop finishes without explicit Final Answer, return last observation
        last_obs = steps[-1].observation if steps else "Max reasoning steps reached."
        return ReActResult(
            agent_name=agent.name,
            final_answer=last_obs,
            steps=steps,
            success=True,
        )
