import streamlit as st
import time
from contextlib import contextmanager
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from langgraph.store.postgres import PostgresStore
from react_agent import ReactAgent
from memory_utils import summarize_history
from rag_service import RagSummarizeService 
from user_store import register_user, verify_user
import pypdf
import io

# 初始化 RAG 服务（缓存，避免重复加载模型）
@st.cache_resource
def get_rag_service():
    return RagSummarizeService()

rag_service = get_rag_service()

DB_URI = "postgresql://postgres:postgres@localhost:5432/postgres"
if "summary" not in st.session_state:
    st.session_state["summary"] = "无前情提要。"

# --- 数据库连接池 ---
@contextmanager
def get_agent_context():
    pool = ConnectionPool(
        conninfo=DB_URI, min_size=1, max_size=2,
        kwargs={"autocommit": True, "row_factory": dict_row},
        check=ConnectionPool.check_connection, open=True,
    )
    pool.check()
    store = PostgresStore(pool)
    store.setup()
    agent = ReactAgent(store=store) 
    try:
        yield agent
    finally:
        pool.close()

st.title("智能回复系统")
st.divider()

# --- 1. 登录/注册逻辑 ---
if "user_id" not in st.session_state:
    st.session_state["user_id"] = None
if "messages" not in st.session_state:
    st.session_state["messages"] = []

def enter_chat(user_name: str, greeting: str):
    st.session_state["user_id"] = user_name
    st.session_state["messages"] = [{"role": "assistant", "content": greeting}]
    st.session_state["summary"] = "无前情提要。" # 重置摘要
    st.rerun() # 刷新页面进入聊天

# 如果没登录，显示登录框，并终止后续渲染
if st.session_state["user_id"] is None:
    with st.form("login_form"):
        st.subheader("请登录")
        st.caption("新用户需先注册，注册后才能登录。")
        username = st.text_input("请输入您的用户名:")
        password = st.text_input("请输入您的密码:", type="password")

        login_col, register_col = st.columns(2)
        with login_col:
            login_btn = st.form_submit_button("登录", use_container_width=True)
        with register_col:
            register_btn = st.form_submit_button("注册", use_container_width=True)

        if login_btn or register_btn:
            user_name = username.strip()
            if not user_name or not password:
                st.error("用户名和密码均不能为空！")
            elif register_btn:
                ok, err = register_user(user_name, password)
                if ok:
                    enter_chat(user_name, f"注册成功，你好 {user_name}！有什么能帮助你的？")
                else:
                    st.error(err)
            else:
                ok, err = verify_user(user_name, password)
                if ok:
                    enter_chat(user_name, f"你好 {user_name}！有什么能帮助你的？")
                else:
                    st.error(err)
    st.stop() # 重点：没登录时，停止运行下面的聊天代码

# --- 2. 聊天界面逻辑（登录后才会执行到这里） ---

with st.sidebar:
    st.write(f"当前登录: **{st.session_state['user_id']}**")
    if st.button("退出登录"):
        st.session_state["user_id"] = None
        st.session_state["messages"] = []
        st.session_state["summary"] = "无前情提要。" # 清空摘要
        st.session_state.pop("last_uploaded", None) # 清空上传记录
        st.rerun()

    st.divider()
    st.subheader("知识库管理")
    uploaded_file = st.file_uploader("上传 PDF 或 TXT 文件", type=["pdf", "txt"])
    
    if uploaded_file is not None:
        # 【优化】结合当前用户 ID 作为标记，防止换号后同名文件不上传
        upload_tag = f"{st.session_state['user_id']}_{uploaded_file.name}"
        
        if st.session_state.get("last_uploaded") != upload_tag:
            with st.spinner("正在解析并存入向量数据库..."):
                file_content = ""
                if uploaded_file.type == "application/pdf":
                    pdf_reader = pypdf.PdfReader(io.BytesIO(uploaded_file.getvalue()))
                    for page in pdf_reader.pages:
                        text = page.extract_text()
                        if text:
                            file_content += text + "\n"
                else:
                    file_content = uploaded_file.getvalue().decode("utf-8")

                # 调用 RAG 服务入库
                rag_service.load_document_from_text(
                    text=file_content, 
                    user_id=st.session_state["user_id"], 
                    source=uploaded_file.name
                )
                
                st.session_state["last_uploaded"] = upload_tag
                st.success(f"文件 {uploaded_file.name} 已成功入库！可以开始提问了。")

# 渲染历史消息
for msg in st.session_state["messages"]:
    st.chat_message(msg["role"]).write(msg["content"])

prompt = st.chat_input()

if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # 【对话压缩逻辑】
    if len(st.session_state["messages"]) >= 10:
        # 取出最老的 8 条（不包含当前的 prompt）
        old_messages = st.session_state["messages"][:-2][:8]
        if old_messages:
            old_text = "\n".join([f"{m['role']}: {m['content']}" for m in old_messages])
            combined_text = f"之前的摘要：{st.session_state['summary']}\n\n最近对话：\n{old_text}"
            
            new_summary = summarize_history(combined_text)
            st.session_state["summary"] = new_summary
            
            # 砍掉最老的 8 条，保留后面的（包括当前的 prompt）
            st.session_state["messages"] = st.session_state["messages"][8:]

    ai_res_list = []

    with st.spinner("AI思考中"):
        with get_agent_context() as agent:
            re_stream = agent.execute_stream(
                prompt, 
                user_id=st.session_state["user_id"],
                history=st.session_state["messages"],
                summary=st.session_state["summary"]
            )

            def capture(generator, cache_list):
                for chunk in generator:
                    cache_list.append(chunk)
                    for char in chunk:
                        time.sleep(0.01)
                        yield char

            with st.chat_message("assistant"):
                st.write_stream(capture(re_stream, ai_res_list))

    full_response = ai_res_list[-1] if ai_res_list else "抱歉，生成回答失败。"
    st.session_state["messages"].append({"role": "assistant", "content": full_response})
    st.rerun()


    