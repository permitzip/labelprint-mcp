import asyncio
from pathlib import Path

from labelprint import mcp_server
from labelprint.paths import default_job_path, default_preview_path


def test_default_job_files_stay_in_cache() -> None:
    preview = default_preview_path()
    job = default_job_path()
    assert preview.parent == Path.home() / ".cache" / "labelprint"
    assert job.parent == preview.parent
    assert preview.name == "preview.png"


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
