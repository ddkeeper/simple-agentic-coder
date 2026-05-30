"""Custom exceptions for the agentic coder."""


class ToolExecutionError(Exception):
    """Raised when a tool fails to execute."""

    def __init__(self, tool_name: str, message: str):
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class ContextLimitError(Exception):
    """Raised when context window limit is exceeded and compaction fails."""

    def __init__(self, message: str = "Context limit exceeded"):
        super().__init__(message)
