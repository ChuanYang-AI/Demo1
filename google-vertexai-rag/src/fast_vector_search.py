"""
高效向量搜索系统 - 基于FAISS + sentence-transformers
提供毫秒级检索和快速索引构建
"""

import os
import time
import pickle
import json
import numpy as np
from typing import List, Dict, Tuple, Optional
from sentence_transformers import SentenceTransformer
import faiss
from datetime import datetime

class FastVectorSearch:
    def __init__(self, 
                 model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                 index_file: str = "./cache/faiss_index.bin",
                 metadata_file: str = "./cache/faiss_metadata.json"):
        """
        初始化高效向量搜索系统
        
        Args:
            model_name: sentence-transformers模型名称
            index_file: FAISS索引文件路径
            metadata_file: 元数据文件路径
        """
        self.model_name = model_name
        self.index_file = index_file
        self.metadata_file = metadata_file
        
        # 确保缓存目录存在
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        
        # 初始化embedding模型
        print(f"🔧 初始化embedding模型: {model_name}")
        start_time = time.time()
        self.model = SentenceTransformer(model_name)
        print(f"✅ 模型加载完成 (耗时: {time.time() - start_time:.2f}秒)")
        
        # 获取embedding维度
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"📏 Embedding维度: {self.embedding_dim}")
        
        # 初始化FAISS索引
        self.index = None
        self.metadata = {}  # id -> {text, source, timestamp}
        
        # 加载现有索引
        self.load_index()
        
    def load_index(self):
        """加载现有的FAISS索引和元数据"""
        try:
            if os.path.exists(self.index_file) and os.path.exists(self.metadata_file):
                print("📂 加载现有索引...")
                # 加载FAISS索引
                self.index = faiss.read_index(self.index_file)
                
                # 加载元数据
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
                
                print(f"✅ 索引加载完成 - 包含 {self.index.ntotal} 个向量")
            else:
                print("🆕 创建新的FAISS索引...")
                # 使用简单的平面索引，避免聚类问题
                self.index = faiss.IndexFlatIP(self.embedding_dim)
                
        except Exception as e:
            print(f"⚠️ 加载索引失败: {e}")
            print("🆕 创建新的FAISS索引...")
            self.index = faiss.IndexFlatIP(self.embedding_dim)
            self.metadata = {}
    
    def save_index(self):
        """保存FAISS索引和元数据"""
        try:
            # 保存FAISS索引
            faiss.write_index(self.index, self.index_file)
            
            # 保存元数据
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
            
            print(f"💾 索引保存完成 - {self.index.ntotal} 个向量")
            
        except Exception as e:
            print(f"❌ 保存索引失败: {e}")
    
    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        生成文本的embedding向量
        
        Args:
            texts: 文本列表
            
        Returns:
            numpy数组，形状为 (len(texts), embedding_dim)
        """
        print(f"🔄 生成 {len(texts)} 个文本的embedding...")
        start_time = time.time()
        
        # 批量生成embedding
        embeddings = self.model.encode(texts, 
                                     batch_size=32,
                                     show_progress_bar=False,
                                     convert_to_numpy=True)
        
        # 标准化向量（重要：用于内积搜索）
        faiss.normalize_L2(embeddings)
        
        print(f"✅ Embedding生成完成 (耗时: {time.time() - start_time:.2f}秒)")
        return embeddings
    
    def add_documents(self, documents: List[Dict[str, str]]) -> List[int]:
        """
        添加文档到索引
        
        Args:
            documents: 文档列表，每个文档包含 {id, text, source}
            
        Returns:
            添加的文档ID列表
        """
        if not documents:
            return []
        
        print(f"📝 添加 {len(documents)} 个文档到索引...")
        start_time = time.time()
        
        # 提取文本
        texts = [doc['text'] for doc in documents]
        
        # 生成embedding
        embeddings = self.generate_embeddings(texts)
        
        # 智能索引管理：检查是否需要升级索引类型
        current_total = self.index.ntotal
        new_total = current_total + len(embeddings)
        
        # 检查是否需要升级索引
        if new_total >= 500 and isinstance(self.index, faiss.IndexFlat):
            print("📈 数据量达到阈值，升级到IVF索引...")
            self._upgrade_to_ivf_index()
        
        # 训练索引（如果需要）
        if not self.index.is_trained:
            print("🏋️ 训练FAISS索引...")
            try:
                self.index.train(embeddings)
            except Exception as e:
                print(f"⚠️ 索引训练失败: {e}")
                # 如果是IVF索引训练失败，降级到平面索引
                if not isinstance(self.index, faiss.IndexFlat):
                    print("🔄 降级到平面索引...")
                    self._downgrade_to_flat_index()
        
        # 添加向量到索引
        start_idx = self.index.ntotal
        self.index.add(embeddings)
        
        # 更新元数据
        added_ids = []
        for i, doc in enumerate(documents):
            doc_id = start_idx + i
            self.metadata[str(doc_id)] = {
                'text': doc['text'],
                'source': doc.get('source', 'unknown'),
                'original_id': doc.get('id', f'doc_{doc_id}'),
                'timestamp': datetime.now().isoformat()
            }
            added_ids.append(doc_id)
        
        # 保存索引
        self.save_index()
        
        print(f"✅ 文档添加完成 (耗时: {time.time() - start_time:.2f}秒)")
        print(f"📊 索引总数: {self.index.ntotal}")
        
        return added_ids
    
    def search(self, query: str, k: int = 5) -> List[Dict]:
        """
        搜索最相关的文档
        
        Args:
            query: 查询文本
            k: 返回的结果数量
            
        Returns:
            搜索结果列表
        """
        if self.index.ntotal == 0:
            print("⚠️ 索引为空，无法搜索")
            return []
        
        print(f"🔍 搜索查询: '{query[:50]}...'")
        start_time = time.time()
        
        # 生成查询向量
        query_embedding = self.generate_embeddings([query])
        
        # 搜索
        scores, indices = self.index.search(query_embedding, k)
        
        # 构建结果
        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx == -1:  # FAISS找不到足够的结果时返回-1
                break
                
            metadata = self.metadata.get(str(idx), {})
            result = {
                'rank': i + 1,
                'score': float(score),
                'similarity': float(score),  # 内积搜索，分数即为相似度
                'index': int(idx),
                'id': metadata.get('original_id', f'doc_{idx}'),
                'text': metadata.get('text', ''),
                'source': metadata.get('source', 'unknown'),
                'timestamp': metadata.get('timestamp', '')
            }
            results.append(result)
        
        search_time = time.time() - start_time
        print(f"✅ 搜索完成 (耗时: {search_time*1000:.1f}ms)")
        print(f"📋 找到 {len(results)} 个结果")
        
        return results
    
    def get_stats(self) -> Dict:
        """获取索引统计信息"""
        return {
            'total_documents': self.index.ntotal if self.index else 0,
            'embedding_dimension': self.embedding_dim,
            'model_name': self.model_name,
            'index_trained': self.index.is_trained if self.index else False,
            'metadata_count': len(self.metadata)
        }
    
    def clear_index(self):
        """清空索引"""
        print("🗑️ 清空索引...")
        self.index.reset()
        self.metadata.clear()
        self.save_index()
        print("✅ 索引已清空")
    
    def _upgrade_to_ivf_index(self):
        """升级到IVF索引以提高大数据集的搜索性能"""
        try:
            # 获取当前所有向量
            if self.index.ntotal == 0:
                return
            
            # 重构所有向量
            all_vectors = np.zeros((self.index.ntotal, self.embedding_dim), dtype='float32')
            for i in range(self.index.ntotal):
                all_vectors[i] = self.index.reconstruct(i)
            
            # 动态计算聚类数量：建议是数据点数量的平方根，最少10个，最多256个
            n_clusters = min(max(int(np.sqrt(self.index.ntotal)), 10), 256)
            
            # 创建新的IVF索引
            quantizer = faiss.IndexFlatIP(self.embedding_dim)
            new_index = faiss.IndexIVFFlat(quantizer, self.embedding_dim, n_clusters)
            
            # 训练新索引
            new_index.train(all_vectors)
            
            # 添加所有向量到新索引
            new_index.add(all_vectors)
            
            # 替换旧索引
            self.index = new_index
            print(f"✅ 成功升级到IVF索引 (聚类数: {n_clusters})")
            
        except Exception as e:
            print(f"❌ 升级索引失败: {e}")
            print("🔄 保持使用平面索引...")
    
    def _downgrade_to_flat_index(self):
        """降级到平面索引以避免训练问题"""
        try:
            # 获取当前所有向量
            if self.index.ntotal == 0:
                # 创建空的平面索引
                self.index = faiss.IndexFlatIP(self.embedding_dim)
                return
            
            # 重构所有向量
            all_vectors = np.zeros((self.index.ntotal, self.embedding_dim), dtype='float32')
            for i in range(self.index.ntotal):
                all_vectors[i] = self.index.reconstruct(i)
            
            # 创建新的平面索引
            new_index = faiss.IndexFlatIP(self.embedding_dim)
            
            # 添加所有向量到新索引
            new_index.add(all_vectors)
            
            # 替换旧索引
            self.index = new_index
            print("✅ 成功降级到平面索引")
            
        except Exception as e:
            print(f"❌ 降级索引失败: {e}")
            # 创建全新的平面索引
            self.index = faiss.IndexFlatIP(self.embedding_dim)
            print("🆕 创建新的平面索引")

# 使用示例
if __name__ == "__main__":
    # 创建向量搜索实例
    search_engine = FastVectorSearch()
    
    # 示例文档
    documents = [
        {"id": "doc1", "text": "人工智能是计算机科学的一个重要分支", "source": "AI教程"},
        {"id": "doc2", "text": "机器学习是实现人工智能的重要方法", "source": "ML指南"},
        {"id": "doc3", "text": "深度学习是机器学习的一个子集", "source": "DL概述"},
        {"id": "doc4", "text": "自然语言处理是AI的重要应用领域", "source": "NLP简介"},
        {"id": "doc5", "text": "计算机视觉帮助机器理解图像", "source": "CV基础"}
    ]
    
    # 添加文档
    doc_ids = search_engine.add_documents(documents)
    print(f"添加的文档ID: {doc_ids}")
    
    # 搜索测试
    results = search_engine.search("什么是人工智能", k=3)
    for result in results:
        print(f"排名{result['rank']}: {result['text'][:50]}... (相似度: {result['similarity']:.3f})")
    
    # 获取统计信息
    stats = search_engine.get_stats()
    print(f"索引统计: {stats}") 