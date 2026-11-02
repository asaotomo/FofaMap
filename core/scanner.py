"""Optional Nuclei worker. It accepts only fields from an approved ScanPlanRequest."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import shutil
import signal
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from core.nuclei_protocols import parse_scan_target
from core.scans import ScanPlanRequest, nuclei_severity_filter

NUCLEI_FOFA_ENV_KEYS = ("FOFA_EMAIL", "FOFA_KEY", "FOFA_API_KEY")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mK]")
_TARGETS_RE = re.compile(r"Targets loaded for current scan:\s*(\d+)", re.IGNORECASE)
_TEMPLATES_RE = re.compile(r"Templates loaded for current scan:\s*(\d+)", re.IGNORECASE)
_LOG_RE = re.compile(r"\[(?:INF|WRN|ERR|FTL|DBG)\]")
SEVERITY_ORDER = ("critical", "high", "medium", "low", "info", "unknown")
SEVERITY_RANK = {name: index for index, name in enumerate(SEVERITY_ORDER)}
SEVERITY_LABELS = {
    "critical": "严重",
    "high": "高危",
    "medium": "中危",
    "low": "低危",
    "info": "信息",
    "unknown": "未知",
}


async def _output_lines(source: asyncio.StreamReader) -> AsyncIterator[bytes]:
    """Drain arbitrary-size output lines with bounded memory; findings live in the JSONL file.

    readline() fails above StreamReader's limit. Keep only a bounded prefix for
    progress/log processing and discard the remainder through the next newline.
    """
    pending = bytearray()
    truncated = False
    max_line = 256 * 1024
    while chunk := await source.read(64 * 1024):
        for index, part in enumerate(chunk.split(b"\n")):
            if index:
                yield bytes(pending) + (b" [output line truncated]" if truncated else b"")
                pending.clear()
                truncated = False
            remaining = max_line - len(pending)
            pending.extend(part[:remaining])
            truncated = truncated or len(part) > remaining
    if pending or truncated:
        yield bytes(pending) + (b" [output line truncated]" if truncated else b"")


def nuclei_subprocess_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Drop FOFA credentials so Nuclei's uncover provider does not abort the scan."""
    env = dict(os.environ if base is None else base)
    for key in NUCLEI_FOFA_ENV_KEYS:
        env.pop(key, None)
    from core.nuclei_install import managed_binary, managed_directory

    if managed_binary().is_file() and (managed_directory() / "ready.json").is_file():
        env.setdefault("NUCLEI_TEMPLATES_DIR", str(managed_directory() / "templates"))
    return env


def resolve_nuclei_executable(explicit: str | None = None) -> str | None:
    """Prefer an explicit path, then env, then ./nuclei in cwd/project root, then PATH."""
    if explicit:
        return explicit
    env = os.environ.get("FOFAMAP_NUCLEI")
    if env:
        env_path = Path(env).expanduser()
        if env_path.is_file():
            return str(env_path)
    names = ("nuclei.exe", "nuclei") if os.name == "nt" else ("nuclei", "nuclei.exe")
    roots = [Path.cwd(), Path(__file__).resolve().parent.parent]
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        for name in names:
            candidate = resolved / name
            if candidate.is_file():
                return str(candidate)
    existing = shutil.which("nuclei") or shutil.which("nuclei.exe")
    if existing:
        return existing
    from core.nuclei_install import managed_binary

    managed = managed_binary()
    return str(managed) if managed.is_file() else None


def strip_nuclei_ansi(value: str) -> str:
    return _ANSI_RE.sub("", value).strip()


def is_nuclei_progress_line(line: str) -> bool:
    return bool(_LOG_RE.search(line) or _TARGETS_RE.search(line) or _TEMPLATES_RE.search(line))


