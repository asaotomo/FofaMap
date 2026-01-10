# 🗺️ FofaMap v2.0 — Platinum Agent Edition
> 🧠 **全网首个支持 MCP 协议 + AI 自我反思机制的红队资产测绘智能体**  
Self-Reflecting AI Queries → MCP Protocol Integration → Intelligent Vulnerability Scanning
>

<!-- 这是一张图片，ocr 内容为： -->
![](https://img.shields.io/badge/Python-3.10+-blue.svg)
![](https://img.shields.io/badge/Version-2.0.0-blue.svg)
![](https://img.shields.io/badge/AI-Self--Reflecting-blueviolet.svg)
![](https://img.shields.io/badge/MCP-AI%20Ready-purple.svg)
![](https://img.shields.io/badge/Nuclei-Integrated-orange.svg)
![](https://img.shields.io/badge/DeepSeek-V3-red.svg)
![](https://img.shields.io/badge/License-MIT-green.svg)
---

# ✨ 一句话介绍
> ❌ 它不是 FOFA 工具  
❌ 也不是 Nuclei 封装  
✅ 它是：**一个可以被 AI 接管、会自己反思、会自己决策扫描策略的「全网资产测绘智能体」**
>

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767970866287-2b0bc337-6e11-4708-a8d8-a6afe484d4b8.png)

---

# 🚀 v2.0 是什么级别的升级？
> FofaMap 从「资产查询工具」→ **进化为 AI Agent（智能体）**
>

### 🧠 1️⃣ 你只要说人话
```bash
python3 fofamap.py -ai "帮我找一下bing.com所有的子域名，并扫描一下"
```

AI 自动完成：

+ 理解你的意图
+ 生成 FOFA 语法
+ 查询资产
+ 若 0 结果 → 启动 **自我反思机制** 自动放宽条件重试
+ 分析资产指纹
+ 判断是否值得扫描
+ 自动生成 Nuclei 扫描参数
+ 询问你是否执行

---

### 🤖 2️⃣ 会“自我反思”的 AI（核心黑科技）
> 不再出现：`0 Results`
>

AI 会自动：

+ 判断：
    - 是否地区条件过严？
    - 是否关键词不合理？
    - 是否语法太死？
+ 自动：
    - 放宽条件
    - 重写语法
    - 多策略重试
+ 直到：**尽量给你产出结果**

---

### 🔌 3️⃣ 原生 MCP 支持（给 AI / Agent 用）
> 支持：**Claude Desktop / Cursor / 自建 Agent**
>

你可以直接对 AI 说：

> 「调用 FofaMap，帮我分析最近致远 OA 的风险态势」
>

AI 会：

> 自动调用 FofaMap → 自动跑任务 → 自动总结报告
>

+ **Cursor调用效果**

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767949431600-3bfb4e1e-4283-4697-94d4-837aed2de331.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767949509622-f814692f-82f6-4291-b5b6-ba334fdd76d4.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767949697647-b2137289-2319-4ada-8094-eecfa88fe83a.png)

+ **LM Stuido调用效果**

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767953068363-036d2e7a-5867-4937-8574-7f9c73f89f71.png)

---

### 🎯 4️⃣ 看人下菜的“智能扫描决策”
AI 会根据资产指纹：

| 发现 | 自动推荐 |
| --- | --- |
| Spring | `-tags spring` |
| WebLogic | `-tags weblogic` |
| ThinkPHP | `-tags thinkphp` |
| Struts2 | `-tags struts` |


> ❌ 不再无脑全量扫  
✅ 每一次扫描都是 **有脑子的精准打击**
>

---

# 🧩 谁适合用？
+ 🧑‍💻 安全小白：

> 会说一句话就能用
>

+ 🛡️ SRC / 红队：

> 批量资产 + 自动化挖洞 + 自动报告
>

+ 🤖 AI Agent 开发者：

> 直接当「安全能力插件」
>

+ 🏗️ 平台开发者：

> 可嵌入到攻防平台 / 资产平台 / SOC
>

---

# 📦 项目结构（平台级架构）
```bash
.
├── config/
│   ├── __init__.py          # ✅ 负责读取 yaml 并导出 settings 对象
│   └── settings.yaml        # ⭐ 全局配置（FOFA / AI / 系统）
│
├── core/                    # 🧠 核心引擎层
│   ├── ai.py                # AI Agent 中枢（意图 / 反思 / 决策 / 总结）
│   ├── client.py            # FOFA API 封装
│   ├── core.py              # 主工作流调度器
│   ├── excel.py             # Excel 报告导出
│   ├── handler.py           # CLI / MCP 入口分发
│   └── scanner.py           # Nuclei 智能联动
│
├── utils/
│   ├── helpers.py           # 通用工具函数
│   ├── logger.py            # 日志系统
│   └── printer.py           # 终端富文本输出
│
├── fofamap.py               # 🚀 CLI 主入口（一切从这里开始）
├── mcp_server.py            # 🔌 MCP Server（给 AI 调用）
├── results/                 # 📂 所有任务项目目录
├── requirements.txt
└── README.md
```

---

# 🛠️ 安装
## 1️⃣ 环境
```bash
Python >= 3.10
```

```bash
git clone https://github.com/asaotomo/FofaMap.git
cd FofaMap
pip3 install -r requirements.txt
```

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767950152421-2122be93-8a0d-471c-aa54-6a1506a7eb67.png)

```bash
python3 fofamap.py --help #查看工具用法
```

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767950323971-23495a54-8810-4f2b-8fc4-6dfe5ab655a9.png)

---

## 2️⃣ 初始化配置（✨ 向导模式）
```bash
python3 fofamap.py init
```

自动引导你填写：

+ FOFA Email / Key
+ 使用的 AI（DeepSeek / OpenAI / Ollama / LMStudio）
+ 默认模型名称

配置保存至：

```bash
config/settings.yaml
```

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767950423887-143904ea-fc2c-435c-a0d6-4f3d6f853f36.png)

---

## 3️⃣ 配置 Nuclei（可选）
如需漏洞扫描：

+ 确保 `nuclei` 在 PATH 中

```bash
nuclei -version  #输入此命令查看是否添加成功
```

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767950503977-57d6011c-dd79-495d-9daf-3eb9a5f11093.png)

