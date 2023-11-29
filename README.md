**FofaMap_V1.1.3 国庆特别版【联动 Nuclei】｜ [FofaMap云查询版](https://github.com/asaotomo/FofaMap-Cloud)**

![image](https://user-images.githubusercontent.com/67818638/149505431-06fbc14b-ac0c-4ccb-a316-949fe08e9ee5.png)

<p align="center">
<a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-_red.svg"></a>
<a href="https://github.com/asaotomo/fofamap/issues"><img src="https://img.shields.io/badge/contributions-welcome-brightgreen.svg?style=flat"></a>
<a href="https://github.com/sqlmapproject/sqlmap/actions/workflows/tests.yml"><img src="https://img.shields.io/badge/python-3.x-blue.svg"></a>
</p>

**好消息：FofaMap又可以正常使用了，感谢🙏大家一直以来对FofaMap的支持，我们将继续对FofaMap进行更新和维护。**

**[FofaMap](https://github.com/asaotomo/FofaMap)是一款基于Python3开发的跨平台FOFA数据采集器。用户可以通过修改配置文件，定制化的采集FOFA数据，并导出生成对应的Excel表格或TXT扫描目标。**

**[Nuclei](https://github.com/projectdiscovery/nuclei)是一款基于YAML语法模板的开发的定制化快速漏洞扫描器。它使用Go语言开发，具有很强的可配置性、可扩展性和易用性。**

**本次我们将Fofamap和Nuclei进行联动，通过Fofamap查询到资产目标后，自动调用Nuclei对发现目标进行漏洞扫描，实现资产探测到漏洞扫描的全流程漏洞发掘工作，极大的提升了白帽子挖掘SRC的效率。**

**一.安装说明**

1.工具使用**Python3**开发，请确保您的电脑上已经安装了**Python3**环境。

2.首次使用请使用 **python3 -m pip install -r requirements.txt** 命令，来安装必要的外部依赖包。

3.**fofa.ini**为Fofamap的配置文件，可以通过修改配置文件内容来定制化采集FOFA数据。

4.在使用该工具前，请先填写用户信息[userinfo]中的email和key，**fofa.ini**配置文件说明如下：

```
[userinfo]#用户信息
#注册和登录时填写的email
email = xxxxx@qq.com
#会员到个人资料可得到key，为32位的hash值
key = 001xxxxxxxxxxxxxxxxxxxxx8b2dc5

[size]#查询数量
#每页查询数量，默认为100条，最大支持10,000条/页
size = 100

[full]#查询范围
#默认搜索一年内的数据，指定为true即可搜索全部数据，false为一年内数据
full = false

[excel]
#当sheet_merge设置为on时，批量查询结果将汇聚到一个文件的多个sheet进行输出，设置为false时，每个查询结果将单独作为一个文件进行输出
sheet_merge = on

[fields]#查询内容选项
#默认查询内容为：ip、端口、网站标题、国家和城市
fields = ip,port,title,country,city
#fields可选项有：['host', 'title', 'ip', 'domain', 'port', 'country', 'province', 'city', 'country_name', 'header', 'server', 'protocol', 'banner', 'cert', 'isp', 'as_number', 'as_organization', 'latitude', 'longitude', 'structinfo','icp', 'fid', 'cname']

[page]#查询页数
#查询启始页数
start_page = 1
#查询结束页数
end_page = 2

[logger]#日志开关
#全局日志开关，开启后会默认输入软件执行日志到fofamap.log文件
logger = on

[fast_check]#网站存活检测（Beta）
#网站存活检测开关，默认开启，开启后系统会对查询到的网站目标进行快速存活性检测
check_alive = on
#设置检测爬虫的超时时间
timeout = 5
```

5.不同用户使用**Fofamap**调用FOFA全网资产收集与检索系统API查询次数如下：

   **企业会员** 免费前100,000条/次

   **高级会员** 免费前10000条/次

   **普通会员** 免费前100条/次

   **注册用户** 1F币（最多10,000条）/次 

用户可以根据自己的账号类型设置对应的查询页数。

6.项目文件结构：

```
├── README.md ##使用说明
├── fofa.ini ##fofa配置文件
├── fofa.py ##fofa api调用类
├── fastcheck.py ##网站存活检测类（引入协程）
├── fofamap.py ##fofamap主程序
├── nuclei ##nuclei主程序，若nuclei主程序有更新，可去https://github.com/projectdiscovery/nuclei/releases下载替换
│   ├── linux ##linux版主程序
│   │   ├── nuclei_386
│   │   ├── nuclei_amd
│   │   ├── nuclei_arm
│   │   └── nuclei_armv6
│   ├── macos ##macos版主程序
│   │   ├── nuclei_amd
│   │   └── nuclei_arm
│   └── windows ##windows版主程序
│       ├── nuclei_386.exe
│       └── nuclei_amd.exe
├── nuclei.py ##nuclei api调用类
├── requirements.txt ##依赖包要求
```

7.适配情况：目前FofaMap春节特别版以及适配了**macOS、Windows、Kali Linux、Ubuntu**等操作系统。

**二.使用方法**

**1.-q 使用FOFA查询语句查询数据**

**关于命令说明：**

如果用户想要使用fofa联合查询语句，例如：**app="grafana" && country="US"**。

Linux和macOS用户直接使用python3 fofamap.py -q 'app="grafana" && country="US"'即可成功查询。

Windows用户因为系统原因，需要使用python3 fofamap.py -q "app=\\"grafana\\" && country=\\"CN\\""系统才可成功识别，即Windows用户需要对查询命令内部的"使用\进行转义，否则系统识别错误。

```
$ python3 fofamap.py -q 'title="Apache APISIX Dashboard"'
```

<img width="1007" alt="image" src="https://user-images.githubusercontent.com/67818638/149065065-205e1f0f-35e1-4c65-a80b-1c632f1f0f58.png">

**网站存活检测功能（Beta）：**

用户可以在fofa.ini文件中修改fast_check模块下的check_alive值，当check_alive为on时，系统将会开启网站存活检测功能，该功能会对用户查询到的数据进行智能识别，筛选出开启http或https协议的网站，并对这些网站进行存活检测，生成检测结果。该功能可以帮助用户快速识别查询到的网站是否可以进行正常访问。


```
$ python3 fofamap.py -q 'title="Grafana"'
```

<img width="1007" alt="image" src="https://user-images.githubusercontent.com/67818638/226097116-849b9d6c-3b17-48c7-8714-8f5f022ec0b9.png">


如上图，在开启fast_check功能后，输出结果会增加Http Status Code一列，该列内容是本机访问对应网站时，服务器返回的状态码，我们可以通过该状态码，判定本机是否可以正常访问查询到的网站，建议将timeout值（默认为5s），超时时间设置越大，系统返回到结果将会越精准。

此外我们可通过-i参数筛选出指定的HTTP响应状态码，若要筛选多个状态码可用逗号隔开，如-i 200,403,500。

```
$ python3 fofamap.py -q 'app="Tomcat"' -i 200,403
```

<img width="1007" alt="image" src="https://user-images.githubusercontent.com/67818638/232236835-c1e6205f-965b-48f3-af1b-42fa99f43f37.png">

上图，我们通过-i参数，筛选出了含有Tomcat应用的网站中网站响应状态码为200和403的网站信息。

（PS：1.该功能目前为测试功能，在Python版本低于3.10的平台上运行可能会输出一些报错信息，但不影响总体结果的输出；2.该功能默认为关闭状态，需要启用该功能，请在fofa.ini文件中将check_alive的值由off改为on。）


**2.-hq 使用FOFAMAP查询Host聚合查询**

**关于命令说明：**

用户使用Host聚合查询模式时，系统可以根据当前的查询内容，生成聚合信息，host通常是ip，包含基础信息和IP标签。

```
$ python3 fofamap.py -hq 8.8.8.8
```

<img width="1375" alt="image" src="https://user-images.githubusercontent.com/67818638/221450671-ab53aeed-b436-4cd9-a99a-719b3222b3be.png">

**3.-cq 使用FOFAMAP查询统计聚合数据**

**关于命令说明：**

使用统计聚合功能，可以根据当前的查询内容，生成全球统计信息，当前可统计每个字段的前5排名。例如，我们使用下列命令统计全球范围内使用Redis应用的Top5国家。其中-cq为查询内容，-f为需要统计聚合的字段，默认为title，可按照示例配置多个字段 fields=country,protocol,domain,port。详细用法见[FOFA API 官方文档](https://fofa.info/api/stats/statistical)

```
$  python3 fofamap.py -cq 'app="redis"' -f country
```

<img width="1050" alt="image" src="https://user-images.githubusercontent.com/67818638/221577605-23451f2d-66d7-4fc8-922a-cc7cfd717963.png">

**PS：该功能限制为每隔5秒查询1次，查询频率太快会被FOFA拒绝。**

**4.-o 自定义输出文件名[默认为fofa.xlsx]**

```
$ python3 fofamap.py -q 'title="Apache APISIX Dashboard"' -o 结果.xlsx
```

<img width="1073" alt="image" src="https://user-images.githubusercontent.com/67818638/149065219-ebaf0649-c756-44d9-a61e-c2b3414311b2.png">


**输出的结果.xlsx内容如下：**

<img width="1088" alt="image" src="https://user-images.githubusercontent.com/67818638/149065268-d7306a51-10f0-4df8-b132-94012e07d73d.png">


**5.-ico 使用网站图标Hash值进行查询**

FofaMap V1.1.2新版支持网站图标查询【仅支持Fofa高级会员及以上用户】。

用户可通过填入任意一网站地址，Fofamap会自动获取该网站的favicon.ico图标文件，并计算其hash值。

```
$ python3 fofamap.py -ico 网站url
```

例如我们查询含有必应(bing)图标的网站，**python3 fofamap.py -ico https://www.bing.com**

<img width="926" alt="image" src="https://user-images.githubusercontent.com/67818638/153366400-7344cd00-f050-42f7-b20d-e46b7466387f.png">

**6.-bq 批量查询数据**

FofaMap V1.1.3新版支持批量查询，用户可新建一个记事本文件，如bat.txt，然后将准备查询的fofa语句写入其中，运行以下命令即可进行批量查询。

```plain
$ python3 fofamap.py -bq bat.txt
```

**bat.txt文件内容：**

```plain
domain="youku.com"   
server=="Microsoft-IIS/7.0" 
ip="211.45.30.16/24"
icp="京ICP备10036305号"
```

![img](https://cdn.nlark.com/yuque/0/2022/png/12839102/1642591372395-0f7c1e18-2d39-400a-9258-b5c4afb587e7.png)

查询完成后，系统会自动根据任务顺序为每个任务生成一个Excel版的查询结果文件。

**如下：**

![img](https://cdn.nlark.com/yuque/0/2022/png/12839102/1642591515080-a0220744-be8c-4030-a5ca-5ba60fa2366f.png)

当然！目前最新版也支持将所有任务查询结果整合到一个文件夹中。

![image](https://github.com/asaotomo/FofaMap/assets/67818638/f6422434-186b-40d7-9a5b-250c4af517ed)



**7.-bhq 批量Host聚合查询**

FofaMap V1.1.3新版支持批量host聚合查询，用户可新建一个记事本文件，如host.txt，然后将准备查询的主机名或IP地址写入其中，运行以下命令即可进行批量查询。

```plain
$ python3 fofamap.py -bhq host.txt
```

**host.txt文件内容：**

```plain
114.114.114.114
8.8.8.8
123.123.123.123
```

<img width="1370" alt="image" src="https://user-images.githubusercontent.com/67818638/233833195-269c205e-83d7-4e8d-bf72-f04c90df6083.png">


**8.-s 输出扫描格式** 

使用输出扫描格式功能时，系统只会获取目标host字段，并自动做去重处理，输出结果同时会自动保存为txt文件，方便后面nuclei进行目标调用扫描。

```
$ python3 fofamap.py -q 'title="Apache APISIX Dashboard"' -s  
```

<img width="1147" alt="image" src="https://user-images.githubusercontent.com/67818638/149065853-aa8a6739-0cce-489a-a081-e3862c8f8eea.png">



**9.使用 -s -n 调用nuclei对查询到的资产进行漏洞扫描** 

```
python3 fofamap.py -q 'title="Apache APISIX Dashboard"' -s  -n
```

![image](https://user-images.githubusercontent.com/67818638/149505569-a5356a33-f02a-4c44-ab52-87bab369380c.png)

**FofaMap支持全功能扫描和自定义扫描两种模式**

**全功能扫描:** 根据提示输入“N”，对目标进行全扫描，默认内置全部PoC。

![image](https://user-images.githubusercontent.com/67818638/149505603-cbc2dc73-fbf2-4e52-923c-dc3d424a13a5.png)

**自定义扫描:** 根据提示输入“Y”，启动自定义扫描，通过设置过滤器对目标进行自定义扫描，只使用指定的PoC。

**FofaMap支持四个基本过滤器来自定义扫描方式。**

1.标签（-tags）根据模板中可用的标签字段进行筛选。如：cev、cms、tech等

2.严重级别（-severity）根据模板中可用的严重级别字段进行筛选。如：critical、high、medium等

3.作者（-author）根据模板中可用的作者字段进行筛选。如：geeknik、pdteam、pikpikcu等

4.指定模板（-templates）根据用户指定的nuclei模板文件进行扫描。如：CVE-2017-6090.yaml、CVE-2021-43798.yaml、CVE-2022-0149.yaml等

5.自定义 （customize）用户可以根据需求使用nuclei的其它高级命令对目标进行扫描。如：-tags cve -severity critical,high -author geeknik

**例1：我们使用自定义扫描的tags过滤器，tags的内容为tech，那么fofamap只会调用nuclei的tech-detect模板对网站进行检测，扫描结果为网站所使用的中间件、数据库、操作系统版本等系统。**

![image](https://user-images.githubusercontent.com/67818638/149505639-a740076d-4e96-438b-b0e1-b54edb39547b.png)

**例2：我们使用指定模板的templates过滤器，-templates的内容为CVE-2021-43798.yaml，那么fofamap只会调用用户指定路径下的特定扫描模板对网站进行检测。**

<img width="955" alt="image" src="https://user-images.githubusercontent.com/67818638/195055536-c08d4989-329e-41d9-bab2-88aeeee2fb04.png">


**更多Nuceli的用法可以参考[这里](https://blog.csdn.net/asaotomo/article/details/122395708)**

另外**FofaMap**会对扫描后的**结果**进行统计，并将结果保存在**scan_result.txt**中。

![image](https://user-images.githubusercontent.com/67818638/149505663-c1988ffe-1bed-49f6-80c2-4910e614dee3.png)

**scan_result.txt文件内容：**

![image](https://user-images.githubusercontent.com/67818638/149505770-582d802d-e46b-4174-8161-fe5d9dbd9ece.png)

在获得**scan_result.txt**后系统会提取**scan_result.txt**中的**IP地址和域名**，并调用**fofa api**去查询其**其域名和备案信息**，辅助用户了解资产归属情况。

![image](https://user-images.githubusercontent.com/67818638/149505746-fc27bd19-d027-487e-a944-914bcb30cd58.png)

**10.-kw，关键词筛选匹配** 

我们可以通过-kw参数对fofamap查询到的数据进行关键词筛选匹配，并输出【关键词匹配结果.xlsx】表。该功能特别推荐在进行批量查询时使用，可以快速将我们指定的包含关键词内容的数据整合到一张汇总表中，方便我们快速定位到特定的资产。

例如：我们使用(-kw "php,登录")筛选出查询结果中包含"php或登录"的数据。


```
$ python3 fofamap.py -q 'app="discuz"' -kw "php,登录"
```

我们可以看到系统输出的内容为汇总之后的包含"php或登录"关键词的数据。

<img width="1284" alt="image" src="https://user-images.githubusercontent.com/67818638/232302814-29130f6e-a4ef-4489-bda2-b8566702f9c6.png">

PS: 1.-kw命令之后所跟的关键词不区分大小写。 2.需要匹配多个关键词时请使用英文逗号(,)隔开。

**11.通过修改配置文件，控制输出内容** 

我们可以通过修改**fofa.ini**配置文件中的fields值来控制工具输出的顺序与字段。
例如：我们将**fields = ip,port,title,country,city**改为**fields = protocol,ip,port,title,icp**。
<img width="989" alt="image" src="https://user-images.githubusercontent.com/67818638/149067409-df7ca188-c06b-4ef3-89a3-95f8460a7aef.png">

接着执行以下命令

```
$ python3 fofamap.py -q 'app="discuz"'   
```

输出内容就会变为协议、IP地址、端口、网站标题、ICP备案号。

<img width="1126" alt="image" src="https://user-images.githubusercontent.com/67818638/149067474-acfdfa54-d55a-4350-b531-607d41584b0e.png">



****************************

**本工具仅提供给安全测试人员进行安全自查使用**
**用户滥用造成的一切后果与作者无关**
**使用者请务必遵守当地法律**
**本程序不得用于商业用途，仅限学习交流**

*********

**FofaMap由Hx0战队开发维护**

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/147641794-82f32969-4214-48da-9df2-764318225589.png">

**特别鸣谢～渊龙Sec团队**

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/167256183-7c485b4c-1e5f-4bbe-a8de-3cf267ebd5ec.jpg">

**特别鸣谢～FOFA官方**

FoFaMap 已加入 FOFA [共创者计划](https://fofa.info/development)，感谢 FOFA 提供的账号支持。

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/210543196-b76f6808-b5dd-4933-9451-0c3217dca8f5.png">

**扫描关注战队公众号，获取最新动态**

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/149507366-4ada14db-a972-4071-bbb6-197659f61ced.png">

**【知识星球】福利大放送**

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/210543877-95b791f0-c677-4019-bb6e-504eefd8164e.png">

## 历史Star

[![Star History Chart](https://api.star-history.com/svg?repos=asaotomo/FofaMap&type=Date)](https://star-history.com/#asaotomo/FofaMap)

---
**更新日志 V1.1.3 国庆特别版**

[+] 修复生成的sheet表格名称不能存在特殊字符的问题。

[+] 优化系统输出逻辑。

[+] 增加批量查询结果整合输出为一个文件的选项。

[+] 增加域名查询结果自动输出xlsx文件。

[+] 增加nuclie扫描指定单一扫描模板（templates）的功能。

[+] 增加全局日志功能，用户可自行选择是否开启日志。

[+] 增加Host聚合查询模式，可以根据当前的查询内容，生成聚合信息。

[+] 增加批量Host聚合查询模式，可以批量查询Host聚合信息。

[+] 新增每页查询数量和数据查询范围设置功能，用户可以根据自己的需求选择每页查询的数据数量以及数据查询的范围（1年内 or 全部数据）。

[+] 优化Host聚合查询模式中端口详情的显示格式和内容。

[+] 优化网站图标查询逻辑，增加网站图标识别成功率。

[+] 修复使用-s命令时，输出内容包含非http协议的问题。

[+] 优化聚合搜索内容，修复部分搜索结果报错的问题。

[+] 增加统计聚合功能，可根据当前的查询内容，生成全球统计信息，当前可统计每个字段的前5排名。

[+] 增加网站存活检测功能（Beta），并支持从输出结果中筛选出自定义的HTTP响应状态码。

[+] 增加关键词筛选匹配功能，可针对查询结果进行自定义关键词筛选，并将匹配结果汇总输出。

[+] 增加Host聚合查询结果自动输出Excel表格。

[+] 修复fastcheck模块中的存在的一些BUG，并在每次请求时增加了随机User-Agent。

[+] 增加对输出文件名中的特殊字符过滤功能，避免因xlsx文件名中包含特殊字符而导致文件生成失败。（特别感谢用户OKVVbin提出的问题）

[+] 增加附录：查询接口支持的字段。


附录：

![image](https://user-images.githubusercontent.com/67818638/195052175-5d94401c-9784-4f54-be81-45db00fdaad3.png)

**更新日志 V1.1.2 春节特别版**

[+] 增加网站图标查询功能，该功能仅支持高级会员及以上用户使用。

[+] 增加查询数据自动去重功能。（特别感谢用户*jackjwang*提出的问题）

[+] 增加备案查询结果自动去重功能。

[+] 修复当查询字段（fields）只有一个时报错的bug。

[+] 新增异常捕获，当fofa语法输入错误时程序不退出。

**更新日志 V1.1.1 春节特别版**

[+] 增加批量查询功能。

[+] 增加fofa备用节点，提高可用性。

**更新日志 V1.1.0 春节特别版**

[+] 增加与nuclei联动，用户在查询到资产后可使用nuclei进行漏洞扫描。

[+] 增加扫描结果分析统计。

[+] 增加对nuclei扫描出的资产进行域名查询。

**更新日志 V1.0.1**

[+] 优化代码逻辑，修复已经BUG。

[+] 优化输出样式，命令行输出结果将以表格形式展示。

[+] 扫描模式输出结果将自动进行去重处理，并会自动将结果保存为txt文档。

