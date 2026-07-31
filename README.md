# 📝 学术论文审稿系统

> AI 深度审阅 + 逻辑连贯性审查 + 修订痕迹 + 自动补全 + 论文润色 + 文献综述 + 期刊推荐

## 功能特性

- **📄 多格式支持**：PDF / DOCX / TXT / Markdown 文件解析提取
- **🤖 多模型选择**：界面切换不同大模型，支持 OpenAI Compatible API / 本地 Ollama / 自定义端点
- **📋 规则引擎**：章节完整性检测 + 引用匹配，精准识别关键问题
- **🧠 AI 深度审阅**：LLM 逐章节语义分析，每条 ≥ 300 字，按内容质量/写作水平/具体问题/优点四维评审
- **🔍 逻辑连贯性审查**：章节逻辑（≥ 4 条）、论点论据逻辑（≥ 4 条）、语句连贯性（≥ 5 条问题检测）、主题一致性评价、总体逻辑评估（≥ 150 字）
- **✍️ 修订痕迹**：增/删/改对比展示，≥ 8 条具体修改建议，标注位置和详细理由
- **📝 自动补全**：检测缺失或内容不足的章节，AI 生成 ≥ 500 字补全草稿，与论文主题紧密结合
- **✨ 论文润色**：逐章 SCI 级语言润色，严格保留技术内容和术语
- **📖 文献综述**：基于论文内容自动生成完整学术文献综述
- **📚 期刊推荐**：基于论文内容创新性智能推荐 Top 10 投稿期刊，含 IF/接受率/审稿周期
- **📥 报告下载**：一键下载 DOCX 审稿报告（含修改痕迹、批注、推荐期刊），文件名含模型名+日期
- **📊 评分报告**：总体评分 + 优点/弱点分析 + 接收建议

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite |
| 后端 | Python FastAPI + OpenAI SDK + python-docx |
| AI | OpenAI Compatible API（支持自定义端点 / 本地 Ollama / Claude 等） |
| PDF 解析 | pypdfium2 |
| DOCX 生成 | python-docx |

## 快速启动

### 1. 配置环境变量

复制 `.env` 文件并配置 API 信息：

```bash
# 使用 Ollama 本地模型（推荐本地部署）
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
MODEL_NAME=qwen3.6:latest

# 或使用自定义局域网端点（如局域网部署的 Claude）
# LAN_MODEL_API_KEY=sk-xxx
# LAN_MODEL_URL=http://your-server:7000/v1
# MODEL_NAME=claude-sonnet-4-5-20251001

# 或使用云端 API
# OPENAI_API_KEY=sk-xxx
# OPENAI_BASE_URL=https://api.openai.com/v1
# MODEL_NAME=gpt-4o
```

### 2. 安装依赖

```bash
# 后端
cd server
pip install -r requirements.txt

# 前端
cd client
npm install
```

### 3. 启动服务

```bash
# Terminal 1：启动后端（端口 8000）
cd server
python main.py

# Terminal 2：启动前端（端口 3000）
cd client
npm run dev
```

打开 **http://localhost:3000** 即可使用。

## 审稿流程

1. **选择模型** — 从下拉列表选择审稿大模型（支持 Claude / GPT / Ollama 等）
2. **上传稿件** — 拖拽或选择论文文件（PDF / DOCX / TXT / Markdown）
3. **自动审稿** — 规则检查 → AI 审阅（语义分析 + 逻辑审查 + 论文润色 + 文献综述） → 生成完整报告
4. **查看结果** — 8 个 Tab 展示：
   - 📊 总评：分数（0-100）+ 优点（≥ 4 条）/弱点（≥ 4 条）+ 接收建议
   - 🔍 逻辑审查：研究主题提炼 / 研究路线图与整体框架 / 章节逻辑 / 论点逻辑 / 语句连贯性 / 主题一致性 / 总体评价
   - 🤖 AI 审阅：逐章节深度意见（每条 ≥ 300 字，含原文定位）
   - ✍️ 修订痕迹：增/删/改对比（≥ 8 条），标注位置和修改理由
   - 📝 自动补全：缺失/不足章节补全草稿（每条 ≥ 500 字）
   - ✨ 论文润色：SCI 级语言润色全文
   - 📖 文献综述：基于论文内容的完整文献综述
   - 📚 推荐期刊：Top 10 投稿期刊推荐
