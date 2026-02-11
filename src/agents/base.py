"""
Base agent class for LLM-based extraction.

Supports multiple LLM providers through LiteLLM.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
import litellm

# Load .env file from project root
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)


@dataclass
class AgentResult:
    """Result from an agent execution."""

    success: bool
    output: Any
    errors: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


# Default model - can use any LiteLLM supported model
# Examples:
#   - "gemini/gemini-2.0-flash" (Google Gemini 2.0 Flash)
#   - "claude-sonnet-4-20250514" (Anthropic Claude)
#   - "gpt-4o" (OpenAI GPT-4)
DEFAULT_MODEL = "gemini/gemini-2.0-flash"


class BaseAgent(ABC):
    """
    Base class for extraction agents.

    Provides common LLM interaction patterns using LiteLLM.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> None:
        """
        Initialize agent.

        Args:
            model: LiteLLM model identifier (e.g., "gemini/gemini-2.0-flash")
            max_tokens: Max tokens in response
            **kwargs: Additional arguments for litellm.completion
        """
        self.model = model
        self.max_tokens = max_tokens
        self.extra_params = kwargs

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    @abstractmethod
    def format_input(self, **kwargs: Any) -> str:
        """Format input data into a user prompt."""
        pass

    @abstractmethod
    def parse_output(self, response: str) -> Any:
        """Parse LLM response into structured output."""
        pass

    def execute(self, **kwargs: Any) -> AgentResult:
        """
        Execute the agent.

        Args:
            **kwargs: Input data for the agent

        Returns:
            AgentResult with extracted data
        """
        try:
            # Format the prompt
            user_prompt = self.format_input(**kwargs)

            # Build messages for LiteLLM (OpenAI format)
            messages = [
                {"role": "system", "content": self.get_system_prompt()},
                {"role": "user", "content": user_prompt},
            ]

            # Call LLM through LiteLLM
            response = litellm.completion(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                **self.extra_params,
            )

            # Extract text content (OpenAI format)
            response_text = response.choices[0].message.content

            # Parse output
            output = self.parse_output(response_text)

            return AgentResult(
                success=True,
                output=output,
                metrics={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "model": response.model,
                },
            )

        except Exception as e:
            return AgentResult(
                success=False,
                output=None,
                errors=[str(e)],
            )
