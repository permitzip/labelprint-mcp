import asyncio

from labelprint import mcp_server


def test_tools_are_registered() -> None:
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names >= {
        "labelprint_doctor",
        "labelprint_list_ports",
        "labelprint_status",
        "labelprint_render",
        "labelprint_print",
    }


def test_print_requires_confirm() -> None:
    raw = mcp_server.labelprint_print(confirm=False, title="TEST")
    assert "confirm=false" in raw
