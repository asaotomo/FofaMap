# FOFA 内置规则与分类 / Bundled rule reference

日期 / Checked: **2026-11-02** · **691 rules / 166 categories / 510 verified / 181 legacy**.

本地参考集使用 FOFA 官网返回的规则表达式，不等于全站规则库。已核验项来自登录后的 [官方规则库](https://fofa.info/library)，通过鹰眼 MCP 读取官网页面客户端返回值；只提取规则名称、分类与原始查询，不保存账号、Cookie 或令牌。
Verified rows preserve exact queries returned by the signed-in official website. No account, cookie, or token is stored in the provenance data. This is a curated local reference, not a full FOFA mirror.

官网返回当日 100 次检索上限后，已停止额外请求。旧映射为兼容性保留并标记 legacy；未确认更名的产品不凭猜测替换。官网分类与产品指纹不代表确认存在漏洞。
The website daily search limit stopped further lookup. Legacy mappings remain for compatibility and are labelled unverified. A product fingerprint is not a confirmed vulnerability.

修正了 Spring Framework 与 Spring Boot 的混用，以及 MySQL/MariaDB、JBoss/WildFly、FineReport/FineBI 等错误等价别名。已有产品名保持可查，官网表达式保留原始大小写。
Updates separate Spring Framework from Spring Boot and remove incorrect equivalences such as MySQL/MariaDB, JBoss/WildFly, and FineReport/FineBI. Original query capitalization is retained.

[机器可读核验记录 / Provenance](data/fofa-library-20261102.json) · [Windows 安装](INSTALL_WINDOWS.md) · [README](../README.md#recipes)

CLI: `fofamap rules --rule-categories` → `fofamap rules --rule-category 工业控制` / `fofamap rules -k Spring`.
MCP: `fofa_rules(keyword="Spring", limit=20)` / `fofa_rules(category="工业控制", limit=20)`; inspect `verified`, `verified_at`, `matched_count`, and `has_more`.

| 分类 / Category | 内置 / Local | 已核验 / Verified | 示例 / Examples |
|---|---:|---:|---|
| ADSL | 3 | 3 | TP_LINK-TD-8616, TP_LINK-TD-8840TB, TP_LINK-TD-W8901N |
| CDN | 3 | 3 | 酷狗-CDN, L7Cache, PokeCDN |
| CMS | 18 | 3 | EZCMS, HoloCMS, Gallery |
| CMS插件 | 3 | 3 | podPress, Pressflow, qTranslate |
| CRM | 3 | 3 | oroCRM, EMS-CRM-Login, GOT-CRM-Login |
| DNS服务器 | 3 | 3 | TinyDNS, 360-安全DNS, wddns智能DNS管理系统 |
| DVR | 3 | 3 | DBR-M190, DBR-T350, DBR-T450 |
| ERP | 3 | 3 | APERP, 万物工业-ERP, 博库-医院在线考试系统 |
| FTP服务器 | 3 | 3 | Cesar, AXIS-ftp, WinFtp服务器 |
| HR系统 | 3 | 3 | UX绩效系统, HRIS招聘系统, 汇视星查寝考勤系统 |
| IDS | 3 | 3 | 网御-APT, HUAWEI-NIP2050, HUAWEI-NIP5000I |
| IPS | 3 | 3 | 入侵防御系统, 天清入侵防御系统, 捷普入侵防御系统 |
| KVM切换器 | 3 | 3 | KVM-SV1042, KVM-SV1204, KVM-SV1242 |
| Modem | 3 | 3 | ZTE-ZXV10-H118N, Cybertec-Series-1000, Cybertec-Series-2000 |
| NAS | 7 | 3 | ASUS-FreeNas, Lenovo-LenovoEMC-ix4-300d, Raidweb-Maxtronic-Orion-410ST |
| OA系统 | 28 | 3 | 泛微OA, 泛微E-Office, 万户OA |
| PBX | 3 | 3 | FUSHIONPBX, OpenVox-PBX, Asterisk-PBX |
| SSL证书 | 3 | 3 | RapidSSL-Cert, Apple-IST-CA-2-G1, WoTrus-OV-Server-CA |
| SaaS平台 | 3 | 3 | 惠动科技-裂变宝, Atlantis, 亿美软通-B/S满意通 |
| UPS | 3 | 3 | DELL-UPS, EATON-5P-650, EATON-5P-750 |
| UPS监控 | 3 | 3 | UMG51, UMG60, UMG604 |
| UTM | 3 | 3 | Winconnection, Hansol-NexG-VForce406, Hansol-NexG-VForce1406 |
| VOIP | 3 | 3 | Mitel-6731i, Mitel-6735i, Mitel-6737i |
| VPN | 3 | 3 | 奇安信VPN, FortiSSLVPN, OpenVPN |
| WAF | 3 | 3 | 蓝盾-WAF, 360-一启快, Teros-WAF |
| Web-Service | 3 | 3 | paas-web, 腾讯-Web-Server, eSolar-Cubo-Light |
| Web中间件 | 22 | 3 | Dorado, Webesp, HornetQ |
| Web服务器 | 3 | 3 | JEUS, Intrasrv, AMR-WinControl |
| docker管理 | 3 | 3 | Harbor, Portainer, mi-Naftis |
| 上网行为管理系统 | 3 | 3 | SANGFOR上网行为管理, SANGFOR-上网优化管理, SANGFOR-行为感知系统 |
| 专用设备 | 3 | 3 | BackupPC, ABB-SREA-01, V_SOL-V1600G2B |
| 业务解决方案 | 3 | 3 | Skylable-SX, 3DPrinterOS, 碧海威L7云流控运营商版 |
| 串口服务器 | 3 | 3 | GW212, GW312, MOXA/UC7101 |
| 云主机 | 3 | 3 | 初始化京东云面板, 云主机管理控制台, 主机宝Linux版 |
| 云计算 | 3 | 3 | 华铄云服务器, PL云服务系统, 尽职调查云服务 |
| 交换机 | 3 | 3 | H3C-S系列产品, ZYXEL-ES-2024, ZYXEL-ES-2048 |
| 交通行业 | 3 | 3 | 车次查询系统, 微信公交查询系统, 船舶网上申报系统 |
| 人工智能 | 3 | 3 | Chatbox, CVAT-AI, Kotaemon |
| 代理 | 3 | 3 | HAProxy, Traefik, Aptproxy |
| 代理服务器 | 3 | 3 | TMG165, GUI-PROXY, Proxomitron |
| 企业云平台 | 12 | 3 | 用友NC Cloud, Superset, 迪奥信息-火眼洞察平台 |
| 企业管理 | 3 | 3 | 管理易, CEMIS, 思迅-星食客 |
| 传真 | 3 | 3 | UFax2-产品, Myfax-公司产品, 汉元-万发传真服务器 |
| 公安行业 | 3 | 3 | 志愿警察查询系统, 警务综合管理系统, 执行案件信息查询系统 |
| 关键信息基础设施 | 3 | 3 | 保险, 机场, 核电 |
| 其他企业应用 | 3 | 3 | zkui, Wekan-开源看板, CashFactory |
| 其他安全产品 | 3 | 3 | 海泰-key验证, 金格-key验证, BASIC-AUTH |
| 其他服务器产品 | 3 | 3 | HP-T310, AXIS-70U, TBDev-YSE |
| 其他类型 | 4 | 4 | 深信服NGAF, Nextcloud, Grafana, RedisInsight |
| 其他组件 | 3 | 3 | Kafka UI, Nginx Proxy Manager, DORG |
| 其他终端 | 3 | 3 | SM-G900F, SM-G955F, OnePlus3 |
| 其他网络产品 | 21 | 3 | CASA-C10G, CASA-C40G, CASA-C100G |
| 分享模块 | 3 | 3 | ujian, Clicky, jiathis |
| 前端库 | 3 | 3 | fibjs/0.10.0, fibjs/0.11.0, fibjs/0.12.0 |
| 区块链 | 3 | 3 | cgminer, 挖金后台管理系统, 区块链管理系统后台 |
| 医疗行业 | 3 | 3 | 中药煎药系统, HIS综合查询系统, 体检预约/查询系统 |
| 协作产品 | 17 | 3 | huddle, Blueprint, KVM坐席协作管理系统 |
| 即插即用设备 | 3 | 3 | RaspberryPi#1, RaspberryPi2-Engine, raspberrypi-AstroBox |
| 台式机 | 3 | 3 | ASUS-PC, Apple-iMac10,1, Apple-iMac11,1 |
| 后门 | 3 | 3 | VB后门, ASP大马, JSP大马 |
| 堡垒机 | 3 | 3 | JumpServer, 云堡垒机, 丞风堡垒机 |
| 大数据 | 8 | 6 | Solr, ZooKeeper, HBase, Hadoop, Flink, Ambari |
| 威胁情报 | 3 | 3 | 威胁情报类产品, 威胁情报监控系统, 企业安全威胁感知系统 |
| 媒体设备 | 3 | 3 | TVW3800, DCX-3450, DCX-3520 |
| 存储管理 | 3 | 3 | Apple-Xserve-RAID, NetApp-NetApp-Release-7.3.4, NetApp-NetApp-Release-7.2.2 |
| 存储系统 | 3 | 3 | Apache Druid, IPSCAN设备, STORAGE-0000 |
| 安全基线 | 1 | 1 | 中电福富-安全基线管理 |
| 安全审计 | 3 | 3 | 网络安全审计系统, 网络行为审计系统, 网御网络审计系统 |
| 安全文件传输 | 3 | 3 | phpATM, 镭速-文件传输系统, CData-RSSBus |
| 安全检测平台 | 3 | 3 | 金电网安网站安全监测系统, 南网数字-蜜罐远程布防系统, LogRhythm-公司产品 |
| 安全网关 | 3 | 3 | JUNIPer-SSG-350M, DELL-SonicWALL-SMA-400, DELL-SonicWALL-SMA-500v |
| 安全软件 | 3 | 3 | Cryptlib, globaleaks, ESET-NOD32 |
| 官网 | 1 | 1 | Facebook-Error |
| 客服系统 | 3 | 3 | PHP121, 68客服系统, 花花网客服系统 |
| 嵌入式Web服务器 | 3 | 3 | IQ3, NET-ARM-Web-Server, Wireless-Product-Web-Server |
| 嵌入式服务器 | 3 | 3 | 即插即用设备, newweb, TCS-QD2040 |
| 工业互联网行业 | 3 | 3 | 优制云, 工业主动防御系统, 工业图纸比对系统 |
| 工业控制 | 3 | 3 | VTScada, PowerLink, RTS-SCADA |
| 工业路由器 | 3 | 3 | USR-DR801, TOPTEL-RG2000-M, TOPTEL-RG2000-V8 |
| 帮助系统 | 3 | 3 | Censura, HelpDocs, Yearning |
| 干扰类数据 | 2 | 2 | 干扰资产, 借贷-规则 |
| 广告联盟 | 3 | 3 | adriver, RevSense, seeyoo广告机 |
| 应用交付 | 3 | 3 | ivanti-VTM, BROADCOM-VTM, FORTINET-FortiGSLB |
| 应用服务器 | 3 | 3 | JBoss, FHFS, Sling |
| 应用网关 | 3 | 3 | Apache APISIX, Spring-GW, 指掌易-零信任·SDP安全网关 |
| 开发框架 | 31 | 11 | ThinkPHP, Django, Spring, Struts2, Express, Ruby on Rails, Dubbo, Shiro, Spring Boot, Spring Boot Admin, Spring Security |
| 开发模板 | 3 | 3 | PSI, AChat, Namazu |
| 户外广告 | 3 | 3 | 数字标牌管理系统, DSS-数字标牌系统, IPUB联网数字标牌平台 |
| 房地产行业 | 3 | 3 | 聚城物业管理软件, 银亿物业综合管理系统, 住房保障综合管理系统 |
| 打印或复印机 | 3 | 3 | Canon-MF220, Canon-LBP6300, Lenovo-LJ2655 |
| 打印服务器 | 3 | 3 | D_Link-DP-100, D_Link-DP-301, D_Link-DP-302 |
| 托管平台 | 3 | 3 | plesk-Onyx-17.5.3, plesk-Onyx-17.8.1, plesk-Onyx-17.8.2 |
| 扫描仪 | 3 | 3 | Canon-TS8330, Canon-TS5000-series, Canon-TS6000-series |
| 投影仪 | 3 | 3 | XGIMI-H1S, BenQ-W3000, BenQ-W1070 |
| 抗DDOS | 3 | 3 | AW-DDOS, AntiDDoS, FortiDDoS |
| 持续集成和交付 | 2 | 2 | Goploy, Airbyte-Integration-Platform |
| 指纹识别 | 3 | 3 | CS_TimeClock, Dr.ID-門禁考勤系統, ZK-Web-Server |
| 操作系统 | 3 | 3 | NS-BSD, Linux-CERN, Red-Giant-公司产品 |
| 政府行业 | 3 | 3 | 中国商品追溯防伪查询系统, 公共资源综合网上交易系统, 浙江省律师综合管理信息系统 |
| 教学考试系统 | 3 | 3 | ipeer, Judge0, TCExam |
| 教育行业 | 3 | 3 | ACAA考试系统登录, 乐智教育系统beta, ROMI在线培训系统 |
| 数字出版 | 3 | 3 | 优阅数字图书馆, posterous, OpenNemas |
| 数据库 | 20 | 8 | Redis, PostgreSQL, Elasticsearch, Microsoft SQL Server, ClickHouse, CouchDB, Cassandra, Apache Doris |
| 数据库审计 | 3 | 3 | 数据库审计系统, 建行云数据库审计系统, 数据库审计系统UDB |
| 数据库管理工具 | 3 | 3 | SQLiteManager, MySQL-Control-Panel, FileMakerPro/4.0 |
| 数据防丢失 | 3 | 3 | LD5200, LD2100, 天融信数据防泄漏系统 |
| 文件管理 | 3 | 3 | GoAnywhere-6.2.4, GoAnywhere-5.0.1, GoAnywhere-5.3.2 |
| 文档管理 | 3 | 3 | 国舜文档管理系统, FS-文件管理系统, WBH-档案管理系统 |
| 日志分析 | 3 | 3 | ModLogAn, 锐捷-大数据安全平台, 建恒信安-日志审计系统 |
| 日志分析系统 | 3 | 3 | FortiAnalyzer-VM, Fortianalyzer-800B, FortiAnalyzer-200D |
| 智能家居 | 3 | 3 | EATON-SC200, TOSHIBA-REGZA-19B3, TOSHIBA-REGZA-26B3 |
| 服务器模块 | 3 | 3 | CISCO-VCI, brother-NC-01h, brother-NC-02w |
| 服务器管理 | 36 | 3 | nginxWebUI, NaviCOPA, 倍网咨询-SF120 |
| 机房监控 | 3 | 3 | iMonitor-DND, AVTECH-TemPageR-3E, AVTECH-TemPageR-4E |
| 水解决方案 | 3 | 3 | 东方世纪-东方祥云, HEDA-智慧水务, InfoMaster-产品 |
| 流量管理 | 3 | 3 | D_Link-DPF-500, InfiniStream-CDM, cPanel-TraceWatch |
| 消息队列 | 4 | 4 | Kafka, RabbitMQ, ActiveMQ, RocketMQ |
| 源代码管理 | 3 | 3 | SegPub, WebGUI, GitLab-Linux-Gitlab-2.6.32 |
| 漏洞扫描 | 3 | 3 | WSTOOL, 铱迅漏洞扫描系统, 天镜脆弱性扫描与管理系统 |
| 物理隔离 | 3 | 3 | 网神-数据自动导入系统, 联软科技-UniNXG, H3C-安全隔离与信息交换系统 |
| 物联网行业 | 3 | 3 | Aliot, armv4l平台, armv5l平台 |
| 电信、邮政行业 | 3 | 3 | BOSS系统登录, 七宝MDR电话录音查询系统, ARRIS-DOCSIS-CMTS |
| 电力行业 | 3 | 3 | 临岐供电所记录系统, 思源充电桩运营平台, 奥动电巴ASS系统 |
| 电商系统 | 3 | 3 | Axous, ECMall, buscape |
| 监控系统 | 3 | 3 | Airflow, Apache SkyWalking, Apache Ranger |
| 石油行业 | 3 | 3 | 加油卡系统, 加油站管理系统, 中石化加油卡查询系统 |
| 硬件服务器 | 3 | 3 | Atop-SE5001A, Atop-SE5001-S2, Atop-SE5001-S5N |
| 移动或商业热点 | 3 | 3 | D_Link-DWL-810+, D_Link-DWL-700AP, D_Link-DWL-2000AP |
| 站长平台 | 3 | 3 | 神马-站长平台, 360-站长平台, Baidu-站长平台 |
| 笔记本 | 3 | 3 | NEC-LAVIE, NEC-NOTEPC, FUJITSU-A573 |
| 终端安全 | 3 | 3 | 默安主机安全防护系统, V8+终端安全系统Web控制台, 护卫神·主机大师-V3.0.0 |
| 统计分析 | 3 | 3 | 易分析, 51la, Mint |
| 网关 | 3 | 3 | BGP协议, H3C-MG6050多媒体网关, ADTRAN-Total-Access-904 |
| 网站云防护 | 3 | 3 | SUCURi, 360wzws, 安恒信息-云防护 |
| 网站模块 | 3 | 3 | mod_jk, mod_hive, mod_apreq2 |
| 网络模块 | 3 | 3 | CISCO-4600, ZTE-Access, MOXA-E1210 |
| 网络空间测绘 | 3 | 3 | D01-探针, 观星-观星台, 奇安信-全球鹰 |
| 网络设备操作系统 | 3 | 3 | DELL-EMC_DATA_DOMAIN, DELL-Isilon-OneFS-DNALink, DELL-Isilon-OneFS-kcisilon |
| 网闸 | 3 | 3 | 网神-光闸, 安全隔离与交换信息系统, 辰锐信息-单向传输系统 |
| 脚本语言 | 3 | 3 | Ruby, Lua/5.1, Lua/5.1.4 |
| 自动化控制 | 3 | 3 | Campbell_SCIENTIFIC-RCS-CR3000-WNM, Campbell_SCIENTIFIC-RCS-CR3000-WEP, Campbell_SCIENTIFIC-RCS-CR3000-VOU |
| 虚拟化 | 3 | 3 | xen4, 易方-EfangVHost, Docker-Enterprise |
| 视频会议 | 3 | 3 | AVAYA-XTE240, Sony-PCS-1-Web-Control, Sony-PCS-11-Web-Control |
| 视频监控 | 8 | 3 | D_Link-DCS-2000, D_Link-DCS-2100, D_Link-DCS-2210 |
| 视频管理产品 | 3 | 3 | HIKVISION-iVMS-5000-安防集成平台, HIKVISION-iVMS-7200-安防集成平台, HIKVISION-iVMS-8310-安防集成平台 |
| 论坛社区 | 3 | 3 | OvBB, TypePad, WiFiDog |
| 访问控制系统 | 3 | 3 | SONY数字身份管理系统, OTPPlus认证管理系统, SKFRM-人脸识别管理系统 |
| 负载均衡 | 3 | 3 | F5 BIG-IP, Citrix ADC, PIOLINK负载均衡 |
| 财务系统 | 3 | 3 | xpe, 学校财务系统, 财务报销系统 |
| 路由器 | 3 | 3 | SMC-router, H3C-AM8000, LINKSYS-WAP |
| 身份认证系统 | 3 | 3 | 统一认证系统, 连网认证系统, 芸台购统一认证系统 |
| 软件工具 | 3 | 3 | Jenkins, Redis Commander, WANem |
| 运维系统 | 3 | 3 | 3k运维系统, 运维支撑工作台, CORS运维系统 |
| 远程管理 | 8 | 3 | Guacamole, Apache Guacamole, Lantronix-UDS |
| 邮件安全 | 3 | 3 | 魔盾邮件安全, KILL邮件安全网关, 网御邮件安全管理系统 |
| 邮件服务器 | 3 | 3 | ESMTP, CloudMail, E-MailRelay |
| 邮件系统 | 3 | 3 | MailMe, Top-Mail, corpmail |
| 金融行业 | 3 | 3 | 资产证券化查询系统, 保险高管在线培训系统, 承保理赔信息查询系统 |
| 门禁系统 | 3 | 3 | 門禁差勤管理系統, 七友-CYT-200SC, 创思软件-门禁视频管理系统 |
| 问题单管理 | 3 | 3 | mantis, AI问题管理系统, BUG提交管理系统 |
| 防火墙 | 3 | 3 | Cisco ASA, FORTINET-FG-80c, FORTINET-FG-60D |
| 防病毒 | 3 | 3 | 奇安信天擎, 360私有云杀毒管理系统, 网御星云-防病毒网关系统 |
| 防篡改系统 | 3 | 3 | 网页防篡改系统, 天翼云-网页防篡改系统, 天融信-网页防篡改系统 |
| 零信任 | 3 | 3 | NSFOCUS-零信任, SANGFOR-aTrust, 奇安信-网神零信任身份服务系统 |
| 项目管理 | 3 | 3 | Confluence, 5D-BIM-工程项目总控系统, e万行动-农村孤儿助养项目信息系统 |
| 黑客工具 | 3 | 3 | frp, Mars, Lanproxy |

## 全部规则 / Full reference

| 名称 / Name | 分类 / Category | 查询 / Query | 核验 / Status |
|---|---|---|---|
| ThinkPHP | 开发框架 | `app="ThinkPHP"` | verified |
| Laravel | 开发框架 | `app="Laravel"` | legacy |
| Django | 开发框架 | `app="django"` | verified |
| Flask | 开发框架 | `app="Flask"` | legacy |
| FastAPI | 开发框架 | `app="FastAPI"` | legacy |
| Spring | 开发框架 | `app="vmware-Spring-Framework"` | verified |
| Struts2 | 开发框架 | `app="Struts2"` | verified |
| ASP.NET | 开发框架 | `app="ASP.NET"` | legacy |
| Node.js | 开发框架 | `app="Node.js"` | legacy |
| Express | 开发框架 | `app="Express"` | verified |
| Yii | 开发框架 | `app="Yii"` | legacy |
| CodeIgniter | 开发框架 | `app="CodeIgniter"` | legacy |
| Symfony | 开发框架 | `app="Symfony"` | legacy |
| Ruby on Rails | 开发框架 | `app="Ruby-on-Rails"` | verified |
| Beego | 开发框架 | `app="Beego"` | legacy |
| Gin | 开发框架 | `app="Gin"` | legacy |
| Dubbo | 开发框架 | `app="APACHE-dubbo"` | verified |
| Shiro | 开发框架 | `app="APACHE-Shiro"` | verified |
| Fastjson | 开发框架 | `app="Fastjson"` | legacy |
| MyBatis | 开发框架 | `app="MyBatis"` | legacy |
| Hibernate | 开发框架 | `app="Hibernate"` | legacy |
| Vue | 开发框架 | `app="Vue.js"` | legacy |
| React | 开发框架 | `app="React"` | legacy |
| Bootstrap | 开发框架 | `app="Bootstrap"` | legacy |
| ThinkCMF | 开发框架 | `app="ThinkCMF"` | legacy |
| JeecgBoot | 开发框架 | `app="JeecgBoot"` | legacy |
| RuoYi | 开发框架 | `app="RuoYi"` | legacy |
| Knife4j | 开发框架 | `app="Knife4j"` | legacy |
| Swagger | 服务器管理 | `app="Swagger"` | legacy |
| Nginx | Web中间件 | `app="Nginx"` | legacy |
| Apache | Web中间件 | `app="APACHE-HTTP_Server"` | legacy |
| Apache Tomcat | Web中间件 | `app="Apache Tomcat"` | legacy |
| Microsoft-IIS | Web中间件 | `app="Microsoft-IIS"` | legacy |
| WebLogic | Web中间件 | `app="BEA-WebLogic-Server"` | legacy |
| JBoss | 应用服务器 | `app="JBoss"` | verified |
| Jetty | Web中间件 | `app="Jetty"` | legacy |
| OpenResty | Web中间件 | `app="OpenResty"` | legacy |
| Tengine | Web中间件 | `app="Tengine"` | legacy |
| Caddy | Web中间件 | `app="Caddy"` | legacy |
| Lighttpd | Web中间件 | `app="lighttpd"` | legacy |
| Resin | Web中间件 | `app="Resin"` | legacy |
| GlassFish | Web中间件 | `app="GlassFish"` | legacy |
| TongWeb | Web中间件 | `app="TongWeb"` | legacy |
| BES | Web中间件 | `app="BES"` | legacy |
| WebSphere | Web中间件 | `app="IBM-WebSphere"` | legacy |
| Undertow | Web中间件 | `app="Undertow"` | legacy |
| HAProxy | 代理 | `app="HAPROXY"` | verified |
| Traefik | 代理 | `app="Traefik"` | verified |
| Squid | Web中间件 | `app="Squid"` | legacy |
| Varnish | Web中间件 | `app="Varnish"` | legacy |
| IIS-FTP | Web中间件 | `app="Microsoft-FTP"` | legacy |
| Redis | 数据库 | `app="redis"` | verified |
| MySQL | 数据库 | `app="MySQL"` | legacy |
| PostgreSQL | 数据库 | `app="PostgreSQL"` | verified |
| MongoDB | 数据库 | `app="MongoDB"` | legacy |
| Elasticsearch | 数据库 | `app="Elasticsearch"` | verified |
| Microsoft SQL Server | 数据库 | `app="Microsoft-SQL-Server"` | verified |
| Oracle | 数据库 | `app="Oracle"` | legacy |
| Kafka | 消息队列 | `app="kafka"` | verified |
| RabbitMQ | 消息队列 | `app="RabbitMQ"` | verified |
| Memcached | 数据库 | `app="Memcached"` | legacy |
| ClickHouse | 数据库 | `app="ClickHouse"` | verified |
| CouchDB | 数据库 | `app="APACHE-CouchDB"` | verified |
| InfluxDB | 数据库 | `app="InfluxDB"` | legacy |
| Neo4j | 数据库 | `app="Neo4j"` | legacy |
| Cassandra | 数据库 | `app="APACHE-Cassandra"` | verified |
| Solr | 大数据 | `app="APACHE-Solr"` | verified |
| ZooKeeper | 大数据 | `app="APACHE-ZooKeeper"` | verified |
| ActiveMQ | 消息队列 | `app="APACHE-ActiveMQ"` | verified |
| RocketMQ | 消息队列 | `app="APACHE-RocketMQ"` | verified |
| HBase | 大数据 | `app="APACHE-HBase"` | verified |
| Hive | 数据库 | `app="Apache-Hive"` | legacy |
| TiDB | 数据库 | `app="TiDB"` | legacy |
| 达梦 | 数据库 | `app="DM-Database"` | legacy |
| 人大金仓 | 数据库 | `app="Kingbase"` | legacy |
| OpenSearch | 数据库 | `app="OpenSearch"` | legacy |
| Druid监控 | 数据库 | `app="Alibaba-Druid"` | legacy |
| Apache Druid | 存储系统 | `app="APACHE-Druid"` | verified |
| 致远OA | OA系统 | `app="致远互联-OA"` | legacy |
| 泛微OA | OA系统 | `app="泛微-协同办公OA"` | verified |
| 泛微E-Office | OA系统 | `app="泛微-EOffice"` | verified |
| 用友NC | OA系统 | `app="用友-UFIDA-NC"` | legacy |
| 用友U8 | OA系统 | `app="用友-U8"` | legacy |
| 用友GRP | OA系统 | `app="用友-GRP-U8"` | legacy |
| 用友畅捷通 | OA系统 | `app="用友畅捷通"` | legacy |
| 金蝶EAS | OA系统 | `app="金蝶"` | legacy |
| 金蝶云星空 | OA系统 | `app="金蝶云星空"` | legacy |
| 金蝶K3 | OA系统 | `app="金蝶-K3"` | legacy |
| 万户OA | OA系统 | `app="万户网络-ezOFFICE"` | verified |
| 华天动力OA | OA系统 | `app="华天动力-OA"` | legacy |
| 金和OA | OA系统 | `app="金和网络-金和OA"` | legacy |
| 红帆OA | OA系统 | `app="红帆-ioffice"` | legacy |
| 新点OA | OA系统 | `app="新点OA"` | legacy |
| 协众OA | OA系统 | `app="协众OA"` | legacy |
| 信呼OA | OA系统 | `app="信呼OA"` | legacy |
| 一米OA | OA系统 | `app="一米OA"` | legacy |
| SAP NetWeaver | OA系统 | `app="SAP-NetWeaver"` | legacy |
| Odoo | OA系统 | `app="Odoo"` | legacy |
| 浪潮GS | OA系统 | `app="浪潮-GS"` | legacy |
| 用友NC Cloud | 企业云平台 | `app="用友-NC-Cloud"` | verified |
| 泛微E-cology | OA系统 | `app="泛微-ecology"` | legacy |
| 致远A8 | OA系统 | `app="致远互联-A8"` | legacy |
| 宏景HR | OA系统 | `app="宏景-HR"` | legacy |
| 明源云 | OA系统 | `app="明源云"` | legacy |
| 广联达 | OA系统 | `app="广联达"` | legacy |
| 帆软报表 | OA系统 | `app="FineReport"` | legacy |
| 禅道 | OA系统 | `app="禅道"` | legacy |
| 深信服VPN | 其他网络产品 | `app="SANGFOR-SSL-VPN"` | legacy |
| 深信服NGAF | 其他类型 | `app="SANGFOR-NGAF"` | verified |
| 深信服AD | 其他网络产品 | `app="SANGFOR-应用交付AD"` | legacy |
| 奇安信VPN | VPN | `app="奇安信-VPN"` | verified |
| 奇安信天擎 | 防病毒 | `app="奇安信-天擎"` | verified |
| Fortinet | 其他网络产品 | `app="FORTINET-防火墙"` | legacy |
| FortiSSLVPN | VPN | `app="FORTINET-SSLVPN"` | verified |
| Cisco ASA | 防火墙 | `app="CISCO-ASA"` | verified |
| Pulse Secure | 其他网络产品 | `app="PULSE-SECURE-VPN"` | legacy |
| Array VPN | 其他网络产品 | `app="Array-VPN"` | legacy |
| Ruijie | 其他网络产品 | `app="Ruijie"` | legacy |
| 天融信VPN | 其他网络产品 | `app="天融信-VPN"` | legacy |
| 启明星辰 | 其他网络产品 | `app="Venustech"` | legacy |
| 绿盟WAF | 其他网络产品 | `app="NSFOCUS-WAF"` | legacy |
| 安恒明御 | 其他网络产品 | `app="安恒信息-明御WAF"` | legacy |
| 长亭WAF | 其他网络产品 | `app="长亭科技-WAF"` | legacy |
| 雷池WAF | 其他网络产品 | `app="SafeLine"` | legacy |
| Palo Alto | 其他网络产品 | `app="PaloAlto-防火墙"` | legacy |
| Check Point | 其他网络产品 | `app="Check_Point"` | legacy |
| SonicWall | 其他网络产品 | `app="SONICWALL-SSL-VPN"` | legacy |
| F5 BIG-IP | 负载均衡 | `app="f5-BIGIP"` | verified |
| Citrix ADC | 负载均衡 | `app="citrix-Netscaler"` | verified |
| OpenVPN | VPN | `app="OPENVPN"` | verified |
| 山石网科 | 其他网络产品 | `app="Hillstone"` | legacy |
| 360天擎 | 其他网络产品 | `app="360天擎"` | legacy |
| Cloudflare | 其他网络产品 | `app="Cloudflare"` | legacy |
| Microsoft Exchange | 协作产品 | `app="Microsoft-Exchange"` | legacy |
| Zimbra | 协作产品 | `app="Zimbra"` | legacy |
| Roundcube | 协作产品 | `app="Roundcube"` | legacy |
| Coremail | 协作产品 | `app="Coremail"` | legacy |
| 亿邮 | 协作产品 | `app="亿邮"` | legacy |
| RainLoop | 协作产品 | `app="RainLoop"` | legacy |
| SquirrelMail | 协作产品 | `app="SquirrelMail"` | legacy |
| IceWarp | 协作产品 | `app="IceWarp"` | legacy |
| Confluence | 项目管理 | `app="ATLASSIAN-Confluence"` | verified |
| Jira | 协作产品 | `app="JIRA"` | legacy |
| ShowDoc | 协作产品 | `app="ShowDoc"` | legacy |
| YApi | 协作产品 | `app="YApi"` | legacy |
| Nextcloud | 其他类型 | `app="Nextcloud"` | verified |
| ownCloud | 协作产品 | `app="ownCloud"` | legacy |
| Seafile | 协作产品 | `app="Seafile"` | legacy |
| 可道云 | 协作产品 | `app="KodExplorer"` | legacy |
| Grafana | 其他类型 | `app="Grafana"` | verified |
| Jenkins | 软件工具 | `app="Jenkins"` | verified |
| GitLab | 服务器管理 | `app="GitLab"` | legacy |
| Gitea | 服务器管理 | `app="Gitea"` | legacy |
| Gogs | 服务器管理 | `app="Gogs"` | legacy |
| Harbor | docker管理 | `app="HARBOR"` | verified |
| Nexus | 服务器管理 | `app="Nexus"` | legacy |
| Artifactory | 服务器管理 | `app="Artifactory"` | legacy |
| Kibana | 服务器管理 | `app="Kibana"` | legacy |
| phpMyAdmin | 服务器管理 | `app="phpMyAdmin"` | legacy |
| Adminer | 服务器管理 | `app="Adminer"` | legacy |
| pgAdmin | 服务器管理 | `app="pgAdmin"` | legacy |
| Nacos | 服务器管理 | `app="Nacos"` | legacy |
| xxl-job | 服务器管理 | `app="xxl-job"` | legacy |
| Apollo | 服务器管理 | `app="Apollo"` | legacy |
| Consul | 服务器管理 | `app="Consul"` | legacy |
| Vault | 服务器管理 | `app="Vault"` | legacy |
| Zabbix | 服务器管理 | `app="ZABBIX-监控系统"` | legacy |
| Prometheus | 服务器管理 | `app="Prometheus"` | legacy |
| Webmin | 服务器管理 | `app="Webmin"` | legacy |
| 宝塔 | 服务器管理 | `app="宝塔-BT.cn"` | legacy |
| 1Panel | 服务器管理 | `app="1Panel"` | legacy |
| cPanel | 服务器管理 | `app="cPanel"` | legacy |
| Plesk | 服务器管理 | `app="Plesk"` | legacy |
| JumpServer | 堡垒机 | `app="Jumpserver"` | verified |
| Rancher | 服务器管理 | `app="Rancher"` | legacy |
| Portainer | docker管理 | `app="portainer"` | verified |
| SonarQube | 服务器管理 | `app="SonarQube"` | legacy |
| Airflow | 监控系统 | `app="APACHE-Airflow"` | verified |
| Superset | 企业云平台 | `app="APACHE-Superset"` | verified |
| Jupyter | 服务器管理 | `app="Jupyter-Notebook"` | legacy |
| DolphinScheduler | 服务器管理 | `app="DolphinScheduler"` | legacy |
| Cacti | 服务器管理 | `app="Cacti"` | legacy |
| Nagios | 服务器管理 | `app="Nagios"` | legacy |
| Netdata | 服务器管理 | `app="Netdata"` | legacy |
| Uptime Kuma | 服务器管理 | `app="Uptime-Kuma"` | legacy |
| Kubernetes Dashboard | 服务器管理 | `app="Kubernetes-Dashboard"` | legacy |
| phpStudy | 服务器管理 | `app="phpStudy"` | legacy |
| WDCP | 服务器管理 | `app="WDCP"` | legacy |
| Kubernetes | 企业云平台 | `app="Kubernetes"` | legacy |
| Docker | 企业云平台 | `app="Docker-Daemon"` | legacy |
| MinIO | 企业云平台 | `app="MinIO"` | legacy |
| etcd | 企业云平台 | `app="etcd"` | legacy |
| VMware ESXi | 企业云平台 | `app="VMware-ESXi"` | legacy |
| vCenter | 企业云平台 | `app="VMware-vCenter"` | legacy |
| Proxmox | 企业云平台 | `app="Proxmox-VE"` | legacy |
| OpenStack | 企业云平台 | `app="OpenStack"` | legacy |
| Istio | 企业云平台 | `app="Istio"` | legacy |
| 海康威视 | 视频监控 | `app="HIKVISION-视频监控"` | legacy |
| 天地伟业 | 视频监控 | `app="Tiandy"` | legacy |
| Axis | 视频监控 | `app="AXIS"` | legacy |
| Foscam | 视频监控 | `app="Foscam"` | legacy |
| 中威电子 | 视频监控 | `app="TVT"` | legacy |
| WordPress | CMS | `app="WordPress"` | legacy |
| Discuz | CMS | `app="Discuz"` | legacy |
| Drupal | CMS | `app="Drupal"` | legacy |
| Joomla | CMS | `app="Joomla"` | legacy |
| DedeCMS | CMS | `app="DedeCMS"` | legacy |
| EmpireCMS | CMS | `app="EmpireCMS"` | legacy |
| PHPCMS | CMS | `app="PHPCMS"` | legacy |
| MetInfo | CMS | `app="MetInfo"` | legacy |
| Typecho | CMS | `app="Typecho"` | legacy |
| Ghost | CMS | `app="Ghost"` | legacy |
| PbootCMS | CMS | `app="PbootCMS"` | legacy |
| ECShop | CMS | `app="ECShop"` | legacy |
| Magento | CMS | `app="Magento"` | legacy |
| ShopXO | CMS | `app="ShopXO"` | legacy |
| 群晖 | NAS | `app="Synology"` | legacy |
| QNAP | NAS | `app="QNAP-NAS"` | legacy |
| TrueNAS | NAS | `app="TrueNAS"` | legacy |
| OpenMediaVault | NAS | `app="OpenMediaVault"` | legacy |
| 向日葵 | 远程管理 | `app="Oray"` | legacy |
| ToDesk | 远程管理 | `app="ToDesk"` | legacy |
| RustDesk | 远程管理 | `app="RustDesk"` | legacy |
| TeamViewer | 远程管理 | `app="TeamViewer"` | legacy |
| AnyDesk | 远程管理 | `app="AnyDesk"` | legacy |
| Guacamole | 远程管理 | `app="guacamole"` | verified |
| Hadoop | 大数据 | `app="Hadoop"` | verified |
| Spark | 大数据 | `app="Apache-Spark"` | legacy |
| Flink | 大数据 | `app="APACHE-Flink"` | verified |
| Hue | 大数据 | `app="Hue"` | legacy |
| Ambari | 大数据 | `app="APACHE-Ambari"` | verified |
| UEditor | CMS | `app="UEditor"` | legacy |
| Spring Boot | 开发框架 | `app="vmware-SpringBoot-Framework"` | verified |
| Spring Boot Admin | 开发框架 | `app="Spring-Boot-Admin"` | verified |
| Apache APISIX | 应用网关 | `app="APACHE-APISIX"` | verified |
| Kafka UI | 其他组件 | `app="APACHE-Kafka-UI"` | verified |
| Apache Doris | 数据库 | `app="APACHE-DORIS"` | verified |
| Nginx Proxy Manager | 其他组件 | `app="Nginx-Proxy-Manager"` | verified |
| nginxWebUI | 服务器管理 | `app="nginxWebUI"` | verified |
| Redis Commander | 软件工具 | `app="Redis-Commander"` | verified |
| RedisInsight | 其他类型 | `app="RedisInsight"` | verified |
| Spring Security | 开发框架 | `app="vmware-Spring-Security"` | verified |
| Apache Guacamole | 远程管理 | `app="APACHE-Guacamole"` | verified |
| Apache SkyWalking | 监控系统 | `app="APACHE-Skywalking"` | verified |
| Apache Ranger | 监控系统 | `app="Apache-Ranger"` | verified |
| Ruby | 脚本语言 | `app="Ruby"` | verified |
| JEUS | Web服务器 | `app="JEUS"` | verified |
| Intrasrv | Web服务器 | `app="Intrasrv"` | verified |
| AMR-WinControl | Web服务器 | `app="AMR-WinControl"` | verified |
| MailMe | 邮件系统 | `app="MailMe"` | verified |
| Top-Mail | 邮件系统 | `app="Top-Mail"` | verified |
| corpmail | 邮件系统 | `app="corpmail"` | verified |
| Canon-MF220 | 打印或复印机 | `app="Canon-MF220"` | verified |
| Canon-LBP6300 | 打印或复印机 | `app="Canon-LBP6300"` | verified |
| Lenovo-LJ2655 | 打印或复印机 | `app="Lenovo-LJ2655"` | verified |
| SMC-router | 路由器 | `app="SMC-router"` | verified |
| H3C-AM8000 | 路由器 | `app="H3C-AM8000"` | verified |
| LINKSYS-WAP | 路由器 | `app="LINKSYS-WAP"` | verified |
| DORG | 其他组件 | `app="DORG"` | verified |
| D_Link-DCS-2000 | 视频监控 | `app="D_Link-DCS-2000"` | verified |
| D_Link-DCS-2100 | 视频监控 | `app="D_Link-DCS-2100"` | verified |
| D_Link-DCS-2210 | 视频监控 | `app="D_Link-DCS-2210"` | verified |
| NS-BSD | 操作系统 | `app="NS-BSD"` | verified |
| Linux-CERN | 操作系统 | `app="Linux-CERN"` | verified |
| Red-Giant-公司产品 | 操作系统 | `app="Red-Giant-公司产品"` | verified |
| EZCMS | CMS | `app="EZCMS"` | verified |
| HoloCMS | CMS | `app="HoloCMS"` | verified |
| Gallery | CMS | `app="Gallery"` | verified |
| H3C-S系列产品 | 交换机 | `app="H3C-S系列产品"` | verified |
| ZYXEL-ES-2024 | 交换机 | `app="ZYXEL-ES-2024"` | verified |
| ZYXEL-ES-2048 | 交换机 | `app="ZYXEL-ES-2048"` | verified |
| TP_LINK-TD-8616 | ADSL | `app="TP_LINK-TD-8616"` | verified |
| TP_LINK-TD-8840TB | ADSL | `app="TP_LINK-TD-8840TB"` | verified |
| TP_LINK-TD-W8901N | ADSL | `app="TP_LINK-TD-W8901N"` | verified |
| DELL-EMC_DATA_DOMAIN | 网络设备操作系统 | `app="DELL-EMC_DATA_DOMAIN"` | verified |
| DELL-Isilon-OneFS-DNALink | 网络设备操作系统 | `app="DELL-Isilon-OneFS-DNALink"` | verified |
| DELL-Isilon-OneFS-kcisilon | 网络设备操作系统 | `app="DELL-Isilon-OneFS-kcisilon"` | verified |
| BGP协议 | 网关 | `app="BGP协议"` | verified |
| H3C-MG6050多媒体网关 | 网关 | `app="H3C-MG6050多媒体网关"` | verified |
| ADTRAN-Total-Access-904 | 网关 | `app="ADTRAN-Total-Access-904"` | verified |
| Lantronix-UDS | 远程管理 | `app="Lantronix-UDS"` | verified |
| 管理易 | 企业管理 | `app="管理易"` | verified |
| CEMIS | 企业管理 | `app="CEMIS"` | verified |
| 思迅-星食客 | 企业管理 | `app="思迅-星食客"` | verified |
| WANem | 软件工具 | `app="WANem"` | verified |
| EATON-SC200 | 智能家居 | `app="EATON-SC200"` | verified |
| TOSHIBA-REGZA-19B3 | 智能家居 | `app="TOSHIBA-REGZA-19B3"` | verified |
| TOSHIBA-REGZA-26B3 | 智能家居 | `app="TOSHIBA-REGZA-26B3"` | verified |
| VTScada | 工业控制 | `app="VTScada"` | verified |
| PowerLink | 工业控制 | `app="PowerLink"` | verified |
| RTS-SCADA | 工业控制 | `app="RTS-SCADA"` | verified |
| Mitel-6731i | VOIP | `app="Mitel-6731i"` | verified |
| Mitel-6735i | VOIP | `app="Mitel-6735i"` | verified |
| Mitel-6737i | VOIP | `app="Mitel-6737i"` | verified |
| FORTINET-FG-80c | 防火墙 | `app="FORTINET-FG-80c"` | verified |
| FORTINET-FG-60D | 防火墙 | `app="FORTINET-FG-60D"` | verified |
| mod_jk | 网站模块 | `app="mod_jk"` | verified |
| mod_hive | 网站模块 | `app="mod_hive"` | verified |
| mod_apreq2 | 网站模块 | `app="mod_apreq2"` | verified |
| CASA-C10G | 其他网络产品 | `app="CASA-C10G"` | verified |
| CASA-C40G | 其他网络产品 | `app="CASA-C40G"` | verified |
| CASA-C100G | 其他网络产品 | `app="CASA-C100G"` | verified |
| D_Link-DWL-810+ | 移动或商业热点 | `app="D_Link-DWL-810+"` | verified |
| D_Link-DWL-700AP | 移动或商业热点 | `app="D_Link-DWL-700AP"` | verified |
| D_Link-DWL-2000AP | 移动或商业热点 | `app="D_Link-DWL-2000AP"` | verified |
| Aliot | 物联网行业 | `app="Aliot"` | verified |
| armv4l平台 | 物联网行业 | `app="armv4l平台"` | verified |
| armv5l平台 | 物联网行业 | `app="armv5l平台"` | verified |
| Lua/5.1 | 脚本语言 | `app="Lua/5.1"` | verified |
| Lua/5.1.4 | 脚本语言 | `app="Lua/5.1.4"` | verified |
| Dorado | Web中间件 | `app="Dorado"` | verified |
| Webesp | Web中间件 | `app="Webesp"` | verified |
| HornetQ | Web中间件 | `app="HornetQ"` | verified |
| FHFS | 应用服务器 | `app="FHFS"` | verified |
| Sling | 应用服务器 | `app="Sling"` | verified |
| CISCO-VCI | 服务器模块 | `app="CISCO-VCI"` | verified |
| brother-NC-01h | 服务器模块 | `app="brother-NC-01h"` | verified |
| brother-NC-02w | 服务器模块 | `app="brother-NC-02w"` | verified |
| 海泰-key验证 | 其他安全产品 | `app="海泰-key验证"` | verified |
| 金格-key验证 | 其他安全产品 | `app="金格-key验证"` | verified |
| BASIC-AUTH | 其他安全产品 | `app="BASIC-AUTH"` | verified |
| NaviCOPA | 服务器管理 | `app="NaviCOPA"` | verified |
| 倍网咨询-SF120 | 服务器管理 | `app="倍网咨询-SF120"` | verified |
| TVW3800 | 媒体设备 | `app="TVW3800"` | verified |
| DCX-3450 | 媒体设备 | `app="DCX-3450"` | verified |
| DCX-3520 | 媒体设备 | `app="DCX-3520"` | verified |
| ACAA考试系统登录 | 教育行业 | `app="ACAA考试系统登录"` | verified |
| 乐智教育系统beta | 教育行业 | `app="乐智教育系统beta"` | verified |
| ROMI在线培训系统 | 教育行业 | `app="ROMI在线培训系统"` | verified |
| 迪奥信息-火眼洞察平台 | 企业云平台 | `app="迪奥信息-火眼洞察平台"` | verified |
| oroCRM | CRM | `app="oroCRM"` | verified |
| EMS-CRM-Login | CRM | `app="EMS-CRM-Login"` | verified |
| GOT-CRM-Login | CRM | `app="GOT-CRM-Login"` | verified |
| CISCO-4600 | 网络模块 | `app="CISCO-4600"` | verified |
| ZTE-Access | 网络模块 | `app="ZTE-Access"` | verified |
| MOXA-E1210 | 网络模块 | `app="MOXA-E1210"` | verified |
| APERP | ERP | `app="APERP"` | verified |
| 万物工业-ERP | ERP | `app="万物工业-ERP"` | verified |
| 博库-医院在线考试系统 | ERP | `app="博库-医院在线考试系统"` | verified |
| DBR-M190 | DVR | `app="DBR-M190"` | verified |
| DBR-T350 | DVR | `app="DBR-T350"` | verified |
| DBR-T450 | DVR | `app="DBR-T450"` | verified |
| HIKVISION-iVMS-5000-安防集成平台 | 视频管理产品 | `app="HIKVISION-iVMS-5000-安防集成平台"` | verified |
| HIKVISION-iVMS-7200-安防集成平台 | 视频管理产品 | `app="HIKVISION-iVMS-7200-安防集成平台"` | verified |
| HIKVISION-iVMS-8310-安防集成平台 | 视频管理产品 | `app="HIKVISION-iVMS-8310-安防集成平台"` | verified |
| ZTE-ZXV10-H118N | Modem | `app="ZTE-ZXV10-H118N"` | verified |
| Cybertec-Series-1000 | Modem | `app="Cybertec-Series-1000"` | verified |
| Cybertec-Series-2000 | Modem | `app="Cybertec-Series-2000"` | verified |
| ASUS-FreeNas | NAS | `app="ASUS-FreeNas"` | verified |
| Lenovo-LenovoEMC-ix4-300d | NAS | `app="Lenovo-LenovoEMC-ix4-300d"` | verified |
| Raidweb-Maxtronic-Orion-410ST | NAS | `app="Raidweb-Maxtronic-Orion-410ST"` | verified |
| 5D-BIM-工程项目总控系统 | 项目管理 | `app="5D-BIM-工程项目总控系统"` | verified |
| e万行动-农村孤儿助养项目信息系统 | 项目管理 | `app="e万行动-农村孤儿助养项目信息系统"` | verified |
| 中药煎药系统 | 医疗行业 | `app="中药煎药系统"` | verified |
| HIS综合查询系统 | 医疗行业 | `app="HIS综合查询系统"` | verified |
| 体检预约/查询系统 | 医疗行业 | `app="体检预约/查询系统"` | verified |
| JUNIPer-SSG-350M | 安全网关 | `app="JUNIPer-SSG-350M"` | verified |
| DELL-SonicWALL-SMA-400 | 安全网关 | `app="DELL-SonicWALL-SMA-400"` | verified |
| DELL-SonicWALL-SMA-500v | 安全网关 | `app="DELL-SonicWALL-SMA-500v"` | verified |
| Atop-SE5001A | 硬件服务器 | `app="Atop-SE5001A"` | verified |
| Atop-SE5001-S2 | 硬件服务器 | `app="Atop-SE5001-S2"` | verified |
| Atop-SE5001-S5N | 硬件服务器 | `app="Atop-SE5001-S5N"` | verified |
| GW212 | 串口服务器 | `app="GW212"` | verified |
| GW312 | 串口服务器 | `app="GW312"` | verified |
| MOXA/UC7101 | 串口服务器 | `app="MOXA/UC7101"` | verified |
| ESMTP | 邮件服务器 | `app="ESMTP"` | verified |
| CloudMail | 邮件服务器 | `app="CloudMail"` | verified |
| E-MailRelay | 邮件服务器 | `app="E-MailRelay"` | verified |
| Cesar | FTP服务器 | `app="Cesar"` | verified |
| AXIS-ftp | FTP服务器 | `app="AXIS-ftp"` | verified |
| WinFtp服务器 | FTP服务器 | `app="WinFtp服务器"` | verified |
| AVAYA-XTE240 | 视频会议 | `app="AVAYA-XTE240"` | verified |
| Sony-PCS-1-Web-Control | 视频会议 | `app="Sony-PCS-1-Web-Control"` | verified |
| Sony-PCS-11-Web-Control | 视频会议 | `app="Sony-PCS-11-Web-Control"` | verified |
| UX绩效系统 | HR系统 | `app="UX绩效系统"` | verified |
| HRIS招聘系统 | HR系统 | `app="HRIS招聘系统"` | verified |
| 汇视星查寝考勤系统 | HR系统 | `app="汇视星查寝考勤系统"` | verified |
| RapidSSL-Cert | SSL证书 | `app="RapidSSL-Cert"` | verified |
| Apple-IST-CA-2-G1 | SSL证书 | `app="Apple-IST-CA-2-G1"` | verified |
| WoTrus-OV-Server-CA | SSL证书 | `app="WoTrus-OV-Server-CA"` | verified |
| SM-G900F | 其他终端 | `app="SM-G900F"` | verified |
| SM-G955F | 其他终端 | `app="SM-G955F"` | verified |
| OnePlus3 | 其他终端 | `app="OnePlus3"` | verified |
| xen4 | 虚拟化 | `app="xen4"` | verified |
| 易方-EfangVHost | 虚拟化 | `app="易方-EfangVHost"` | verified |
| Docker-Enterprise | 虚拟化 | `app="Docker-Enterprise"` | verified |
| 优制云 | 工业互联网行业 | `app="优制云"` | verified |
| 工业主动防御系统 | 工业互联网行业 | `app="工业主动防御系统"` | verified |
| 工业图纸比对系统 | 工业互联网行业 | `app="工业图纸比对系统"` | verified |
| Aptproxy | 代理 | `app="Aptproxy"` | verified |
| SQLiteManager | 数据库管理工具 | `app="SQLiteManager"` | verified |
| MySQL-Control-Panel | 数据库管理工具 | `app="MySQL-Control-Panel"` | verified |
| FileMakerPro/4.0 | 数据库管理工具 | `app="FileMakerPro/4.0"` | verified |
| 3k运维系统 | 运维系统 | `app="3k运维系统"` | verified |
| 运维支撑工作台 | 运维系统 | `app="运维支撑工作台"` | verified |
| CORS运维系统 | 运维系统 | `app="CORS运维系统"` | verified |
| Axous | 电商系统 | `app="Axous"` | verified |
| ECMall | 电商系统 | `app="ECMall"` | verified |
| buscape | 电商系统 | `app="buscape"` | verified |
| IPSCAN设备 | 存储系统 | `app="IPSCAN设备"` | verified |
| STORAGE-0000 | 存储系统 | `app="STORAGE-0000"` | verified |
| 临岐供电所记录系统 | 电力行业 | `app="临岐供电所记录系统"` | verified |
| 思源充电桩运营平台 | 电力行业 | `app="思源充电桩运营平台"` | verified |
| 奥动电巴ASS系统 | 电力行业 | `app="奥动电巴ASS系统"` | verified |
| D_Link-DP-100 | 打印服务器 | `app="D_Link-DP-100"` | verified |
| D_Link-DP-301 | 打印服务器 | `app="D_Link-DP-301"` | verified |
| D_Link-DP-302 | 打印服务器 | `app="D_Link-DP-302"` | verified |
| 车次查询系统 | 交通行业 | `app="车次查询系统"` | verified |
| 微信公交查询系统 | 交通行业 | `app="微信公交查询系统"` | verified |
| 船舶网上申报系统 | 交通行业 | `app="船舶网上申报系统"` | verified |
| Chatbox | 人工智能 | `app="Chatbox"` | verified |
| CVAT-AI | 人工智能 | `app="CVAT-AI"` | verified |
| Kotaemon | 人工智能 | `app="Kotaemon"` | verified |
| Skylable-SX | 业务解决方案 | `app="Skylable-SX"` | verified |
| 3DPrinterOS | 业务解决方案 | `app="3DPrinterOS"` | verified |
| 碧海威L7云流控运营商版 | 业务解决方案 | `app="碧海威L7云流控运营商版"` | verified |
| podPress | CMS插件 | `app="podPress"` | verified |
| Pressflow | CMS插件 | `app="Pressflow"` | verified |
| qTranslate | CMS插件 | `app="qTranslate"` | verified |
| fibjs/0.10.0 | 前端库 | `app="fibjs/0.10.0"` | verified |
| fibjs/0.11.0 | 前端库 | `app="fibjs/0.11.0"` | verified |
| fibjs/0.12.0 | 前端库 | `app="fibjs/0.12.0"` | verified |
| ASUS-PC | 台式机 | `app="ASUS-PC"` | verified |
| Apple-iMac10,1 | 台式机 | `app="Apple-iMac10,1"` | verified |
| Apple-iMac11,1 | 台式机 | `app="Apple-iMac11,1"` | verified |
| Campbell_SCIENTIFIC-RCS-CR3000-WNM | 自动化控制 | `app="Campbell_SCIENTIFIC-RCS-CR3000-WNM"` | verified |
| Campbell_SCIENTIFIC-RCS-CR3000-WEP | 自动化控制 | `app="Campbell_SCIENTIFIC-RCS-CR3000-WEP"` | verified |
| Campbell_SCIENTIFIC-RCS-CR3000-VOU | 自动化控制 | `app="Campbell_SCIENTIFIC-RCS-CR3000-VOU"` | verified |
| xpe | 财务系统 | `app="xpe"` | verified |
| 学校财务系统 | 财务系统 | `app="学校财务系统"` | verified |
| 财务报销系统 | 财务系统 | `app="财务报销系统"` | verified |
| Winconnection | UTM | `app="Winconnection"` | verified |
| Hansol-NexG-VForce406 | UTM | `app="Hansol-NexG-VForce406"` | verified |
| Hansol-NexG-VForce1406 | UTM | `app="Hansol-NexG-VForce1406"` | verified |
| zkui | 其他企业应用 | `app="zkui"` | verified |
| Wekan-开源看板 | 其他企业应用 | `app="Wekan-开源看板"` | verified |
| CashFactory | 其他企业应用 | `app="CashFactory"` | verified |
| HP-T310 | 其他服务器产品 | `app="HP-T310"` | verified |
| AXIS-70U | 其他服务器产品 | `app="AXIS-70U"` | verified |
| TBDev-YSE | 其他服务器产品 | `app="TBDev-YSE"` | verified |
| 中国商品追溯防伪查询系统 | 政府行业 | `app="中国商品追溯防伪查询系统"` | verified |
| 公共资源综合网上交易系统 | 政府行业 | `app="公共资源综合网上交易系统"` | verified |
| 浙江省律师综合管理信息系统 | 政府行业 | `app="浙江省律师综合管理信息系统"` | verified |
| 酷狗-CDN | CDN | `app="酷狗-CDN"` | verified |
| L7Cache | CDN | `app="L7Cache"` | verified |
| PokeCDN | CDN | `app="PokeCDN"` | verified |
| PHP121 | 客服系统 | `app="PHP121"` | verified |
| 68客服系统 | 客服系统 | `app="68客服系统"` | verified |
| 花花网客服系统 | 客服系统 | `app="花花网客服系统"` | verified |
| OvBB | 论坛社区 | `app="OvBB"` | verified |
| TypePad | 论坛社区 | `app="TypePad"` | verified |
| WiFiDog | 论坛社区 | `app="WiFiDog"` | verified |
| 蓝盾-WAF | WAF | `app="蓝盾-WAF"` | verified |
| 360-一启快 | WAF | `app="360-一启快"` | verified |
| Teros-WAF | WAF | `app="Teros-WAF"` | verified |
| GoAnywhere-6.2.4 | 文件管理 | `app="GoAnywhere-6.2.4"` | verified |
| GoAnywhere-5.0.1 | 文件管理 | `app="GoAnywhere-5.0.1"` | verified |
| GoAnywhere-5.3.2 | 文件管理 | `app="GoAnywhere-5.3.2"` | verified |
| KVM-SV1042 | KVM切换器 | `app="KVM-SV1042"` | verified |
| KVM-SV1204 | KVM切换器 | `app="KVM-SV1204"` | verified |
| KVM-SV1242 | KVM切换器 | `app="KVM-SV1242"` | verified |
| 统一认证系统 | 身份认证系统 | `app="统一认证系统"` | verified |
| 连网认证系统 | 身份认证系统 | `app="连网认证系统"` | verified |
| 芸台购统一认证系统 | 身份认证系统 | `app="芸台购统一认证系统"` | verified |
| PIOLINK负载均衡 | 负载均衡 | `app="PIOLINK负载均衡"` | verified |
| IQ3 | 嵌入式Web服务器 | `app="IQ3"` | verified |
| NET-ARM-Web-Server | 嵌入式Web服务器 | `app="NET-ARM-Web-Server"` | verified |
| Wireless-Product-Web-Server | 嵌入式Web服务器 | `app="Wireless-Product-Web-Server"` | verified |
| NEC-LAVIE | 笔记本 | `app="NEC-LAVIE"` | verified |
| NEC-NOTEPC | 笔记本 | `app="NEC-NOTEPC"` | verified |
| FUJITSU-A573 | 笔记本 | `app="FUJITSU-A573"` | verified |
| cgminer | 区块链 | `app="cgminer"` | verified |
| 挖金后台管理系统 | 区块链 | `app="挖金后台管理系统"` | verified |
| 区块链管理系统后台 | 区块链 | `app="区块链管理系统后台"` | verified |
| 国舜文档管理系统 | 文档管理 | `app="国舜文档管理系统"` | verified |
| FS-文件管理系统 | 文档管理 | `app="FS-文件管理系统"` | verified |
| WBH-档案管理系统 | 文档管理 | `app="WBH-档案管理系统"` | verified |
| FortiAnalyzer-VM | 日志分析系统 | `app="FortiAnalyzer-VM"` | verified |
| Fortianalyzer-800B | 日志分析系统 | `app="Fortianalyzer-800B"` | verified |
| FortiAnalyzer-200D | 日志分析系统 | `app="FortiAnalyzer-200D"` | verified |
| Apple-Xserve-RAID | 存储管理 | `app="Apple-Xserve-RAID"` | verified |
| NetApp-NetApp-Release-7.3.4 | 存储管理 | `app="NetApp-NetApp-Release-7.3.4"` | verified |
| NetApp-NetApp-Release-7.2.2 | 存储管理 | `app="NetApp-NetApp-Release-7.2.2"` | verified |
| 华铄云服务器 | 云计算 | `app="华铄云服务器"` | verified |
| PL云服务系统 | 云计算 | `app="PL云服务系统"` | verified |
| 尽职调查云服务 | 云计算 | `app="尽职调查云服务"` | verified |
| frp | 黑客工具 | `app="frp"` | verified |
| Mars | 黑客工具 | `app="Mars"` | verified |
| Lanproxy | 黑客工具 | `app="Lanproxy"` | verified |
| D_Link-DPF-500 | 流量管理 | `app="D_Link-DPF-500"` | verified |
| InfiniStream-CDM | 流量管理 | `app="InfiniStream-CDM"` | verified |
| cPanel-TraceWatch | 流量管理 | `app="cPanel-TraceWatch"` | verified |
| 易分析 | 统计分析 | `app="易分析"` | verified |
| 51la | 统计分析 | `app="51la"` | verified |
| Mint | 统计分析 | `app="Mint"` | verified |
| SegPub | 源代码管理 | `app="SegPub"` | verified |
| WebGUI | 源代码管理 | `app="WebGUI"` | verified |
| GitLab-Linux-Gitlab-2.6.32 | 源代码管理 | `app="GitLab-Linux-Gitlab-2.6.32"` | verified |
| plesk-Onyx-17.5.3 | 托管平台 | `app="plesk-Onyx-17.5.3"` | verified |
| plesk-Onyx-17.8.1 | 托管平台 | `app="plesk-Onyx-17.8.1"` | verified |
| plesk-Onyx-17.8.2 | 托管平台 | `app="plesk-Onyx-17.8.2"` | verified |
| 网络安全审计系统 | 安全审计 | `app="网络安全审计系统"` | verified |
| 网络行为审计系统 | 安全审计 | `app="网络行为审计系统"` | verified |
| 网御网络审计系统 | 安全审计 | `app="网御网络审计系统"` | verified |
| 数字标牌管理系统 | 户外广告 | `app="数字标牌管理系统"` | verified |
| DSS-数字标牌系统 | 户外广告 | `app="DSS-数字标牌系统"` | verified |
| IPUB联网数字标牌平台 | 户外广告 | `app="IPUB联网数字标牌平台"` | verified |
| UMG51 | UPS监控 | `app="UMG51"` | verified |
| UMG60 | UPS监控 | `app="UMG60"` | verified |
| UMG604 | UPS监控 | `app="UMG604"` | verified |
| BOSS系统登录 | 电信、邮政行业 | `app="BOSS系统登录"` | verified |
| 七宝MDR电话录音查询系统 | 电信、邮政行业 | `app="七宝MDR电话录音查询系统"` | verified |
| ARRIS-DOCSIS-CMTS | 电信、邮政行业 | `app="ARRIS-DOCSIS-CMTS"` | verified |
| 云堡垒机 | 堡垒机 | `app="云堡垒机"` | verified |
| 丞风堡垒机 | 堡垒机 | `app="丞风堡垒机"` | verified |
| 志愿警察查询系统 | 公安行业 | `app="志愿警察查询系统"` | verified |
| 警务综合管理系统 | 公安行业 | `app="警务综合管理系统"` | verified |
| 执行案件信息查询系统 | 公安行业 | `app="执行案件信息查询系统"` | verified |
| SONY数字身份管理系统 | 访问控制系统 | `app="SONY数字身份管理系统"` | verified |
| OTPPlus认证管理系统 | 访问控制系统 | `app="OTPPlus认证管理系统"` | verified |
| SKFRM-人脸识别管理系统 | 访问控制系统 | `app="SKFRM-人脸识别管理系统"` | verified |
| paas-web | Web-Service | `app="paas-web"` | verified |
| 腾讯-Web-Server | Web-Service | `app="腾讯-Web-Server"` | verified |
| eSolar-Cubo-Light | Web-Service | `app="eSolar-Cubo-Light"` | verified |
| iMonitor-DND | 机房监控 | `app="iMonitor-DND"` | verified |
| AVTECH-TemPageR-3E | 机房监控 | `app="AVTECH-TemPageR-3E"` | verified |
| AVTECH-TemPageR-4E | 机房监控 | `app="AVTECH-TemPageR-4E"` | verified |
| ipeer | 教学考试系统 | `app="ipeer"` | verified |
| Judge0 | 教学考试系统 | `app="Judge0"` | verified |
| TCExam | 教学考试系统 | `app="TCExam"` | verified |
| 初始化京东云面板 | 云主机 | `app="初始化京东云面板"` | verified |
| 云主机管理控制台 | 云主机 | `app="云主机管理控制台"` | verified |
| 主机宝Linux版 | 云主机 | `app="主机宝Linux版"` | verified |
| 默安主机安全防护系统 | 终端安全 | `app="默安主机安全防护系统"` | verified |
| V8+终端安全系统Web控制台 | 终端安全 | `app="V8+终端安全系统Web控制台"` | verified |
| 护卫神·主机大师-V3.0.0 | 终端安全 | `app="护卫神·主机大师-V3.0.0"` | verified |
| WSTOOL | 漏洞扫描 | `app="WSTOOL"` | verified |
| 铱迅漏洞扫描系统 | 漏洞扫描 | `app="铱迅漏洞扫描系统"` | verified |
| 天镜脆弱性扫描与管理系统 | 漏洞扫描 | `app="天镜脆弱性扫描与管理系统"` | verified |
| huddle | 协作产品 | `app="huddle"` | verified |
| Blueprint | 协作产品 | `app="Blueprint"` | verified |
| KVM坐席协作管理系统 | 协作产品 | `app="KVM坐席协作管理系统"` | verified |
| DELL-UPS | UPS | `app="DELL-UPS"` | verified |
| EATON-5P-650 | UPS | `app="EATON-5P-650"` | verified |
| EATON-5P-750 | UPS | `app="EATON-5P-750"` | verified |
| RaspberryPi#1 | 即插即用设备 | `app="RaspberryPi#1"` | verified |
| RaspberryPi2-Engine | 即插即用设备 | `app="RaspberryPi2-Engine"` | verified |
| raspberrypi-AstroBox | 即插即用设备 | `app="raspberrypi-AstroBox"` | verified |
| 威胁情报类产品 | 威胁情报 | `app="威胁情报类产品"` | verified |
| 威胁情报监控系统 | 威胁情报 | `app="威胁情报监控系统"` | verified |
| 企业安全威胁感知系统 | 威胁情报 | `app="企业安全威胁感知系统"` | verified |
| 资产证券化查询系统 | 金融行业 | `app="资产证券化查询系统"` | verified |
| 保险高管在线培训系统 | 金融行业 | `app="保险高管在线培训系统"` | verified |
| 承保理赔信息查询系统 | 金融行业 | `app="承保理赔信息查询系统"` | verified |
| LD5200 | 数据防丢失 | `app="LD5200"` | verified |
| LD2100 | 数据防丢失 | `app="LD2100"` | verified |
| 天融信数据防泄漏系统 | 数据防丢失 | `app="天融信数据防泄漏系统"` | verified |
| 网御-APT | IDS | `app="网御-APT"` | verified |
| HUAWEI-NIP2050 | IDS | `app="HUAWEI-NIP2050"` | verified |
| HUAWEI-NIP5000I | IDS | `app="HUAWEI-NIP5000I"` | verified |
| Cryptlib | 安全软件 | `app="Cryptlib"` | verified |
| globaleaks | 安全软件 | `app="globaleaks"` | verified |
| ESET-NOD32 | 安全软件 | `app="ESET-NOD32"` | verified |
| TinyDNS | DNS服务器 | `app="TinyDNS"` | verified |
| 360-安全DNS | DNS服务器 | `app="360-安全DNS"` | verified |
| wddns智能DNS管理系统 | DNS服务器 | `app="wddns智能DNS管理系统"` | verified |
| SUCURi | 网站云防护 | `app="SUCURi"` | verified |
| 360wzws | 网站云防护 | `app="360wzws"` | verified |
| 安恒信息-云防护 | 网站云防护 | `app="安恒信息-云防护"` | verified |
| 門禁差勤管理系統 | 门禁系统 | `app="門禁差勤管理系統"` | verified |
| 七友-CYT-200SC | 门禁系统 | `app="七友-CYT-200SC"` | verified |
| 创思软件-门禁视频管理系统 | 门禁系统 | `app="创思软件-门禁视频管理系统"` | verified |
| 聚城物业管理软件 | 房地产行业 | `app="聚城物业管理软件"` | verified |
| 银亿物业综合管理系统 | 房地产行业 | `app="银亿物业综合管理系统"` | verified |
| 住房保障综合管理系统 | 房地产行业 | `app="住房保障综合管理系统"` | verified |
| 即插即用设备 | 嵌入式服务器 | `app="即插即用设备"` | verified |
| newweb | 嵌入式服务器 | `app="newweb"` | verified |
| TCS-QD2040 | 嵌入式服务器 | `app="TCS-QD2040"` | verified |
| 数据库审计系统 | 数据库审计 | `app="数据库审计系统"` | verified |
| 建行云数据库审计系统 | 数据库审计 | `app="建行云数据库审计系统"` | verified |
| 数据库审计系统UDB | 数据库审计 | `app="数据库审计系统UDB"` | verified |
| 保险 | 关键信息基础设施 | `app="保险"` | verified |
| 机场 | 关键信息基础设施 | `app="机场"` | verified |
| 核电 | 关键信息基础设施 | `app="核电"` | verified |
| 360私有云杀毒管理系统 | 防病毒 | `app="360私有云杀毒管理系统"` | verified |
| 网御星云-防病毒网关系统 | 防病毒 | `app="网御星云-防病毒网关系统"` | verified |
| 魔盾邮件安全 | 邮件安全 | `app="魔盾邮件安全"` | verified |
| KILL邮件安全网关 | 邮件安全 | `app="KILL邮件安全网关"` | verified |
| 网御邮件安全管理系统 | 邮件安全 | `app="网御邮件安全管理系统"` | verified |
| 惠动科技-裂变宝 | SaaS平台 | `app="惠动科技-裂变宝"` | verified |
| Atlantis | SaaS平台 | `app="Atlantis"` | verified |
| 亿美软通-B/S满意通 | SaaS平台 | `app="亿美软通-B/S满意通"` | verified |
| 金电网安网站安全监测系统 | 安全检测平台 | `app="金电网安网站安全监测系统"` | verified |
| 南网数字-蜜罐远程布防系统 | 安全检测平台 | `app="南网数字-蜜罐远程布防系统"` | verified |
| LogRhythm-公司产品 | 安全检测平台 | `app="LogRhythm-公司产品"` | verified |
| mantis | 问题单管理 | `app="mantis"` | verified |
| AI问题管理系统 | 问题单管理 | `app="AI问题管理系统"` | verified |
| BUG提交管理系统 | 问题单管理 | `app="BUG提交管理系统"` | verified |
| PSI | 开发模板 | `app="PSI"` | verified |
| AChat | 开发模板 | `app="AChat"` | verified |
| Namazu | 开发模板 | `app="Namazu"` | verified |
| ModLogAn | 日志分析 | `app="ModLogAn"` | verified |
| 锐捷-大数据安全平台 | 日志分析 | `app="锐捷-大数据安全平台"` | verified |
| 建恒信安-日志审计系统 | 日志分析 | `app="建恒信安-日志审计系统"` | verified |
| Spring-GW | 应用网关 | `app="Spring-GW"` | verified |
| 指掌易-零信任·SDP安全网关 | 应用网关 | `app="指掌易-零信任·SDP安全网关"` | verified |
| adriver | 广告联盟 | `app="adriver"` | verified |
| RevSense | 广告联盟 | `app="RevSense"` | verified |
| seeyoo广告机 | 广告联盟 | `app="seeyoo广告机"` | verified |
| phpATM | 安全文件传输 | `app="phpATM"` | verified |
| 镭速-文件传输系统 | 安全文件传输 | `app="镭速-文件传输系统"` | verified |
| CData-RSSBus | 安全文件传输 | `app="CData-RSSBus"` | verified |
| TMG165 | 代理服务器 | `app="TMG165"` | verified |
| GUI-PROXY | 代理服务器 | `app="GUI-PROXY"` | verified |
| Proxomitron | 代理服务器 | `app="Proxomitron"` | verified |
| AW-DDOS | 抗DDOS | `app="AW-DDOS"` | verified |
| AntiDDoS | 抗DDOS | `app="AntiDDoS"` | verified |
| FortiDDoS | 抗DDOS | `app="FortiDDoS"` | verified |
| 入侵防御系统 | IPS | `app="入侵防御系统"` | verified |
| 天清入侵防御系统 | IPS | `app="天清入侵防御系统"` | verified |
| 捷普入侵防御系统 | IPS | `app="捷普入侵防御系统"` | verified |
| 神马-站长平台 | 站长平台 | `app="神马-站长平台"` | verified |
| 360-站长平台 | 站长平台 | `app="360-站长平台"` | verified |
| Baidu-站长平台 | 站长平台 | `app="Baidu-站长平台"` | verified |
| D01-探针 | 网络空间测绘 | `app="D01-探针"` | verified |
| 观星-观星台 | 网络空间测绘 | `app="观星-观星台"` | verified |
| 奇安信-全球鹰 | 网络空间测绘 | `app="奇安信-全球鹰"` | verified |
| 网神-光闸 | 网闸 | `app="网神-光闸"` | verified |
| 安全隔离与交换信息系统 | 网闸 | `app="安全隔离与交换信息系统"` | verified |
| 辰锐信息-单向传输系统 | 网闸 | `app="辰锐信息-单向传输系统"` | verified |
| USR-DR801 | 工业路由器 | `app="USR-DR801"` | verified |
| TOPTEL-RG2000-M | 工业路由器 | `app="TOPTEL-RG2000-M"` | verified |
| TOPTEL-RG2000-V8 | 工业路由器 | `app="TOPTEL-RG2000-V8"` | verified |
| Censura | 帮助系统 | `app="Censura"` | verified |
| HelpDocs | 帮助系统 | `app="HelpDocs"` | verified |
| Yearning | 帮助系统 | `app="Yearning"` | verified |
| 优阅数字图书馆 | 数字出版 | `app="优阅数字图书馆"` | verified |
| posterous | 数字出版 | `app="posterous"` | verified |
| OpenNemas | 数字出版 | `app="OpenNemas"` | verified |
| XGIMI-H1S | 投影仪 | `app="XGIMI-H1S"` | verified |
| BenQ-W3000 | 投影仪 | `app="BenQ-W3000"` | verified |
| BenQ-W1070 | 投影仪 | `app="BenQ-W1070"` | verified |
| BackupPC | 专用设备 | `app="BackupPC"` | verified |
| ABB-SREA-01 | 专用设备 | `app="ABB-SREA-01"` | verified |
| V_SOL-V1600G2B | 专用设备 | `app="V_SOL-V1600G2B"` | verified |
| NSFOCUS-零信任 | 零信任 | `app="NSFOCUS-零信任"` | verified |
| SANGFOR-aTrust | 零信任 | `app="SANGFOR-aTrust"` | verified |
| 奇安信-网神零信任身份服务系统 | 零信任 | `app="奇安信-网神零信任身份服务系统"` | verified |
| 网页防篡改系统 | 防篡改系统 | `app="网页防篡改系统"` | verified |
| 天翼云-网页防篡改系统 | 防篡改系统 | `app="天翼云-网页防篡改系统"` | verified |
| 天融信-网页防篡改系统 | 防篡改系统 | `app="天融信-网页防篡改系统"` | verified |
| ujian | 分享模块 | `app="ujian"` | verified |
| Clicky | 分享模块 | `app="Clicky"` | verified |
| jiathis | 分享模块 | `app="jiathis"` | verified |
| mi-Naftis | docker管理 | `app="mi-Naftis"` | verified |
| Canon-TS8330 | 扫描仪 | `app="Canon-TS8330"` | verified |
| Canon-TS5000-series | 扫描仪 | `app="Canon-TS5000-series"` | verified |
| Canon-TS6000-series | 扫描仪 | `app="Canon-TS6000-series"` | verified |
| 网神-数据自动导入系统 | 物理隔离 | `app="网神-数据自动导入系统"` | verified |
| 联软科技-UniNXG | 物理隔离 | `app="联软科技-UniNXG"` | verified |
| H3C-安全隔离与信息交换系统 | 物理隔离 | `app="H3C-安全隔离与信息交换系统"` | verified |
| UFax2-产品 | 传真 | `app="UFax2-产品"` | verified |
| Myfax-公司产品 | 传真 | `app="Myfax-公司产品"` | verified |
| 汉元-万发传真服务器 | 传真 | `app="汉元-万发传真服务器"` | verified |
| CS_TimeClock | 指纹识别 | `app="CS_TimeClock"` | verified |
| Dr.ID-門禁考勤系統 | 指纹识别 | `app="Dr.ID-門禁考勤系統"` | verified |
| ZK-Web-Server | 指纹识别 | `app="ZK-Web-Server"` | verified |
| 加油卡系统 | 石油行业 | `app="加油卡系统"` | verified |
| 加油站管理系统 | 石油行业 | `app="加油站管理系统"` | verified |
| 中石化加油卡查询系统 | 石油行业 | `app="中石化加油卡查询系统"` | verified |
| VB后门 | 后门 | `app="VB后门"` | verified |
| ASP大马 | 后门 | `app="ASP大马"` | verified |
| JSP大马 | 后门 | `app="JSP大马"` | verified |
| ivanti-VTM | 应用交付 | `app="ivanti-VTM"` | verified |
| BROADCOM-VTM | 应用交付 | `app="BROADCOM-VTM"` | verified |
| FORTINET-FortiGSLB | 应用交付 | `app="FORTINET-FortiGSLB"` | verified |
| FUSHIONPBX | PBX | `app="FUSHIONPBX"` | verified |
| OpenVox-PBX | PBX | `app="OpenVox-PBX"` | verified |
| Asterisk-PBX | PBX | `app="Asterisk-PBX"` | verified |
| 东方世纪-东方祥云 | 水解决方案 | `app="东方世纪-东方祥云"` | verified |
| HEDA-智慧水务 | 水解决方案 | `app="HEDA-智慧水务"` | verified |
| InfoMaster-产品 | 水解决方案 | `app="InfoMaster-产品"` | verified |
| 干扰资产 | 干扰类数据 | `app="干扰资产"` | verified |
| 借贷-规则 | 干扰类数据 | `app="借贷-规则"` | verified |
| Goploy | 持续集成和交付 | `app="Goploy"` | verified |
| Airbyte-Integration-Platform | 持续集成和交付 | `app="Airbyte-Integration-Platform"` | verified |
| 中电福富-安全基线管理 | 安全基线 | `app="中电福富-安全基线管理"` | verified |
| Facebook-Error | 官网 | `app="Facebook-Error"` | verified |
| SANGFOR上网行为管理 | 上网行为管理系统 | `app="SANGFOR上网行为管理"` | verified |
| SANGFOR-上网优化管理 | 上网行为管理系统 | `app="SANGFOR-上网优化管理"` | verified |
| SANGFOR-行为感知系统 | 上网行为管理系统 | `app="SANGFOR-行为感知系统"` | verified |
