"""Fetch official stable source releases, then hand installation to an external worker."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

import httpx

from core.version import VERSION

REPOSITORY = "asaotomo/FofaMap"
LATEST = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
ALLOWED_HOSTS = {
    "api.github.com",
    "github.com",
    "codeload.github.com",
    "release-assets.githubusercontent.com",
    "objects.githubusercontent.com",
}
MAX_DOWNLOAD = 64 * 1024 * 1024


class UpdateError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def release_version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"[vV]?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise UpdateError("The stable release tag must use a version such as v2.0.2")
    return tuple(int(part) for part in match.groups())


def checked_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password:
        raise UpdateError("The release download did not use an official GitHub HTTPS address")
    return url


def fetch(client: httpx.Client, url: str, destination: Path | None = None) -> bytes:
    for _ in range(8):
        with client.stream("GET", checked_url(url)) as response:
            if response.is_redirect:
                url = str(response.url.join(response.headers["location"]))
                continue
            if response.status_code != 200:
                raise UpdateError(
                    f"GitHub returned HTTP {response.status_code}. Check network access or try again later.",
                    status_code=response.status_code,
                )
            size = 0
            chunks = []
            with destination.open("wb") if destination else nullcontext() as output:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > (MAX_DOWNLOAD if destination else 2 * 1024 * 1024):
                        raise UpdateError("The GitHub response exceeded the download limit")
                    if output:
                        output.write(chunk)
                    else:
                        chunks.append(chunk)
            return b"" if destination else b"".join(chunks)
    raise UpdateError("Too many GitHub redirects")


def latest_release(client: httpx.Client) -> dict:
    try:
        return json.loads(fetch(client, LATEST))
    except UpdateError as exc:
        if exc.status_code not in {403, 429}:
            raise
    # Public GitHub release pages remain usable when anonymous REST quota is
    # exhausted. Follow the official stable-release redirect, never a branch.
    url = f"https://github.com/{REPOSITORY}/releases/latest"
    with client.stream("GET", url) as response:
        location = str(response.url.join(response.headers.get("location", "")))
        checked_url(location)
        prefix = f"https://github.com/{REPOSITORY}/releases/tag/"
        if not response.is_redirect or not location.lower().startswith(prefix.lower()):
            raise UpdateError("GitHub release checks are unavailable. Try again later.")
        tag = unquote(location[len(prefix) :])
        release_version(tag)
        return {"tag_name": tag, "zipball_url": f"https://codeload.github.com/{REPOSITORY}/zip/refs/tags/{tag}", "assets": []}


def unpack_source(archive: Path, destination: Path, version: str) -> Path:
    with ZipFile(archive) as package:
        files = package.infolist()
        if len(files) > 15000 or sum(item.file_size for item in files) > 256 * 1024 * 1024:
            raise UpdateError("The source archive is too large")
        seen = set()
        for item in files:
            original = item.orig_filename
            path = PurePosixPath(original)
            mode = item.external_attr >> 16
            key = item.filename.casefold().rstrip("/")
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in original
                or ":" in original
                or "\0" in original
                or stat.S_ISLNK(mode)
                or key in seen
            ):
                raise UpdateError("Unsafe or duplicate source archive entry")
            seen.add(key)
        package.extractall(destination)
    candidates = list(destination.glob("pyproject.toml")) + list(destination.glob("*/pyproject.toml"))
    if len(candidates) != 1:
        raise UpdateError("The archive must contain exactly one FofaMap source root")
    source = candidates[0].parent
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    with candidates[0].open("rb") as handle:
        project = tomllib.load(handle).get("project", {})
    if project.get("name", "").lower() != "fofamap" or release_version(project.get("version", "")) != release_version(version):
        raise UpdateError("The downloaded source version does not match the GitHub release")
    for required in ("fofamap.py", "core/version.py", "config/__init__.py", "scripts/check_installation.py", "scripts/register_command.py"):
        if not (source / required).is_file():
            raise UpdateError(f"Incomplete source release: {required}")
    return source


def prepare_update(root: Path, *, client: httpx.Client | None = None) -> dict:
    owns_client = client is None
    client = client or httpx.Client(
        timeout=httpx.Timeout(90, connect=15),
        headers={"User-Agent": f"FofaMap/{VERSION}", "Accept": "application/vnd.github+json"},
        follow_redirects=False,
    )
    staging = None
    try:
        release = latest_release(client)
        tag = release.get("tag_name", "")
        if release.get("draft") or release.get("prerelease"):
            raise UpdateError("GitHub did not return a stable published release")
        if release_version(tag) <= release_version(VERSION):
            return {"status": "current", "installed": VERSION, "latest": tag}
        if not (root / "pyproject.toml").is_file() or not (root / ".venv").is_dir():
            raise UpdateError("Automatic updates require a source installation made with install.bat/install.sh")
        staging = Path(tempfile.mkdtemp(prefix="fofamap-update-"))
        archive = staging / "source.zip"
        asset = next(
            (
                item
                for item in release.get("assets", [])
                if re.fullmatch(r"fofamap-[vV]?\d+\.\d+\.\d+-source\.zip", item.get("name", ""), re.I)
            ),
            None,
        )
        url = asset["browser_download_url"] if asset else release.get("zipball_url", "")
        fetch(client, url, archive)
        digest = asset.get("digest", "") if asset else ""
        if digest.startswith("sha256:") and hashlib.sha256(archive.read_bytes()).hexdigest() != digest[7:]:
            raise UpdateError("The source archive SHA-256 does not match GitHub")
        source = unpack_source(archive, staging / "source", tag)
        if any((source / name).exists() for name in ("tests", ".github", "scripts/build_source.py")):
            from core.distribution import stage_user_bundle

            stage_user_bundle(source, staging / "user-source")
            source = staging / "user-source"
        worker = staging / "update_worker.py"
        shutil.copy2(root / "scripts/update_worker.py", worker)
        return {
            "status": "ready",
            "installed": VERSION,
            "latest": tag,
            "root": str(root),
            "staging": str(staging),
            "source": str(source),
            "worker": str(worker),
        }
    except Exception:
        if staging:
            shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        if owns_client:
            client.close()


def update_cli(*, machine: bool = False) -> int:
    from utils.cli_ui import console
    from utils.i18n import t

    root = Path(__file__).resolve().parents[1]
    try:
        if not machine:
            console.print(t("正在检查 GitHub 最新正式版本…", "Checking the latest stable GitHub release…"))
        plan = prepare_update(root)
        if plan["status"] == "current":
            if machine:
                print(json.dumps(plan))
            else:
                console.print(t("当前版本无需更新：", "No update is needed: "), f"{VERSION} (GitHub: {plan['latest']})", markup=False)
            return 0
        command = [sys.executable, plan["worker"], "--root", plan["root"], "--source", plan["source"], "--version", plan["latest"]]
        if os.name == "nt":
            # The distlib fofamap.exe launcher is locked until this process exits.
            # A separate console keeps progress visible after releasing that lock.
            command += ["--wait-pid", str(os.getpid()), "--pause"]
            subprocess.Popen(command, cwd=plan["staging"], creationflags=subprocess.CREATE_NEW_CONSOLE)  # noqa: S603 - verified repository worker
            result = {"status": "started", "latest": plan["latest"], "progress": "new_console"}
        else:
            completed = subprocess.run(  # noqa: S603 - verified repository worker
                command, cwd=plan["staging"], check=False, stdout=sys.stderr if machine else None
            )
            result = {"status": "updated" if completed.returncode == 0 else "failed", "latest": plan["latest"]}
            if completed.returncode:
                raise UpdateError("Update failed. The previous installation was restored; inspect the update log.")
            shutil.rmtree(plan["staging"], ignore_errors=True)
        if machine:
            print(json.dumps(result))
        elif result["status"] == "started":
            console.print(
                t(
                    "更新窗口已打开，将自动安装并校验；完成后输入 fofamap。",
                    "The update window is open. Installation and verification will run automatically; then run fofamap.",
                )
            )
        else:
            console.print(t("更新完成，输入 fofamap 即可启动。", "Update complete. Run fofamap to start."))
        return 0
    except (UpdateError, httpx.HTTPError, ValueError, OSError) as exc:
        if machine:
            print(json.dumps({"error": "update_failed", "message": str(exc)}))
        else:
            console.print(t("更新未完成：", "Update did not complete: "), str(exc), markup=False)
        return 2
