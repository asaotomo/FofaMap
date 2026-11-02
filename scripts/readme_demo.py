"""Real, bounded README examples. No mock data; scanning uses a temporary loopback fixture only.

mcp: two genuine FOFA records through stdio.
scan: one controlled HTTP request through an exact MCP plan; explicit flag required.
schedule: one real worker run, two records, no model, and isolated lifecycle cleanup.
rest: starts a loopback REST server and fetches one genuine FOFA record.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import socket
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console(highlight=False)
QUERY = 'domain="baidu.com"'


def say(zh, en, language):
    console.print(zh if language == "zh" else en)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def environment(folder):
    folder.mkdir(parents=True, exist_ok=True)
    return {**os.environ, "FOFAMAP_STATE_DIR": str(folder), "FOFAMAP_DATABASE_URL": f"sqlite:///{folder / 'jobs.db'}"}


async def start_service(command, env, port):
    process = await asyncio.create_subprocess_exec(
        *command, env=env, cwd=ROOT, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    for _ in range(100):
        if process.returncode is not None:
            raise RuntimeError("Local service exited during startup")
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.close()
            await writer.wait_closed()
            return process
        except OSError:
            await asyncio.sleep(0.1)
    process.terminate()
    await process.wait()
    raise TimeoutError("Local service did not start")


async def tool(client, name, args=None):
    result = await client.call_tool(name, args or {})
    if result.is_error:
        raise RuntimeError(str(result.content))
    return result.structured_content


async def poll(client, job_id, timeout=90):
    for _ in range(timeout * 2):
        job = (await tool(client, "fofa_job_status", {"job_id": job_id}))["data"]
        if job["status"] in {"completed", "failed", "cancelled"}:
            if job["status"] != "completed":
                raise RuntimeError(str(job.get("error")))
            return job
        await asyncio.sleep(0.5)
    await tool(client, "fofa_job_cancel", {"job_id": job_id})
    raise TimeoutError("Demo job was cancelled at its deadline")


async def mcp_demo(folder, language):
    env = environment(folder)
    async with Client(stdio_client(StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")], env=env))) as client:
        tools = sorted(row.name for row in (await client.list_tools()).tools)
        say("[bold cyan]MCP 真实任务：校验 → 查询 → 用量[/]", "[bold cyan]Real MCP task: validate → search → usage[/]", language)
        console.print(f"Loaded tools: {len(tools)}   protocol: {client.protocol_version}")
        checked = await tool(client, "fofa_validate_query", {"query": QUERY})
        console.print("fofa_validate_query:", checked["data"]["valid"], QUERY)
        data = await tool(
            client,
            "fofa_search",
            {
                "query": QUERY,
                "fields": ["host", "ip", "port", "protocol"],
                "size": 2,
                "max_records": 2,
                "max_pages": 1,
                "observe_cost": True,
            },
        )
        table = Table(title="fofa_search · actual FOFA records")
        for field in ["host", "ip", "port", "protocol"]:
            table.add_column(field)
        for row in data["records"]:
            table.add_row(*(str(row.get(field, "")) for field in ["host", "ip", "port", "protocol"]))
        console.print(table)
        console.print_json(
            data={
                "total": data["total"],
                "returned": len(data["records"]),
                "duplicates_removed": data["duplicates_removed"],
                "usage": {
                    name: data["usage"][name]
                    for name in ("requests", "records_fetched", "records_returned", "reported_consumed_fpoint", "charge_source")
                },
            }
        )
        console.print("Full tool catalogue: use fofa_fields / fofa_syntax / nuclei_guide or the README tool table.")
        (folder / "mcp-result.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))


async def scan_demo(folder, language):
    say("[bold cyan]受控扫描：仅本机临时 HTTP 靶标[/]", "[bold cyan]Controlled scan: temporary loopback HTTP fixture only[/]", language)

    async def respond(reader, writer):
        try:
            await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
            body = b"FOFAMAP_README_LOCAL_FIXTURE"
            writer.write(b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    target = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"
    try:
        with tempfile.TemporaryDirectory(prefix="fofamap-readme-template-") as temporary:
            template = Path(temporary) / "readme-local.yaml"
            template.write_text("""id: fofamap-readme-local
