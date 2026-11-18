from tools import compressor_llm
from langchain_core.messages import SystemMessage

def summarize_history(history_text: str) -> str:
    #调用大模型对历史对话进行摘要压缩
    prompt = f"你是一个无情的记忆压缩器。请阅读以下用户与AI的历史对话，提取出关于用户的关键信息（姓名、偏好、正在讨论的核心话题等），压缩成一段不超过150字的“前情提要”。不要输出废话，直接输出提要内容。历史对话：{history_text}"
    response = compressor_llm.invoke([SystemMessage(content=prompt)])
    return response.content