+ 或下载nuclei二进制文件后直接放入项目根目录

```bash
https://github.com/projectdiscovery/nuclei/releases ## nuclei 扫描器官方下载地址，注意要下载对应自己操作系统版本的二进制文件
```

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767950804043-97f52c4e-2aaa-4fb4-bb5a-41bc58d6285c.png)

---

# ⚙️ 配置文件详解（config/settings.yaml）
```bash
#====== 用户信息 (User Info) ======
userinfo:
  # [基础] FOFA 凭证
  email: "your_email@example.com"
  key: "your_fofa_api_key"
  
  # [进阶] AI 模型配置 (支持 DeepSeek/OpenAI/Ollama 等)
  deepseek_api_key: "sk-xxxxxxxxxxxxxxxxxxxxxxxx"
  
  # 场景 A: 使用官方 DeepSeek
  api_type: "deepseek"
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-chat"

  # 场景 B: 使用本地 Ollama (注释掉上方，启用下方)
  # api_type: "ollama"
  # base_url: "http://localhost:11434/v1"
  # model: "qwen2.5:7b"

# ====== 搜索设置 (Search Settings) ======
search:
  fields: "host,protocol,ip,port,title,domain,country,icp"
  size: 100
  full: false      # 设为 true 可查询一年前的数据
  start_page: 1
  end_page: 5      # 自动爬取前 5 页

# ====== 性能与输出 (System) ======
system:
  logger: true
  sheet_merge: true
  concurrency: 15  # 建议根据网络状况调整 (10-50)
```

---

# 💻 使用方法
---

# 🧙 模式一：交互式任务向导模式（✨ 新手 & 日常首选）
💡 **什么参数都不用记，只要运行：**

```plain
python3 fofamap.py
```

或：

```plain
python fofamap.py
```

即可进入 **AI 驱动的交互式任务向导界面**：

```plain
________      ____        __  ___            
   / ____/ /_  __/ __/___ _  /  |/  /___ _____   
  / /_  / __ \/ / /_/ __ `/ / /|_/ / __ `/ __ \  
 / __/ / /_/ / / __/ /_/ / / /  / / /_/ / /_/ /  
/_/    \____/_/_/  \__,_/ /_/  /_/\__,_/ .___/   
                                      /_/   v2.0 
    [ AI Powered & Interactive Wizard ] -- By Hx0 Team

[!] 启动任务向导...
? 请选择您要执行的操作:
 » 1. 🔮 AI 智能侦察 (自然语言 -> 自动决策)
   2. 🔍 FOFA 标准查询 (语法输入)
   3. 🖥️ Host 聚合查询 (IP/域名详情)
   4. 📊 统计聚合查询 (数据分布分析)
   5. 🖼️ Icon Hash 查询 (favicon 逆向)
   6. 📁 批量文件查询 (TXT 批量指令)
   ---------------
   0. 🚪 退出程序
```

---

## 🎯 这个模式适合谁？
+ ✅ 不想记命令参数的人
+ ✅ 第一次使用的新手
+ ✅ 日常使用 / 演示 / 培训 / 快速操作
+ ✅ 所有“我只想点一下跑任务”的场景

---

## 🧠 向导模式能做什么？
你可以通过方向键选择：