@dataclass(frozen=True)
class NucleiFinding:
    template_id: str = ""
    name: str = ""
    severity: str = "unknown"
    host: str = ""
    matched_at: str = ""
    protocol: str = ""
    matcher_name: str = ""
    extracted: tuple[str, ...] = ()
    ip: str = ""
    description: str = ""
    remediation: str = ""

    @property
    def target(self) -> str:
        return self.matched_at or self.host

    @property
    def site(self) -> str:
        """Normalize HTTP URLs and TLS host:port matches to one asset hostname."""
        value = self.target.strip()
        parsed = urlparse(value if "://" in value else f"//{value}")
        return (parsed.hostname or value).lower()

    @property
    def details(self) -> tuple[str, ...]:
        if self.matcher_name:
            return (self.matcher_name, *self.extracted)
        return self.extracted


@dataclass(frozen=True)
class NucleiGroupedHit:
    target: str
    ip: str
    template_id: str
    name: str
    severity: str
    details: tuple[str, ...]
    count: int
    protocol: str = ""
    description: str = ""
    remediation: str = ""


@dataclass
class NucleiProgressEvent:
    line: str
    findings: int = 0
    loaded_targets: int | None = None
    loaded_templates: int | None = None
    elapsed_seconds: float = 0.0
    percent: float | None = None
    requests: int | None = None
    total_requests: int | None = None
    rps: float | None = None
    errors: int | None = None


@dataclass
class NucleiScanResult:
    artifact: Path
    findings: list[NucleiFinding] = field(default_factory=list)
    target_count: int = 0
    duration_seconds: float = 0.0
    summary_path: Path | None = None
    loaded_targets: int | None = None
    loaded_templates: int | None = None
    warnings: list[str] = field(default_factory=list)
    statistics: dict = field(default_factory=dict)
    completed: bool = True

    @property
    def host_count(self) -> int:
        return len({item.site for item in self.findings if item.site})

    @property
    def severity_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.findings:
            key = item.severity if item.severity in SEVERITY_RANK else "unknown"
            counts[key] = counts.get(key, 0) + 1
        return {name: counts[name] for name in SEVERITY_ORDER if name in counts}

    def grouped(self) -> list[NucleiGroupedHit]:
        buckets: dict[tuple[str, str, str], list[NucleiFinding]] = {}
        for item in self.findings:
            buckets.setdefault((item.target, item.template_id, item.severity), []).append(item)
        hits: list[NucleiGroupedHit] = []
        for (target, template_id, severity), items in buckets.items():
            labels: list[str] = []
            seen: set[str] = set()
            for item in items:
                for label in item.details:
                    if label and label not in seen:
                        seen.add(label)
                        labels.append(label)
            first = items[0]
            hits.append(
                NucleiGroupedHit(
                    target=target,
                    ip=first.ip,
                    template_id=template_id,
                    name=first.name or template_id,
                    severity=severity,
                    protocol=first.protocol,
                    details=tuple(labels),
                    count=len(items),
                    description=first.description,
                    remediation=first.remediation,
                )
            )
        hits.sort(key=lambda hit: (SEVERITY_RANK.get(hit.severity, 99), hit.target))
        return hits

    def headline(self) -> str:
        if not self.completed:
            return f"扫描未完成：计划 {self.target_count:,} 个目标，已记录 {len(self.findings):,} 条命中（部分结果）。"
        scanned = self.loaded_targets or self.target_count
        if not self.findings:
            if self.warnings:
                return f"已处理 {scanned:,} 个目标，未发现命中；存在扫描环境或请求异常，结果不充分，需复核。"
            return f"已扫描 {scanned:,} 个目标，未发现命中。"
        counts = "、".join(f"{SEVERITY_LABELS.get(name, name)} {count:,}" for name, count in self.severity_counts.items())
        return f"已扫描 {scanned:,} 个目标，命中 {len(self.findings):,} 条（{counts}），涉及 {self.host_count:,} 个站点。"

    def to_job_payload(self) -> dict[str, object]:
        return {
            "headline": self.headline(),
            "finding_count": len(self.findings),
            "target_count": self.target_count,
            "loaded_targets": self.loaded_targets,
            "loaded_templates": self.loaded_templates,
            "host_count": self.host_count,
            "protocol_counts": {
                protocol: sum(item.protocol == protocol for item in self.findings)
                for protocol in sorted({item.protocol for item in self.findings if item.protocol})
            },
            "severity_counts": self.severity_counts,
            "summary_path": str(self.summary_path) if self.summary_path else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "assessment": "partial" if not self.completed else "inconclusive" if self.warnings and not self.findings
                          else "matches" if self.findings else "no_matches",
            "completed": self.completed,
            "warnings": self.warnings,
            "statistics": self.statistics,
            "grouped": [
                {
                    "target": hit.target,
                    "template_id": hit.template_id,
                    "protocol": hit.protocol,
                    "severity": hit.severity,
                    "description": hit.description,
                    "remediation": hit.remediation,
                    "name": hit.name,
                    "details": list(hit.details),
                    "count": hit.count,
                }
                for hit in self.grouped()[:50]
            ],
        }