info:
  name: README Local Fixture
  author: hx0
  severity: info
http:
  - method: GET
    path:
      - "{{BaseURL}}/"
    matchers:
      - type: word
        words:
          - FOFAMAP_README_LOCAL_FIXTURE
""")
            env = {
                **environment(folder),
                "FOFAMAP_ENABLE_SCANNING": "true",
                "FOFAMAP_ALLOW_PRIVATE_NETWORK": "true",
                "FOFAMAP_SCAN_APPROVAL_SECRET": secrets.token_urlsafe(32),
                "FOFAMAP_NUCLEI_TEMPLATE_ALLOWLIST": str(template),
            }
            async with Client(
                stdio_client(StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")], env=env))
            ) as client:
                plan = (
                    await tool(
                        client,
                        "nuclei_plan",
                        {
                            "request": {
                                "targets": [target],
                                "templates": [str(template)],
                                "protocols": ["http"],
                                "severities": ["info"],
                                "rate_limit": 2,
                                "concurrency": 1,
                                "max_duration": 30,
                            }
                        },
                    )
                )["data"]
                identifier = plan["plan"]["id"]
                console.print("Target:", target, "\nTemplate: fofamap-readme-local · severity=info · rate=2/s · concurrency=1")
                console.print("nuclei_plan → exact scope approved by --approve-local-fixture")
                console.print("approval_token: [hidden; one-time only]", markup=False)
                await tool(client, "nuclei_execute", {"plan_id": identifier, "approval_token": plan["approval_token"]})
                job = await poll(client, identifier)
                assert job["result"]["finding_count"] == 1, job
                console.print("nuclei_execute → fofa_job_status:", job["status"])
                for row in job["result"]["grouped"]:
                    console.print(f"[green]MATCH[/] {row['template_id']} · {row['severity']} · {row['target']}")
                console.print("Finding count:", job["result"]["finding_count"], "\nArtifacts:", job["artifact_path"])
                for key, value in job["result"]["report"].items():
                    console.print(key + ":", value)
                safe = {key: job[key] for key in ["id", "status", "result", "artifact_path"]}
                (folder / "scan-result.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2))
    finally:
        server.close()
        await server.wait_closed()


async def schedule_demo(folder, language):
    env = environment(folder)
    # Worker owns only this temporary database. It cannot claim production jobs.
    worker = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "service.scheduler",
        "--interval",
        "1",
        cwd=ROOT,
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with Client(
            stdio_client(StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")], env=env))
        ) as client:
            say("[bold cyan]定时任务：真实到期执行与报告[/]", "[bold cyan]Schedule: real due-time execution and reports[/]", language)
            due = datetime.now(timezone.utc) + timedelta(seconds=3)
            request = {
                "name": "README bounded inventory",
                "task": "Map fixed query only, no active probing or scanning",
                "queries": [QUERY],
                "timing": {"recurrence": "once", "run_at": due.isoformat(), "timezone": "Asia/Shanghai"},
                "max_records": 2,
                "max_pages": 1,
                "analyze": False,
                "check_alive": False,
                "language": language,
            }
            created = (await tool(client, "fofa_schedule_create", {"request": request}))["data"]["schedule"]
            identifier = created["id"]
            try:
                console.print("Created:", identifier, "\nDue:", due.isoformat(), "\nQuery:", QUERY)
                for _ in range(100):
                    rows = (await tool(client, "fofa_schedule_history", {"schedule_id": identifier}))["data"]["runs"]
                    if rows and rows[0]["status"] in {"completed", "failed"}:
                        break
                    await asyncio.sleep(0.5)
                assert rows and rows[0]["status"] == "completed", rows
                row = rows[0]
                console.print("Worker status:", row["status"], " · records:", row["result"]["count"])
                for key, path in row["result"]["reports"].items():
                    console.print(key + ":", path)
                state = (await tool(client, "fofa_schedule_list"))["data"]["worker"]
                console.print("Worker local heartbeat:", state["heartbeat_local"])
                console.print("Timezone:", state["heartbeat_timezone"])
                (folder / "schedule-result.json").write_text(json.dumps(row, ensure_ascii=False, indent=2))
            finally:
                await tool(client, "fofa_schedule_stop", {"schedule_id": identifier})
                await tool(client, "fofa_schedule_delete", {"schedule_id": identifier})
                console.print("Temporary schedule stopped/deleted; reports retained. Production tasks untouched.")
    finally:
        worker.terminate()
        await worker.wait()


async def exposure_demo(folder, language):
    env = environment(folder)
    async with Client(stdio_client(StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")], env=env))) as client:
        say(
            "[bold cyan]暴露面评审：最多 1 条，扫描是模拟[/]",
            "[bold cyan]Exposure review: one record at most; scan is simulated[/]",
            language,
        )
        result = (
            await tool(client, "fofa_exposure_review", {"product": "Redis", "city": "Hefei", "size": 1, "max_records": 1, "sample": True})
        )["data"]
        console.print_json(
            data={name: result[name] for name in ["query", "mode", "time_basis", "population_size", "result_count", "usage", "scan"]}
        )
        assert result["scan"]["executed"] is False
        (folder / "exposure-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))


async def transports_demo(folder, language):
    from mcp_server import check_server

    evidence = []
    say(
        "[bold cyan]MCP 传输：真实启动、握手与工具检查[/]",
        "[bold cyan]MCP transports: real startup, handshake and tool checks[/]",
        language,
    )
    for transport, suffix in [("streamable-http", "/mcp"), ("sse", "/sse")]:
        port = free_port()
        env = environment(folder / transport)
        command = [sys.executable, str(ROOT / "mcp_server.py"), "--transport", transport, "--port", str(port)]
        process = await start_service(command, env, port)
        try:
            console.print("fofamap-mcp --transport", transport, "--host 127.0.0.1 --port", port)
            checked = await check_server(f"http://127.0.0.1:{port}{suffix}", expected_source=ROOT)
            evidence.append(checked)
            console.print_json(
                data={name: checked[name] for name in ["ok", "version", "build_date", "protocol_version", "tool_count", "quota_spent"]}
            )
        finally:
            process.terminate()
            await process.wait()
    (folder / "transports-result.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2))


async def rest_demo(folder, language):
    port = free_port()
    env = {**environment(folder), "FOFAMAP_PORT": str(port)}
    # No service token is sent to output; a loopback process still honors configured auth.
    token = os.getenv("FOFAMAP_SERVICE_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    process = await start_service([sys.executable, "-m", "service.api"], env, port)
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", headers=headers, timeout=90) as http:
            say("[bold cyan]REST：真实服务和只读查询[/]", "[bold cyan]REST: real service and read-only query[/]", language)
            schema = (await http.get("/openapi.json")).json()
            console.print("OpenAPI:", schema["info"]["title"], schema["info"]["version"])
            response = await http.post(
                "/v1/search", json={"query": QUERY, "fields": ["host", "ip", "port"], "size": 1, "max_records": 1, "max_pages": 1}
            )
            response.raise_for_status()
            data = response.json()
            console.print("POST /v1/search → HTTP", response.status_code)
            console.print_json(data=data)
            (folder / "rest-result.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    finally:
        process.terminate()
        await process.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=["mcp", "scan", "schedule", "rest", "exposure", "transports"])
    parser.add_argument("--output", type=Path, default=ROOT / "results/readme-demo")
    parser.add_argument("--language", choices=["zh", "en"], default="zh")
    parser.add_argument("--approve-local-fixture", action="store_true", help="Authorize exactly the temporary local scan created by scan")
    args = parser.parse_args()
    if args.task == "scan" and not args.approve_local_fixture:
        parser.error("scan requires --approve-local-fixture; no public targets can be supplied")
    asyncio.run(
        {
            "mcp": mcp_demo,
            "scan": scan_demo,
            "schedule": schedule_demo,
            "rest": rest_demo,
            "exposure": exposure_demo,
            "transports": transports_demo,
        }[args.task](args.output.expanduser().resolve(), args.language)
    )
