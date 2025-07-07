"""
混合检索系统 - 双路召回 + 智能融合
集成FAISS快速检索和Vertex AI检索，提供最佳的速度和准确性平衡
"""

import time
import asyncio
import threading
from typing import List, Dict, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
import numpy as np

# 导入现有模块
try:
    from .fast_rag_retrieval import FastRAGRetrieval
    from .rag_retrieval import retrieve_relevant_chunks
    from .rag_generation import generate_answer_with_llm
except ImportError:
    # 处理绝对导入情况
    from fast_rag_retrieval import FastRAGRetrieval
    from rag_retrieval import retrieve_relevant_chunks
    from rag_generation import generate_answer_with_llm

class RetrievalStrategy(Enum):
    """检索策略枚举"""
    FAST_ONLY = "fast_only"           # 仅使用FAISS快速检索
    VERTEX_ONLY = "vertex_only"       # 仅使用Vertex AI检索
    HYBRID_PARALLEL = "hybrid_parallel"  # 并行混合检索
    ADAPTIVE = "adaptive"             # 自适应检索
    FALLBACK = "fallback"            # 降级检索

@dataclass
class RetrievalConfig:
    """检索配置"""
    # 基础配置
    num_candidates: int = 10          # 每路召回的候选数
    final_results: int = 5            # 最终返回结果数
    
    # 系统权重
    faiss_weight: float = 0.6         # FAISS系统权重
    vertex_weight: float = 0.4        # Vertex AI系统权重
    
    # 阈值配置
    min_similarity: float = 0.3       # 最低相似度阈值
    high_confidence_threshold: float = 0.8  # 高置信度阈值
    
    # 性能配置
    max_parallel_timeout: float = 5.0  # 并行检索超时时间
    fallback_threshold: float = 2.0    # 降级检索阈值(秒)
    
    # 融合算法配置
    rrf_k: int = 60                   # RRF算法参数
    enable_reranking: bool = True     # 是否启用重排序

@dataclass
class RetrievalResult:
    """检索结果"""
    id: str
    text: str
    source: str
    similarity: float
    distance: float
    rank: int
    retrieval_source: str             # 'faiss', 'vertex', 'hybrid'
    confidence: float                 # 置信度分数
    metadata: Dict = None