### 1️⃣ 🔮 AI 智能侦察（⭐ 强烈推荐）
直接输入一句话：

```plain
我收集一下美国哈佛大学的子域名网站，并扫描一下
```

系统将自动：

+ AI 理解意图
+ 自动生成 FOFA 语法
+ 自动查询
+ 自动反思（0 结果会重试）
+ 自动判断是否扫描
+ 自动生成扫描参数
+ 自动生成报告

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767951546443-9d44a9ad-6b35-44fb-91e3-ea109d596712.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767951571098-29b92150-0196-4958-826b-ca23e43fe811.png)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767952132926-1739cb75-8448-4034-9861-6967af7ada0f.png)

---

### 2️⃣ 🔍 FOFA 标准查询
使用FOFA查询语句查询数据

```plain
app="ThinkPHP" && country="CN"
```

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767969525080-a73044c2-440e-4c72-a114-4965e6f7a454.png)

---

### 3️⃣ 🖥️ Host 聚合查询（AI 深度画像）
根据当前的查询内容，生成聚合信息，host通常是ip，包含基础信息和IP标签。

```plain
8.8.8.8 / baidu.com 
```

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767969742560-30b321cd-3993-43aa-b22a-b09e55c7a2fe.png)

---

### 4️⃣ 📊 统计聚合查询（AI 态势分析）
根据当前的查询内容，生成全球统计信息，当前可统计每个字段的前5排名。

```plain
app="redis"
```

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767969913563-68bcdcb8-9107-41c3-8fe3-933e2e456d73.png)

---

### 5️⃣ 🖼️ Icon Hash 查询
<font style="color:rgb(31, 35, 40);">用户可通过填入任意一网站地址，</font>系统<font style="color:rgb(31, 35, 40);">会自动获取该网站的favicon.ico图标文件，并计算其hash值，并查找与此图标相似的网站。</font>

```plain
https://www.bing.com
```

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767969989542-9374fb72-3f71-40bb-83cd-16a298bc5ba0.png)

---

### 6️⃣ 📁 批量文件查询
<font style="color:rgb(31, 35, 40);">批量查询，用户可新建一个记事本文件，如targets.txt，然后将准备查询的fofa语句写入其中，输入文件路径（若放在工具根目录可以直接输入文件名称）即可进行批量查询。</font>

```plain
114.114.114.114
www.baidu.com
app="kafka"
```

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767970211247-9467dce6-257d-4f5c-ada0-aad859eff97d.png)

# 🔮 模式二：经典模式（ 老用户推荐）
## 1️⃣ AI查询模式
```bash
python3 fofamap.py -ai "帮我收集一下美国哈佛大学的子域名网站，并扫描一下"
```

## 2️⃣ 基础查询
```bash
python3 fofamap.py -q 'app="ThinkPHP" && country="CN"'
```

## 3️⃣ Host 深度画像（AI 报告）
```bash
python3 fofamap.py -hq 8.8.8.8
```

## 4️⃣ 统计聚合（AI 态势解读）
```bash
python3 fofamap.py -cq 'app="redis"' -f country,org
```

---

## 5️⃣ 图标 Hash 查询
```bash
python3 fofamap.py -ico https://www.bing.com
```

---

## 6️⃣ 批量查询
```bash
python3 fofamap.py -bq targets.txt
```

---

# 🔌 模式三：MCP 服务（🔥 给 AI / Agent 用）
### 1️⃣ 集成到 Cursor (最推荐，体验丝滑)
Cursor 对 MCP 的支持非常完善，配置好后，你可以直接在 Composer (Ctrl+I) 或 Chat (Ctrl+L) 中用自然语言调用工具。

1. 打开 **Cursor Settings** (点击右上角齿轮)。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767953701100-91d40367-76ae-4239-9cdb-e64c4b442251.png)

2. 在左侧菜单找到 **Tools** **&** **MCP**。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767953756050-3947fa69-3f69-4e3f-9264-96147c13027d.png)

3. 点击 **+ Add New MCP Server**。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767953462183-08f47ea0-6683-4f71-886c-fb645b92f9b8.png)

4. 填写mcp.json配置信息：
    - **Name**: `fofamap-v2` (随便起)
    - **Type**: `command` (或者叫 Stdio)
    - **Command**: `你的Python解释器绝对路径（若写入环境变量可以直接填python）`
        * 例如：`python3.10`
    - **Args**: `你的脚本绝对路径`
        * 例如：`/Users/ka/Downloads/fofamap/fofa/mcp_server.py`

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767953312691-9b0133cf-fc4c-47d7-82d8-a2bf55d2efec.png)

