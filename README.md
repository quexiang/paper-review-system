# 学术论文审稿系统

> 智能规则检查 + AI 语义审阅 + 自动补全建议

## 功能特性

- **📄 多格式支持**：PDF / DOCX / TXT / Markdown
- **📋 规则引擎**：章节完整性、格式规范、引用匹配等自动化检查
- **🤖 AI 审阅**：基于 LLM（OpenAI Claude/GPT）的深度语义审阅
- **✍️ 修订痕迹**：以审阅模式展示增删改的对比结果
- **📝 自动补全**：对缺失章节生成内容草稿
- **📊 评分报告**：总体评分 + 优点/弱点分析

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite |
| 后端 | Python FastAPI + OpenAI SDK |
| AI | OpenAI Compatible API (GPT-4o / Claude) |

## 快速启动

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY
```

### 2. 安装依赖

```bash
# 后端
cd server
pip install -r requirements.txt

# 前端
cd ../../client
npm install
```

### 3. 启动服务

```bash
# Terminal 1：启动后端（端口 8000）
cd server
uvicorn main:app --reload --port 8000

# Terminal 2：启动前端（端口 3000）
cd client
npm run dev
```

打开 http://localhost:3000 即可使用。

## 审稿流程

1. **上传稿件** → 拖拽或选择论文文件
2. **规则检查** → 自动检测章节、格式、引用等
3. **AI 审阅** → 大模型对全文进行语义分析
4. **查看结果** → 评分 + 规则报告 + AI 意见 + 修订痕迹 + 补全建议

## 项目结构

```
claude-review-system/
├── server/                          # FastAPI 后端
│   ├── main.py                      # API 入口 & 审稿流程编排
│   ├── models.py                    # 数据模型 (Pydantic)
│   ├── parser.py                    # PDF/DOCX/TXT/MD 解析器
│   ├── requirements.txt             # Python 依赖
│   ├── rule_engine/                 # 规则检查模块
│   │   ├── section_check.py         # 章节完整性
│   │   ├── format_check.py          # 格式规范
│   │   └── citation_check.py        # 引用匹配
│   ├── ai_service/                  # AI 审阅服务
│   │   ├── llm_client.py            # LLM API 客户端
│   │   └── reviewer.py              # AI 审稿逻辑
│   └── utils/                       # 工具函数
├── client/                          # React 前端
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx                 # 入口
│       ├── App.tsx                  # 主应用（路由）
│       ├── styles.css               # 全局样式
│       ├── types/index.ts           # TypeScript 类型
│       ├── api/client.ts            # API 客户端
│       ├── hooks/useReview.ts       # 审稿 Hook
│       └── pages/
│           ├── UploadPage.tsx       # 上传页面
│           ├── ReviewResultPage.tsx # 审稿结果页
│           └── HistoryPage.tsx      # 历史记录页
├── .env.example                     # 环境变量模板
└── README.md
```
