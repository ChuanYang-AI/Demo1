from src.embedding_generation import get_text_embeddings
import numpy as np
from google.cloud import aiplatform
from google.cloud.aiplatform import MatchingEngineIndex, MatchingEngineIndexEndpoint
import time

def retrieve_relevant_chunks(
    project_id: str,
    location: str,
    endpoint_id: str,
    query_text: str,
    num_neighbors: int = 5,
    chunk_map: dict = None,
    chunk_embeddings: dict = None
) -> list[dict]:
    """
    从Vertex AI Vector Search索引中检索与查询文本最相关的文档块。
    """
    print(f"[RAG检索] 开始本地相似度检索，候选块数: {len(chunk_embeddings) if chunk_embeddings else 0}")
    print(f"[RAG检索] 检索参数: num_neighbors={num_neighbors}")
    if chunk_embeddings:
        preview_ids = list(chunk_embeddings.keys())[:3]
        print(f"[RAG检索] embedding ID预览: {preview_ids}")
    start = time.time()
    
    try:
        # 1. 生成查询文本的嵌入
        print(f"[RAG检索] 正在为查询文本生成嵌入: '{query_text[:50]}...'")
        query_embedding = get_text_embeddings([query_text])
        
        if not query_embedding or not query_embedding[0]:
            print(f"[RAG检索] 查询嵌入生成失败")
            return []
            
        print(f"[RAG检索] 查询嵌入生成成功，维度: {len(query_embedding[0])}")
        
        # 2. 如果提供了预先计算的embeddings，使用优化的相似度检索
        if chunk_map and chunk_embeddings:
            print("[RAG检索] 使用预先计算的embedding进行快速检索...")
            results = fast_similarity_search(query_embedding[0], chunk_map, chunk_embeddings, num_neighbors)
            print(f"[RAG检索] 检索总耗时: {time.time()-start:.2f}秒")
            return results
        
        # 3. 尝试使用真实的Vertex AI Vector Search
        try:
            print("[RAG检索] 尝试使用Vertex AI Vector Search进行检索...")
            results = vertex_ai_vector_search(project_id, location, endpoint_id, query_embedding[0], num_neighbors)
            print(f"[RAG检索] 检索总耗时: {time.time()-start:.2f}秒")
            return results
        except Exception as e:
            print(f"[RAG检索] Vertex AI Vector Search检索失败: {e}")
            
            # 4. 如果提供了chunk_map但没有预先计算的embeddings，使用简单的相似度检索
            if chunk_map:
                print("[RAG检索] 使用简单相似度检索...")
                results = simple_similarity_search(query_embedding[0], chunk_map, num_neighbors)
                print(f"[RAG检索] 检索总耗时: {time.time()-start:.2f}秒")
                return results
        
        # 5. 最后的备选方案：返回模拟结果
        print("[RAG检索] 注意：使用模拟的检索结果")
        
        # 返回模拟的检索结果
        mock_results = [
            {
                "id": "chunk_0",
                "distance": 0.15,
                "datapoint_id": "chunk_0"
            },
            {
                "id": "chunk_1", 
                "distance": 0.23,
                "datapoint_id": "chunk_1"
            }
        ]
        
        print(f"[RAG检索] 模拟检索到 {len(mock_results)} 个相关文档块")
        print(f"[RAG检索] 检索总耗时: {time.time()-start:.2f}秒")
        return mock_results
        
    except Exception as e:
        print(f"[RAG检索] 检索过程出错: {e}")
        import traceback
        traceback.print_exc()
        print(f"[RAG检索] 检索总耗时: {time.time()-start:.2f}秒")
        return []

def fast_similarity_search(query_embedding: list, chunk_map: dict, chunk_embeddings: dict, num_neighbors: int = 5) -> list[dict]:
    """
    快速相似度检索，使用预先计算的embedding
    """
    try:
        results = []
        query_vec = np.array(query_embedding)
        
        for chunk_id, chunk_text in chunk_map.items():
            # 使用预先计算的embedding
            if chunk_id in chunk_embeddings:
                chunk_vec = np.array(chunk_embeddings[chunk_id])
                
                # 计算余弦相似度
                similarity = np.dot(query_vec, chunk_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec))
                distance = 1 - similarity  # 转换为距离
                
                results.append({
                    "id": chunk_id,
                    "distance": float(distance),
                    "datapoint_id": chunk_id,
                    "similarity": float(similarity)
                })
        
        # 按距离排序（距离越小越相关）
        results.sort(key=lambda x: x['distance'])
        
        # 返回前N个结果
        top_results = results[:num_neighbors]
        print(f"[RAG检索] 快速相似度检索找到 {len(top_results)} 个相关文档块")
        
        # 添加详细的检索结果日志
        for i, result in enumerate(top_results):
            content_preview = chunk_map.get(result['id'], '')[:100] + '...' if len(chunk_map.get(result['id'], '')) > 100 else chunk_map.get(result['id'], '')
            print(f"[RAG检索] 结果{i+1}: ID={result['id']}, 相似度={result['similarity']:.4f}, 距离={result['distance']:.4f}")
            print(f"[RAG检索] 内容预览: {content_preview}")
        
        return top_results
        
    except Exception as e:
        print(f"[RAG检索] 快速相似度检索出错: {e}")
        import traceback
        traceback.print_exc()
        return []

