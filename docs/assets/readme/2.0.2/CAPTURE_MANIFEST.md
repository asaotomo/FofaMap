# FofaMap 2.0.2 · 命令与配图 / Commands and screenshots

终端图片来自实际执行，身份与凭据已脱敏；长输出展示首屏、末屏或相关任务区域。产品封面为插画，不是查询结果。
Terminal images show actual execution with identities and credentials redacted. Long output shows relevant excerpts. Product covers are illustrations, not query results.

域名例子使用 Baidu / Bing；已执行的主动扫描只针对本机临时靶标。公共范围预览在审批处取消。
Domain examples use Baidu / Bing; executed scans target temporary local fixtures. Public-scope previews are cancelled at approval.

共 110 张终端配图；图片哈希与命令见 [capture-manifest.json](capture-manifest.json)。

| Task | 中文 | English | Command |
|---|---|---|---|
| account | [PNG](zh/account.png) | [PNG](en/account.png) | `fofamap account` |
| agent | [PNG](zh/agent.png) | [PNG](en/agent.png) | `fofamap -ai '仅查询 domain="baidu.com" 的公开网站资产，最多2条，不扩展范围，不扫描。生成中文简报。' --size 2 --pages 1 --max-records 2 --no-check-alive --no-deepseek-search --no-save --report-lang zh --report-file results/readme-demo/report-zh.md` |
| alive | [PNG](zh/alive.png) | [PNG](en/alive.png) | `fofamap -q 'domain="bing.com" && host="www.bing.com"' -f host,port --size 1 --pages 1 --max-records 1 --check-alive --no-save` |
| approval | [PNG](zh/approval.png) | [PNG](en/approval.png) | `fofamap -q 'domain="baidu.com"' --size 1 --pages 1 --max-records 1 --no-check-alive --no-save --no-scan-ai-dedupe -n --nuclei-id tech-detect --severity info` |
| batch | [PNG](zh/batch.png) | [PNG](en/batch.png) | `fofamap -bq examples/queries.txt --batch-group-size 1 --size 3 --pages 1 --max-records 3 --no-check-alive --no-full --no-save` |
| component-install | [PNG](zh/component-install.png) | [PNG](en/component-install.png) | `fofamap --update-nuclei` |
| export-csv | [PNG](zh/export-csv.png) | [PNG](en/export-csv.png) | `fofamap -q 'domain="baidu.com"' -f host,ip,port,title --size 3 --pages 1 --max-records 3 --no-check-alive --export-format csv --save -o results/readme-demo/inventory.csv` |
| export-jsonl | [PNG](zh/export-jsonl.png) | [PNG](en/export-jsonl.png) | `fofamap -q 'domain="baidu.com"' -f host,ip,port,title --size 3 --pages 1 --max-records 3 --no-check-alive --export-format jsonl --save -o results/readme-demo/inventory.jsonl` |
| export-xlsx | [PNG](zh/export-xlsx.png) | [PNG](en/export-xlsx.png) | `fofamap -q 'domain="baidu.com"' -f host,ip,port,title --size 3 --pages 1 --max-records 3 --no-check-alive --export-format xlsx --save -o results/readme-demo/inventory.xlsx` |
| exposure | [PNG](zh/exposure.png) | [PNG](en/exposure.png) | `python scripts/readme_demo.py exposure --language zh --output results/readme-demo/exposure-zh` |
| fields | [PNG](zh/fields.png) | [PNG](en/fields.png) | `fofamap fields` |
| filters | [PNG](zh/filters.png) | [PNG](en/filters.png) | `fofamap -q 'domain="baidu.com"' -f host,port,status_code,title -i 200 -k 百度 --size 3 --pages 1 --max-records 3 --no-check-alive --no-full --no-save` |
| first-search | [PNG](zh/first-search.png) | [PNG](en/first-search.png) | `fofamap` |
| help | [PNG](zh/help.png) | [PNG](en/help.png) | `fofamap --help` |
| host | [PNG](zh/host.png) | [PNG](en/host.png) | `fofamap -hq www.bing.com --no-host-detail --no-save` |
| hosts | [PNG](zh/hosts.png) | [PNG](en/hosts.png) | `fofamap integrate --list` |
| icon | [PNG](zh/icon.png) | [PNG](en/icon.png) | `fofamap -ico https://www.bing.com --size 3 --pages 1 --max-records 3 --no-check-alive --no-full --no-save` |
| install | [PNG](zh/install.png) | [PNG](en/install.png) | `python3 -m venv .venv → source .venv/bin/activate → python -m pip install -e . → fofamap --version` |
| install-language | [PNG](zh/install-language.png) | [PNG](en/install-language.png) | `bash install.sh` |
| install-menu | [PNG](zh/install-menu.png) | [PNG](en/install-menu.png) | `bash install.sh` |
| integrate | [PNG](zh/integrate.png) | [PNG](en/integrate.png) | `fofamap integrate --agent cursor --scope project --project-root results/readme-demo/host` |
| invalid-query | [PNG](zh/invalid-query.png) | [PNG](en/invalid-query.png) | `fofamap -q 'title="x" &&' --no-save --size 1 --pages 1 --max-records 1` |
| json | [PNG](zh/json.png) | [PNG](en/json.png) | `fofamap -q 'domain="baidu.com"' -f host,ip,port --size 1 --pages 1 --max-records 1 --no-save --json` |
| language-setting | [PNG](zh/language-setting.png) | [PNG](en/language-setting.png) | `fofamap` |
| mcp-check | [PNG](zh/mcp-check.png) | [PNG](en/mcp-check.png) | `fofamap-mcp --check --expect-version 2.0.2 --expect-build-date 2026-11-02 --expect-source .` |
| mcp-task | [PNG](zh/mcp-task.png) | [PNG](en/mcp-task.png) | `python scripts/readme_demo.py mcp --language zh --output results/readme-demo/mcp-zh` |
| menu | [PNG](zh/menu.png) | [PNG](en/menu.png) | `fofamap` |
| model-presets | [PNG](zh/model-presets.png) | [PNG](en/model-presets.png) | `fofamap` |
| models | [PNG](zh/models.png) | [PNG](en/models.png) | `fofamap models` |
| nuclei | [PNG](zh/nuclei.png) | [PNG](en/nuclei.png) | `nuclei -version` |
| onboarding | [PNG](zh/onboarding.png) | [PNG](en/onboarding.png) | `fofamap --setup` |
| pagination | [PNG](zh/pagination.png) | [PNG](en/pagination.png) | `fofamap -q 'domain="baidu.com"' -f host,ip,port --size 2 --pages 2 --max-records 4 --no-check-alive --no-save` |
| quick-install | [PNG](zh/quick-install.png) | [PNG](en/quick-install.png) | `bash install.sh → bash start.sh --version` |
| repair-menu | [PNG](zh/repair-menu.png) | [PNG](en/repair-menu.png) | `bash install.sh` |
| rest-task | [PNG](zh/rest-task.png) | [PNG](en/rest-task.png) | `python scripts/readme_demo.py rest --language zh --output results/readme-demo/rest-zh` |
| rule-ai | [PNG](zh/rule-ai.png) | [PNG](en/rule-ai.png) | `fofamap rules --rule-category 人工智能` |
| rule-categories | [PNG](zh/rule-categories.png) | [PNG](en/rule-categories.png) | `fofamap rules --rule-categories` |
| rule-industrial | [PNG](zh/rule-industrial.png) | [PNG](en/rule-industrial.png) | `fofamap rules --rule-category 工业控制` |
| rules | [PNG](zh/rules.png) | [PNG](en/rules.png) | `fofamap rules --rule ThinkPHP` |
| scan-task | [PNG](zh/scan-task.png) | [PNG](en/scan-task.png) | `python scripts/readme_demo.py scan --approve-local-fixture --language zh --output results/readme-demo/scan-zh` |
| schedule-list | [PNG](zh/schedule-list.png) | [PNG](en/schedule-list.png) | `fofamap schedule --schedule-action list --json` |
| schedule-task | [PNG](zh/schedule-task.png) | [PNG](en/schedule-task.png) | `python scripts/readme_demo.py schedule --language zh --output results/readme-demo/schedule-zh` |
| search | [PNG](zh/search.png) | [PNG](en/search.png) | `fofamap -q 'domain="baidu.com"' -f host,ip,port,protocol,title --size 3 --pages 1 --max-records 3 --no-check-alive --no-full --no-save` |
| settings-menu | [PNG](zh/settings-menu.png) | [PNG](en/settings-menu.png) | `fofamap` |
| setup | [PNG](zh/setup.png) | [PNG](en/setup.png) | `fofamap init` |
| skill-check | [PNG](zh/skill-check.png) | [PNG](en/skill-check.png) | `fofamap integrate --agent cursor --scope project --project-root results/readme-demo/host --check-stale --json` |
| skill-package | [PNG](zh/skill-package.png) | [PNG](en/skill-package.png) | `fofamap integrate --export-skill results/readme-demo/fofamap.skill → fofamap integrate --agent cursor --scope project --project-root results/readme-demo/host --import-skill results/readme-demo/fofamap.skill → fofamap integrate --agent cursor --scope project --project-root results/readme-demo/host --check-stale --json` |
| smart-fields-setting | [PNG](zh/smart-fields-setting.png) | [PNG](en/smart-fields-setting.png) | `fofamap` |
| stats | [PNG](zh/stats.png) | [PNG](en/stats.png) | `fofamap -cq 'domain="baidu.com"' -f port,protocol --size 5 --no-save` |
| status | [PNG](zh/status.png) | [PNG](en/status.png) | `fofamap -q 'domain="baidu.com" && status_code=200' -f host,port,status_code --size 3 --pages 1 --max-records 3 --no-check-alive --no-full --no-save` |
| syntax | [PNG](zh/syntax.png) | [PNG](en/syntax.png) | `fofamap syntax` |
| transports | [PNG](zh/transports.png) | [PNG](en/transports.png) | `python scripts/readme_demo.py transports --language zh --output results/readme-demo/transports-zh` |
| update | [PNG](zh/update.png) | [PNG](en/update.png) | `fofamap --update` |
| version | [PNG](zh/version.png) | [PNG](en/version.png) | `fofamap --version → python --version` |
| wizard | [PNG](zh/wizard.png) | [PNG](en/wizard.png) | `fofamap` |