5. 点击 **Save**。
    - 此时你会看到一个 **绿色的圆点** 🟢，状态显示 `Connected`。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767953585044-97eb5e90-3a00-4ef7-9b83-9a1fa7b80397.png)

    - 如果显示红色，点击刷新图标，或者去 Cursor 的 `Output` -> `MCP Log` 或者是我们刚才修好的 `Log` 窗口看报错。

**👉**** 如何使用：** 打开 Cursor Chat (Ctrl+L)，直接输入：

“帮我查一下 baidu.com 的资产信息，并检查是否有存活。” 

Cursor 会自动分析意图，并在界面上显示 `Using tool: search_assets...`。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767953662133-8e369f5a-3d4b-499d-aed0-74094190fe0d.png)

---

### 2️⃣ 集成到 LM Studio (本地模型)
LM Studio 0.3.0+ 版本开始支持 MCP。这允许你用本地的 DeepSeek 或 Llama 3 调用你的工具。

1. 打开 **LM Studio**。
2. 点击对话框中的 **MCP (插头图标)**。
3. 点击**Install按钮** 。
4. **选择Edit mcp.json**。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767953870043-013b0c77-5282-4125-b9b8-911084c2bc8c.png)

5. 填写配置：
    - **Name**: `fofamap-v2`
    - **Command**: `你的Python解释器绝对路径`
    - **Args**: `你的脚本绝对路径` (注意：LM Studio 有时需要把 args 分开填，或者填在一个框里，视版本而定)。
        * _建议形式_: `["/Users/ka/.../mcp_server.py"]`

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767954026399-f53295dc-ac1e-4101-9f54-dc87fd438ea5.png)

6. 点击 **Save**。

**👉**** 如何使用：**

1. 去 **Chat** 界面。
2. 加载一个支持 Tool Calling 的模型（推荐 `openai/gpt-oss-20b` 或 `Qwen 2.5 7B Instruct`，或者是 LM Studio 里的 DeepSeek R1/V3）。
3. 在聊天框上方的 **Tools** 下拉菜单中，勾选 `mcp/fofamap-v2`。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767954105711-a5c74b58-4181-4f91-afcb-17b449bd6d89.png)

4. 输入提示词：“帮我查一下Nginx在美国的分布情况···”

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/12839102/1767954226754-f5f9b4b3-95b5-4690-bf08-a5279470dda5.png)

---

# ☢️ 漏洞扫描联动（Nuclei）
在2.0版本中AI 会根据查询结果智能生成Nuclei漏洞扫描命令参数：

```latex
[AI] 推荐命令: nuclei -tags spring -severity critical,high

> 🚀 执行
> ✏️ 修改
> 🚫 仅生成报告
```

---

# 📂 结果输出结构
```bash
results/
└── domain__harvard_edu_____country__US_20260108_173107
    ├── batch_merge_20260108_173107.xlsx
    ├── nuclei_result_20260108_173107.txt
    ├── report_20260108_173107.md
    └── targets_20260108_173107.txt
```

---

# 🛡️ 免责声明
+ 本工具仅面向**合法授权**的企业安全建设行为（如内部攻防演练、资产管理）。
+ 在使用本工具进行检测时，您应确保该行为符合当地法律法规，并已取得目标所有者的授权。
+ **禁止用于任何非法用途**。如您在使用本工具的过程中存在非法行为，您需自行承担相应后果，开发者不承担任何法律责任。

---

**FofaMap-V2.0由Hx0战队开发维护**

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/147641794-82f32969-4214-48da-9df2-764318225589.png">

**【打赏支持❤️】代码传情跨山海，点滴支持皆温暖✨**

虽然代码完全开源，但每杯咖啡都能让我们走得更远 ☕️

<img width="500" height="400" alt="打赏码" src="https://github.com/user-attachments/assets/02868aed-357e-4740-983a-d5a8ea05bdbf" />

**特别鸣谢～渊龙Sec团队**

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/167256183-7c485b4c-1e5f-4bbe-a8de-3cf267ebd5ec.jpg">

**特别鸣谢～FOFA官方**

FoFaMap 已加入 FOFA [共创者计划](https://fofa.info/development)，感谢 FOFA 提供的账号支持。

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/210543196-b76f6808-b5dd-4933-9451-0c3217dca8f5.png">

**【战队公众号】扫描关注战队公众号，获取最新动态**

<img width="318" alt="image" src="https://user-images.githubusercontent.com/67818638/149507366-4ada14db-a972-4071-bbb6-197659f61ced.png">

**【战队知识星球】福利大放送，限时优惠-仅限前100名**

<img width="318" height="958" alt="星球优惠券" src="https://github.com/user-attachments/assets/ab5b2b9b-82b6-4668-94e1-9e5e3d055f9a" />


## 历史Star

[![Star History Chart](https://api.star-history.com/svg?repos=asaotomo/FofaMap&type=Date)](https://star-history.com/#asaotomo/FofaMap)