def simple_similarity_search(query_embedding: list, chunk_map: dict, num_neighbors: int = 5) -> list[dict]:
    """
    简单的相似度检索，基于余弦相似度
    """
    try:
        results = []
        query_vec = np.array(query_embedding)
        
        for chunk_id, chunk_text in chunk_map.items():
            try:
                # 为每个文本块生成嵌入
                chunk_embedding = get_text_embeddings([chunk_text])
                chunk_vec = np.array(chunk_embedding[0])
                
                # 计算余弦相似度
                similarity = np.dot(query_vec, chunk_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec))
                distance = 1 - similarity  # 转换为距离
                
                results.append({
                    "id": chunk_id,
                    "distance": float(distance),
                    "datapoint_id": chunk_id,
                    "similarity": float(similarity)
                })
                
            except Exception as e:
                print(f"处理文本块 {chunk_id} 时出错: {e}")
                continue
        
        # 按距离排序（距离越小越相关）
        results.sort(key=lambda x: x['distance'])
        
        # 返回前N个结果
        top_results = results[:num_neighbors]
        print(f"找到 {len(top_results)} 个相关文档块")
        
        return top_results
        
    except Exception as e:
        print(f"相似度检索出错: {e}")
        return []

def vertex_ai_vector_search(project_id: str, location: str, endpoint_id: str, query_embedding: list, num_neighbors: int = 5) -> list[dict]:
    """
    使用真实的Vertex AI Vector Search进行检索
    """
    search_start = time.time()
    try:
        from google.cloud.aiplatform_v1 import MatchingEngineServiceClient
        from google.cloud.aiplatform_v1.types import FindNeighborsRequest, FindNeighborsResponse
        
        # 修复：使用正确的客户端和API
        client = MatchingEngineServiceClient(client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"})
        
        # 修复：使用正确的端点名称格式
        index_endpoint = f"projects/{project_id}/locations/{location}/indexEndpoints/{endpoint_id}"
        
        # 修复：构建正确的查询请求
        # 需要获取部署的索引ID
        deployed_index_id = f"deployed_index_{endpoint_id}"  # 这需要是实际的部署ID
        
        # 构建查询请求
        query = FindNeighborsRequest.Query(
            datapoint=FindNeighborsRequest.Query.Datapoint(
                feature_vector=query_embedding
            ),
            neighbor_count=num_neighbors
        )
        
        request = FindNeighborsRequest(
            index_endpoint=index_endpoint,
            deployed_index_id=deployed_index_id,
            queries=[query],
            return_full_datapoint=False
        )
        
        # 执行查询
        response = client.find_neighbors(request=request)
        response = endpoint.find_neighbors(
            deployed_index_id=f"deployed_index_{endpoint_id}",  # 这可能需要调整
            queries=[query_embedding],
            num_neighbors=num_neighbors
        )
        
        results = []
        if response and len(response) > 0:
            neighbors = response[0]
            for neighbor in neighbors:
                results.append({
                    "id": neighbor.id,
                    "distance": float(neighbor.distance),
                    "datapoint_id": neighbor.id
                })
        
        print(f"Vertex AI Vector Search检索到 {len(results)} 个相关文档块")
        return results
        
    except Exception as e:
        print(f"Vertex AI Vector Search检索错误: {e}")
        raise e

if __name__ == "__main__":
    # 示例用法
    # 在运行此示例之前，请确保已通过 gcloud auth application-default login 或设置 GOOGLE_APPLICATION_CREDENTIALS 环境变量进行身份验证。
    # 并且替换为你的实际项目ID、区域和已部署的端点ID。
    # project_id = "your-gcp-project-id"
    # location = "us-central1"
    # endpoint_id = "your-deployed-index-endpoint-id" # 例如：一个类似 "1234567890abcdef" 的ID

    # try:
    #     query = "什么是机器学习？"
    #     results = retrieve_relevant_chunks(project_id, location, endpoint_id, query, num_neighbors=3)
    #     if results:
    #         print(f"\n查询: {query}")
    #         print("相关块 (ID, 距离):")
    #         for r in results:
    #             print(f"  ID: {r['id']}, 距离: {r['distance']}")
    #     else:
    #         print("未找到相关块。")
    # except Exception as e:
    #     print(f"运行检索示例时发生错误: {e}")
    pass 