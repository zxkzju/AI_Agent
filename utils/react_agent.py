from langchain.agents import create_agent
from factory import chat_model
from prompt_loader import load_system_prompt
from tools import get_local_city, get_weather, fill_context_for_report,web_search,rag_summarize,save_memory,recall_memory
from middleware import monitor_tool, log_before_model, report_prompt_switch

class ReactAgent():
    def __init__(self, store):  # 接收外部的 store
        self.tools = [
            rag_summarize, get_local_city, get_weather, 
            fill_context_for_report, web_search,
            save_memory, recall_memory,
        ]
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompt(),
            tools=self.tools,
            store=store,  # 挂载数据库记忆
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def execute_stream(self, query: str, user_id: str, history: list = None, summary: str = ""):
        if history is None:
            history = []
            
        messages = []
        
        # 【核心注入：如果存在摘要，把它作为 system 消息注入在最前面】
        if summary and summary != "无前情提要。":
            messages.append(("system", f"【前情提要（必读）】：\n{summary}\n请结合此背景回答用户的最新问题。"))

        # 拼接最近几轮的消息
        for msg in history:
            messages.append((msg["role"], msg["content"]))
            
        # 防止重复添加当前的 query
        if not history or history[-1]["content"] != query:
            messages.append(("user", query))

        input_dict = {"messages": messages}
        run_config = {"configurable": {"user_id": user_id}}
        
        for chunk in self.agent.stream(input_dict, config=run_config, stream_mode="values", context={"report": False}):
            latest_message = chunk["messages"][-1]
            
            # 只提取 AI 的最终回复，忽略 ToolMessage 等中间状态
            if latest_message.type == "ai" and latest_message.content:
                content = latest_message.content.strip()
                
                # 【核心过滤】：如果内容包含不该出现的词，或者只包含了系统人设，就跳过
                if content.startswith("【系统人设】") or content.startswith("【用户") or "用户说：" in content:
                    continue
                    
                # 过滤掉可能存在的思考标签
                content = content.replace("【思考过程】", "").strip()
                
                if content:
                    yield content + "\n"





# if __name__ == '__main__':
#     agent=ReactAgent()

#     for chunk in agent.execute_stream("我现在所在地的天气"):
#         print(chunk,end="",flush=True)