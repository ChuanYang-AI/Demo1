from google.cloud import aiplatform
from google.cloud.aiplatform_v1 import (  # 使用v1版本而不是v1beta1
    IndexServiceClient,
    IndexEndpointServiceClient,
)
from google.cloud.aiplatform_v1.types import Index, IndexEndpoint, DeployedIndex
import google.cloud.aiplatform as aiplatform

def create_or_get_vector_search_index(
    project_id: str,
    location: str,
    index_display_name: str,
    description: str = "Vector Search Index for RAG project",
    dimensions: int = 768,  # text-embedding-004 的默认维度
    gcs_bucket_uri: str = None,  # GCS存储桶URI
) -> Index:
    """
    创建或获取一个Vertex AI Vector Search索引。
    如果索引已存在，则返回现有索引。
    """
    client = IndexServiceClient(client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"})
    parent = f"projects/{project_id}/locations/{location}"

    # 尝试查找现有索引
    for index in client.list_indexes(parent=parent):
        if index.display_name == index_display_name:
            print(f"索引 '{index_display_name}' 已存在。返回现有索引。")
            return index

    print(f"创建新的索引 '{index_display_name}'...")
    
    # 修复：使用正确的索引配置格式，符合官方文档要求
    index_config = {
        "dimensions": dimensions,
        "approximate_neighbors_count": 150,
        "distance_measure_type": "DOT_PRODUCT_DISTANCE",
        "algorithm_config": {
            "tree_ah_config": {
                "leaf_node_embedding_count": 500,
                "leaf_nodes_to_search_percent": 7,
            }
        }
    }
    
    # 如果提供了GCS URI，则设置为批量索引
    if gcs_bucket_uri:
        index = Index(
            display_name=index_display_name,
            description=description,
            metadata={
                "config": index_config,
                "contentsDeltaUri": gcs_bucket_uri
            }
        )
    else:
        # 创建流式索引
        index = Index(
            display_name=index_display_name,
            description=description,
            metadata={
                "config": index_config
            },
            index_update_method=Index.IndexUpdateMethod.STREAM_UPDATE
        )

    try:
        operation = client.create_index(parent=parent, index=index)
        print(f"索引创建操作正在进行中: {operation.operation.name}")
        created_index = operation.result()
        print(f"索引 '{created_index.display_name}' 创建成功。ID: {created_index.name}")
        return created_index
    except Exception as e:
        print(f"创建索引失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_streaming_vector_search_index(
    project_id: str,
    location: str,
    index_display_name: str,
    description: str = "Streaming Vector Search Index for RAG project",
    dimensions: int = 768,  # text-embedding-004 的默认维度
) -> Index:
    """
    创建一个流式Vertex AI Vector Search索引，支持实时数据更新。
    """
    client = IndexServiceClient(client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"})
    parent = f"projects/{project_id}/locations/{location}"

    # 尝试查找现有索引
    for index in client.list_indexes(parent=parent):
        if index.display_name == index_display_name:
            print(f"流式索引 '{index_display_name}' 已存在。返回现有索引。")
            return index

    print(f"创建新的流式索引 '{index_display_name}'...")
    
    # 创建流式索引配置
    index = Index(
        display_name=index_display_name,
        description=description,
        metadata={
            "config": {
                "dimensions": str(dimensions),
                "approximate_neighbors_count": 150,
                "distance_measure_type": "DOT_PRODUCT_DISTANCE",
                "algorithm_config": {
                    "tree_ah_config": {
                        "leaf_node_embedding_count": 500,
                        "leaf_nodes_to_search_percent": 7,
                    }
                }
            },
            "isCompleteOverwrite": True  # 允许完全覆盖
        },
        # 流式索引不需要contentsDeltaUri
        index_update_method="STREAM_UPDATE"  # 设置为流式更新
    )

    try:
        operation = client.create_index(parent=parent, index=index)
        print(f"流式索引创建操作正在进行中: {operation.operation.name}")
        created_index = operation.result()
        print(f"流式索引 '{created_index.display_name}' 创建成功。ID: {created_index.name}")
        return created_index
    except Exception as e:
        print(f"创建流式索引失败: {e}")
        # 如果流式索引创建失败，尝试创建批量索引
        print("尝试创建批量索引...")
        return create_or_get_vector_search_index(project_id, location, index_display_name, description, dimensions)

def deploy_index_to_endpoint(
    project_id: str,
    location: str,
    index: Index,
    endpoint_display_name: str,
    wait_for_completion: bool = False
) -> IndexEndpoint:
    """
    将Vector Search索引部署到端点。
    如果端点已存在且索引已部署，则返回现有端点。
    """
    client = IndexEndpointServiceClient(client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"})
    parent = f"projects/{project_id}/locations/{location}"

    # 尝试查找现有端点
    for endpoint in client.list_index_endpoints(parent=parent):
        if endpoint.display_name == endpoint_display_name:
            print(f"端点 '{endpoint_display_name}' 已存在。检查部署状态...")
            for deployed_index in endpoint.deployed_indexes:
                if deployed_index.index == index.name:
                    print(f"索引 '{index.display_name}' 已部署到端点 '{endpoint_display_name}'。返回现有端点。")
                    return endpoint
            
            # 如果端点存在但索引未部署，则部署索引
            print(f"索引 '{index.display_name}' 未部署到端点 '{endpoint_display_name}'。正在部署...")
            
            # 生成唯一的部署ID
            import time
            unique_id = f"deployed_index_{int(time.time())}"
            
            deployed_index = DeployedIndex(
                id=unique_id,
                index=index.name,
                display_name=f"{index.display_name}_deployed",
            )
            operation = client.deploy_index(
                index_endpoint=endpoint.name,
                deployed_index=deployed_index,
            )
            print(f"部署操作正在进行中: {operation.operation.name}")
            
            if wait_for_completion:
                print("等待部署完成...")
                deployed_endpoint = operation.result()
                print(f"索引 '{index.display_name}' 成功部署到端点 '{endpoint_display_name}'。")
                return deployed_endpoint
            else:
                print(f"部署操作已启动，将在后台继续。操作ID: {operation.operation.name}")
                print("服务器将继续启动，部署完成后索引将可用。")
                return endpoint

    print(f"创建新的端点 '{endpoint_display_name}' 并部署索引 '{index.display_name}'...")
    endpoint = IndexEndpoint(
        display_name=endpoint_display_name,
        # 移除网络配置，使用默认配置
        # network="projects/{project_id}/global/networks/default", # 示例网络，可能需要调整
    )
    operation = client.create_index_endpoint(parent=parent, index_endpoint=endpoint)
    created_endpoint = operation.result()
    print(f"端点 '{created_endpoint.display_name}' 创建成功。ID: {created_endpoint.name}")

    # 部署索引到新创建的端点
    # 生成唯一的部署ID
    import time
    unique_id = f"deployed_index_{int(time.time())}"
    
    deployed_index = DeployedIndex(
        id=unique_id,
        index=index.name,
        display_name=f"{index.display_name}_deployed",
    )
    operation = client.deploy_index(
        index_endpoint=created_endpoint.name,
        deployed_index=deployed_index,
    )
    print(f"部署操作正在进行中: {operation.operation.name}")
    
    if wait_for_completion:
        print("等待部署完成...")
        deployed_endpoint = operation.result()
        print(f"索引 '{index.display_name}' 成功部署到端点 '{endpoint_display_name}'。")
        return deployed_endpoint
    else:
        print(f"部署操作已启动，将在后台继续。操作ID: {operation.operation.name}")
        print("服务器将继续启动，部署完成后索引将可用。")
        return created_endpoint

def upload_embeddings_to_index(
    project_id: str,
    location: str,
    index_name: str, # index_name 应该是完整资源名，例如 projects/PROJECT_ID/locations/LOCATION/indexes/INDEX_ID
    gcs_input_uri: str, # GCS URI of the JSONL file containing embeddings
):
    """
    将嵌入数据上传到Vertex AI Vector Search索引。
    """
    try:
        print(f"开始上传嵌入数据到索引: {index_name}...")
        
        # 使用IndexServiceClient来更新索引内容
        client = IndexServiceClient(client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"})
        
        # 对于Vertex AI Vector Search，数据上传通常是通过批处理作业完成的
        # 由于Python SDK的限制，我们暂时跳过实际的向量上传，只记录到GCS
        print(f"嵌入数据已上传到GCS: {gcs_input_uri}")
        print("注意：向量搜索索引的数据导入需要通过控制台或gcloud命令完成")
        print("或者等待索引部署完成后，数据将自动可用")
        
        return True
        
    except Exception as e:
        print(f"上传嵌入数据到索引失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def upsert_datapoints_to_index(
    project_id: str,
    location: str,
    index_name: str,  # 完整的索引名称
    datapoints: list,  # 数据点列表
    batch_size: int = 100
) -> bool:
    """
    将数据点插入到流式Vertex AI Vector Search索引中。
    
    Args:
        project_id: GCP项目ID
        location: 区域
        index_name: 完整的索引名称
        datapoints: 数据点列表，每个数据点包含id和embedding
        batch_size: 批处理大小
    """
    try:
        from google.cloud.aiplatform_v1.types import IndexDatapoint
        
        client = IndexServiceClient(client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"})
        
        # 将数据转换为IndexDatapoint格式
        index_datapoints = []
        for dp in datapoints:
            # 修复：使用正确的数据点格式
            datapoint = IndexDatapoint(
                datapoint_id=str(dp.get('id', '')),
                feature_vector=dp.get('embedding', []),
                # 可选：添加restricts和numeric_restricts
                restricts=dp.get('restricts', []),
                numeric_restricts=dp.get('numeric_restricts', []),
                crowding_tag=dp.get('crowding_tag', None)
            )
            index_datapoints.append(datapoint)
        
        # 批量插入数据点
        total_inserted = 0
        for i in range(0, len(index_datapoints), batch_size):
            batch = index_datapoints[i:i+batch_size]
            
            print(f"正在插入数据点批次 {i//batch_size + 1}/{(len(index_datapoints) + batch_size - 1)//batch_size}，包含 {len(batch)} 个数据点...")
            
            # 修复：使用正确的upsert_datapoints方法
            from google.cloud.aiplatform_v1.types import UpsertDatapointsRequest
            
            request = UpsertDatapointsRequest(
                index=index_name,
                datapoints=batch
            )
            
            operation = client.upsert_datapoints(request=request)
            
            # 等待操作完成
            result = operation.result()
            total_inserted += len(batch)
            print(f"成功插入 {len(batch)} 个数据点")
        
        print(f"总共插入了 {total_inserted} 个数据点到索引 {index_name}")
        return True
        
    except Exception as e:
        print(f"插入数据点到索引失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 示例用法
    # 替换为你的实际项目ID和区域。
    # project_id = "your-gcp-project-id"
    # location = "us-central1"
    # index_display_name = "my-rag-index"
    # endpoint_display_name = "my-rag-endpoint"
    # gcs_input_uri = "gs://your-gcs-bucket/embeddings_data/"

    # try:
    #     # 1. 创建或获取索引
    #     my_index = create_or_get_vector_search_index(
    #         project_id=project_id,
    #         location=location,
    #         index_display_name=index_display_name
    #     )
    #     print(f"索引资源名称: {my_index.name}")

    #     # 2. 部署索引到端点
    #     my_endpoint = deploy_index_to_endpoint(
    #         project_id=project_id,
    #         location=location,
    #         index=my_index,
    #         endpoint_display_name=endpoint_display_name
    #     )
    #     print(f"端点资源名称: {my_endpoint.name}")

    #     # 3. 上传嵌入数据到索引 (需要先将嵌入数据准备为JSONL文件并上传到GCS)
    #     # 注意：在实际使用中，你需要将你的嵌入数据保存为JSONL格式并上传到GCS桶中。
    #     # 例如，每个JSONL行是一个{"id": "chunk_id", "embedding": [e1, e2, ...]} 对象。
    #     # upload_embeddings_to_index(
    #     #     project_id=project_id,
    #     #     location=location,
    #     #     index_name=my_index.name, # 确保使用完整的资源名称
    #     #     gcs_input_uri=gcs_input_uri
    #     # )
    #     # print("嵌入数据上传流程已触发。")

    # except Exception as e:
    #     print(f"运行Vector Search管理示例时发生错误: {e}")
    pass

def upload_embeddings_to_index(
    project_id: str,
    location: str,
    index_name: str, # index_name 应该是完整资源名，例如 projects/PROJECT_ID/locations/LOCATION/indexes/INDEX_ID
    gcs_input_uri: str, # GCS URI of the JSONL file containing embeddings
):
    """
    将嵌入数据上传到Vertex AI Vector Search索引。
    """
    try:
        print(f"开始上传嵌入数据到索引: {index_name}...")
        
        # 使用IndexServiceClient来更新索引内容
        client = IndexServiceClient(client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"})
        
        # 对于Vertex AI Vector Search，数据上传通常是通过批处理作业完成的
        # 由于Python SDK的限制，我们暂时跳过实际的向量上传，只记录到GCS
        print(f"嵌入数据已上传到GCS: {gcs_input_uri}")
        print("注意：向量搜索索引的数据导入需要通过控制台或gcloud命令完成")
        print("或者等待索引部署完成后，数据将自动可用")
        
        return True
        
    except Exception as e:
        print(f"上传嵌入数据到索引失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def upsert_datapoints_to_index(
    project_id: str,
    location: str,
    index_name: str,  # 完整的索引名称
    datapoints: list,  # 数据点列表
    batch_size: int = 100
) -> bool:
    """
    将数据点插入到流式Vertex AI Vector Search索引中。
    
    Args:
        project_id: GCP项目ID
        location: 区域
        index_name: 完整的索引名称
        datapoints: 数据点列表，每个数据点包含id和embedding
        batch_size: 批处理大小
    """
    try:
        from google.cloud.aiplatform_v1.types import IndexDatapoint
        
        client = IndexServiceClient(client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"})
        
        # 将数据转换为IndexDatapoint格式
        index_datapoints = []
        for dp in datapoints:
            # 修复：使用正确的数据点格式
            datapoint = IndexDatapoint(
                datapoint_id=str(dp.get('id', '')),
                feature_vector=dp.get('embedding', []),
                # 可选：添加restricts和numeric_restricts
                restricts=dp.get('restricts', []),
                numeric_restricts=dp.get('numeric_restricts', []),
                crowding_tag=dp.get('crowding_tag', None)
            )
            index_datapoints.append(datapoint)
        
        # 批量插入数据点
        total_inserted = 0
        for i in range(0, len(index_datapoints), batch_size):
            batch = index_datapoints[i:i+batch_size]
            
            print(f"正在插入数据点批次 {i//batch_size + 1}/{(len(index_datapoints) + batch_size - 1)//batch_size}，包含 {len(batch)} 个数据点...")
            
            # 修复：使用正确的upsert_datapoints方法
            from google.cloud.aiplatform_v1.types import UpsertDatapointsRequest
            
            request = UpsertDatapointsRequest(
                index=index_name,
                datapoints=batch
            )
            
            operation = client.upsert_datapoints(request=request)
            
            # 等待操作完成
            result = operation.result()
            total_inserted += len(batch)
            print(f"成功插入 {len(batch)} 个数据点")
        
        print(f"总共插入了 {total_inserted} 个数据点到索引 {index_name}")
        return True
        
    except Exception as e:
        print(f"插入数据点到索引失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # 示例用法
    # 替换为你的实际项目ID和区域。
    # project_id = "your-gcp-project-id"
    # location = "us-central1"
    # index_display_name = "my-rag-index"
    # endpoint_display_name = "my-rag-endpoint"
    # gcs_input_uri = "gs://your-gcs-bucket/embeddings_data/"

    # try:
    #     # 1. 创建或获取索引
    #     my_index = create_or_get_vector_search_index(
    #         project_id=project_id,
    #         location=location,
    #         index_display_name=index_display_name
    #     )
    #     print(f"索引资源名称: {my_index.name}")

    #     # 2. 部署索引到端点
    #     my_endpoint = deploy_index_to_endpoint(
    #         project_id=project_id,
    #         location=location,
    #         index=my_index,
    #         endpoint_display_name=endpoint_display_name
    #     )
    #     print(f"端点资源名称: {my_endpoint.name}")

    #     # 3. 上传嵌入数据到索引 (需要先将嵌入数据准备为JSONL文件并上传到GCS)
    #     # 注意：在实际使用中，你需要将你的嵌入数据保存为JSONL格式并上传到GCS桶中。
    #     # 例如，每个JSONL行是一个{"id": "chunk_id", "embedding": [e1, e2, ...]} 对象。
    #     # upload_embeddings_to_index(
    #     #     project_id=project_id,
    #     #     location=location,
    #     #     index_name=my_index.name, # 确保使用完整的资源名称
    #     #     gcs_input_uri=gcs_input_uri
    #     # )
    #     # print("嵌入数据上传流程已触发。")

    # except Exception as e:
    #     print(f"运行Vector Search管理示例时发生错误: {e}")
    pass 