class _JsonlLineCounter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.offset = 0
        self.count = 0
        self._partial = b""

    def refresh(self) -> int:
        if not self.path.exists():
            return self.count
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            chunk = handle.read()
            self.offset = handle.tell()
        buffer = self._partial + chunk
        lines = buffer.split(b"\n")
        self._partial = lines[-1]
        for line in lines[:-1]:
            if line.strip():
                self.count += 1
        return self.count


def parse_nuclei_jsonl(path: Path) -> list[NucleiFinding]:
    if not path.exists():
        return []
    findings: list[NucleiFinding] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict):
                continue
            info = item.get("info") if isinstance(item.get("info"), dict) else {}
            extracted = item.get("extracted-results") or []
            if isinstance(extracted, str):
                extracted = [extracted]
            findings.append(
                NucleiFinding(
                    template_id=str(item.get("template-id") or ""),
                    name=str(info.get("name") or item.get("template-id") or ""),
                    protocol=str(item.get("type") or ""),
                    severity=str(info.get("severity") or item.get("severity") or "unknown").lower(),
                    host=str(item.get("host") or ""),
                    matched_at=str(item.get("matched-at") or item.get("url") or ""),
                    matcher_name=str(item.get("matcher-name") or ""),
                    extracted=tuple(str(value) for value in extracted if value),
                    ip=str(item.get("ip") or ""),
                    description=" ".join(str(info.get("description") or "").split()),
                    remediation=" ".join(str(info.get("remediation") or "").split()),
                )
            )
    return findings


def format_nuclei_summary_markdown(result: NucleiScanResult, *, preview: int = 80) -> str:
    lines = [
        "# Nuclei 扫描摘要",
        "",
        result.headline(),
        "",
        f"- 目标数量：{result.target_count:,}",
        f"- 命中条数：{len(result.findings):,}",
        f"- 涉及站点：{result.host_count:,}",
        f"- 耗时：{result.duration_seconds:.1f}s",
        f"- 原始结果：`{result.artifact}`",
        "",
    ]
    if result.warnings:
        lines.extend(["## 扫描环境与覆盖限制", "", *[f"- {warning}" for warning in result.warnings], ""])
    if result.severity_counts:
        lines.extend(["## 严重级别", "", "| 级别 | 数量 |", "|---|---:|"])
        for name, count in result.severity_counts.items():
            lines.append(f"| {SEVERITY_LABELS.get(name, name)} (`{name}`) | {count:,} |")
        lines.append("")
    grouped = result.grouped()
    if not grouped:
        lines.extend(["未发现可展示的命中项。", ""])
        return "\n".join(lines)
    lines.extend(
        [
            "## 按站点汇总",
            "",
            "| 严重级别 | 站点 | 检测项 | 命中详情 |",
            "|---|---|---|---|",
        ]
    )
    for hit in grouped[:preview]:
        details = ", ".join(hit.details) if hit.details else f"{hit.count} 条命中"
        lines.append(f"| {SEVERITY_LABELS.get(hit.severity, hit.severity)} | {hit.target} | {hit.name or hit.template_id} | {details} |")
    if len(grouped) > preview:
        lines.extend(["", f"> 仅展示前 {preview:,} 个站点；完整命中见 `{result.artifact}`。"])
    lines.append("")
    return "\n".join(lines)


