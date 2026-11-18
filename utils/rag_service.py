#总结服务：用户提问，搜索参考资料，将提问与参考资料交给模型，让模型总结回复

from vector_store import VectorStoreService
from prompt_loader import load_rag_prompt
from langchain_core.prompts import PromptTemplate
from factory import chat_model
from langchain_core.output_parsers import StrOutputParser
from config_handler import chroma_conf

class RagSummarizeService(object):
    def __init__(self):
        self.vector_store_service = VectorStoreService()
        self.retriever = self.vector_store_service.get_retriever()
        self.prompt_text = load_rag_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()
    
    def load_document_from_text(self, text: str, user_id: str, source: str = "user_upload"):
        # 【修复】调用 VectorStoreService 里面真正的入库方法
        chunk_count = self.vector_store_service.add_user_text(
            text=text, 
            user_id=user_id, 
            source=source
        )
        return f"成功入库 {chunk_count} 个文本切片。"

    def _init_chain(self):
        chain = self.prompt_template | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str, user_id: str):
        """从底层 Chroma 检索，并强制按 user_id 过滤"""
        try:
            # 直接访问 VectorStoreService 里的 vector_store 实例
            docs = self.vector_store_service.vector_store.similarity_search(
                query=query,
                k=chroma_conf["k"],
                filter={"user_id": user_id}  # 核心过滤条件
            )
            return docs
        except Exception as e:
            # 如果报错（比如因为部分老数据没有 user_id 标签导致不兼容），退回普通检索
            print(f"带过滤的检索失败: {e}，退回普通检索")
            return self.retriever.invoke(query)

    def rag_summarize(self, query: str, user_id: str) -> str:
        # print(f"\n--- 用户提问: {query} ---")
        context_docs = self.retriever_docs(query, user_id=user_id)
        #print(f"--- 检索到了 {len(context_docs)} 个文档 ---")
        # for d in context_docs:
        #     print(f"    [切片内容]: {d.page_content[:50]}... [元数据]: {d.metadata}")
        if not context_docs:
            return "在你的专属知识库中没有找到相关参考资料。"

        context = ""
        idx = 0
        for doc in context_docs:
            idx += 1
            context += f"【参考资料{idx}】：{doc.page_content} | 参考元数据：{doc.metadata}\n"

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
            }
        )
