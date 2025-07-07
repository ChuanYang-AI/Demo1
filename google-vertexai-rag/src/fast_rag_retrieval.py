"""
高效RAG检索模块 - 集成FAISS向量搜索
提供毫秒级检索性能和快速索引构建
"""

import time
import os
from typing import List, Dict, Optional
try:
    from .fast_vector_search import FastVectorSearch
    from .data_preprocessing import chunk_text
except ImportError:
    from fast_vector_search import FastVectorSearch
    from data_preprocessing import chunk_text

class FastRAGRetrieval:
    def __init__(self, 
                 model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                 cache_dir: str = "./cache"):
        """
        初始化高效RAG检索系统
        
        Args:
            model_name: sentence-transformers模型名称
            cache_dir: 缓存目录
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # 初始化向量搜索引擎
        index_file = os.path.join(cache_dir, "faiss_index.bin")
        metadata_file = os.path.join(cache_dir, "faiss_metadata.json")
        
        print("🚀 初始化高效向量搜索引擎...")
        start_time = time.time()
        
        self.search_engine = FastVectorSearch(
            model_name=model_name,
            index_file=index_file,
            metadata_file=metadata_file
        )
        
        print(f"✅ 高效检索系统初始化完成 (耗时: {time.time() - start_time:.2f}秒)")
        
        # 显示初始统计信息
        stats = self.search_engine.get_stats()
        print(f"📊 当前索引状态: {stats['total_documents']} 个文档, {stats['embedding_dimension']} 维向量")
    
    def add_document(self, file_id: str, text: str, filename: str = None) -> int:
        """
        添加单个文档到索引
        
        Args:
            file_id: 文件ID
            text: 文档文本
            filename: 文件名（可选）
            
        Returns:
            添加的文档块数量
        """
        print(f"📝 处理文档: {filename or file_id}")
        
        # 分块处理
        chunks = chunk_text(text, chunk_size=500, overlap_size=100)
        
        if not chunks:
            print("⚠️ 文档为空，跳过处理")
            return 0
        
        # 准备文档数据
        documents = []
        for i, chunk in enumerate(chunks):
            doc = {
                'id': f"{file_id}_chunk_{i}",
                'text': chunk,
                'source': filename or file_id
            }
            documents.append(doc)
        
        # 添加到索引
        added_ids = self.search_engine.add_documents(documents)
        
        print(f"✅ 文档处理完成: {len(added_ids)} 个块已添加到索引")
        return len(added_ids)
    
    def add_documents_batch(self, documents: List[Dict[str, str]]) -> int:
        """
        批量添加文档到索引
        
        Args:
            documents: 文档列表 [{file_id, text, filename}, ...]
            
        Returns:
            添加的文档块总数
        """
        if not documents:
            return 0
        
        print(f"📚 批量处理 {len(documents)} 个文档...")
        start_time = time.time()
        
        all_chunks = []
        chunk_count = 0
        
        for doc in documents:
            file_id = doc['file_id']
            text = doc['text']
            filename = doc.get('filename', file_id)
            
            # 分块处理
            chunks = chunk_text(text, chunk_size=500, overlap_size=100)
            
            # 准备文档数据
            for i, chunk in enumerate(chunks):
                chunk_doc = {
                    'id': f"{file_id}_chunk_{i}",
                    'text': chunk,
                    'source': filename
                }
                all_chunks.append(chunk_doc)
                chunk_count += 1
        
        # 批量添加到索引
        if all_chunks:
            added_ids = self.search_engine.add_documents(all_chunks)
            
            print(f"✅ 批量处理完成 (耗时: {time.time() - start_time:.2f}秒)")
            print(f"📊 总共添加 {len(added_ids)} 个文档块")
            return len(added_ids)
        
        return 0
    
    def search(self, query: str, k: int = 5, min_score: float = 0.3) -> List[Dict]:
        """
        搜索最相关的文档
        
        Args:
            query: 查询文本
            k: 返回的结果数量
            min_score: 最低相似度阈值
            
        Returns:
            搜索结果列表
        """
        print(f"🔍 执行高效搜索: '{query[:50]}...'")
        start_time = time.time()
        
        # 执行搜索
        results = self.search_engine.search(query, k=k)
        
        # 过滤低分结果
        filtered_results = []
        for result in results:
            if result['similarity'] >= min_score:
                # 转换为兼容格式
                compatible_result = {
                    'id': result['id'],
                    'datapoint_id': result['id'],
                    'distance': 1.0 - result['similarity'],  # 转换为距离
                    'similarity': result['similarity'],
                    'score': result['score'],
                    'rank': result['rank'],
                    'text': result['text'],
                    'source': result['source'],
                    'content_preview': result['text'][:100] + '...' if len(result['text']) > 100 else result['text']
                }
                filtered_results.append(compatible_result)
        
        search_time = time.time() - start_time
        print(f"✅ 高效搜索完成 (耗时: {search_time*1000:.1f}ms)")
        print(f"📋 找到 {len(filtered_results)} 个相关结果")
        
        # 显示搜索结果摘要
        for i, result in enumerate(filtered_results[:3]):
            print(f"   {i+1}. {result['source']}: {result['text'][:50]}... (相似度: {result['similarity']:.3f})")
        
        return filtered_results
    
    def get_stats(self) -> Dict:
        """获取检索系统统计信息"""
        base_stats = self.search_engine.get_stats()
        return {
            'retrieval_engine': 'FastRAG + FAISS',
            'total_documents': base_stats['total_documents'],
            'embedding_dimension': base_stats['embedding_dimension'],
            'model_name': base_stats['model_name'],
            'index_trained': base_stats['index_trained'],
            'cache_dir': self.cache_dir,
            'performance': '毫秒级检索'
        }
    
    def clear_index(self):
        """清空索引"""
        print("🗑️ 清空检索索引...")
        self.search_engine.clear_index()
        print("✅ 索引已清空")
    
    def rebuild_index(self, documents: List[Dict[str, str]]):
        """重建索引"""
        print("🔄 重建检索索引...")
        start_time = time.time()
        
        # 清空现有索引
        self.clear_index()
        
        # 重新添加文档
        added_count = self.add_documents_batch(documents)
        
        print(f"✅ 索引重建完成 (耗时: {time.time() - start_time:.2f}秒)")
        print(f"📊 重建结果: {added_count} 个文档块")
        
        return added_count

# 便捷函数：替换原有的retrieve_relevant_chunks
def retrieve_relevant_chunks_fast(
    query_text: str,
    retrieval_engine: FastRAGRetrieval,
    num_neighbors: int = 5,
    min_similarity: float = 0.3,
    **kwargs  # 兼容旧参数
) -> List[Dict]:
    """
    高效检索相关文档块 - 兼容原有接口
    
    Args:
        query_text: 查询文本
        retrieval_engine: 高效检索引擎实例
        num_neighbors: 返回的邻居数量
        min_similarity: 最低相似度阈值
        
    Returns:
        检索结果列表
    """
    print(f"[FastRAG] 使用高效检索引擎进行搜索...")
    
    # 执行搜索
    results = retrieval_engine.search(
        query=query_text,
        k=num_neighbors,
        min_score=min_similarity
    )
    
    print(f"[FastRAG] 高效检索完成，返回 {len(results)} 个结果")
    return results

# 使用示例
if __name__ == "__main__":
    # 创建高效检索系统
    retrieval_system = FastRAGRetrieval()
    
    # 示例文档
    documents = [
        {
            'file_id': 'legal_doc_1',
            'text': '合同是当事人之间设立、变更、终止民事权利义务关系的协议。合同的成立需要当事人达成合意，并且合意的内容必须合法。',
            'filename': '合同法基础.docx'
        },
        {
            'file_id': 'legal_doc_2', 
            'text': '民事责任是指民事主体因违反民事义务而承担的法律后果。民事责任的承担方式包括停止侵害、赔偿损失、恢复原状等。',
            'filename': '民事责任.docx'
        }
    ]
    
    # 批量添加文档
    added_count = retrieval_system.add_documents_batch(documents)
    print(f"添加了 {added_count} 个文档块")
    
    # 搜索测试
    results = retrieval_system.search("什么是合同", k=3)
    for result in results:
        print(f"相似度 {result['similarity']:.3f}: {result['text'][:50]}...")
    
    # 显示统计信息
    stats = retrieval_system.get_stats()
    print(f"系统统计: {stats}") 