def write_nuclei_summary(result: NucleiScanResult) -> Path:
    path = result.artifact.with_name("nuclei_summary.md")
    path.write_text(format_nuclei_summary_markdown(result), encoding="utf-8")
    result.summary_path = path
    result.artifact.with_name("scan-metadata.json").write_text(
        json.dumps({"warnings": result.warnings, "statistics": result.statistics, "completed": result.completed,
                    "loaded_targets": result.loaded_targets, "loaded_templates": result.loaded_templates}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_nuclei_result(path: Path, *, target_count: int = 0) -> NucleiScanResult:
    artifact = Path(path)
    metadata = artifact.with_name("scan-metadata.json")
    try:
        data = json.loads(metadata.read_text(encoding="utf-8")) if metadata.is_file() else {}
    except (OSError, ValueError):
        data = {}
    return NucleiScanResult(artifact=artifact, findings=parse_nuclei_jsonl(artifact), target_count=target_count,
                            warnings=data.get("warnings", []), statistics=data.get("statistics", {}),
                            loaded_targets=data.get("loaded_targets"), loaded_templates=data.get("loaded_templates"),
                            completed=data.get("completed", True))


def build_nuclei_command(executable: str, plan: ScanPlanRequest, targets_path: Path, result_path: Path) -> list[str]:
    import socket

    # Old clistats versions cannot poll their own metrics when port=0. Allocate a real free local port.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        metrics_port = probe.getsockname()[1]
    command = [
        executable,
        "-l",
        str(targets_path),
        "-jsonl",
        "-ot",
        "-o",
        str(result_path),
        "-nc",
        "-duc",
        "-dr",
        "-no-stdin",
        "-stats", "-sj", "-si", "1", "-mp", str(metrics_port),
        "-rl",
        str(plan.rate_limit),
        "-c",
        str(plan.concurrency),
        "-timeout",
        str(plan.request_timeout),
        "-retries",
        str(plan.retries),
    ]
    if not plan.allow_oast:
        command.append("-ni")
    if plan.protocols:
        command.extend(["-pt", ",".join(plan.protocols)])
    for enabled, flag in ((plan.enable_headless, "-headless"), (plan.enable_code, "-code"), (plan.enable_file, "-file")):
        if enabled:
            command.append(flag)
    severity_filter = nuclei_severity_filter(
        plan.template_ids,
        plan.severities,
        all_severities=plan.all_severities,
    )
    if severity_filter:
        command.extend(["-severity", ",".join(severity_filter)])
    for template in plan.templates:
        command.extend(["-t", template])
    for template_id in plan.template_ids:
        command.extend(["-id", template_id])
    return command


class NucleiScanner:
    def __init__(self, executable: str | None = None) -> None:
        self.executable = resolve_nuclei_executable(executable)

    @staticmethod
    def _target(value: str) -> str:
        return parse_scan_target(value).nuclei_input

    async def run_plan(
        self,
        plan: ScanPlanRequest,
        output_dir: Path,
        *,
        on_progress: Callable[[NucleiProgressEvent], None] | None = None,
    ) -> NucleiScanResult:
        if not self.executable:
            raise RuntimeError("未安装 Nuclei；请在交互扫描中选择 Y 安装，或手动安装后重试。")
        output_dir.mkdir(parents=True, exist_ok=True)
        targets_path = output_dir / "targets.txt"
        result_path = output_dir / "nuclei.jsonl"
        targets_path.write_text("\n".join(self._target(value) for value in plan.targets) + "\n", encoding="utf-8")
        command = build_nuclei_command(self.executable, plan, targets_path, result_path)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=1024 * 1024,
            env=nuclei_subprocess_env(),
            **({"start_new_session": True} if os.name != "nt" else {}),
        )
        stderr_lines: list[str] = []
        loaded_targets: int | None = None
        loaded_templates: int | None = None
        counter = _JsonlLineCounter(result_path)
        started = time.monotonic()
        statistics: dict = {}
        latest = "正在启动 Nuclei…"

        def emit() -> None:
            if on_progress:
                on_progress(NucleiProgressEvent(
                    line=latest, findings=counter.refresh(), loaded_targets=loaded_targets,
                    loaded_templates=loaded_templates, elapsed_seconds=time.monotonic() - started,
                    percent=statistics.get("percent"), requests=statistics.get("requests"),
                    total_requests=statistics.get("total"), rps=statistics.get("rps"), errors=statistics.get("errors"),
                ))

        def handle_line(text: str) -> None:
            nonlocal loaded_targets, loaded_templates, latest
            cleaned = strip_nuclei_ansi(text)
            if not cleaned:
                return
            if cleaned.startswith("{"):
                try:
                    data = json.loads(cleaned)
                    if "requests" not in data or "template-id" in data:
                        return
                    for name in ("percent", "requests", "total", "rps", "errors"):
                        if data.get(name) is not None:
                            statistics[name] = float(str(data[name]).rstrip("%")) if name in {"percent", "rps"} else int(data[name])
                    statistics["percent"] = min(100.0, max(0.0, statistics.get("percent", 0)))
                    emit()
                    return
                except (ValueError, TypeError):
                    return
            latest = cleaned[:4000]
            stderr_lines.append(latest)
            if len(stderr_lines) > 200:
                del stderr_lines[0]
            match = _TARGETS_RE.search(cleaned)
            if match:
                loaded_targets = int(match.group(1))
            match = _TEMPLATES_RE.search(cleaned)
            if match:
                loaded_templates = int(match.group(1))
            if is_nuclei_progress_line(cleaned):
                emit()

        async def collect() -> int:
            stream = getattr(process, "stderr", None)
            if stream is not None:
                async def read(source):
                    if source is None:
                        return
                    async for raw in _output_lines(source):
                        handle_line(raw.decode(errors="replace"))

                await asyncio.gather(read(stream), read(getattr(process, "stdout", None)))
                return await process.wait()
            _, stderr = await process.communicate()
            for line in stderr.decode(errors="replace").splitlines():
                handle_line(line)
            return process.returncode

        async def heartbeat():
            while True:
                await asyncio.sleep(1)
                emit()

        def save_partial():
            result_path.touch(exist_ok=True)
            write_nuclei_summary(NucleiScanResult(
                artifact=result_path, findings=parse_nuclei_jsonl(result_path), target_count=len(plan.targets),
                duration_seconds=time.monotonic() - started, loaded_targets=loaded_targets, loaded_templates=loaded_templates,
                statistics=statistics, completed=False,
                warnings=["扫描被取消、超时或异常中断，仅保留部分输出；加载目标数不代表完成检测数量。"],
            ))

        ticker = asyncio.create_task(heartbeat())
        try:
            returncode = await asyncio.wait_for(collect(), timeout=plan.max_duration)
        except (Exception, asyncio.CancelledError):
            if process.returncode is None:
                pid = getattr(process, "pid", None)
                try:
                    if os.name != "nt" and isinstance(pid, int):
                        os.killpg(pid, signal.SIGKILL)
                    else:
                        process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()
            save_partial()
            raise
        finally:
            ticker.cancel()
            await asyncio.gather(ticker, return_exceptions=True)
            (output_dir / "nuclei.log").write_text("\n".join(stderr_lines), encoding="utf-8")
        duration = time.monotonic() - started
        if returncode != 0:
            save_partial()
            raise RuntimeError(f"Nuclei 退出码 {returncode}：{''.join(stderr_lines)[-1000:]}")
        if loaded_templates == 0 or loaded_targets == 0:
            save_partial()
            raise RuntimeError("Nuclei did not load any templates or targets; the scan was not completed")
        result_path.touch(exist_ok=True)
        warnings = []
        if statistics.get("errors", 0):
            warnings.append(f"Nuclei 报告 {statistics['errors']} 个请求错误；未成功检测的服务不能判断为无风险。")
        if any(re.search(r"handshake|connection refused|no such host|context deadline|could not.*resolv", line, re.I)
               for line in stderr_lines):
            warnings.append("日志包含连接、DNS 或 TLS 异常；请检查代理/网络和服务可达性。")
        if loaded_targets is not None:
            warnings.extend(await _diagnose_targets(plan.targets))
        result = NucleiScanResult(
            artifact=result_path,
            findings=parse_nuclei_jsonl(result_path),
            target_count=len(plan.targets),
            duration_seconds=duration,
            loaded_targets=loaded_targets,
            loaded_templates=loaded_templates,
            warnings=warnings,
            statistics=statistics,
        )
        write_nuclei_summary(result)
        return result


async def inspect_nuclei_templates(keyword: str = "", protocol: str = "", limit: int = 50) -> dict:
    """Enumerate installed templates through Nuclei's list mode; never supply a target."""
    import yaml

    from core.nuclei_protocols import NUCLEI_PROTOCOLS

    if protocol and protocol not in NUCLEI_PROTOCOLS:
        raise ValueError("Unsupported template protocol")
    executable = resolve_nuclei_executable()
    if not executable:
        raise ValueError("Nuclei is not installed")
    command = [executable, "-tl", "-duc", "-nc"]
    if protocol:
        command.extend(["-pt", protocol])
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=nuclei_subprocess_env()
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=30)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError("Template listing timed out") from None
    raw = strip_nuclei_ansi(output.decode(errors="replace"))
    if process.returncode:
        raise RuntimeError("Nuclei template listing failed: " + raw[-500:])
    match = re.search(r"templates for (.+)", raw)
    root = Path(match.group(1).strip()).expanduser() if match else None
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.endswith((".yaml", ".yml")) or line.startswith("["):
            continue
        path = Path(line)
        if not path.is_absolute() and root:
            path = root / path
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            raw_template = path.read_text(encoding="utf-8")
            term = keyword.split(":", 1)[-1].strip()
            if term and not re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", raw_template, re.I):
                continue
            data = yaml.safe_load(raw_template)
            if not isinstance(data, dict):
                continue
            info = data.get("info") or {}
            tags = info.get("tags") or []
            tags = tags.split(",") if isinstance(tags, str) else tags
            selected = (
                ",".join(map(str, tags))
                if keyword.startswith("tag:")
                else " ".join([str(data.get("id", "")), str(info.get("name", "")), ",".join(map(str, tags))])
            )
            if term and not re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", selected, re.I):
                continue
            kinds = [key for key in NUCLEI_PROTOCOLS if key in data]
            if "network" in data:
                kinds.append("tcp")
            rows.append(
                {
                    "id": data.get("id"),
                    "name": info.get("name"),
                    "severity": info.get("severity"),
                    "protocols": sorted(kinds),
                    "tags": tags,
                    "path": str(path),
                    "network_ports": [block.get("port") for block in data.get("tcp", data.get("network", [])) if isinstance(block, dict)],
                }
            )
        except (ValueError, OSError, yaml.YAMLError):
            continue
        if len(rows) >= max(1, min(limit, 200)):
            break
    return {
        "templates": rows,
        "returned": len(rows),
        "limit": max(1, min(limit, 200)),
        "root": str(root) if root else None,
        "note": "Inspect template-defined hosts and ports before approval. Listing does not authorize or execute them.",
    }


async def _diagnose_targets(targets: list[str]) -> list[str]:
    """Flag benchmarking/fake-IP answers without changing the user's proxy or network settings."""
    import socket

    hosts = {parse_scan_target(target).host for target in targets}
    semaphore = asyncio.Semaphore(20)

    async def check(host):
        async with semaphore:
            try:
                addresses = await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM), timeout=3)
                return any(ipaddress.ip_address(item[4][0]) in ipaddress.ip_network("198.18.0.0/15") for item in addresses)
            except (OSError, asyncio.TimeoutError, ValueError):
                return False

    flags = await asyncio.gather(*(check(host) for host in hosts))
    if any(flags):
        return ["目标域名解析到 198.18.0.0/15（基准测试网段，常见于 fake-IP 代理）；请核验 DNS/代理链路，零命中不能当作扫描充分。"]
    return []
