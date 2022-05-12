**FofaMap_V1.1.2 春节特别版【联动 Nuclei】｜ [FofaMap云查询版](https://github.com/asaotomo/FofaMap-Cloud)**

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

[fields]#查询内容选项
#默认查询内容为：ip、端口、网站标题、国家和城市
fields = ip,port,title,country,city

#fields可选项有：['host', 'title', 'ip', 'domain', 'port', 'country', 'province', 'city', 'country_name', 'header', 'server', 'protocol', 'banner', 'cert', 'isp', 'as_number', 'as_organization', 'latitude', 'longitude', 'structinfo','icp', 'fid', 'cname']


[page]#查询页数
#查询启始页数
start_page = 1
#查询结束页数
end_page = 2
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



**2.-o 自定义输出文件名[默认为fofa.xlsx]**

```
$ python3 fofamap.py -q 'title="Apache APISIX Dashboard"' -o 结果.xlsx
```

<img width="1073" alt="image" src="https://user-images.githubusercontent.com/67818638/149065219-ebaf0649-c756-44d9-a61e-c2b3414311b2.png">


**输出的结果.xlsx内容如下：**

<img width="1088" alt="image" src="https://user-images.githubusercontent.com/67818638/149065268-d7306a51-10f0-4df8-b132-94012e07d73d.png">


**3.-ico 使用网站图标Hash值进行查询**

FofaMap V1.1.2新版支持网站图标查询【仅支持Fofa高级会员及以上用户】。

用户可通过填入任意一网站地址，Fofamap会自动获取该网站的favicon.ico图标文件，并计算其hash值。

```
$ python3 fofamap.py -ico 网站url
```

例如我们查询含有必应(bing)图标的网站，**python3 fofamap.py -ico https://www.bing.com**

<img width="926" alt="image" src="https://user-images.githubusercontent.com/67818638/153366400-7344cd00-f050-42f7-b20d-e46b7466387f.png">

**4.-bq 批量查询数据**

FofaMap V1.1.2新版支持批量查询，用户可新建一个记事本文件，如bat.txt，然后将准备查询的fofa语句写入其中，运行以下命令即可进行批量查询。

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



**5.-s 输出扫描格式** 

使用输出扫描格式功能时，系统只会获取目标host字段，并自动做去重处理，输出结果同时会自动保存为txt文件，方便后面nuclei进行目标调用扫描。

```
$ python3 fofamap.py -q 'title="Apache APISIX Dashboard"' -s  
```

<img width="1147" alt="image" src="https://user-images.githubusercontent.com/67818638/149065853-aa8a6739-0cce-489a-a081-e3862c8f8eea.png">



**6.使用 -s -n 调用nuclei对查询到的资产进行漏洞扫描** 

```
python3 fofamap.py -q 'title="Apache APISIX Dashboard"' -s  -n
```

![image](https://user-images.githubusercontent.com/67818638/149505569-a5356a33-f02a-4c44-ab52-87bab369380c.png)

**FofaMap支持全功能扫描和自定义扫描两种模式**

**全功能扫描:** 根据提示输入“N”，对目标进行全扫描，默认内置全部PoC。

![image](https://user-images.githubusercontent.com/67818638/149505603-cbc2dc73-fbf2-4e52-923c-dc3d424a13a5.png)

**自定义扫描:** 根据提示输入“Y”，启动自定义扫描，通过设置过滤器对目标进行自定义扫描，只使用指定的PoC。

**FofaMap支持三个基本过滤器来自定义扫描方式。**

1.标签（-tags）根据模板中可用的标签字段进行筛选。如：cev、cms、tech等

2.严重级别（-severity）根据模板中可用的严重级别字段进行筛选。如：critical、high、medium等

3.作者（-author）根据模板中可用的作者字段进行筛选。如：geeknik、pdteam、pikpikcu等

4.自定义 （customize）用户可以根据需求使用nuclei的其它高级命令对目标进行扫描。如：-tags cve -severity critical,high -author geeknik

**例如：我们使用自定义扫描的tags过滤器，tags的内容为tech，那么fofamap只会调用nuclei的tech-detect模板对网站进行检测，扫描结果为网站所使用的中间件、数据库、操作系统版本等系统。**

![image](https://user-images.githubusercontent.com/67818638/149505639-a740076d-4e96-438b-b0e1-b54edb39547b.png)

**更多Nuceli的用法可以参考[这里](https://blog.csdn.net/asaotomo/article/details/122395708)**

另外**FofaMap**会对扫描后的**结果**进行统计，并将结果保存在**scan_result.txt**中。

![image](https://user-images.githubusercontent.com/67818638/149505663-c1988ffe-1bed-49f6-80c2-4910e614dee3.png)

**scan_result.txt文件内容：**

![image](https://user-images.githubusercontent.com/67818638/149505770-582d802d-e46b-4174-8161-fe5d9dbd9ece.png)

在获得**scan_result.txt**后系统会提取**scan_result.txt**中的**IP地址和域名**，并调用**fofa api**去查询其**其域名和备案信息**，辅助用户了解资产归属情况。

![image](https://user-images.githubusercontent.com/67818638/149505746-fc27bd19-d027-487e-a944-914bcb30cd58.png)

**7.通过修改配置文件，控制输出内容** 

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

**扫描关注战队公众号，获取最新动态**

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/149507366-4ada14db-a972-4071-bbb6-197659f61ced.png">

**【知识星球】福利大放送**

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/156556995-f3798cb1-027e-47e6-84ba-b7537d85b158.png">

---
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

