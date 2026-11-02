# Manual macOS / Linux installation

Choose Chinese / English as the first installer step. The account guide and future sessions use this language. Change it later under Settings → Interface language; no YAML editing is required. Automation accepts `-Language en` (Windows) or `--language en` (macOS/Linux).

The installer supports install, repair and uninstall: first use offers Install; existing installations offer Repair or Uninstall; `0` cancels. Repair reinstalls dependencies and restores the command. Offline uninstall needs no Python and retains source, settings, keys, results, reports, databases and backups. Automation: `install.bat -Action install|repair|uninstall` (Windows) or `bash install.sh --action install|repair|uninstall` (macOS/Linux); the pipe denotes alternatives and is not part of the command. See [installation management](../README_EN.md#install-repair-and-uninstall).

Use the [one-click installer](../README_EN.md#install) for the recommended setup. These steps are for custom environments and troubleshooting.

### macOS / Linux: four installation steps

Run one line at a time. The capture is from an actual fresh isolated source installation.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
fofamap --version
```

<details>
<summary>Actual task output: macOS / Linux: four installation steps</summary>

![macOS / Linux: four installation steps](https://github.com/user-attachments/assets/5347e6b6-2bb4-4113-95ed-2a24cab41470)

</details>

The final line should say `FofaMap, version 2.0.2`. Activate `.venv` again in each new terminal, or call `.venv/bin/fofamap` directly. A 2.0.1 result means you are running the older release or a different environment.