5. **下载报告** — 📥 下载 DOCX（含完整批注和推荐期刊）

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | API 信息及文档链接 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/models` | 可用大模型列表（Ollama 自动发现 + 自定义端点模型） |
| POST | `/api/review` | 上传论文并执行审稿（可选 `model` 参数） |
| GET | `/api/history` | 审稿历史记录 |
| DELETE | `/api/history/{id}` | 删除历史记录 |
| GET | `/api/recommend-journals/{id}` | 获取审稿报告的期刊推荐 |
| GET | `/api/download/{id}` | 下载审稿报告 DOCX |

## 项目结构

```
paper-review-system/
├── server/                          # FastAPI 后端
│   ├── main.py                      # API 入口 & 审稿流程编排
│   ├── models.py                    # 数据模型 (Pydantic)
│   ├── parser.py                    # 论文文本解析 & 章节提取
│   ├── journal_recommender.py       # 期刊推荐引擎（50+ 期刊数据库）
│   ├── requirements.txt             # Python 依赖
│   ├── rule_engine/                 # 规则检查模块
│   │   ├── section_check.py         # 章节完整性检测
│   │   ├── format_check.py          # 格式规范检查
│   │   └── citation_check.py        # 引用匹配检查
│   └── ai_service/                  # AI 审阅服务
│       ├── llm_client.py            # LLM API 客户端
│       ├── reviewer.py              # AI 深度审阅 Prompt
│       ├── polisher.py              # 论文逐章润色
│       └── lit_review.py            # 文献综述生成
├── client/                          # React 前端
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx                 # 入口
│       ├── App.tsx                  # 主应用（页面路由 + 模型管理）
│       ├── styles.css               # 全局样式
│       ├── types/index.ts           # TypeScript 类型定义
│       ├── api/client.ts            # API 请求封装
│       ├── hooks/useReview.ts       # 审稿 Hook（含模型传参 + 进度显示）
│       └── pages/
│           ├── UploadPage.tsx       # 上传页面（含模型选择器）
│           ├── ReviewResultPage.tsx # 审稿结果页（8 Tab + 下载）
│           └── HistoryPage.tsx      # 历史记录页
├── .env                              # 环境变量配置
├── .gitignore
└── README.md
```

## 支持的 AI 模型

系统默认提供以下 Claude 4.5 系列模型（通过自定义局域网端点访问）：

- **Claude Sonnet 4.5** — 深度推理，性价比高
- **Claude Opus 4.5** — 最强推理能力
- **Claude Haiku 4.5** — 极速响应

同时支持 Ollama 本地模型自动发现，以及任何 OpenAI Compatible API。

Ollama 服务需在本地运行（默认 `localhost:11434`），系统启动时自动发现可用模型。

自定义模型端点通过环境变量 `LAN_MODEL_API_KEY` 和 `LAN_MODEL_URL` 配置。

## 推荐期刊数据库

`journal_recommender.py` 内置 50+ 中英文学术期刊/会议，覆盖：

- NLP/AI 顶会：ACL、EMNLP、NeurIPS、ICLR、AAAI 等
- 信息科学/学术出版：Scientometrics、JASIST、Learned Publishing 等
- 计算机应用：Expert Systems with Applications、IP&M、KBS 等
- 中文核心：计算机学报、软件学报、情报学报、图书情报工作 等

每条期刊含影响因子（IF）、接受率、审稿周期、征稿范围等信息，系统根据论文内容匹配度和质量评分智能排序推荐。
