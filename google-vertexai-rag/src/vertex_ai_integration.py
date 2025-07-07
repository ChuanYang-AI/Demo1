#!/usr/bin/env python3
"""
Vertex AI Vector Search完整集成模块
整合embedding生成、索引管理、数据插入和检索功能
"""
import os
import json
import time
from typing import List, Dict, Any, Optional
from src.embedding_generation import initialize_vertex_ai, get_text_embeddings
from src.vector_search_management import (
    create_or_get_vector_search_index,
    deploy_index_to_endpoint,
    upsert_datapoints_to_index
)
from src.vector_data_formatter import VectorDataFormatter
from src.rag_retrieval import vertex_ai_vector_search

class VertexAIVectorSearchManager:
    """
    Vertex AI Vector Search管理器
    提供完整的向量搜索功能
    """
    
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.formatter = VectorDataFormatter()
        self.index = None
        self.endpoint = None
        
        # 初始化Vertex AI
        initialize_vertex_ai(project_id, location)
        
    def setup_vector_search(self, 
                           index_name: str,
                           endpoint_name: str,
                           dimensions: int = 768,
                           gcs_bucket_uri: Optional[str] = None) -> bool:
        """
        设置向量搜索环境（索引和端点）
        
        Args:
            index_name: 索引名称
            endpoint_name: 端点名称
            dimensions: 向量维度
            gcs_bucket_uri: GCS存储桶URI（可选）
            
        Returns:
            是否设置成功
        """
        try:
            print(f"正在设置Vertex AI Vector Search环境...")
            
            # 1. 创建或获取索引
            print(f"创建或获取索引: {index_name}")
            self.index = create_or_get_vector_search_index(
                project_id=self.project_id,
                location=self.location,
                index_display_name=index_name,
                dimensions=dimensions,
                gcs_bucket_uri=gcs_bucket_uri
            )
            
            if not self.index:
                print("❌ 索引创建失败")
                return False
            
            print(f"✅ 索引设置成功: {self.index.name}")
            
            # 2. 部署索引到端点
            print(f"部署索引到端点: {endpoint_name}")
            self.endpoint = deploy_index_to_endpoint(
                project_id=self.project_id,
                location=self.location,
                index=self.index,
                endpoint_display_name=endpoint_name,
                wait_for_completion=False  # 异步部署
            )
            
            if not self.endpoint:
                print("❌ 端点部署失败")
                return False
                
            print(f"✅ 端点设置成功: {self.endpoint.name}")
            return True
            
        except Exception as e:
            print(f"❌ 设置向量搜索环境失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def add_documents_to_index(self, documents: List[Dict[str, Any]]) -> bool:
        """
        将文档添加到向量索引
        
        Args:
            documents: 文档列表，每个文档包含：
                - id: 文档ID
                - text: 文档文本
                - metadata: 元数据（可选）
                
        Returns:
            是否添加成功
        """
        try:
            if not self.index:
                print("❌ 索引未初始化")
                return False
            
            print(f"正在处理 {len(documents)} 个文档...")
            
            # 1. 生成embedding
            texts = [doc['text'] for doc in documents]
            embeddings = get_text_embeddings(texts)
            
            if not embeddings or len(embeddings) != len(documents):
                print("❌ Embedding生成失败")
                return False
            
            # 2. 格式化数据点
            datapoints = []
            for i, doc in enumerate(documents):
                datapoint = {
                    'id': str(doc['id']),
                    'embedding': embeddings[i]
                }
                
                # 添加元数据作为限制条件
                if 'metadata' in doc and doc['metadata']:
                    metadata = doc['metadata']
                    restricts = []
                    numeric_restricts = []
                    
                    for key, value in metadata.items():
                        if isinstance(value, str):
                            restricts.append({
                                "namespace": key,
                                "allow": [value]
                            })
                        elif isinstance(value, (int, float)):
                            if isinstance(value, int):
                                numeric_restricts.append({
                                    "namespace": key,
                                    "value_int": value
                                })
                            else:
                                numeric_restricts.append({
                                    "namespace": key,
                                    "value_float": value
                                })
                    
                    if restricts:
                        datapoint['restricts'] = restricts
                    if numeric_restricts:
                        datapoint['numeric_restricts'] = numeric_restricts
                
                datapoints.append(datapoint)
            
            # 3. 插入到索引
            success = upsert_datapoints_to_index(
                project_id=self.project_id,
                location=self.location,
                index_name=self.index.name,
                datapoints=datapoints
            )
            
            if success:
                print(f"✅ 成功添加 {len(documents)} 个文档到索引")
            else:
                print("❌ 文档添加失败")
                
            return success
            
        except Exception as e:
            print(f"❌ 添加文档到索引失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def search_similar_documents(self, 
                                query_text: str, 
                                num_results: int = 5,
                                filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        搜索相似文档
        
        Args:
            query_text: 查询文本
            num_results: 返回结果数量
            filters: 过滤条件（可选）
            
        Returns:
            相似文档列表
        """
        try:
            if not self.endpoint:
                print("❌ 端点未初始化")
                return []
            
            # 提取端点ID
            endpoint_id = self.endpoint.name.split('/')[-1]
            
            # 生成查询embedding
            query_embeddings = get_text_embeddings([query_text])
            if not query_embeddings or not query_embeddings[0]:
                print("❌ 查询embedding生成失败")
                return []
            
            # 执行向量搜索
            results = vertex_ai_vector_search(
                project_id=self.project_id,
                location=self.location,
                endpoint_id=endpoint_id,
                query_embedding=query_embeddings[0],
                num_neighbors=num_results
            )
            
            return results
            
        except Exception as e:
            print(f"❌ 搜索相似文档失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def export_data_for_batch_import(self, 
                                   documents: List[Dict[str, Any]], 
                                   output_file: str,
                                   format_type: str = 'jsonl') -> bool:
        """
        导出数据用于批量导入
        
        Args:
            documents: 文档列表
            output_file: 输出文件路径
            format_type: 格式类型 ('jsonl' 或 'csv')
            
        Returns:
            是否导出成功
        """
        try:
            # 生成embedding
            texts = [doc['text'] for doc in documents]
            embeddings = get_text_embeddings(texts)
            
            if not embeddings or len(embeddings) != len(documents):
                print("❌ Embedding生成失败")
                return False
            
            # 格式化数据
            datapoints = []
            for i, doc in enumerate(documents):
                datapoint = {
                    'id': str(doc['id']),
                    'embedding': embeddings[i]
                }
                
                # 添加元数据
                if 'metadata' in doc:
                    datapoint.update(doc['metadata'])
                
                datapoints.append(datapoint)
            
            # 使用格式化器转换数据
            formatted_data = self.formatter.create_sample_data(datapoints)
            
            # 保存到文件
            return self.formatter.save_to_file(formatted_data, output_file, format_type)
            
        except Exception as e:
            print(f"❌ 导出数据失败: {e}")
            import traceback
            traceback.print_exc()
            return False

def example_usage():
    """使用示例"""
    # 配置信息
    PROJECT_ID = "cy-aispeci-demo"  # 替换为你的项目ID
    LOCATION = "us-central1"
    INDEX_NAME = "rag-legal-index"
    ENDPOINT_NAME = "rag-legal-endpoint"
    
    # 创建管理器
    manager = VertexAIVectorSearchManager(PROJECT_ID, LOCATION)
    
    # 设置向量搜索环境
    success = manager.setup_vector_search(INDEX_NAME, ENDPOINT_NAME)
    if not success:
        print("❌ 向量搜索环境设置失败")
        return
    
    # 示例文档
    documents = [
        {
            "id": "legal_doc_1",
            "text": "定金是指当事人约定由一方向对方给付的，作为债权担保的一定数额的货币。",
            "metadata": {
                "category": "legal",
                "type": "definition",
                "priority": 1
            }
        },
        {
            "id": "legal_doc_2", 
            "text": "盗窃罪是指以非法占有为目的，秘密窃取公私财物数额较大或者多次盗窃的行为。",
            "metadata": {
                "category": "legal",
                "type": "crime_definition",
                "priority": 2
            }
        }
    ]
    
    # 添加文档到索引
    success = manager.add_documents_to_index(documents)
    if success:
        print("✅ 文档添加成功")
        
        # 搜索相似文档
        results = manager.search_similar_documents("什么是定金？", num_results=3)
        print(f"搜索结果: {results}")
    else:
        print("❌ 文档添加失败")

if __name__ == "__main__":
    example_usage() 
 
 
 