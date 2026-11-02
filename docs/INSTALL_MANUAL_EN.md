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

![macOS / Linux: four installation steps](https://camo.githubusercontent.com/5edd4b75c1dd373838248906bb64c4bbe259ec586200f06d506ad409820a509b/68747470733a2f2f7261772e6769746875622e636f6d2f6173616f746f6d6f2f466f66614d61702f626464626135336330623862636133316466663337393263323734636537363435343964353333362f646f63732f6173736574732f726561646d652f322e302e322f656e2f696e7374616c6c2e706e67)

</details>

The final line should say `FofaMap, version 2.0.2`. Activate `.venv` again in each new terminal, or call `.venv/bin/fofamap` directly. A 2.0.1 result means you are running the older release or a different environment.
