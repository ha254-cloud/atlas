class ToolRegistry:
    """
    Central registry for all MCP tools.
    Tools register themselves by name; the server dispatches by name.
    Adding a new capability is a one-line registration — nothing else changes.
    """

    def __init__(self):
        self._tools: dict[str, object] = {}

    def register(self, tool) -> None:
        """Register a tool instance. The tool must expose a `name` attribute."""
        self._tools[tool.name] = tool

    def get(self, name: str):
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown MCP tool: '{name}'")
        return tool

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


# Module-level singleton — imported everywhere
registry = ToolRegistry()
