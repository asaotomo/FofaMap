"""Install official Nuclei binaries only after the caller obtained user consent."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import re
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from zipfile import ZipFile

import httpx

HOSTS = {"github.com", "api.github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}


def managed_directory() -> Path:
    if os.getenv("FOFAMAP_TOOLS_DIR"):
        return Path(os.environ["FOFAMAP_TOOLS_DIR"]).expanduser() / "nuclei"
    if os.name == "nt":
        return Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData/Local") / "FofaMap/tools/nuclei"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/FofaMap/tools/nuclei"
    return Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local/share") / "fofamap/tools/nuclei"


def managed_binary() -> Path:
    return managed_directory() / ("nuclei.exe" if os.name == "nt" else "nuclei")


def needs_setup(executable: str | None) -> bool:
    return not executable or (
        Path(executable).resolve() == managed_binary().resolve() and not (managed_directory() / "ready.json").is_file()
    )


def release_platform(system: str | None = None, machine: str | None = None) -> str:
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    if system == "Windows":
        # The supported Windows installer uses x64 Python, including Windows 11 ARM.
        return "windows_amd64"
    architecture = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "amd64", "amd64": "amd64"}.get(machine)
    operating_system = {"Darwin": "macOS", "Linux": "linux"}.get(system)
    if not architecture or not operating_system:
        raise RuntimeError("Nuclei 自动安装支持 Windows x64、macOS/Linux x64 和 ARM64；其他平台请手动安装。")
    return f"{operating_system}_{architecture}"


async def download(client: httpx.AsyncClient, url: str, destination: Path | None = None) -> bytes:
    for _ in range(8):
        parsed = httpx.URL(url)
        if parsed.scheme != "https" or parsed.host not in HOSTS:
            raise RuntimeError("Nuclei 下载地址必须是官方 GitHub HTTPS 地址")
        async with client.stream("GET", url) as response:
            if response.is_redirect:
                url = str(response.url.join(response.headers["location"]))
                continue
            response.raise_for_status()
            content = bytearray()
            size = 0
            output = destination.open("wb") if destination else None
            try:
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > (128 * 1024 * 1024 if destination else 2 * 1024 * 1024):
                        raise RuntimeError("Nuclei 下载内容超过大小限制")
                    if output:
                        output.write(chunk)
                    else:
                        content.extend(chunk)
            finally:
                if output:
                    output.close()
            return bytes(content)
    raise RuntimeError("Nuclei 下载重定向过多")


async def release_tag(client: httpx.AsyncClient) -> str:
    try:
        data = json.loads(await download(client, "https://api.github.com/repos/projectdiscovery/nuclei/releases/latest"))
        tag = data.get("tag_name", "")
        if data.get("draft") or data.get("prerelease"):
            raise RuntimeError("Nuclei 下载必须使用官方正式版本")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in {403, 429}:
            raise
        response = await client.get("https://github.com/projectdiscovery/nuclei/releases/latest")
        location = str(response.url.join(response.headers.get("location", "")))
        prefix = "https://github.com/projectdiscovery/nuclei/releases/tag/"
        if not response.is_redirect or not location.startswith(prefix):
            raise RuntimeError("暂时无法读取 Nuclei 最新正式版本") from exc
        tag = location[len(prefix) :]
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise RuntimeError("无法验证 Nuclei 正式版本号")
    return tag


@asynccontextmanager
async def install_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    with (root / "install.lock").open("a+b") as stream:
        stream.write(b"0")
        stream.flush()
        deadline = time.monotonic() + 600
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise RuntimeError("等待其他 Nuclei 安装任务超时") from None
                await asyncio.sleep(0.2)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


async def _run(arguments: list[str], *, timeout: int, env: dict[str, str]) -> str:
    process = await asyncio.create_subprocess_exec(
        *arguments,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise
    text = output.decode("utf-8", errors="replace")
    if process.returncode:
        raise RuntimeError("Nuclei 安装校验或模板下载失败：" + text[-1200:])
    return text


async def ensure_installed(*, consent: bool, progress: Callable[[str], None] | None = None) -> str:
    """No download, directory creation, or subprocess execution before explicit consent."""
    from core.scanner import nuclei_subprocess_env, resolve_nuclei_executable

    existing = resolve_nuclei_executable()
    if not needs_setup(existing):
        return str(existing)
    if not consent:
        raise RuntimeError("Nuclei 未安装；请先询问用户是否自动下载，或由用户手动安装后重试。")
    report = progress or (lambda message: print(message, file=sys.stderr, flush=True))
    root = managed_directory()
    executable = managed_binary()
    async with install_lock(root):
        existing = resolve_nuclei_executable()
        if not needs_setup(existing):
            return str(existing)
        metadata = root / "engine.json"
        if not executable.is_file() or not metadata.is_file():
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(180, connect=20), follow_redirects=False, headers={"User-Agent": "FofaMap-Nuclei-Installer"}
            ) as client:
                tag = await release_tag(client)
                version = tag[1:]
                name = f"nuclei_{version}_{release_platform()}.zip"
                base = f"https://github.com/projectdiscovery/nuclei/releases/download/{tag}"
                report(f"正在下载官方 Nuclei {version}（{release_platform()}）…")
                checksums = (await download(client, f"{base}/nuclei_{version}_checksums.txt")).decode("utf-8")
                expected = next(
                    (line.split()[0] for line in checksums.splitlines() if len(line.split()) == 2 and line.split()[1].lstrip("*") == name),
                    "",
                )
                if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
                    raise RuntimeError("官方校验文件中缺少对应平台的 SHA-256，已停止安装")
                with tempfile.TemporaryDirectory(prefix="download-", dir=root) as temporary:
                    archive = Path(temporary) / name
                    await download(client, f"{base}/{name}", archive)
                    if hashlib.sha256(archive.read_bytes()).hexdigest().lower() != expected.lower():
                        raise RuntimeError("Nuclei SHA-256 不匹配，未执行下载的程序")
                    with ZipFile(archive) as package:
                        info = package.getinfo(executable.name)
                        if info.file_size > 300 * 1024 * 1024:
                            raise RuntimeError("Nuclei 程序超过大小限制")
                        candidate = Path(temporary) / executable.name
                        candidate.write_bytes(package.read(info))
                    candidate.chmod(0o755)
                    text = await _run([str(candidate), "-version"], timeout=30, env=nuclei_subprocess_env())
                    if version not in text:
                        raise RuntimeError("Nuclei 返回版本与官方发行版本不一致")
                    os.replace(candidate, executable)
                    metadata.write_text(json.dumps({"version": version, "sha256": expected, "url": f"{base}/{name}"}), encoding="utf-8")
        report("正在下载/更新 Nuclei 官方模板（不会执行扫描）…")
        templates = root / "templates"
        env = nuclei_subprocess_env()
        env["NUCLEI_TEMPLATES_DIR"] = str(templates)
        await _run([str(executable), "-ut", "-ud", str(templates)], timeout=600, env=env)
        if not templates.is_dir() or not next(templates.rglob("*.yaml"), None):
            raise RuntimeError("官方模板未下载完整；重新选择 Y 可继续安装")
        (root / "ready.json").write_text(json.dumps({"templates": str(templates), "ready": True}), encoding="utf-8")
        report("✓ Nuclei 程序、版本和官方模板已就绪，继续本次扫描方案。")
        return str(executable)
