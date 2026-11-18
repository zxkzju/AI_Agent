import os
import requests
import time
import uuid
from langchain.tools import tool, ToolRuntime
from typing_extensions import TypedDict
from langchain_openai import ChatOpenAI
from config_handler import rag_conf
from langchain_core.messages import SystemMessage
from rag_service import RagSummarizeService
from logger_handler import logger
from tavily import TavilyClient  

# ================= 1. 读取环境变量 =================
GAODE_KEY = os.getenv("GAODE_API_KEY")
DASHSCOPE_KEY = os.getenv("DASHSCOPE_API_KEY")
TAVILY_KEY=os.getenv("TAVILY_API_KEY")

rag = RagSummarizeService()

# ================= 2. 高德天气相关函数 =================
def get_weather_gaode(city_adcode: str, extensions="base"):
    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    params = {
        "key": GAODE_KEY,  
        "city": city_adcode,
        "extensions": extensions
    }
    resp = requests.get(url, params=params, timeout=10)
    return resp.json()

def city_name_to_adcode(city_name: str):
    url = "https://restapi.amap.com/v3/config/district"
    params = {
        "key": GAODE_KEY,  
        "keywords": city_name,
        "subdistrict": 0,
        "output": "json"
    }
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    if data.get("status") != "1":
        return None
    districts = data.get("districts", [])
    if not districts:
        return None
    return districts[0].get("adcode")

@tool(description="查询国内城市实况天气")
def get_weather(city_name: str) -> str:
    city_adcode = city_name_to_adcode(city_name)
    if city_adcode is None:
        return f"抱歉，无法识别城市：{city_name}" # 必须 return 防崩溃

    data = get_weather_gaode(city_adcode, extensions="base")
    if data.get("status") != "1" or data.get("infocode") != "10000":
        return f"天气查询失败，接口返回：{data.get('info', '未知错误')}" # 必须 return

    lives = data.get("lives", [])
    if not lives:
        return f"抱歉，暂未获取到该地区天气数据。" # 必须 return 防 IndexError

    live = lives[0]
    province = live["province"]
    city = live["city"]
    weather = live["weather"]
    temp = live["temperature"]
    wind_dir = live["winddirection"]
    wind_power = live["windpower"]
    humidity = live["humidity"]
    report_time = live["reporttime"]

    return (
        f"【{province}{city} 实时天气】\n"
        f"天气：{weather}，温度：{temp}℃，湿度：{humidity}%\n"
        f"风向风力：{wind_dir}风 {wind_power}级\n"
        f"数据更新时间：{report_time}"
    )

@tool(description="获取用户所在城市与城市编码")
def get_local_city() -> dict:
    url = "https://restapi.amap.com/v3/ip"
    try:
        resp = requests.get(url, params={"key": GAODE_KEY}, timeout=10) # 加 Key
        data = resp.json()
        if data.get("status") != "1":
            return {}
        return {
            "province": data["province"],
            "city": data["city"],
            "adcode": data["adcode"]
        }
    except Exception as e:
        logger.error(f"获取用户所在城市失败：{str(e)}")
        return {} # 加 return

# ================= 3. 其他工具 =================
@tool(description="从当前用户的专属向量检索库中检索参考资料")
def rag_summarize(query: str, runtime: ToolRuntime) -> str:
    user_id = runtime.config.get("configurable", {}).get("user_id", "default_user")
    return rag.rag_summarize(query, user_id=user_id)

@tool(description="无入参和返回值，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_report已调用"

tavily_client = TavilyClient(api_key=TAVILY_KEY)

@tool(description="当你不确定答案、或问题涉及实时信息时，使用此工具搜索网络")
def web_search(query: str) -> str:
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            results = tavily_client.search(query, max_results=1,search_depth='basic')
            return "\n".join([r["content"] for r in results["results"]])
        except Exception as e:
            error_msg = str(e)
            is_connection_error = any(kw in error_msg.lower() for kw in 
                ["connection aborted", "remote disconnected", "connection reset", "timeout"])
            if is_connection_error and attempt < max_retries:
                logger.warning(f"Tavily 连接失败，第 {attempt + 1} 次重试：{error_msg}")
                time.sleep(1 * (attempt + 1))
                continue
            logger.error(f"Tavily 搜索最终失败：{error_msg}")
            return f"搜索暂时不可用：{error_msg}"
    return "搜索暂时不可用"

# ================= 4. 长期记忆工具 =================
class MemoryEntry(TypedDict):
    content: str
    category: str

@tool(description="当需要回忆用户个人信息、偏好、历史对话时调用此工具。")
def recall_memory(runtime: ToolRuntime) -> str:
    assert runtime.store is not None
    user_id = runtime.config.get("configurable", {}).get("user_id", "default_user")
    items = runtime.store.search((user_id, "memories"))
    if not items:
        return "当前用户暂无历史记忆。"
    memories_text = [f"- {item.value.get('content', '')}" for item in items]
    return "已查到的用户历史记忆如下：\n" + "\n".join(memories_text)


compressor_llm = ChatOpenAI(
    model=rag_conf["ys_chat_model_name"],
    base_url="https://ws-dp8z53dewsii2bnm.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
)

@tool(description="将用户透露的重要信息保存到长期记忆中。")
def save_memory(content: str, category: str, runtime: ToolRuntime) -> str:
    assert runtime.store is not None
    user_id = runtime.config.get("configurable", {}).get("user_id", "default_user")
    items = runtime.store.search((user_id, "memories"))
    
    if len(items) >= 10:
        try:
            old_items = items[:5]
            old_text = "\n".join([f"- {item.value.get('content', '')}" for item in old_items])
            
            prompt = f"你是一个记忆压缩助手。请将以下关于该用户的碎片化记忆，合并成一段精炼的、不超过 150 字的总结。要求：保留所有核心事实，去除冗余。直接输出总结内容。碎片记忆：{old_text}"
            response = compressor_llm.invoke([SystemMessage(content=prompt)])
            compressed_content = response.content
            
            for item in old_items:
                runtime.store.delete((user_id, "memories"), item.key)
                
            summary_key = f"summary_{str(uuid.uuid4())[:8]}"
            runtime.store.put((user_id, "memories"), summary_key, {
                "content": f"【记忆总结】：{compressed_content}",
                "category": "综合记忆"
            })
            logger.info(f"=== 用户 {user_id} 的记忆已成功压缩合并 ===")
            
        except Exception as e:
            logger.error(f"记忆压缩失败: {e}，将跳过压缩直接保存新记忆。")
    
    unique_key = str(uuid.uuid4())
    runtime.store.put((user_id, "memories"), unique_key, {
        "content": content,
        "category": category
    })
    
    return f"已记住：{content}"