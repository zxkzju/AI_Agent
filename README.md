智能赛博朋友 Agent 系统 
基于大语言模型（LLM）、LangChain 与 LangGraph 打造的多端、多模态、具备长期记忆的智能对话系统。支持 Web 界面交互，并成功接入 QQ 官方机器人生态，化身名为“林克”的赛博朋友与你实时互动。

✨ 核心特性
🧠 长期记忆机制 (Long-term Memory)：基于 PostgreSQL 数据库存储，跨会话记住用户的姓名、偏好、配置等信息，并支持滑动窗口记忆压缩，防止大模型 Token 溢出。

📚 专属知识库 (RAG)：基于 Chroma 向量库构建，支持多用户隔离上传 PDF/TXT 文件，Agent 会结合用户的专属文档进行精准检索与问答。

🖼️ 多模态视觉理解 (Multimodal Vision)：接入通义千问 qwen-vl-plus 视觉模型，支持在 QQ 中发送图片，Agent 能看懂图片并给出幽默吐槽。

💬 多端无缝接入 (Multi-platform)：

Web 端：基于 Streamlit 构建，支持流式打字机输出、历史摘要压缩、登录隔离。

QQ 机器人：基于 qq-botpy-v2 接入 QQ 官方生态，支持群聊 @ 与 C2C 私聊，完美解决 5 秒超时限制与消息去重问题。

🛠️ 丰富的工具链：集成高德地图天气查询、Tavily 实时联网搜索等外部工具。

🛠️ 技术栈 (Tech Stack)
核心框架：Python 3.11+, LangChain, LangGraph

大模型 (LLM)：兼容 OpenAI 接口的大模型（如 通义千问 Qwen 系列）

数据库：PostgreSQL (长期记忆), Chroma (向量检索)

前端 UI：Streamlit

QQ 机器人：qq-botpy-v2

视觉模型：qwen3-vl-plus

🚀 快速开始 (Quick Start)
1. 环境准备
确保你本地安装了 Python 3.11+ 以及 PostgreSQL 数据库。

2. 安装依赖
bash
pip install -r requirements.txt
(主要依赖包括：langchain, langgraph, langchain-openai, langgraph-checkpoint-postgres, psycopg[binary], psycopg_pool, streamlit, qq-botpy-v2, chromadb, tavily-python, pypdf)

3. 配置环境变量
在项目根目录创建 .env 文件，填入你的 API Keys：

env
# 阿里百炼 API Key (用于通义千问文本与视觉模型)
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxx

# 高德地图 API Key (用于天气查询)
GAODE_API_KEY=xxxxxxxxxxxxxxxxxxx

# Tavily API Key (用于联网搜索)
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxx

# PostgreSQL 数据库连接 (请根据实际情况修改)
DB_URI=postgresql://postgres:你的密码@localhost:5432/postgres

# QQ 机器人配置
QQ_APP_ID=你的AppID
QQ_APP_SECRET=你的AppSecret
4. 启动 Web 端 (Streamlit)
bash
streamlit run app.py
在浏览器中打开 http://localhost:8501，输入你的用户 ID 即可开始对话、上传专属知识库文档。

5. 启动 QQ 机器人
bash
python qq_bot.py
在 QQ 群里 @ 机器人，或者私聊机器人，即可体验具备长期记忆和看图能力的“林克”。

📂 项目结构 
text
agent_project/
├── app.py                  # Streamlit Web 端主入口
├── qq_bot.py               # QQ 机器人主入口 (多模态与异步处理)
├── react_agent.py          # 核心 Agent 逻辑 (封装 create_agent)
├── tools.py                # Agent 可调用的工具箱 (天气、搜索、记忆等)
├── rag_service.py          # 知识库 RAG 检索服务
├── vector_store.py         # Chroma 向量库封装 (多用户隔离)
├── memory_utils.py         # 历史对话摘要压缩工具
├── prompt_loader.py        # 系统提示词加载模块
├── config_handler.py       # 配置文件读取
├── factory.py              # 模型初始化工厂
├── .env                    # 敏感配置信息 (需加入 .gitignore)
├── requirements.txt        # 项目依赖列表
└── chroma_db/              # 本地向量数据库存储目录
💡 核心实现细节 (Implementation Details)
多租户数据隔离
在保存和检索向量库、长期记忆时，严格按 user_id 作为 namespace（命名空间）进行数据隔离。在 QQ 机器人中，自动将 QQ 的 member_openid 映射为系统的 user_id，确保跨平台身份一致。

记忆压缩机制
当用户的长期记忆超过 10 条时，自动触发压缩机制，将最早的 5 条记忆交给模型总结成 150 字以内的摘要，并替换原记忆，有效防止上下文过长导致的性能问题。

QQ 原生“输入中”状态
为规避 QQ 官方 5 秒被动回复超时的限制，通过发送 msg_type=6 的 input_notify 请求，实现类似真人打字的“正在输入...”提示，体验极为自然。

⚠️ 免责声明 (Disclaimer)
本项目仅供学习与技术交流使用。请妥善保管你的 API Key 与数据库密码，不要将带有真实 Key 的代码上传至公开仓库。
