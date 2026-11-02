# FofaMap AI 资产侦察报告

- 生成时间：2026-11-02T21:53:29+08:00
- 任务开始：2026-11-02 21:50:10
- 任务耗时：3 分 18 秒
- Token 消耗：36,498（输入 3,776 · 输出 32,722）
- Run ID：`be84ddca-fe2a-4a92-b721-1f2f54234183`
- 状态：`completed`
- 动作：`fofa_search`
- 用户需求：仅查询 domain="baidu.com" 的公开网站资产，最多2条，不扩展范围，不扫描。生成中文简报。
- FOFA 查询：`domain="baidu.com"`
- 结果数量：2

## 执行过程

| # | 开始时间 | 阶段 | 说明 |
|---|---|---|---|
| 1 | 21:50:10 | intent_parsing | 正在识别任务类型并制定 FOFA 执行策略 |
| 2 | 21:50:23 | intent_parsing | 已选择动作 fofa_search |
| 3 | 21:50:23 | intent_parsing | 已生成 2 个初始查询策略 |
| 4 | 21:50:23 | intent_parsing | 已按账号等级（professional）和任务智能选择 10 个返回字段 |
| 5 | 21:50:23 | query_validation | 查询策略 1/2 语法校验通过 |
| 6 | 21:50:23 | query_validation | 查询策略 2/2 语法校验通过 |
| 7 | 21:50:23 | execute | 正在执行查询策略 1/2：基线查询：覆盖 baidu.com 主域下全部公开网站资产（含子域），用于统计协议、端口、归属国家与地域分布，构建整体资产地图。 |
| 8 | 21:50:24 | execute | 策略 1 第 1 页：返回 1 条，新增 1 条，累计去重资产 1 条 |
| 9 | 21:50:24 | execute | 正在执行查询策略 2/2：精确查询：在 domain= 限定范围内筛选使用自有证书（CN 为 baidu.com 或其通配符）的 HTTPS 资产，识别证书归属明确的核心对外站点，降低 CDN 或第三方代持证书资产的噪声。 |
| 10 | 21:50:24 | execute | 策略 2 第 1 页：返回 1 条，新增 0 条，累计去重资产 1 条 |
| 11 | 21:50:24 | evaluate | 首轮 2 个查询完成，共发现 1 条去重资产 |
| 12 | 21:50:24 | execute | 可见规模远大于抽样上限，正在读取主查询的统计分布 |
| 13 | 21:50:26 | reflect | 正在进行第 1/2 轮结果驱动反思 |
| 14 | 21:51:50 | reflect | 第 1 轮反思完成，新增 1 个混合查询策略 |
| 15 | 21:51:50 | execute | 正在执行查询策略 3/3：协议补样：基于已观测样本为HTTPS/443，补充HTTP协议公开网站资产，避免与现有样本重复并提升协议维度覆盖；严格限定 domain="baidu.com"，不扩展范围、不扫描，用于最多2条资产的中文简报。 |
| 16 | 21:51:50 | execute | 策略 3 第 1 页：返回 1 条，新增 1 条，累计去重资产 2 条 |
| 17 | 21:51:50 | evaluate | 第 1 轮补充查询新增 1 条去重资产 |
| 18 | 21:51:50 | evaluate | 已整理 1 个带证据等级的网站候选 |
| 19 | 21:51:50 | evaluate | 全部 3 个查询策略执行完成，共发现 2 条去重资产 |
| 20 | 21:51:50 | summarize | 正在基于资产样本生成总结 |
| 21 | 21:53:29 | completed | 侦察任务已完成 |

## 多维查询策略

| # | 来源 | 策略 | 查询目的 | FOFA 查询 | FOFA 总量 | 取样 | 去重新增 |
|---:|---|---|---|---|---:|---:|---:|
| 1 | 首轮规划 | balanced | 基线查询：覆盖 baidu.com 主域下全部公开网站资产（含子域），用于统计协议、端口、归属国家与地域分布，构建整体资产地图。 | `domain="baidu.com"` | 78721 | 1 | 1 |
| 2 | 首轮规划 | precision | 精确查询：在 domain= 限定范围内筛选使用自有证书（CN 为 baidu.com 或其通配符）的 HTTPS 资产，识别证书归属明确的核心对外站点，降低 CDN 或第三方代持证书资产的噪声。 | `domain="baidu.com" && (cert.subject.cn="baidu.com" \|\| cert.subject.cn="*.baidu.com")` | 36161 | 1 | 0 |
| 3 | 动态反思 R1 | balanced | 协议补样：基于已观测样本为HTTPS/443，补充HTTP协议公开网站资产，避免与现有样本重复并提升协议维度覆盖；严格限定 domain="baidu.com"，不扩展范围、不扫描，用于最多2条资产的中文简报。 | `domain="baidu.com" && protocol="http"` | 78 | 1 | 1 |

## 网站候选清单

