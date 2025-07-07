#!/usr/bin/env python3
"""
重新生成并保存所有文档的embedding
"""
import os
import sys
import json
import requests
sys.path.append('.')

# 使用配置系统设置认证
try:
    from config import setup_google_credentials
    setup_google_credentials()
except ImportError:
    # 如果配置文件不存在，使用备用方案
    credentials_path = os.path.join(os.path.dirname(__file__), 'credentials', 'cy-aispeci-demo-da47ddabfaf6.json')
    if os.path.exists(credentials_path):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    else:
        print("⚠️ 无法找到Google Cloud认证文件")

from src.embedding_generation import get_text_embeddings

def regenerate_all_embeddings():
    """重新生成所有文档的embedding"""
    print("🔄 开始重新生成所有文档的embedding...")
    print("=" * 50)
    
    # 1. 获取所有文件
    response = requests.get('http://localhost:8080/files')
    files = response.json()['files']
    
    print(f"系统中共有 {len(files)} 个文件")
    
    # 2. 清空现有的embedding文件
    with open('embeddings_data.jsonl', 'w', encoding='utf-8') as f:
        pass  # 清空文件
    
    print("✅ 已清空现有embedding文件")
    
    # 3. 为每个文件重新生成embedding
    all_embeddings = []
    
    for file in files:
        if file['status'] != 'completed':
            print(f"⏭️ 跳过未完成的文件: {file['name']}")
            continue
            
        print(f"\n📄 处理文件: {file['name']} (ID: {file['id']})")
        
        try:
            # 获取文件的chunks
            response = requests.get(f"http://localhost:8080/files/{file['id']}/chunks")
            chunks_data = response.json()
            chunks = chunks_data['chunks']
            
            print(f"   - 文件包含 {len(chunks)} 个块")
            
            # 为每个chunk生成embedding
            for i, chunk in enumerate(chunks):
                print(f"   - 正在生成块 {i+1}/{len(chunks)} 的embedding...")
                
                # 生成embedding
                embedding = get_text_embeddings([chunk['content']])[0]
                
                # 准备数据
                embedding_data = {
                    'id': chunk['id'],
                    'file_id': file['id'],
                    'file_name': file['name'],
                    'chunk_index': i,
                    'content': chunk['content'],
                    'embedding': embedding
                }
                
                all_embeddings.append(embedding_data)
                
                # 追加到文件
                with open('embeddings_data.jsonl', 'a', encoding='utf-8') as f:
                    f.write(json.dumps(embedding_data, ensure_ascii=False) + '\n')
                
                print(f"   ✅ 块 {i+1} embedding已保存 (维度: {len(embedding)})")
                
        except Exception as e:
            print(f"   ❌ 处理文件时出错: {e}")
            continue
    
    print(f"\n🎉 完成！共生成 {len(all_embeddings)} 个embedding")
    
    # 4. 验证生成的embedding
    print("\n=== 验证生成的embedding ===")
    with open('embeddings_data.jsonl', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"文件中保存了 {len(lines)} 个embedding记录")
    
    # 显示前几个记录的信息
    for i, line in enumerate(lines[:5]):
        data = json.loads(line.strip())
        content_preview = data['content'][:100] + '...' if len(data['content']) > 100 else data['content']
        print(f"{i+1}. ID: {data['id']}, 文件: {data['file_name']}, 内容: {content_preview}")
    
    if len(lines) > 5:
        print(f"... 还有 {len(lines) - 5} 个记录")
    
    print("\n✅ Embedding重新生成完成！")

if __name__ == "__main__":
    regenerate_all_embeddings() 
 