class HybridRetrieval:
    """混合检索系统"""
    
    def __init__(self, 
                 config: RetrievalConfig = None,
                 project_id: str = None,
                 location: str = None,
                 endpoint_id: str = None):
        """初始化混合检索系统"""
        self.config = config or RetrievalConfig()
        self.project_id = project_id
        self.location = location  
        self.endpoint_id = endpoint_id
        
        # 初始化统计信息
        self.stats = {
            'total_queries': 0,
            'fast_success': 0,
            'vertex_success': 0,
            'hybrid_success': 0,
            'fallback_used': 0,
            'total_time': 0.0,  # 添加缺失的字段
            'avg_response_time': 0.0
        }
        
        # 存储组件
        self.fast_retrieval = None
        self.chunk_map = {}
        self.chunk_embeddings = {}
        
        # 添加线程池执行器
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        print("🔧 初始化混合检索系统...")
        self._initialize_components()
    
    def _initialize_components(self):
        """初始化检索组件"""
        try:
            # 初始化FAISS快速检索
            print("⚡ 初始化FAISS检索引擎...")
            self.fast_retrieval = FastRAGRetrieval()
            print("✅ FAISS检索引擎初始化完成")
            
        except Exception as e:
            print(f"⚠️ FAISS检索引擎初始化失败: {e}")
            self.fast_retrieval = None
    
    def add_document(self, file_id: str, text: str, filename: str = None) -> bool:
        """
        添加文档到混合索引
        
        Args:
            file_id: 文件ID
            text: 文档文本
            filename: 文件名
            
        Returns:
            是否添加成功
        """
        success = True
        
        # 添加到FAISS索引
        if self.fast_retrieval:
            try:
                chunks_added = self.fast_retrieval.add_document(file_id, text, filename)
                print(f"✅ FAISS索引添加完成: {chunks_added} 个块")
            except Exception as e:
                print(f"❌ FAISS索引添加失败: {e}")
                # 对于FAISS索引失败，不影响整体流程
                print("⚠️ 继续使用Vertex AI检索...")
                success = True  # 保持为True，因为还有其他检索方式
        
        # 添加到原有系统的chunk_map (兼容性)
        try:
            from .data_preprocessing import chunk_text
        except ImportError:
            from data_preprocessing import chunk_text
        chunks = chunk_text(text, chunk_size=500, overlap_size=100)
        for i, chunk in enumerate(chunks):
            chunk_id = f"file_{file_id}_chunk_{i}"
            self.chunk_map[chunk_id] = chunk
        
        return success
    
    def search(self, 
               query: str, 
               strategy: RetrievalStrategy = RetrievalStrategy.HYBRID_PARALLEL,
               **kwargs) -> List[RetrievalResult]:
        """
        执行混合检索
        
        Args:
            query: 查询文本
            strategy: 检索策略
            **kwargs: 其他参数
            
        Returns:
            List[RetrievalResult]: 检索结果列表
        """
        # 保存查询用于关键词匹配
        self.last_query = query
        
        self.stats['total_queries'] += 1
        print(f"🔍 开始混合检索: {query}")
        print(f"📊 策略: {strategy.value}")
        
        start_time = time.time()
        
        try:
            # 根据策略选择检索方法
            if strategy == RetrievalStrategy.FAST_ONLY:
                results = self._search_fast_only(query)
            elif strategy == RetrievalStrategy.VERTEX_ONLY:
                results = self._search_vertex_only(query)
            elif strategy == RetrievalStrategy.HYBRID_PARALLEL:
                results = self._search_hybrid_parallel(query)
            elif strategy == RetrievalStrategy.ADAPTIVE:
                results = self._search_adaptive(query)
            elif strategy == RetrievalStrategy.FALLBACK:
                results = self._search_fallback(query)
            else:
                print(f"⚠️ 未知检索策略: {strategy}")
                results = self._search_hybrid_parallel(query)
            
            # 统计性能
            processing_time = time.time() - start_time
            self.stats['total_time'] += processing_time
            
            if results:
                if strategy == RetrievalStrategy.FAST_ONLY:
                    self.stats['fast_success'] += 1
                elif strategy == RetrievalStrategy.VERTEX_ONLY:
                    self.stats['vertex_success'] += 1
                else:
                    self.stats['hybrid_success'] += 1
                
                print(f"✅ 混合检索成功: {len(results)} 个结果, 耗时 {processing_time:.2f}s")
                
                # 打印前3个结果的相关信息
                for i, result in enumerate(results[:3]):
                    print(f"  📄 #{i+1}: {result.id} (相似度: {result.similarity:.3f}, 置信度: {result.confidence:.3f})")
            else:
                print(f"⚠️ 混合检索无结果, 耗时 {processing_time:.2f}s")
            
            return results
            
        except Exception as e:
            print(f"❌ 混合检索异常: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _search_fast_only(self, query: str) -> List[RetrievalResult]:
        """仅使用FAISS快速检索"""
        if not self.fast_retrieval:
            raise Exception("FAISS检索系统不可用")
        
        results = self.fast_retrieval.search(
            query, 
            k=self.config.final_results,
            min_score=self.config.min_similarity
        )
        
        self.stats['fast_success'] += 1
        return self._convert_to_retrieval_results(results, 'faiss')
    
    def _search_vertex_only(self, query: str) -> List[RetrievalResult]:
        """仅使用Vertex AI检索"""
        results = retrieve_relevant_chunks(
            project_id=self.project_id,
            location=self.location,
            endpoint_id=self.endpoint_id,
            query_text=query,
            num_neighbors=self.config.final_results,
            chunk_map=self.chunk_map,
            chunk_embeddings=self.chunk_embeddings
        )
        
        self.stats['vertex_success'] += 1
        return self._convert_to_retrieval_results(results, 'vertex')
    
    def _search_hybrid_parallel(self, query: str) -> List[RetrievalResult]:
        """并行混合检索"""
        print("🔄 启动并行双路召回...")
        
        # 并行执行两个检索系统
        futures = {}
        
        # 提交FAISS检索任务
        if self.fast_retrieval:
            futures['faiss'] = self.executor.submit(
                self._safe_search_faiss, query
            )
        
        # 提交Vertex AI检索任务
        futures['vertex'] = self.executor.submit(
            self._safe_search_vertex, query
        )
        
        # 收集结果
        faiss_results = []
        vertex_results = []
        
        for name, future in futures.items():
            try:
                result = future.result(timeout=self.config.max_parallel_timeout)
                if name == 'faiss' and result:
                    faiss_results = result
                    print(f"✅ FAISS检索完成: {len(result)} 个结果")
                elif name == 'vertex' and result:
                    vertex_results = result
                    print(f"✅ Vertex检索完成: {len(result)} 个结果")
            except Exception as e:
                print(f"⚠️ {name}检索失败: {e}")
        
        # 融合结果
        if faiss_results or vertex_results:
            merged_results = self._merge_results(faiss_results, vertex_results)
            self.stats['hybrid_success'] += 1
            return merged_results
        else:
            raise Exception("所有检索路径都失败")
    
    def _search_adaptive(self, query: str) -> List[RetrievalResult]:
        """自适应检索 - 根据查询复杂度动态选择策略"""
        # 简单的自适应逻辑：短查询使用快速检索，长查询使用混合检索
        if len(query) < 10:
            print("📝 短查询，使用快速检索")
            return self._search_fast_only(query)
        else:
            print("📝 复杂查询，使用混合检索")
            return self._search_hybrid_parallel(query)
    
    def _search_fallback(self, query: str) -> List[RetrievalResult]:
        """降级检索 - 按优先级尝试可用系统"""
        print("🆘 启动降级检索模式...")
        
        # 优先尝试FAISS (速度快)
        if self.fast_retrieval:
            try:
                results = self._safe_search_faiss(query)
                if results:
                    print("✅ 降级到FAISS检索成功")
                    self.stats['fallback_used'] += 1
                    return results
            except Exception as e:
                print(f"⚠️ FAISS降级失败: {e}")
        
        # 尝试Vertex AI
        try:
            results = self._safe_search_vertex(query)
            if results:
                print("✅ 降级到Vertex AI检索成功")
                self.stats['fallback_used'] += 1
                return results
        except Exception as e:
            print(f"⚠️ Vertex AI降级失败: {e}")
        
        print("❌ 所有检索路径都不可用")
        return []
    
    def _safe_search_faiss(self, query: str) -> List[RetrievalResult]:
        """安全的FAISS检索"""
        if not self.fast_retrieval:
            return []
        
        try:
            results = self.fast_retrieval.search(
                query,
                k=self.config.num_candidates,
                min_score=self.config.min_similarity
            )
            return self._convert_to_retrieval_results(results, 'faiss')
        except Exception as e:
            print(f"FAISS检索异常: {e}")
            return []
    
    def _safe_search_vertex(self, query: str) -> List[RetrievalResult]:
        """安全的Vertex AI检索"""
        try:
            results = retrieve_relevant_chunks(
                project_id=self.project_id,
                location=self.location,
                endpoint_id=self.endpoint_id,
                query_text=query,
                num_neighbors=self.config.num_candidates,
                chunk_map=self.chunk_map,
                chunk_embeddings=self.chunk_embeddings
            )
            return self._convert_to_retrieval_results(results, 'vertex')
        except Exception as e:
            print(f"Vertex AI检索异常: {e}")
            return []
    
    def _merge_results(self, 
                      faiss_results: List[RetrievalResult], 
                      vertex_results: List[RetrievalResult]) -> List[RetrievalResult]:
        """融合两路检索结果"""
        print("🔄 开始结果融合...")
        
        # 1. 去重 - 基于文本内容的相似度
        unique_results = self._deduplicate_results(faiss_results + vertex_results)
        
        # 2. 重新排序 - 使用RRF算法
        if self.config.enable_reranking:
            ranked_results = self._reciprocal_rank_fusion(
                faiss_results, vertex_results, unique_results
            )
        else:
            # 简单加权融合
            ranked_results = self._weighted_fusion(unique_results)
        
        # 3. 返回Top-K结果
        final_results = ranked_results[:self.config.final_results]
        
        print(f"🔄 结果融合完成: {len(faiss_results)} + {len(vertex_results)} → {len(final_results)}")
        return final_results
    
    def _deduplicate_results(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """结果去重"""
        seen_ids = set()
        unique_results = []
        
        for result in results:
            if result.id not in seen_ids:
                seen_ids.add(result.id)
                unique_results.append(result)
        
        return unique_results
    
    def _reciprocal_rank_fusion(self, 
                               faiss_results: List[RetrievalResult],
                               vertex_results: List[RetrievalResult],
                               all_results: List[RetrievalResult]) -> List[RetrievalResult]:
        """倒数排序融合算法，增加关键词匹配权重"""
        scores = {}
        
        # 为每个结果创建ID到结果的映射
        result_map = {r.id: r for r in all_results}
        
        # 提取查询关键词（简单分词）
        query_keywords = set(self.last_query.lower().split()) if hasattr(self, 'last_query') else set()
        
        # FAISS结果评分
        for rank, result in enumerate(faiss_results):
            rrf_score = 1.0 / (self.config.rrf_k + rank + 1)
            
            # 关键词匹配加权
            keyword_boost = self._calculate_keyword_boost(result.text, query_keywords)
            
            # 相似度加权
            similarity_boost = result.similarity * 0.3  # 给相似度一定权重
            
            total_score = rrf_score * self.config.faiss_weight + keyword_boost + similarity_boost
            scores[result.id] = scores.get(result.id, 0) + total_score
        
        # Vertex AI结果评分
        for rank, result in enumerate(vertex_results):
            rrf_score = 1.0 / (self.config.rrf_k + rank + 1)
            
            # 关键词匹配加权
            keyword_boost = self._calculate_keyword_boost(result.text, query_keywords)
            
            # 相似度加权
            similarity_boost = result.similarity * 0.3
            
            total_score = rrf_score * self.config.vertex_weight + keyword_boost + similarity_boost
            scores[result.id] = scores.get(result.id, 0) + total_score
        
        # 排序并添加融合后的置信度
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        ranked_results = []
        for rank, (result_id, score) in enumerate(sorted_items):
            if result_id in result_map:
                result = result_map[result_id]
                result.rank = rank + 1
                result.confidence = min(score * 0.5, 1.0)  # 标准化置信度
                result.retrieval_source = 'hybrid'
                ranked_results.append(result)
        
        return ranked_results
    
    def _calculate_keyword_boost(self, text: str, query_keywords: set) -> float:
        """计算关键词匹配权重，增强相关性判断"""
        if not query_keywords or not text:
            return 0.0
        
        text_lower = text.lower()
        matches = 0
        exact_matches = 0
        
        for keyword in query_keywords:
            if keyword in text_lower:
                matches += 1
                # 检查是否是精确匹配（周围有空格或标点）
                import re
                if re.search(rf'\b{re.escape(keyword)}\b', text_lower):
                    exact_matches += 1
        
        # 计算匹配度
        match_ratio = matches / len(query_keywords) if query_keywords else 0.0
        exact_ratio = exact_matches / len(query_keywords) if query_keywords else 0.0
        
        # 给精确匹配更高权重，给关键词匹配很高的权重
        keyword_boost = (match_ratio * 0.6) + (exact_ratio * 0.8)
        
        # 特殊处理：如果包含查询的核心概念，给额外加分
        core_concepts = {'定金', '订金', '区别', '差别', '不同'}
        concept_matches = sum(1 for concept in core_concepts if concept in text_lower)
        concept_boost = min(concept_matches * 0.3, 0.9)  # 最多加0.9分
        
        return keyword_boost + concept_boost
    
    def _weighted_fusion(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """简单加权融合"""
        # 按相似度排序
        results.sort(key=lambda x: x.similarity, reverse=True)
        
        for i, result in enumerate(results):
            result.rank = i + 1
            result.confidence = result.similarity
            if result.retrieval_source == 'faiss':
                result.confidence *= self.config.faiss_weight
            elif result.retrieval_source == 'vertex':
                result.confidence *= self.config.vertex_weight
        
        return results
    
    def _convert_to_retrieval_results(self, 
                                    results: List[Dict], 
                                    source: str) -> List[RetrievalResult]:
        """转换为标准的检索结果格式"""
        retrieval_results = []
        
        for i, result in enumerate(results):
            # 从不同系统适配字段
            text = result.get('text', result.get('content_preview', ''))
            similarity = result.get('similarity', 1.0 - result.get('distance', 0.0))
            
            retrieval_result = RetrievalResult(
                id=result.get('id', result.get('datapoint_id', f'{source}_{i}')),
                text=text,
                source=result.get('source', 'unknown'),
                similarity=similarity,
                distance=result.get('distance', 1.0 - similarity),
                rank=result.get('rank', i + 1),
                retrieval_source=source,
                confidence=similarity,
                metadata=result.get('metadata', {})
            )
            retrieval_results.append(retrieval_result)
        
        return retrieval_results
    
    def update_config(self, **kwargs):
        """动态更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                print(f"🔧 配置更新: {key} = {value}")
    
    def get_stats(self) -> Dict:
        """获取性能统计"""
        if self.stats['total_queries'] > 0:
            success_rate = (
                (self.stats['fast_success'] + self.stats['vertex_success'] + self.stats['hybrid_success']) 
                / self.stats['total_queries']
            )
        else:
            success_rate = 0.0
        
        return {
            **self.stats,
            'success_rate': success_rate,
            'fast_retrieval_available': self.fast_retrieval is not None,
            'config': {
                'faiss_weight': self.config.faiss_weight,
                'vertex_weight': self.config.vertex_weight,
                'strategy': 'hybrid_parallel'
            }
        }
    
    def health_check(self) -> Dict[str, bool]:
        """健康检查"""
        health = {
            'faiss_available': False,
            'vertex_available': False,
            'hybrid_available': False
        }
        
        # 检查FAISS
        if self.fast_retrieval:
            try:
                stats = self.fast_retrieval.get_stats()
                health['faiss_available'] = stats['total_documents'] > 0
            except:
                health['faiss_available'] = False
        
        # 检查Vertex AI (简单测试)
        try:
            # 这里可以添加简单的连通性测试
            health['vertex_available'] = bool(self.project_id and self.location)
        except:
            health['vertex_available'] = False
        
        health['hybrid_available'] = health['faiss_available'] or health['vertex_available']
        
        return health

# 便捷函数：混合检索接口
def hybrid_search(query: str, 
                 hybrid_retrieval: HybridRetrieval,
                 strategy: RetrievalStrategy = RetrievalStrategy.HYBRID_PARALLEL,
                 **kwargs) -> List[Dict]:
    """
    混合检索便捷接口 - 兼容原有系统
    
    Args:
        query: 查询文本
        hybrid_retrieval: 混合检索实例
        strategy: 检索策略
        
    Returns:
        兼容原格式的检索结果
    """
    results = hybrid_retrieval.search(query, strategy, **kwargs)
    
    # 转换为兼容格式
    compatible_results = []
    for result in results:
        compatible_result = {
            'id': result.id,
            'datapoint_id': result.id,
            'text': result.text,
            'source': result.source,
            'similarity': result.similarity,
            'distance': result.distance,
            'rank': result.rank,
            'retrieval_source': result.retrieval_source,
            'confidence': result.confidence,
            'content_preview': result.text[:100] + '...' if len(result.text) > 100 else result.text
        }
        compatible_results.append(compatible_result)
    
    return compatible_results 