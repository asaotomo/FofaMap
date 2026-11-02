# FofaMap AI asset report

- Generated: 2026-11-02T11:17:46+08:00
- Started: 2026-11-02 11:17:14
- Elapsed: 31s
- Tokens: 7,928 (input 2,861 · output 5,067)
- Run ID: `a862ef35-45f3-44ef-949c-06a4907ef0bd`
- Status: `completed`
- Action: `fofa_search`
- Request: Query only domain="baidu.com", at most 2 public website records. Do not expand scope or scan. Write an English briefing under 250 words.
- FOFA query: `domain="baidu.com"`
- Result count: 2

## What ran

| # | Started | Stage | Detail |
|---|---|---|---|
| 1 | 11:17:14 | intent_parsing | Identifying the task and choosing a FOFA plan |
| 2 | 11:17:17 | intent_parsing | Selected action fofa_search |
| 3 | 11:17:17 | intent_parsing | Prepared 1 initial queries |
| 4 | 11:17:17 | intent_parsing | Selected 10 return fields for tier professional and this task |
| 5 | 11:17:17 | query_validation | Query 1/1 passed syntax checks |
| 6 | 11:17:17 | execute | Running query 1/1: Briefing: retrieve a minimal sample of public web assets registered under baidu.com, capped at two records. Scope is intentionally restricted to this single registrable domain; no subdomain expansion, no alternates, no organization-name pivots, and no scanning are performed. Expected returned information covers hostname, transport protocol, IP, port, page title, the domain field, country, detected product, last update time and server banner — enough to confirm live public web presence while staying inside the requested limit. |
| 7 | 11:17:18 | execute | Query 1 page 1: 2 returned, 2 new, 2 unique so far |
| 8 | 11:17:18 | evaluate | The first pass finished 1 queries and found 2 unique assets |
| 9 | 11:17:18 | execute | The visible set is much larger than the sample cap. Reading the primary query distribution. |
| 10 | 11:17:19 | evaluate | Prepared 1 website candidates with evidence levels |
| 11 | 11:17:19 | evaluate | All 1 queries finished. Found 2 unique assets. |
| 12 | 11:17:19 | summarize | Writing the briefing from the asset sample |
| 13 | 11:17:46 | completed | Reconnaissance finished |

## Query plan

| # | Source | Strategy | Purpose | FOFA query | FOFA total | Sample | New |
|---:|---|---|---|---|---:|---:|---:|
| 1 | Initial plan | precision | Briefing: retrieve a minimal sample of public web assets registered under baidu.com, capped at two records. Scope is intentionally restricted to this single registrable domain; no subdomain expansion, no alternates, no organization-name pivots, and no scanning are performed. Expected returned information covers hostname, transport protocol, IP, port, page title, the domain field, country, detected product, last update time and server banner — enough to confirm live public web presence while staying inside the requested limit. | `domain="baidu.com"` | 78719 | 2 | 2 |

## Website candidates

| Status | Domain | Preferred URL | Evidence |
|---|---|---|---|
| Seen in FOFA | `baidu.com` | https://xiangce.baidu.com | entity_resolution, fofa_precision |

> Corroborated means several FOFA clues agree. It is not legal or organizational confirmation.

## Asset candidates

| # | host | protocol | ip | port | title | domain | country | product | Attribution |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | https://xiangce.baidu.com | https | 182.61.200.179 | 443 | 百度网盘-免费云盘丨文件共享软件丨超大容量丨存储安全 | baidu.com | CN | NGINX,digicert-Cert | High |
| 2 | https://c.tieba.baidu.com | https | 183.2.172.1 | 443 | 百度安全验证 | baidu.com | CN | Baidu-BFE,digicert-Cert | High |

## AI summary

## Conclusion
The attributable boundary is `baidu.com`, but no site is corroborated; the indexed hosts remain medium-confidence candidates. Passive records show HTTPS/443 frontage in CN on nginx and Baidu-BFE, not proof of current reachability. The verification title is an interstitial, not evidence of access-control bypass.

## High-confidence assets
- **No corroborated website cluster**: no site meets confirmation; `https://xiangce.baidu.com` and `https://c.tieba.baidu.com` remain observed candidates.

## Exposure
- **HTTPS edge**: `xiangce.baidu.com` (`182.61.200.179`, nginx) and `c.tieba.baidu.com` (`183.2.172.1`, Baidu-BFE) are passive 443/CN records with DigiCert labels.
- **Verification page**: Tieba’s title suggests a challenge or gateway; it does not prove a vulnerability or a reachable backend.
- **Transport**: public web frontage only, not confirmed live service.

## Evidence limits
- **Observed candidate**: attribution is medium-confidence; domain, certificate and product matches do not establish legal ownership.
- **Tieba title**: `c.tieba.baidu.com` may be a generic interstitial, so backend role is uncertain.
- **No probes**: index entries cannot support “currently reachable” claims.

## Coverage gaps
- **Scope gap**: no subdomain expansion, so sibling Baidu services and ownership boundaries remain unknown.
- **Metadata gap**: no organization, DNS, certificate chain, headers or page content; product labels rest on passive banners.

## Priority actions
1. Confirm `xiangce.baidu.com` in Baidu’s official asset registry or DNS delegation; expect ownership confirmation or removal.
2. Review `c.tieba.baidu.com` and its verification page; expect an official-gateway or generic-interstitial classification.
3. Seek passive certificate-transparency or DNS corroboration for the listed hosts; expect stronger attribution without scanning.
4. If reachability is required, obtain owner authorization before any benign request; expect a documented live/dead result.



## Model routing and usage

| Task | Provider | Model | Fallback | Input | Output |
|---|---|---|---|---:|---:|
| planner | deepseek | deepseek-flash | No | 1349 | 422 |
| summarizer | deepseek | deepseek-flash | No | 1512 | 4645 |

> A FOFA fingerprint is exposure, not a confirmed vulnerability. Nuclei hits still need an authorized review.
