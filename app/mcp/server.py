"""Minimal MCP server scaffold."""

class MCPServer:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, func):
        self.tools[name] = func

    def call_tool(self, name, *args, **kwargs):
        tool = self.tools.get(name)
        if not tool:
            raise KeyError(name)
        return tool(*args, **kwargs)
