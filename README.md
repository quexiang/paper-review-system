# 📝 学术论文审稿系统

> 智能规则检查 + AI 语义审阅 + 修订痕迹 + 自动补全 + 期刊推荐

## 功能特性

- **📄 多格式支持**：PDF / DOCX / TXT / Markdown
- **🤖 多模型选择**：界面切换不同大模型（GPT-4o / Claude / Qwen / DeepSeek 等），Ollama 自动发现
- **📋 规则引擎**：章节完整性、格式规范、引用匹配、中英文混排检测
- **🧠 AI 深度审阅**：LLM 逐章节语义分析，含原文定位和具体修改建议
- **✍️ 修订痕迹**：增/删/改对比展示，标注修改位置和理由
- **📝 自动补全**：检测缺失章节并生成 AI 补全草稿（含置信度）
- **📚 期刊推荐**：基于论文内容创新性智能推荐 Top 10 投稿期刊，含 IF/接受率/审稿周期
- **📥 报告下载**：一键下载 DOCX 审稿报告（含修改痕迹、批注、推荐期刊），文件名含模型名+日期
- **📊 评分报告**：总体评分 + 优点/弱点分析 + 接收建议

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite |
| 后端 | Python FastAPI + OpenAI SDK + python-docx |
| AI | OpenAI Compatible API（支持本地 Ollama / GPT / Claude 等） |
| PDF 解析 | pypdfium2 |
| DOCX 生成 | python-docx |

## 快速启动

### 1. 配置环境变量

```bash
# 使用 Ollama 本地模型（推荐）
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
MODEL_NAME=qwen3.6:latest

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

1. **选择模型** — 从下拉列表选择审稿大模型
2. **上传稿件** — 拖拽或选择论文文件
3. **自动审稿** — 规则检查 → AI 语义分析 → 生成完整报告
4. **查看结果** — 6 个 Tab 展示：
   - 📊 总评：分数 + 优点/弱点
   - 📋 规则检查：章节/格式/引用问题
   - 🤖 AI 审阅：逐章节深度意见
   - ✍️ 修订痕迹：增删改对比
   - 📝 自动补全：缺失章节草稿
   - 📚 推荐期刊：Top 10 投稿期刊
5. **下载报告** — 📥 下载 DOCX（含完整批注和推荐期刊）

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/models` | 可用大模型列表（Ollama 自动发现 + 静态列表） |
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
│   │   ├── section_check.py         # 章节完整性
│   │   ├── format_check.py          # 格式规范
│   │   └── citation_check.py        # 引用匹配
│   └── ai_service/                  # AI 审阅服务
│       ├── llm_client.py            # LLM API 客户端
│       └── reviewer.py              # AI 审稿 Prompt 模板
├── client/                          # React 前端
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx                 # 入口
│       ├── App.tsx                  # 主应用（页面路由 + 模型管理）
│       ├── styles.css               # 全局样式（现代化设计系统）
│       ├── types/index.ts           # TypeScript 类型定义
│       ├── hooks/useReview.ts       # 审稿 Hook（含模型传参）
│       └── pages/
│           ├── UploadPage.tsx       # 上传页面（含模型选择器）
│           ├── ReviewResultPage.tsx # 审稿结果页（6 Tab + 下载）
│           └── HistoryPage.tsx      # 历史记录页
├── .env                              # 环境变量配置
├── .gitignore
└── README.md
```

## 支持的 AI 模型

系统自动识别 Ollama 本地可用模型，并预置以下模型列表：

- **本地**：Qwen 3.6、DeepSeek R1、Llama 3.3
- **云端**：GPT-4o、GPT-4o-mini、Claude Sonnet 4、Claude Haiku 4

Ollama 服务需在本地运行（默认 `localhost:11434`），系统启动时自动发现可用模型。

## 推荐期刊数据库

`journal_recommender.py` 内置 50+ 中英文学术期刊/会议，覆盖：

- NLP/AI 顶会：ACL、EMNLP、NeurIPS、ICLR、AAAI 等
- 信息科学/学术出版：Scientometrics、JASIST、Learned Publishing 等
- 计算机应用：Expert Systems with Applications、IP&M、KBS 等
- 中文核心：计算机学报、软件学报、情报学报、图书情报工作 等

每条期刊含影响因子（IF）、接受率、审稿周期、征稿范围等信息。