| 状态 | 域名 | 首选 URL | 证据 |
|---|---|---|---|
| FOFA 已观测 | `baidu.com` | https://applets.baidu.com | entity_resolution, certificate_observed, fofa_precision, fofa_balanced |

> 交叉印证表示 FOFA 中存在多种一致线索，仍不等同于法律或组织归属确认。

## 查询到的资产候选

| # | host | protocol | ip | port | title | domain | cname | icp | 归属证据 |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | https://applets.baidu.com | https | 124.237.176.244 | 443 |  | baidu.com | iov_oauth.n.shifen.com |  | 高 |
| 2 | dts.pubserver-1.public.bce.baidu.com | http | 180.97.107.216 | 80 |  | baidu.com |  |  | 中 |

## AI 总结

## 结论
当前资产图谱仅呈现 `applets.baidu.com` 与 `dts.pubserver-1.public.bce.baidu.com` 的被动索引记录：前者为 observed/medium 候选，后者仅有域名、IP 与 HTTP 关联，两者均未确证归属。最重信号是 `dts.pubserver-1.public.bce.baidu.com` 的 80 明文 HTTP 与 `applets.baidu.com` 的证书主体 `baidu.com`，但均不等于漏洞或当前可达。应先做被动归属核验，不把索引记录当作扫描结果。

## 高置信资产
- **无已确证站点**：`applets.baidu.com` 仍为 observed/medium 候选，不能升格为确认或高置信网站。
- **无高置信归属**：`dts.pubserver-1.public.bce.baidu.com`（`180.97.107.216`）仅有域名后缀、IP 与 HTTP 关联，缺少证书、组织与标题字段。

## 风险与暴露面
- **品牌证书线索**：`applets.baidu.com`（`124.237.176.244`，443/HTTPS）索引到 `cert.subject.cn=baidu.com`；证书字段一致只能作线索，未验证签发链、SAN 与有效期。
- **明文 HTTP 端点**：`dts.pubserver-1.public.bce.baidu.com`（`180.97.107.216`，80/HTTP）只有明文协议；明文本身不是漏洞，但缺少响应内容，无法排除用于登录或数据提交的可能。
- **云命名线索**：主机名含 `public.bce.baidu.com` 层级，相关 IP 属 CN，可能是云公共入口、CDN 或租户资产，不能直接归为百度核心站点。

## 证据边界与噪声
- **候选状态**：`applets.baidu.com` 为 observed/medium，证据含 entity_resolution、certificate_observed 与索引精度项，未达 confirmed。
- **证书与主机名**：`cert.subject.cn=baidu.com` 不证明合法所有权；`public.bce` 层级也只是命名线索，缺少 ASN、WHOIS 与组织字段。
- **无探针证据**：未做连通性、HTTP 响应或端口探测，所有“可达”“开放”表述都应降级为索引观测。

## 覆盖缺口
- **技术栈字段缺失**：title、server、product、org 为空，无法判断应用类型、框架或管理面，不能把“无标题”当成“无应用指纹”。
- **证书与归属字段不全**：仅有 subject CN，缺 issuer、SAN、有效期、CT 交叉验证、ASN 与 WHOIS，无法确认证书链或托管方。
- **范围与存活性**：仅围绕 `baidu.com` 的被动索引，未做独立子域枚举或主动探测；无响应头或正文，不能评估跳转、安全头或登录入口。

## 处置优先级
1. 对 `applets.baidu.com` 做被动证书链核验：比对 CT 日志、签发者、SAN、有效期与权威 DNS；目的为提升或降级候选，预期形成可审计归属结论，不扫描。
2. 对 `dts.pubserver-1.public.bce.baidu.com` 做被动 DNS、WHOIS、ASN 与云租户台账比对；目的确认 `180.97.107.216` 是百度自有还是云客户入口，预期明确 80 明文端点责任方。
3. 将上述主机以“索引观测/未探针”登记并保留证书与 IP 证据；目的防止候选被误报为高置信或漏洞，预期形成待核验清单。
4. 若 `dts.pubserver-1.public.bce.baidu.com` 经业务确认承载正式服务，再由其核对既有 HTTPS 入口与证书部署；目的判断 80 明文是否历史遗留，预期给出保留、整改或下线结论，不主动探测。
5. 若 `applets.baidu.com` 无法归属，转品牌与域名治理核查第三方代持；目的排除品牌证书滥用，预期补全授权或下架。



## 模型路由与用量

| 任务 | 提供商 | 模型 | 回退 | 输入 | 输出 |
|---|---|---|---|---:|---:|
| planner | deepseek | deepseek-flash | 否 | 1337 | 1767 |
| reflector | deepseek | deepseek-flash | 否 | 837 | 13112 |
| summarizer | deepseek | deepseek-flash | 否 | 1602 | 17843 |

> FOFA 指纹代表资产暴露信息，不等同于已确认漏洞。Nuclei 结果也应由授权人员复核。
