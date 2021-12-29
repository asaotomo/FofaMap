**FofaMap_V1.0.0** 

**FofaMap是一款基于Python3开发的跨平台FOFA数据采集器。用户可以通过修改配置文件，定制化的采集FOFA数据，并导出生成对应的Excel表格**

**一.安装说明**

1.工具使用**Python3**开发，请确保您的电脑上已经安装了**Python3**环境。

2.首次使用请使用 **python3 -m pip install -r requirements.txt** 命令，来安装必要的外部依赖包。

3.**fofa.ini**为Fofamap的配置文件，可以通过修改配置文件内容来定制化采集FOFA数据

4.在使用该工具前，请先填写用户信息**[userinfo]**中的**email**和**key**,**fofa.ini**配置文件说明如下：

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
   企业会员 免费前100,000条/次
   高级会员 免费前10000条/次
   普通会员 免费前100条/次
   注册用户 1F币（最多10,000条）/次 

用户可以根据自己的账号类型设置对应的查询页数。

6.项目文件结构：

```
├── README.md ##使用说明
├── fofa.ini ##fofa配置文件
├── fofa.py  ##fofa api调用类
├── fofamap.py  ##fofamap主程序
└── requirements.txt  ##依赖包要求
```

**二.使用方法**

**1.-q 使用FOFA查询语句查询数据**

```
$ python3 fofamap.py -q title="Apache APISIX Dashboard"
```
![image-20211229160059142](/Users/qiuan/Library/Application Support/typora-user-images/image-20211229160059142.png)

**2.-o 自定义输出文件名[默认为fofa.xlsx]**

```
$ python3 fofamap.py -q title="Apache APISIX Dashboard" -o aaa.xlsx
```
![image-20211229160446094](/Users/qiuan/Library/Application Support/typora-user-images/image-20211229160446094.png)

**输出的aaa.xlsx内容如下：**

![image-20211229160614948](/Users/qiuan/Library/Application Support/typora-user-images/image-20211229160614948.png)

**3.-s 输出扫描格式** 

扫描格式，系统只会获取目标ip地址和端口号两个字段，方便大家导出到扫描器进行扫描。

```
$ python3 searchmap.py -q title="Apache APISIX Dashboard" -s  
```
![image-20211229161050702](/Users/qiuan/Library/Application Support/typora-user-images/image-20211229161050702.png)

****************************

**本工具仅提供给安全测试人员进行安全自查使用**
**用户滥用造成的一切后果与作者无关**
**使用者请务必遵守当地法律**
**本程序不得用于商业用途，仅限学习交流**

*********

**本工具由Hx0战队开发维护**

[![iShot2021-12-23 15 42 05](https://user-images.githubusercontent.com/67818638/147206433-402f9d35-7187-4417-b60c-afb0e8ec4686.png)](https://user-images.githubusercontent.com/67818638/147206433-402f9d35-7187-4417-b60c-afb0e8ec4686.png)
