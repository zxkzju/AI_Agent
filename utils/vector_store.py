from langchain_chroma import Chroma
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from datetime import datetime
from config_handler import chroma_conf
from factory import embed_model
import os
from path_tool import get_abs_path
from file_handler import txt_loader,pdf_loader,listdir_with_allowed_type,get_file_md5_hex
from logger_handler import logger
from langchain_core.documents import Document


class VectorStoreService(object):
    def __init__(self):
        self.vector_store=Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=chroma_conf["persist_directory"],
        )
        self.spliter=RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )
    

    def add_user_text(self, text: str, user_id: str, source: str = "user_upload"):
        """专用于前端用户上传的文本，带用户标签和切片"""
        doc = Document(
            page_content=text,
            metadata={"source": source, "user_id": user_id}
        )
        # 复用你初始化好的 self.spliter
        split_docs = self.spliter.split_documents([doc])
        # print(f"=== 测试：切片数量为 {len(split_docs)} ===") # 加上这行
        if split_docs:
            self.vector_store.add_documents(split_docs)
            logger.info(f"用户 {user_id} 上传的文件 {source} 入库成功，共 {len(split_docs)} 个切片")
            return len(split_docs)
        return 0
    
    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k":chroma_conf["k"]})
    


    def load_document(self):
        #从数据文件中读取内容转为向量存入向量库，计算文件的MD5来去重
        def check_md5_hex(md5_for_check:str):
            if not os.path.exists(get_abs_path(chroma_conf["md5_hex_store"])):
                open(get_abs_path(chroma_conf["md5_hex_store"]),"w",encoding="utf-8").close()
                return False
            
            with open(get_abs_path(chroma_conf["md5_hex_store"]),"r",encoding="utf-8") as f:
                for line in f:
                    line=line.strip()
                    if line==md5_for_check:
                        return True
                    
                return False
            


        def save_md5_hex(md5_for_check:str):
            with open(get_abs_path(chroma_conf["md5_hex_store"]),"a",encoding="utf-8") as f:
                f.write(md5_for_check + "\n")


        
        def get_file_documents(read_path:str):
            if read_path.endswith("txt"):
                return txt_loader(read_path)
            
            if read_path.endswith("pdf"):
                return pdf_loader(read_path)
            
            return []
        

        allowed_files_path: list[str] = listdir_with_allowed_type(
            get_abs_path(chroma_conf["data_path"]),
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        for path in allowed_files_path:
            #获取文件MD5
            md5_hex=get_file_md5_hex(path)

            if(check_md5_hex(md5_hex)):
                logger.info(f"[加载知识库]{path}内容已经存在于知识库内，跳过")
                continue

            try:
                documents: list[Document] = get_file_documents(path)

                if not documents:
                    logger.warning(f"[加载知识库]{path}内没有有效文本内容，跳过")
                    continue

                split_document: list[Document] = self.spliter.split_documents(documents)

                if not split_document:
                    logger.warning(f"[加载知识库]{path}分片后没有有效文本内容，跳过")
                    continue

                self.vector_store.add_documents(split_document)
                save_md5_hex(md5_hex)

                logger.info(f"[加载知识库]{path}内容加载成功")

            except Exception as e:
                logger.error(f"[加载知识库]{path}内容加载失败：{str(e)}",exc_info=True)    #exc_info为True会记录详细的报错堆栈，否则只会记录报错信息本身
                continue



# if __name__=='__main__':
#     vs=VectorStoreService()

#     vs.load_document()