#!/usr/bin/env python3
"""
Vertex AI Vector Search数据格式处理模块
根据官方文档格式化数据：https://cloud.google.com/vertex-ai/docs/vector-search/setup/format-structure
"""
import json
import csv
import io
from typing import List, Dict, Any, Optional

class VectorDataFormatter:
    """
    Vertex AI Vector Search数据格式处理器
    支持JSONL、CSV、Avro格式
    """
    
    def __init__(self):
        self.supported_formats = ['jsonl', 'csv', 'avro']
    
    def format_to_jsonl(self, data_points: List[Dict[str, Any]]) -> str:
        """
        将数据点格式化为JSONL格式
        
        Args:
            data_points: 数据点列表，每个数据点包含：
                - id: 唯一标识符
                - embedding: 密集向量 (可选)
                - sparse_embedding: 稀疏向量 (可选)
                - restricts: 限制条件 (可选)
                - numeric_restricts: 数值限制 (可选)
                - crowding_tag: 聚类标签 (可选)
        
        Returns:
            JSONL格式的字符串
        """
        jsonl_lines = []
        
        for dp in data_points:
            # 基本字段验证
            if 'id' not in dp:
                raise ValueError("每个数据点必须包含'id'字段")
            
            # 构建符合官方格式的数据点
            formatted_dp = {
                "id": str(dp['id'])
            }
            
            # 密集向量
            if 'embedding' in dp and dp['embedding']:
                formatted_dp["embedding"] = dp['embedding']
            
            # 稀疏向量
            if 'sparse_embedding' in dp and dp['sparse_embedding']:
                sparse_emb = dp['sparse_embedding']
                if 'values' in sparse_emb and 'dimensions' in sparse_emb:
                    formatted_dp["sparse_embedding"] = {
                        "values": sparse_emb['values'],
                        "dimensions": sparse_emb['dimensions']
                    }
            
            # 限制条件
            if 'restricts' in dp and dp['restricts']:
                restricts = []
                for restrict in dp['restricts']:
                    restrict_obj = {"namespace": restrict['namespace']}
                    if 'allow' in restrict:
                        restrict_obj["allow"] = restrict['allow']
                    if 'deny' in restrict:
                        restrict_obj["deny"] = restrict['deny']
                    restricts.append(restrict_obj)
                formatted_dp["restricts"] = restricts
            
            # 数值限制
            if 'numeric_restricts' in dp and dp['numeric_restricts']:
                numeric_restricts = []
                for num_restrict in dp['numeric_restricts']:
                    num_restrict_obj = {"namespace": num_restrict['namespace']}
                    if 'value_int' in num_restrict:
                        num_restrict_obj["value_int"] = num_restrict['value_int']
                    elif 'value_float' in num_restrict:
                        num_restrict_obj["value_float"] = num_restrict['value_float']
                    elif 'value_double' in num_restrict:
                        num_restrict_obj["value_double"] = num_restrict['value_double']
                    numeric_restricts.append(num_restrict_obj)
                formatted_dp["numeric_restricts"] = numeric_restricts
            
            # 聚类标签
            if 'crowding_tag' in dp and dp['crowding_tag']:
                formatted_dp["crowding_tag"] = str(dp['crowding_tag'])
            
            jsonl_lines.append(json.dumps(formatted_dp, ensure_ascii=False))
        
        return '\n'.join(jsonl_lines)
    
    def format_to_csv(self, data_points: List[Dict[str, Any]]) -> str:
        """
        将数据点格式化为CSV格式
        格式：ID,N feature vector values,dimension:value sparse values,name=value lists
        """
        csv_lines = []
        
        for dp in data_points:
            if 'id' not in dp:
                raise ValueError("每个数据点必须包含'id'字段")
            
            line_parts = [str(dp['id'])]
            
            # 密集向量
            if 'embedding' in dp and dp['embedding']:
                line_parts.extend([str(float(v)) for v in dp['embedding']])
            
            # 稀疏向量
            if 'sparse_embedding' in dp and dp['sparse_embedding']:
                sparse_emb = dp['sparse_embedding']
                if 'values' in sparse_emb and 'dimensions' in sparse_emb:
                    for dim, val in zip(sparse_emb['dimensions'], sparse_emb['values']):
                        line_parts.append(f"{dim}:{val}")
            
            # 聚类标签
            if 'crowding_tag' in dp and dp['crowding_tag']:
                line_parts.append(f"crowding_tag={dp['crowding_tag']}")
            
            # 限制条件
            if 'restricts' in dp and dp['restricts']:
                for restrict in dp['restricts']:
                    namespace = restrict['namespace']
                    if 'allow' in restrict:
                        for allow_val in restrict['allow']:
                            line_parts.append(f"{namespace}={allow_val}")
                    if 'deny' in restrict:
                        for deny_val in restrict['deny']:
                            line_parts.append(f"{namespace}=!{deny_val}")
            
            # 数值限制
            if 'numeric_restricts' in dp and dp['numeric_restricts']:
                for num_restrict in dp['numeric_restricts']:
                    namespace = num_restrict['namespace']
                    if 'value_int' in num_restrict:
                        line_parts.append(f"#{namespace}={num_restrict['value_int']}i")
                    elif 'value_float' in num_restrict:
                        line_parts.append(f"#{namespace}={num_restrict['value_float']}f")
                    elif 'value_double' in num_restrict:
                        line_parts.append(f"#{namespace}={num_restrict['value_double']}d")
            
            csv_lines.append(','.join(line_parts))
        
        return '\n'.join(csv_lines)
    
    def create_sample_data(self, embeddings_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从embedding数据创建符合Vertex AI格式的样本数据
        
        Args:
            embeddings_data: 包含id和embedding的数据列表
            
        Returns:
            格式化后的数据点列表
        """
        formatted_data = []
        
        for item in embeddings_data:
            data_point = {
                "id": str(item.get('id', '')),
                "embedding": item.get('embedding', []),
            }
            
            # 可选：添加元数据作为限制条件
            if 'metadata' in item:
                metadata = item['metadata']
                if 'file_type' in metadata:
                    data_point['restricts'] = [{
                        "namespace": "file_type",
                        "allow": [metadata['file_type']]
                    }]
                
                if 'file_size' in metadata:
                    data_point['numeric_restricts'] = [{
                        "namespace": "file_size",
                        "value_int": int(metadata['file_size'])
                    }]
            
            formatted_data.append(data_point)
        
        return formatted_data
    
    def save_to_file(self, data_points: List[Dict[str, Any]], 
                     output_path: str, format_type: str = 'jsonl') -> bool:
        """
        将数据保存到文件
        
        Args:
            data_points: 数据点列表
            output_path: 输出文件路径
            format_type: 格式类型 ('jsonl', 'csv')
            
        Returns:
            是否保存成功
        """
        try:
            if format_type == 'jsonl':
                content = self.format_to_jsonl(data_points)
            elif format_type == 'csv':
                content = self.format_to_csv(data_points)
            else:
                raise ValueError(f"不支持的格式类型: {format_type}")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"数据已保存到 {output_path}，格式: {format_type}")
            return True
            
        except Exception as e:
            print(f"保存数据失败: {e}")
            return False

def example_usage():
    """使用示例"""
    formatter = VectorDataFormatter()
    
    # 示例数据
    sample_data = [
        {
            "id": "doc_1",
            "embedding": [0.1, 0.2, 0.3, 0.4],
            "restricts": [
                {
                    "namespace": "category",
                    "allow": ["legal", "document"]
                }
            ],
            "numeric_restricts": [
                {
                    "namespace": "priority",
                    "value_int": 1
                }
            ],
            "crowding_tag": "legal_docs"
        },
        {
            "id": "doc_2", 
            "embedding": [0.5, 0.6, 0.7, 0.8],
            "sparse_embedding": {
                "values": [0.1, 0.2],
                "dimensions": [10, 20]
            }
        }
    ]
    
    # 生成JSONL格式
    jsonl_output = formatter.format_to_jsonl(sample_data)
    print("JSONL格式:")
    print(jsonl_output)
    
    # 生成CSV格式
    csv_output = formatter.format_to_csv(sample_data)
    print("\nCSV格式:")
    print(csv_output)

if __name__ == "__main__":
    example_usage() 
 
 
 