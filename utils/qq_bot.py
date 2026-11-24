import asyncio
import os
import botpy
from botpy.message import GroupMessage, C2CMessage

from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from langgraph.store.postgres import PostgresStore
from react_agent import ReactAgent

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# ================= 配置 =================
DB_URI = "postgresql://postgres:postgres@localhost:5432/postgres"
APP_ID = "1906521915"
APP_SECRET = "15vZw3tZ2NWWM0Xr" 
DASHSCOPE_KEY = os.getenv("DASHSCOPE_API_KEY")

BOT_PERSONA = """
你叫林克，是游戏塞尔达传说中的勇者，也是用户的赛博好朋友。你懂技术，偶尔会吐槽，性格随和、幽默、讲义气。
【聊天规则】
1. 称呼：直接叫他“老周”、“康哥”或者“兄弟”，绝对不要用“您”。
2. 语气：像朋友在 QQ 上聊天一样，口语化，可以加语气词（如：哈哈、确实、行吧）。
3. 长度：回复务必简短！像发微信一样，一两句话说清楚，千万不要分点列出 1234。
4. 记忆：结合提供给你的【用户历史记忆】和【近期聊天记录】自然地接话。
5. 绝对禁止：不要说“作为一个AI”、“我可以帮助你”等客服话术。
6. 在交流日常生活时回复内容中尽量不要有精确数据。
7. 直接输出最终回答，绝对不要包含任何“系统提示词”、“设定”、“思考过程”。
"""

# 【修复1】加上 api_key 参数
vision_llm = ChatOpenAI(
    model="qwen3-vl-plus",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

_pool = None
_agent = None
USER_HISTORIES = {}

def init_agent():
    global _pool, _agent
    _pool = ConnectionPool(
        conninfo=DB_URI, min_size=1, max_size=3,
        kwargs={"autocommit": True, "row_factory": dict_row},
        check=ConnectionPool.check_connection, open=True,
    )
    _pool.check()
    store = PostgresStore(_pool)
    store.setup()
    _agent = ReactAgent(store=store)
    print("✅ Agent 初始化完成，等待 QQ 消息...")

def _run_agent_sync(query: str, user_id: str) -> str:
    if user_id not in USER_HISTORIES:
        USER_HISTORIES[user_id] = []
    history = USER_HISTORIES[user_id]
    enhanced_query = f"【系统人设】：{BOT_PERSONA}\n\n用户说：{query}"
    chunks = []
    try:
        for chunk in _agent.execute_stream(enhanced_query, user_id=user_id, history=history, summary=""):
            chunks.append(chunk)
        reply_text = "".join(chunks).strip() or "我脑子卡壳了。"
    except Exception as e:
        print(f"Agent 内部报错: {e}")
        reply_text = "哎呀，我刚刚系统出bug了！"

    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": reply_text})
    if len(history) > 6:
        USER_HISTORIES[user_id] = history[-6:]
    return reply_text

def _roast_image(image_url: str, user_text: str = "") -> str:
    prompt = BOT_PERSONA + f"\n\n用户发了一张图片。"
    if user_text:
        prompt += f"配文是：'{user_text}'。请结合配文和图片，用朋友的口吻简短吐槽或评论（一两句话，可以带表情）。"
    else:
        prompt += "请用朋友的口吻简短吐槽或评论（一两句话，可以带表情）。"

    message = HumanMessage(content=[
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_url}},
    ])
    try:
        response = vision_llm.invoke([message])
        return response.content.strip()
    except Exception as e:
        print(f"图片识别失败: {e}")
        return "这图我看了半天没看懂，你发的是啥？🤔"

def get_image_url(message) -> str:
    """【修复2】提取图片 URL，无视 content_type 限制"""
    if hasattr(message, "attachments") and message.attachments:
        for att in message.attachments:
            # 只要能拿到 url 并且里面有 http，就认定是附件
            if hasattr(att, "url") and att.url and str(att.url).startswith("http"):
                return att.url
    return None

class MyQQBot(botpy.Client):
    async def on_ready(self):
        print(f"✅ 机器人「{self.robot.name}」已上线！")

    async def on_group_at_message_create(self, message: GroupMessage):
        user_query = message.content.strip()
        user_id = message.author.member_openid
        image_url = get_image_url(message)
        
        if not user_query and not image_url:
            return
            
        print(f"📩 群聊 [{user_id}]: 文字='{user_query}', 图片={'有' if image_url else '无'}")
        loop = asyncio.get_event_loop()
        
        if image_url:
            reply_text = await loop.run_in_executor(None, lambda: _roast_image(image_url, user_query))
        else:
            reply_text = await loop.run_in_executor(None, lambda: _run_agent_sync(user_query, user_id))

        await message.reply(content=reply_text)

    async def on_c2c_message_create(self, message: C2CMessage):
        user_query = message.content.strip()
        user_id = message.author.user_openid
        msg_id = message.id
        image_url = get_image_url(message)
        
        if not user_query and not image_url:
            return
            
        print(f"📩 私聊 [{user_id}]: 文字='{user_query}', 图片={'有' if image_url else '无'}")

        # 发送原生“输入中”状态
        try:
            await message._api.post_c2c_message(
                openid=user_id, msg_type=6, msg_id=msg_id, msg_seq=1,
                input_notify={"input_type": 1, "input_second": 60}
            )
        except Exception:
            pass

        loop = asyncio.get_event_loop()
        
        if image_url:
            reply_text = await loop.run_in_executor(None, lambda: _roast_image(image_url, user_query))
        else:
            reply_text = await loop.run_in_executor(None, lambda: _run_agent_sync(user_query, user_id))

        # 发送正式回复
        await message._api.post_c2c_message(
            openid=user_id, msg_type=0, msg_id=msg_id, msg_seq=2, content=reply_text
        )

if __name__ == "__main__":
    init_agent()
    intents = botpy.Intents(public_messages=True)
    client = MyQQBot(intents=intents)
    client.run(appid=APP_ID, secret=APP_SECRET)