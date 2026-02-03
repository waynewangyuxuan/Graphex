"""
Base agent class for LLM-based extraction.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from anthropic import Anthropic


@dataclass
class AgentResult:
    """Result from an agent execution."""

    success: bool
    output: Any
    errors: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for extraction agents.

    Provides common LLM interaction patterns.
    """

    def __init__(
        self,
        client: Optional[Anthropic] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ) -> None:
        """
        Initialize agent.

        Args:
            client: Anthropic client (creates new if not provided)
            model: Model to use for extraction
            max_tokens: Max tokens in response
        """
        self.client = client or Anthropic()
        self.model = model
        self.max_tokens = max_tokens

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

            # Call LLM
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.get_system_prompt(),
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Extract text content
            response_text = response.content[0].text

            # Parse output
            output = self.parse_output(response_text)

            return AgentResult(
                success=True,
                output=output,
                metrics={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            )

        except Exception as e:
            return AgentResult(
                success=False,
                output=None,
                errors=[str(e)],
            )
