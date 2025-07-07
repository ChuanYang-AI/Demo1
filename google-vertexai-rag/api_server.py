#!/usr/bin/env python3
"""
Flask API服务器 - 连接RAG系统与前端，集成GCS存储
"""

import os
import sys
import json
import time
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

# 添加src目录到Python路径
sys.path.append('./src')

from embedding_generation import initialize_vertex_ai, get_text_embeddings
from rag_retrieval import retrieve_relevant_chunks
from rag_generation import generate_answer_with_llm
from data_preprocessing import extract_text_from_pdf, extract_text_from_docx, chunk_text
from gcs_storage import GCSFileManager
from cache_manager import CacheManager

# 导入混合检索系统
try:
    from src.hybrid_retrieval import HybridRetrieval, RetrievalStrategy, RetrievalConfig, hybrid_search
except ImportError:
    from hybrid_retrieval import HybridRetrieval, RetrievalStrategy, RetrievalConfig, hybrid_search

import threading
import queue
from enum import Enum

class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

# 全局变量用于管理处理状态
PROCESSING_QUEUE = queue.Queue()
PROCESSING_STATUS = {}  # file_id -> {"status": ProcessingStatus, "progress": int, "error": str, "chunks": int}

# 全局变量用于存储预先计算的embedding
CHUNK_EMBEDDINGS = {}  # chunk_id -> embedding vector

# 全局变量用于跟踪处理状态
PROCESSING_FILES = set()  # 用于跟踪正在处理的文件，避免重复处理

def background_file_processor():
    """后台文件处理线程"""
    while True:
        try:
            task = PROCESSING_QUEUE.get(timeout=1)
            if task is None:  # 停止信号
                break
                
            file_id = task['file_id']
            file_content = task['file_content']
            file_ext = task['file_ext']
            filename = task['filename']
            
            print(f"开始后台处理文件: {filename} (ID: {file_id})")
            
            # 更新状态为处理中
            PROCESSING_STATUS[file_id]["status"] = ProcessingStatus.PROCESSING
            PROCESSING_STATUS[file_id]["progress"] = 10
            
            try:
                # 保存到临时文件进行文本提取
                temp_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                        temp_file.write(file_content)
                        temp_path = temp_file.name
                        temp_file.flush()  # 确保数据写入磁盘
                    
                    # 更新进度
                    PROCESSING_STATUS[file_id]["progress"] = 30
                    
                    # 验证文件是否存在
                    if not os.path.exists(temp_path):
                        raise FileNotFoundError(f"Temporary file not found: {temp_path}")
                    
                    # 提取文本
                    if file_ext == '.pdf':
                        text = extract_text_from_pdf(temp_path)
                    elif file_ext in ['.doc', '.docx']:
                        text = extract_text_from_docx(temp_path)
                    elif file_ext == '.txt':
                        with open(temp_path, 'r', encoding='utf-8') as f:
                            text = f.read()
                    else:
                        raise ValueError(f"Unsupported file type: {file_ext}")
                    
                    # 更新进度
                    PROCESSING_STATUS[file_id]["progress"] = 60
                    
                    # 分块
                    chunks = chunk_text(text, chunk_size=500, overlap_size=100)
                    
                    # 更新进度
                    PROCESSING_STATUS[file_id]["progress"] = 80
                    
                    # 更新全局chunk映射
                    global CHUNK_MAP
                    for i, chunk in enumerate(chunks):
                        chunk_id = f"file_{file_id}_chunk_{i}"
                        CHUNK_MAP[chunk_id] = chunk
                    
                    # 将新chunks添加到全局的预先生成的chunk索引中
                    # 这样检索时就能找到新文件的内容
                    global chunk_id_to_text_map
                    for i, chunk in enumerate(chunks):
                        chunk_id = f"file_{file_id}_chunk_{i}"
                        chunk_id_to_text_map[chunk_id] = chunk
                    
                    # 预先计算embedding并存储
                    print(f"正在为文件 {filename} 预先计算embedding...")
                    chunk_texts = list(chunks)
                    if chunk_texts:
                        try:
                            embeddings = get_text_embeddings(chunk_texts)
                            global CHUNK_EMBEDDINGS
                            
                            # 准备上传到向量搜索的数据
                            chunk_embeddings_data = []
                            
                            for i, embedding in enumerate(embeddings):
                                chunk_id = f"file_{file_id}_chunk_{i}"
                                CHUNK_EMBEDDINGS[chunk_id] = embedding
                                
                                # 添加到向量搜索数据
                                chunk_embeddings_data.append({
                                    "id": chunk_id,
                                    "embedding": embedding
                                })
                            
                            print(f"成功预先计算了 {len(embeddings)} 个embedding")
                            
                            # 上传到向量搜索索引
                            print(f"正在上传文件 {filename} 的embedding到向量搜索索引...")
                            upload_success = upload_embeddings_to_vector_search(chunk_embeddings_data)
                            
                            if upload_success:
                                print(f"成功上传文件 {filename} 的embedding到向量搜索索引")
                            else:
                                print(f"上传文件 {filename} 的embedding到向量搜索索引失败")
                                
                        except Exception as e:
                            print(f"预先计算embedding失败: {e}")
                            # 即使embedding失败，文件处理也应该继续
                    
                    # 清理临时文件
                    if temp_path and os.path.exists(temp_path):
                        os.remove(temp_path)
                    
                    # 添加文档到混合检索系统
                    if hybrid_retrieval:
                        try:
                            print(f"正在将文件 {filename} 添加到混合检索系统...")
                            full_text = "\n".join(chunks)
                            success = hybrid_retrieval.add_document(file_id, full_text, filename)
                            if success:
                                print(f"✅ 文件 {filename} 已添加到混合检索系统")
                            else:
                                print(f"⚠️ 文件 {filename} 添加到混合检索系统失败")
                        except Exception as e:
                            print(f"❌ 混合检索系统添加文档失败: {e}")
                    
                    # 更新状态为完成
                    PROCESSING_STATUS[file_id]["status"] = ProcessingStatus.COMPLETED
                    PROCESSING_STATUS[file_id]["progress"] = 100
                    PROCESSING_STATUS[file_id]["chunks"] = len(chunks)
                    
                    print(f"文件处理完成: {filename} - {len(chunks)} 个文本块")
                    
                except Exception as e:
                    print(f"文件处理失败: {filename} - {e}")
                    PROCESSING_STATUS[file_id]["status"] = ProcessingStatus.ERROR
                    PROCESSING_STATUS[file_id]["error"] = str(e)
                    
                    # 清理临时文件
                    if temp_path and os.path.exists(temp_path):
                        os.remove(temp_path)
                    
            except Exception as e:
                print(f"处理任务失败: {e}")
                PROCESSING_STATUS[file_id]["status"] = ProcessingStatus.ERROR
                PROCESSING_STATUS[file_id]["error"] = str(e)
                
        except queue.Empty:
            continue
        except Exception as e:
            print(f"后台处理器错误: {e}")
            break

# 启动后台处理线程
processing_thread = threading.Thread(target=background_file_processor, daemon=True)
processing_thread.start()

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 导入项目配置
try:
    from config import setup_google_credentials, PROJECT_CONFIG, SERVER_CONFIG, PATHS
    # 设置Google认证
    setup_google_credentials()
    
    # 配置从config.py获取
    PROJECT_ID = PROJECT_CONFIG["project_id"]
    LOCATION = PROJECT_CONFIG["location"]
    ENDPOINT_ID = PROJECT_CONFIG["endpoint_id"]
    BUCKET_NAME = PROJECT_CONFIG["bucket_name"]
    VECTOR_BUCKET_NAME = "vertex_ai_rag_demo_vectors"  # 向量存储桶名称
    
    print("✅ 项目配置加载成功")
    
except ImportError as e:
    print(f"⚠️ 无法导入配置文件，使用默认配置: {e}")
    # 配置（备用）
    PROJECT_ID = "cy-aispeci-demo"
    LOCATION = "us-central1"
    ENDPOINT_ID = "7934957714357092352"
    BUCKET_NAME = "vertex_ai_rag_demo"
    VECTOR_BUCKET_NAME = "vertex_ai_rag_demo_vectors"

# 向量搜索配置
INDEX_DISPLAY_NAME = "rag-document-index"
ENDPOINT_DISPLAY_NAME = "rag-document-endpoint"

# 全局变量存储文档块映射和文件信息
CHUNK_MAP = {}
UPLOADED_FILES = []
chunk_id_to_text_map = {}  # 用于存储预先生成的chunk索引

# 缓存管理器
cache_manager = None

# 延迟加载标志
DOCUMENTS_LOADED = False
DOCUMENTS_LOADING = False

# 初始化GCS文件管理器
gcs_manager = None
vector_index = None
vector_endpoint = None

# 混合检索系统
hybrid_retrieval = None

def init_gcs():
    """初始化GCS文件管理器"""
    global gcs_manager
    try:
        gcs_manager = GCSFileManager(
            project_id=PROJECT_ID,
            bucket_name=BUCKET_NAME,
            service_account_path=None  # 使用环境变量GOOGLE_APPLICATION_CREDENTIALS
        )
        print("GCS File Manager initialized successfully")
        return True
    except Exception as e:
        print(f"Failed to initialize GCS: {e}")
        return False

# 初始化Vertex AI
def init_vertex_ai():
    """初始化Vertex AI"""
    try:
        # 认证已经在配置阶段设置好了
        initialize_vertex_ai(PROJECT_ID, LOCATION)
        print("Vertex AI initialized successfully")
        return True
    except Exception as e:
        print(f"Failed to initialize Vertex AI: {e}")
        return False

def init_hybrid_retrieval():
    """初始化混合检索系统"""
    global hybrid_retrieval
    try:
        print("🔧 初始化混合检索系统...")
        
        # 创建检索配置
        config = RetrievalConfig(
            num_candidates=10,        # 每路召回10个候选
            final_results=5,          # 最终返回5个结果
            faiss_weight=0.6,         # FAISS权重60%
            vertex_weight=0.4,        # Vertex AI权重40%
            min_similarity=0.3,       # 最低相似度30%
            enable_reranking=True     # 启用重排序
        )
        
        # 初始化混合检索
        hybrid_retrieval = HybridRetrieval(
            config=config,
            project_id=PROJECT_ID,
            location=LOCATION,
            endpoint_id=ENDPOINT_ID
        )
        
        print("✅ 混合检索系统初始化完成")
        return True
        
    except Exception as e:
        print(f"❌ 混合检索系统初始化失败: {e}")
        # 即使混合检索失败，系统也应该能够运行（使用原有的检索）
        return False

def init_vector_search():
    """初始化向量搜索索引和端点"""
    global vector_index, vector_endpoint
    try:
        print("开始初始化向量搜索...")
        
        # 尝试导入向量搜索管理模块
        try:
            from src.vector_search_management import create_or_get_vector_search_index, deploy_index_to_endpoint
            print("成功导入向量搜索管理模块")
        except ImportError as e:
            print(f"导入向量搜索管理模块失败: {e}")
            return False
        
        print("Initializing Vector Search...")
        
        # 创建或获取向量搜索索引
        try:
            print("正在创建或获取向量搜索索引...")
            vector_index = create_or_get_vector_search_index(
                project_id=PROJECT_ID,
                location=LOCATION,
                index_display_name=INDEX_DISPLAY_NAME,
                description="RAG Document Index for intelligent Q&A",
                dimensions=768  # text-embedding-004 的维度
            )
            print(f"向量搜索索引获取成功: {vector_index.name}")
        except Exception as e:
            print(f"创建或获取向量搜索索引失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 部署索引到端点（不等待完成）
        try:
            print("正在部署索引到端点...")
            vector_endpoint = deploy_index_to_endpoint(
                project_id=PROJECT_ID,
                location=LOCATION,
                index=vector_index,
                endpoint_display_name=ENDPOINT_DISPLAY_NAME,
                wait_for_completion=False  # 不等待完成，允许服务器快速启动
            )
            print(f"向量搜索端点获取成功: {vector_endpoint.name}")
        except Exception as e:
            print(f"部署索引到端点失败: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print(f"Vector Search initialized successfully")
        print(f"Index: {vector_index.name}")
        print(f"Endpoint: {vector_endpoint.name}")
        print("注意：索引部署可能需要10-30分钟完成，在此期间将使用本地相似度搜索")
        return True
        
    except Exception as e:
        print(f"Failed to initialize Vector Search: {e}")
        import traceback
        traceback.print_exc()
        return False

def upload_embeddings_to_vector_search(chunk_embeddings_data: list):
    """将embedding数据上传到向量搜索索引"""
    try:
        if not vector_index or not chunk_embeddings_data:
            print("No vector index or no embeddings to upload")
            return False
        
        from src.vector_search_management import upload_embeddings_to_index
        from google.cloud import storage
        import tempfile
        
        # 创建JSONL文件
        jsonl_data = []
        for item in chunk_embeddings_data:
            jsonl_data.append({
                "id": item["id"],
                "embedding": item["embedding"]
            })
        
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as temp_file:
            for item in jsonl_data:
                temp_file.write(json.dumps(item, ensure_ascii=False) + '\n')
            temp_file_path = temp_file.name
        
        # 上传到GCS
        storage_client = storage.Client(project=PROJECT_ID)
        try:
            bucket = storage_client.bucket(VECTOR_BUCKET_NAME)
        except Exception:
            # 如果桶不存在，创建它
            bucket = storage_client.create_bucket(VECTOR_BUCKET_NAME, location=LOCATION)
        
        blob_name = f"embeddings_data/embeddings_{int(time.time())}.jsonl"
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(temp_file_path)
        
        gcs_uri = f"gs://{VECTOR_BUCKET_NAME}/{blob_name}"
        print(f"Embeddings uploaded to GCS: {gcs_uri}")
        
        # 上传到向量搜索索引
        upload_embeddings_to_index(
            project_id=PROJECT_ID,
            location=LOCATION,
            index_name=vector_index.name,
            gcs_input_uri=gcs_uri
        )
        
        # 清理临时文件
        os.unlink(temp_file_path)
        
        print(f"Successfully uploaded {len(jsonl_data)} embeddings to Vector Search")
        return True
        
    except Exception as e:
        print(f"Failed to upload embeddings to Vector Search: {e}")
        import traceback
        traceback.print_exc()
        return False

# 加载现有文档内容
def load_existing_documents():
    """加载现有的文档内容"""
    global CHUNK_MAP, chunk_id_to_text_map
    doc_path = "./docs/法律知识问答.docx"
    if os.path.exists(doc_path):
        try:
            print("Loading existing document...")
            text = extract_text_from_docx(doc_path)
            chunks = chunk_text(text, chunk_size=500, overlap_size=100)
            
            chunk_texts = []
            for i, chunk in enumerate(chunks):
                chunk_id = f"chunk_{i}"
                CHUNK_MAP[chunk_id] = chunk
                chunk_id_to_text_map[chunk_id] = chunk
                chunk_texts.append(chunk)
            
            print(f"Loaded {len(chunks)} chunks from existing document")
            
            # 异步处理embedding，不阻塞服务器启动
            if chunk_texts:
                try:
                    print(f"正在为现有文档预先计算embedding（异步处理）...")
                    # 使用线程池异步处理embedding
                    import threading
                    def process_embeddings():
                        try:
                            # 检查是否已经在处理
                            if "existing_doc" in PROCESSING_FILES:
                                print("现有文档embedding已在处理中，跳过")
                                return
                            
                            PROCESSING_FILES.add("existing_doc")
                            
                            embeddings = get_text_embeddings(chunk_texts)
                            global CHUNK_EMBEDDINGS
                            
                            # 准备上传到向量搜索的数据
                            chunk_embeddings_data = []
                            
                            for i, embedding in enumerate(embeddings):
                                chunk_id = f"chunk_{i}"
                                CHUNK_EMBEDDINGS[chunk_id] = embedding
                                
                                # 添加到向量搜索数据
                                chunk_embeddings_data.append({
                                    "id": chunk_id,
                                    "embedding": embedding
                                })
                            
                            print(f"成功预先计算了 {len(embeddings)} 个现有文档embedding")
                            
                            # 暂时跳过向量搜索上传
                            print("跳过向量搜索上传，使用本地embedding")
                                
                        except Exception as e:
                            print(f"异步处理现有文档embedding失败: {e}")
                        finally:
                            PROCESSING_FILES.discard("existing_doc")
                    
                    # 在后台线程中处理embedding
                    embedding_thread = threading.Thread(target=process_embeddings, daemon=True)
                    embedding_thread.start()
                    print("现有文档embedding处理已在后台启动")
                    
                except Exception as e:
                    print(f"启动现有文档embedding处理失败: {e}")
            
        except Exception as e:
            print(f"Failed to load existing document: {e}")
    else:
        print("No existing document found")

def lazy_load_documents():
    """延迟加载文档数据"""
    global DOCUMENTS_LOADED, DOCUMENTS_LOADING, cache_manager
    
    if DOCUMENTS_LOADED or DOCUMENTS_LOADING:
        return
    
    DOCUMENTS_LOADING = True
    
    try:
        print("🔄 延迟加载文档数据...")
        
        # 初始化缓存管理器
        cache_manager = CacheManager()
        
        # 尝试从缓存加载现有文档
        cached_chunks = cache_manager.get_cached_chunks("existing_doc")
        if cached_chunks:
            print(f"📦 从缓存加载了 {len(cached_chunks)} 个现有文档块")
            
            # 加载到内存
            for i, chunk in enumerate(cached_chunks):
                chunk_id = f"chunk_{i}"
                CHUNK_MAP[chunk_id] = chunk
                chunk_id_to_text_map[chunk_id] = chunk
            
            # 从缓存加载embeddings
            chunk_ids = [f"chunk_{i}" for i in range(len(cached_chunks))]
            cached_embeddings = cache_manager.get_cached_embeddings(chunk_ids)
            if cached_embeddings:
                CHUNK_EMBEDDINGS.update(cached_embeddings)
                print(f"📦 从缓存加载了 {len(cached_embeddings)} 个embeddings")
        else:
            # 如果缓存不存在，异步加载现有文档
            print("⏳ 现有文档缓存不存在，异步加载...")
            threading.Thread(target=load_existing_documents_async, daemon=True).start()
        
        # 异步加载GCS文件
        print("⏳ 异步加载GCS文件...")
        threading.Thread(target=load_gcs_files_async, daemon=True).start()
        
        DOCUMENTS_LOADED = True
        print("✅ 延迟加载完成")
        
    except Exception as e:
        print(f"❌ 延迟加载失败: {e}")
    finally:
        DOCUMENTS_LOADING = False

def load_existing_documents_async():
    """异步加载现有文档"""
    try:
        doc_path = "./docs/法律知识问答.docx"
        if os.path.exists(doc_path):
            print("🔄 异步加载现有文档...")
            
            # 计算文件hash
            file_hash = cache_manager.get_file_hash(doc_path) if cache_manager else None
            
            # 检查缓存
            cached_chunks = cache_manager.get_cached_chunks("existing_doc", file_hash) if cache_manager else None
            
            if cached_chunks:
                print(f"📦 从缓存加载了 {len(cached_chunks)} 个现有文档块")
                
                # 加载到内存
                for i, chunk in enumerate(cached_chunks):
                    chunk_id = f"chunk_{i}"
                    CHUNK_MAP[chunk_id] = chunk
                    chunk_id_to_text_map[chunk_id] = chunk
                
                # 从缓存加载embeddings
                chunk_ids = [f"chunk_{i}" for i in range(len(cached_chunks))]
                cached_embeddings = cache_manager.get_cached_embeddings(chunk_ids) if cache_manager else {}
                if cached_embeddings:
                    CHUNK_EMBEDDINGS.update(cached_embeddings)
                    print(f"📦 从缓存加载了 {len(cached_embeddings)} 个embeddings")
            else:
                # 重新处理文档
                print("⏳ 重新处理现有文档...")
                text = extract_text_from_docx(doc_path)
                chunks = chunk_text(text, chunk_size=500, overlap_size=100)
                
                # 更新内存
                for i, chunk in enumerate(chunks):
                    chunk_id = f"chunk_{i}"
                    CHUNK_MAP[chunk_id] = chunk
                    chunk_id_to_text_map[chunk_id] = chunk
                
                # 缓存文档块
                if cache_manager:
                    cache_manager.cache_chunks("existing_doc", chunks, file_hash)
                
                # 异步计算embeddings
                print("⏳ 异步计算embeddings...")
                threading.Thread(target=compute_embeddings_async, args=(chunks, "existing_doc"), daemon=True).start()
                
                print(f"✅ 异步加载了 {len(chunks)} 个现有文档块")
                
    except Exception as e:
        print(f"❌ 异步加载现有文档失败: {e}")

def load_gcs_files_async():
    """异步加载GCS文件"""
    try:
        if not gcs_manager:
            print("❌ GCS manager not available")
            return
            
        print("🔄 异步加载GCS文件...")
        gcs_files = gcs_manager.list_files()
        print(f"📁 发现 {len(gcs_files)} 个GCS文件")
        
        # 批量处理文件，每批最多5个
        batch_size = 5
        for i in range(0, len(gcs_files), batch_size):
            batch = gcs_files[i:i + batch_size]
            
            # 为每个批次创建线程
            batch_threads = []
            for gcs_file in batch:
                thread = threading.Thread(
                    target=process_gcs_file_async,
                    args=(gcs_file,),
                    daemon=True
                )
                batch_threads.append(thread)
                thread.start()
            
            # 等待当前批次完成
            for thread in batch_threads:
                thread.join()
                
        print("✅ GCS文件异步加载完成")
        
    except Exception as e:
        print(f"❌ 异步加载GCS文件失败: {e}")

def process_gcs_file_async(gcs_file):
    """异步处理单个GCS文件"""
    try:
        file_id = gcs_file['file_id']
        file_name = gcs_file['file_name']
        
        print(f"🔄 处理文件: {file_name}")
        
        # 检查缓存
        cached_chunks = cache_manager.get_cached_chunks(file_id) if cache_manager else None
        if cached_chunks:
            print(f"📦 从缓存加载文件 {file_name}: {len(cached_chunks)} 个块")
            
            # 加载到内存
            for i, chunk in enumerate(cached_chunks):
                chunk_id = f"file_{file_id}_chunk_{i}"
                CHUNK_MAP[chunk_id] = chunk
                chunk_id_to_text_map[chunk_id] = chunk
            
            # 从缓存加载embeddings
            chunk_ids = [f"file_{file_id}_chunk_{i}" for i in range(len(cached_chunks))]
            cached_embeddings = cache_manager.get_cached_embeddings(chunk_ids) if cache_manager else {}
            if cached_embeddings:
                CHUNK_EMBEDDINGS.update(cached_embeddings)
            
            # 添加到文件列表
            file_info = {
                'id': file_id,
                'name': file_name,
                'size': gcs_file['size'],
                'type': gcs_file['content_type'],
                'uploadedAt': int(datetime.fromisoformat(gcs_file['created'].replace('Z', '+00:00')).timestamp()) if gcs_file['created'] else int(time.time()),
                'chunks': len(cached_chunks),
                'gcs_info': gcs_file
            }
            UPLOADED_FILES.append(file_info)
            return
        
        # 如果缓存不存在，重新处理文件
        print(f"⏳ 重新处理文件: {file_name}")
        
        # 下载文件
        temp_path = gcs_manager.save_to_temp_file(file_id, file_name)
        if not temp_path:
            print(f"❌ 无法下载文件: {file_name}")
            return
            
        # 提取文本
        file_ext = os.path.splitext(file_name)[1].lower()
        if not file_ext:
            content_type = gcs_file.get('content_type', '').lower()
            if 'pdf' in content_type:
                file_ext = '.pdf'
            elif 'wordprocessingml' in content_type or 'msword' in content_type:
                file_ext = '.docx'
            elif 'text/plain' in content_type:
                file_ext = '.txt'
        
        text = None
        if file_ext == '.pdf':
            text = extract_text_from_pdf(temp_path)
        elif file_ext in ['.doc', '.docx']:
            text = extract_text_from_docx(temp_path)
        elif file_ext == '.txt':
            with open(temp_path, 'r', encoding='utf-8') as f:
                text = f.read()
        
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if text:
            # 分块
            chunks = chunk_text(text, chunk_size=500, overlap_size=100)
            
            # 更新内存
            for i, chunk in enumerate(chunks):
                chunk_id = f"file_{file_id}_chunk_{i}"
                CHUNK_MAP[chunk_id] = chunk
                chunk_id_to_text_map[chunk_id] = chunk
            
            # 缓存文档块
            if cache_manager:
                cache_manager.cache_chunks(file_id, chunks)
            
            # 异步计算embeddings
            threading.Thread(target=compute_embeddings_async, args=(chunks, file_id), daemon=True).start()
            
            # 添加到文件列表
            file_info = {
                'id': file_id,
                'name': file_name,
                'size': gcs_file['size'],
                'type': gcs_file['content_type'],
                'uploadedAt': int(datetime.fromisoformat(gcs_file['created'].replace('Z', '+00:00')).timestamp()) if gcs_file['created'] else int(time.time()),
                'chunks': len(chunks),
                'gcs_info': gcs_file
            }
            UPLOADED_FILES.append(file_info)
            
            print(f"✅ 成功处理文件 {file_name}: {len(chunks)} 个块")
        else:
            print(f"❌ 无法提取文本: {file_name}")
            
    except Exception as e:
        print(f"❌ 处理文件失败 {gcs_file.get('file_name', 'unknown')}: {e}")

def compute_embeddings_async(chunks, file_id):
    """异步计算embeddings"""
    try:
        if not chunks:
            return
            
        print(f"🔄 计算embeddings: {file_id}")
        
        embeddings = get_text_embeddings(chunks)
        
        # 更新内存
        chunk_embeddings = {}
        for i, embedding in enumerate(embeddings):
            if file_id == "existing_doc":
                chunk_id = f"chunk_{i}"
            else:
                chunk_id = f"file_{file_id}_chunk_{i}"
            
            CHUNK_EMBEDDINGS[chunk_id] = embedding
            chunk_embeddings[chunk_id] = embedding
        
        # 缓存embeddings
        if cache_manager:
            cache_manager.cache_embeddings(chunk_embeddings)
        
        print(f"✅ 计算完成embeddings: {file_id} ({len(embeddings)} 个)")
        
    except Exception as e:
        print(f"❌ 计算embeddings失败 {file_id}: {e}")

def load_gcs_files():
    """从GCS加载已存在的文件"""
    global UPLOADED_FILES, CHUNK_MAP
    try:
        if not gcs_manager:
            print("GCS manager not available")
            return
        
        print("Loading files from GCS...")
        gcs_files = gcs_manager.list_files()
        print(f"Found {len(gcs_files)} files in GCS")
        
        # 限制同时处理的文件数量，避免阻塞
        max_files_to_process = 10
        files_processed = 0
        
        for gcs_file in gcs_files:
            if files_processed >= max_files_to_process:
                print(f"已处理 {max_files_to_process} 个文件，剩余文件将在后台处理")
                break
                
            file_id = gcs_file['file_id']
            file_name = gcs_file['file_name']
            
            # 检查文件是否已经在UPLOADED_FILES中
            existing_file = next((f for f in UPLOADED_FILES if f['id'] == file_id), None)
            if existing_file:
                print(f"File {file_name} already loaded, skipping")
                continue
            
            print(f"Loading file: {file_name} (ID: {file_id})")
            
            # 先添加文件到列表，即使处理失败也要记录
            file_info = {
                'id': file_id,
                'name': file_name,
                'size': gcs_file['size'],
                'type': gcs_file['content_type'],
                'uploadedAt': int(datetime.fromisoformat(gcs_file['created'].replace('Z', '+00:00')).timestamp()) if gcs_file['created'] else int(time.time()),
                'chunks': 0,
                'gcs_info': gcs_file
            }
            
            try:
                # 下载文件到临时目录（添加超时）
                temp_path = None
                try:
                    temp_path = gcs_manager.save_to_temp_file(file_id, file_name)
                    print(f"File downloaded successfully: {gcs_file['blob_name']}")
                except Exception as e:
                    print(f"Failed to download file {file_name}: {e}")
                    UPLOADED_FILES.append(file_info)
                    continue
                
                # 提取文本
                file_ext = os.path.splitext(file_name)[1].lower()
                
                # 如果文件名没有扩展名，尝试从content_type推断
                if not file_ext:
                    content_type = gcs_file.get('content_type', '').lower()
                    if 'pdf' in content_type:
                        file_ext = '.pdf'
                    elif 'wordprocessingml' in content_type or 'msword' in content_type:
                        file_ext = '.docx'
                    elif 'text/plain' in content_type:
                        file_ext = '.txt'
                    else:
                        print(f"Cannot determine file type from content_type: {content_type}")
                
                text = None
                
                if file_ext == '.pdf':
                    text = extract_text_from_pdf(temp_path)
                elif file_ext in ['.doc', '.docx']:
                    text = extract_text_from_docx(temp_path)
                elif file_ext == '.txt':
                    with open(temp_path, 'r', encoding='utf-8') as f:
                        text = f.read()
                else:
                    print(f"Unsupported file type: {file_ext} (content_type: {gcs_file.get('content_type', 'unknown')})")
                    # 即使不支持的文件类型也要添加到列表中
                    UPLOADED_FILES.append(file_info)
                    continue
                
                if text:
                    # 分块
                    chunks = chunk_text(text, chunk_size=500, overlap_size=100)
                    
                    # 更新chunk映射
                    for i, chunk in enumerate(chunks):
                        chunk_id = f"file_{file_id}_chunk_{i}"
                        CHUNK_MAP[chunk_id] = chunk
                    
                    # 将新chunks添加到全局的预先生成的chunk索引中
                    global chunk_id_to_text_map
                    for i, chunk in enumerate(chunks):
                        chunk_id = f"file_{file_id}_chunk_{i}"
                        chunk_id_to_text_map[chunk_id] = chunk
                    
                    # 更新文件信息
                    file_info['chunks'] = len(chunks)
                    print(f"Successfully processed {file_name}: {len(chunks)} chunks")
                    
                    # 异步处理embedding，不阻塞启动
                    def process_file_embeddings(file_id, file_name, chunks):
                        try:
                            # 检查是否已经在处理
                            if file_id in PROCESSING_FILES:
                                print(f"文件 {file_name} 的embedding已在处理中，跳过")
                                return
                            
                            PROCESSING_FILES.add(file_id)
                            
                            print(f"正在为文件 {file_name} 预先计算embedding...")
                            chunk_texts = list(chunks)
                            if chunk_texts:
                                embeddings = get_text_embeddings(chunk_texts)
                                global CHUNK_EMBEDDINGS
                                
                                # 准备上传到向量搜索的数据
                                chunk_embeddings_data = []
                                
                                for i, embedding in enumerate(embeddings):
                                    chunk_id = f"file_{file_id}_chunk_{i}"
                                    CHUNK_EMBEDDINGS[chunk_id] = embedding
                                    
                                    # 添加到向量搜索数据
                                    chunk_embeddings_data.append({
                                        "id": chunk_id,
                                        "embedding": embedding
                                    })
                                
                                print(f"成功预先计算了 {len(embeddings)} 个embedding for {file_name}")
                                
                                # 暂时跳过向量搜索上传
                                print("跳过向量搜索上传，使用本地embedding")
                        except Exception as e:
                            print(f"处理文件 {file_name} 的embedding失败: {e}")
                        finally:
                            PROCESSING_FILES.discard(file_id)
                    
                    # 在后台线程中处理embedding
                    import threading
                    embedding_thread = threading.Thread(
                        target=process_file_embeddings, 
                        args=(file_id, file_name, chunks),
                        daemon=True
                    )
                    embedding_thread.start()
                else:
                    print(f"Failed to extract text from {file_name}")
                
                # 清理临时文件
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                
            except Exception as e:
                print(f"Failed to process GCS file {file_name}: {e}")
                # 即使处理失败，也要记录文件信息
                pass
            
            # 添加到文件列表
            UPLOADED_FILES.append(file_info)
            files_processed += 1
        
        print(f"Loaded {len(UPLOADED_FILES)} files from GCS")
        print(f"Total chunks available for search: {len(chunk_id_to_text_map)}")
        print(f"Embedding processing is running in background...")
        
    except Exception as e:
        print(f"Failed to load GCS files: {e}")
        import traceback
        traceback.print_exc()

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    hybrid_health = {}
    hybrid_stats = {}
    
    # 获取混合检索系统状态
    if hybrid_retrieval:
        try:
            hybrid_health = hybrid_retrieval.health_check()
            hybrid_stats = hybrid_retrieval.get_stats()
        except Exception as e:
            hybrid_health = {'error': str(e)}
    
    return jsonify({
        'status': 'healthy',
        'timestamp': int(time.time()),
        'vertex_ai_initialized': 'initialize_vertex_ai' in globals(),
        'gcs_initialized': gcs_manager is not None,
        'documents_loaded': DOCUMENTS_LOADED,
        'documents_loading': DOCUMENTS_LOADING,
        'total_files': len(UPLOADED_FILES),
        'total_chunks': len(CHUNK_MAP),
        'cache_stats': cache_manager.get_cache_stats() if cache_manager else None,
        'hybrid_retrieval': {
            'available': hybrid_retrieval is not None,
            'health': hybrid_health,
            'stats': hybrid_stats
        }
    })

@app.route('/chat', methods=['POST'])
def chat():
    """处理聊天消息"""
    try:
        # 确保文档已加载
        if not DOCUMENTS_LOADED:
            print("🔄 首次调用chat，触发文档加载...")
            lazy_load_documents()
        
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        print(f"\n{'='*60}")
        print(f"📝 用户问题: {message}")
        print(f"{'='*60}")
        
        # 使用混合检索系统 (优先) 或传统检索 (降级)
        print(f"🔍 开始检索相关文档块...")
        print(f"   - 项目ID: {PROJECT_ID}")
        print(f"   - 位置: {LOCATION}")
        print(f"   - 端点ID: {ENDPOINT_ID}")
        print(f"   - 可用文档块数量: {len(chunk_id_to_text_map)}")
        
        retrieved_chunks = []
        
        # 优先使用混合检索系统
        if hybrid_retrieval:
            try:
                print(f"🚀 使用混合检索系统 (FAISS + Vertex AI)")
                
                # 更新混合检索系统的数据，确保与原有系统同步
                hybrid_retrieval.chunk_map = chunk_id_to_text_map
                hybrid_retrieval.chunk_embeddings = CHUNK_EMBEDDINGS
                
                # 根据查询复杂度选择检索策略
                if len(message) > 20:
                    strategy = RetrievalStrategy.HYBRID_PARALLEL
                else:
                    strategy = RetrievalStrategy.ADAPTIVE
                
                # 执行混合检索
                hybrid_results = hybrid_search(
                    query=message,
                    hybrid_retrieval=hybrid_retrieval,
                    strategy=strategy
                )
                
                retrieved_chunks = hybrid_results
                print(f"✅ 混合检索完成，找到 {len(retrieved_chunks)} 个相关块")
                
            except Exception as e:
                print(f"⚠️ 混合检索失败，降级到传统检索: {e}")
                # 降级到传统检索
                retrieved_chunks = retrieve_relevant_chunks(
                    project_id=PROJECT_ID,
                    location=LOCATION,
                    endpoint_id=ENDPOINT_ID,
                    query_text=message,
                    num_neighbors=3,
                    chunk_map=chunk_id_to_text_map,
                    chunk_embeddings=CHUNK_EMBEDDINGS
                )
                print(f"✅ 传统检索完成，找到 {len(retrieved_chunks)} 个相关块")
        else:
            # 使用传统检索
            print(f"🔍 使用传统检索系统 (混合检索不可用)")
            retrieved_chunks = retrieve_relevant_chunks(
                project_id=PROJECT_ID,
                location=LOCATION,
                endpoint_id=ENDPOINT_ID,
                query_text=message,
                num_neighbors=3,
                chunk_map=chunk_id_to_text_map,
                chunk_embeddings=CHUNK_EMBEDDINGS
            )
            print(f"✅ 传统检索完成，找到 {len(retrieved_chunks)} 个相关块")
        
        # 获取文本内容
        relevant_texts = []
        sources = []
        
        print(f"📚 检索到的相关内容:")
        print(f"{'-'*60}")
        
        for i, chunk in enumerate(retrieved_chunks):
            chunk_id = chunk.get('id', chunk.get('datapoint_id', ''))
            distance = chunk.get('distance', 0)
            similarity = chunk.get('similarity', 1 - distance)
            
            # 获取文本内容，优先从返回结果中取，否则从映射中取
            chunk_text = chunk.get('text', '') or chunk_id_to_text_map.get(chunk_id, "")
            
            if chunk_text:
                relevant_texts.append(chunk_text)
                
                # 尝试从chunk_id中提取文件信息
                file_name = "未知文档"
                if chunk_id.startswith("file_"):
                    # 格式：file_{file_id}_chunk_{index}
                    parts = chunk_id.split('_')
                    if len(parts) >= 4:
                        file_id = '_'.join(parts[1:-2])  # 提取file_id部分
                        # 查找对应的文件名
                        for uploaded_file in UPLOADED_FILES:
                            if uploaded_file['id'] == file_id:
                                file_name = uploaded_file['name']
                                break
                elif chunk_id.startswith("chunk_"):
                    file_name = "法律知识问答.docx"
                
                sources.append({
                    "chunk_id": chunk_id,
                    "file_name": file_name,
                    "similarity": float(similarity),
                    "content_preview": chunk_text[:100] + "..." if len(chunk_text) > 100 else chunk_text
                })
                
                print(f"📄 块 {i+1}: {file_name} (块{chunk_id.split('_')[-1] if '_' in chunk_id else 'N/A'})")
                print(f"   相似度: {similarity:.3f}")
                print(f"   ID: {chunk_id}")
                print(f"   内容: {chunk_text[:100]}{'...' if len(chunk_text) > 100 else ''}")
                print(f"   {'-'*40}")
        
        if not relevant_texts:
            print("📚 检索到的相关内容:")
            print("------------------------------------------------------------")
            print("未找到相关文档，使用基础知识回答")
            print("------------------------------------------------------------")
        
        # 生成回答
        print(f"\n🤖 开始生成回答...")
        print(f"   输入上下文长度: {sum(len(text) for text in relevant_texts)} 字符")
        
        start_time = time.time()
        
        # 使用新的优化版本，支持相关性阈值和答案来源标识
        llm_result = generate_answer_with_llm(
            query=message,
            retrieved_chunks=relevant_texts,
            sources=sources,
                            similarity_threshold=0.60  # 相关性阈值：>60%使用RAG检索，<=60%使用基础知识
        )
        
        processing_time = time.time() - start_time
        
        # 提取结果
        answer = llm_result["answer"]
        answer_source = llm_result["source"]
        confidence = llm_result["confidence"]
        use_rag = llm_result["use_rag"]
        max_similarity = llm_result["max_similarity"]
        
        print(f"✅ 回答生成完成 (耗时: {processing_time:.2f}秒)")
        print(f"\n💬 生成的回答:")
        print(f"{'-'*60}")
        print(f"{answer}")
        print(f"{'-'*60}")
        
        # 构建响应，包含答案来源信息
        response = {
            'answer': answer,
            'sources': sources,
            'processingTime': processing_time,
            'answerSource': answer_source,  # 'rag' 或 'knowledge' 或 'error'
            'confidence': confidence,
            'useRag': use_rag,
            'maxSimilarity': max_similarity,
            'qualityMetrics': {
                'relevanceScore': max_similarity,
                'sourceCount': len(sources),
                'avgSimilarity': sum(s.get('similarity', 0) for s in sources) / len(sources) if sources else 0
            }
        }
        
        print(f"\n📊 响应统计:")
        print(f"   - 处理时间: {processing_time:.2f}秒")
        print(f"   - 检索块数: {len(sources)}")
        print(f"   - 回答长度: {len(answer)} 字符")
        print(f"   - 答案来源: {answer_source}")
        print(f"   - 置信度: {confidence:.3f}")
        print(f"   - 使用RAG: {'是' if use_rag else '否'}")
        print(f"   - 最高相似度: {max_similarity:.3f}")
        print(f"{'='*60}\n")
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ 聊天错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传 - 异步模式"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # 检查文件类型
        allowed_extensions = {'.pdf', '.doc', '.docx', '.txt'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({'error': 'Unsupported file type'}), 400
        
        # 检查文件大小 (10MB)
        file.seek(0, 2)  # 移动到文件末尾
        file_size = file.tell()
        file.seek(0)  # 重置到文件开头
        
        if file_size > 10 * 1024 * 1024:
            return jsonify({'error': 'File size exceeds 10MB limit'}), 400
        
        # 保留原始文件名，但确保安全性
        original_filename = file.filename
        # 只移除路径分隔符和一些危险字符，保留中文等字符
        filename = original_filename.replace('/', '_').replace('\\', '_').replace('..', '_')
        print(f"接收文件上传: {filename} (原始: {original_filename})")
        
        # 读取文件内容
        file_content = file.read()
        
        # 上传到GCS
        metadata = {
            'original_filename': file.filename,
            'file_extension': file_ext,
            'upload_timestamp': datetime.utcnow().isoformat()
        }
        
        gcs_info = gcs_manager.upload_file(
            file_content=file_content,
            file_name=filename,
            content_type=file.content_type or 'application/octet-stream',
            metadata=metadata
        )
        
        file_id = gcs_info['file_id']
        
        # 记录上传的文件（处理前）
        file_info = {
            'id': file_id,
            'name': filename,
            'size': file_size,
            'type': file.content_type or 'application/octet-stream',
            'uploadedAt': int(time.time()),
            'gcs_info': gcs_info
        }
        
        UPLOADED_FILES.append(file_info)
        
        # 初始化处理状态
        PROCESSING_STATUS[file_id] = {
            "status": ProcessingStatus.PENDING,
            "progress": 0,
            "error": None,
            "chunks": 0
        }
        
        # 添加到处理队列
        PROCESSING_QUEUE.put({
            'file_id': file_id,
            'file_content': file_content,
            'file_ext': file_ext,
            'filename': filename
        })
        
        response = {
            'success': True,
            'fileId': file_id,
            'fileName': filename,
            'message': '文件上传成功，正在后台处理...',
            'gcs_uri': gcs_info['gs_uri'],
            'signed_url': gcs_info['signed_url'],
            'processing_status': 'pending'
        }
        
        print(f"文件上传成功，已加入处理队列: {file_id}")
        return jsonify(response)
        
    except Exception as e:
        print(f"Upload error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/files', methods=['GET'])
def get_files():
    """获取所有上传的文件"""
    try:
        files_with_status = []
        
        for file_info in UPLOADED_FILES:
            file_id = file_info['id']
            
            # 检查处理状态
            processing_status = PROCESSING_STATUS.get(file_id)
            
            # 构建文件信息
            file_data = {
                'id': file_id,
                'name': file_info['name'],
                'size': file_info['size'],
                'type': file_info['type'],
                'uploadedAt': file_info['uploadedAt'],
                'chunks': file_info.get('chunks', 0),
                'gcs_info': file_info.get('gcs_info', {}),
            }
            
            # 添加处理状态信息 - 优先使用实际的chunks数量来判断状态
            chunks_count = file_info.get('chunks', 0)
            
            if processing_status:
                # 如果有处理状态记录，使用它
                file_data.update({
                    'status': processing_status['status'].value,
                    'progress': processing_status['progress'],
                    'processed': processing_status['status'] == ProcessingStatus.COMPLETED,
                    'error': processing_status.get('error')
                })
            else:
                # 如果没有处理状态记录，根据chunks数量判断真实状态
                if chunks_count > 0:
                    # 有chunks说明已经处理完成
                    file_data.update({
                        'status': 'completed',
                        'progress': 100,
                        'processed': True
                    })
                else:
                    # 没有chunks，检查是否在GCS中存在
                    # 如果存在但没有chunks，说明是pending状态
                    file_data.update({
                        'status': 'pending',
                        'progress': 0,
                        'processed': False
                    })
            
            files_with_status.append(file_data)
        
        # 按上传时间排序（最新的在前）
        files_with_status.sort(key=lambda x: x['uploadedAt'], reverse=True)
        
        return jsonify({
            'files': files_with_status,
            'total': len(files_with_status)
        })
        
    except Exception as e:
        print(f"Get files error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/upload/<file_id>/status', methods=['GET'])
def get_upload_status(file_id):
    """获取文件处理状态 - 真实状态查询"""
    try:
        # 查找文件信息
        file_info = next((f for f in UPLOADED_FILES if f['id'] == file_id), None)
        if not file_info:
            return jsonify({'error': 'File not found'}), 404
        
        # 获取处理状态
        status_info = PROCESSING_STATUS.get(file_id)
        if not status_info:
            return jsonify({'error': 'Processing status not found'}), 404
        
        # 如果处理完成，更新文件信息中的chunks数量
        if status_info["status"] == ProcessingStatus.COMPLETED and status_info["chunks"] > 0:
            # 更新UPLOADED_FILES中的chunks信息
            for file in UPLOADED_FILES:
                if file['id'] == file_id:
                    file['chunks'] = status_info["chunks"]
                    break
        
        return jsonify({
            'file_id': file_id,
            'status': status_info["status"].value,
            'progress': status_info["progress"],
            'processed': status_info["status"] == ProcessingStatus.COMPLETED,
            'chunks': status_info["chunks"],
            'error': status_info["error"],
            'estimated_time_remaining': calculate_estimated_time(status_info["progress"])
        })
        
    except Exception as e:
        print(f"Status check error: {e}")
        return jsonify({'error': str(e)}), 500

def calculate_estimated_time(progress):
    """计算预估剩余时间（秒）"""
    if progress >= 100:
        return 0
    elif progress >= 80:
        return 5  # 最后20%预计5秒
    elif progress >= 60:
        return 15  # 60-80%预计15秒
    elif progress >= 30:
        return 30  # 30-60%预计30秒
    else:
        return 60  # 前30%预计60秒

@app.route('/files/<file_id>/preview', methods=['GET'])
def preview_file(file_id):
    """获取文件预览内容"""
    try:
        # 查找文件信息
        file_info = next((f for f in UPLOADED_FILES if f['id'] == file_id), None)
        if not file_info:
            return jsonify({'error': 'File not found'}), 404
        
        # 获取文件的所有文本块
        file_chunks = []
        for chunk_id, chunk_text in CHUNK_MAP.items():
            if chunk_id.startswith(f"file_{file_id}_chunk_"):
                chunk_index = int(chunk_id.split('_')[-1])
                file_chunks.append({
                    'index': chunk_index,
                    'content': chunk_text,
                    'length': len(chunk_text)
                })
        
        # 按索引排序
        file_chunks.sort(key=lambda x: x['index'])
        
        # 合并所有文本块获取完整内容
        full_text = '\n\n'.join([chunk['content'] for chunk in file_chunks])
        
        # 获取GCS文件信息
        gcs_file_info = None
        try:
            gcs_file_info = gcs_manager.get_file_info(file_id, file_info['name'])
        except Exception as e:
            print(f"Failed to get GCS file info: {e}")
        
        # 构建预览响应
        preview_data = {
            'fileId': file_id,
            'fileName': file_info['name'],
            'fileSize': file_info['size'],
            'uploadedAt': file_info['uploadedAt'],
            'totalChunks': len(file_chunks),
            'fullText': full_text,
            'chunks': file_chunks,
            'metadata': {
                'wordCount': len(full_text.split()),
                'charCount': len(full_text),
                'type': file_info.get('type', 'unknown')
            },
            'gcs_info': {
                'gs_uri': file_info.get('gcs_info', {}).get('gs_uri'),
                'signed_url': gcs_file_info.get('signed_url') if gcs_file_info else None,
                'public_url': gcs_file_info.get('public_url') if gcs_file_info else None
            }
        }
        
        return jsonify(preview_data)
        
    except Exception as e:
        print(f"Preview error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/files/<file_id>/download', methods=['GET'])
def download_file(file_id):
    """下载文件"""
    try:
        # 查找文件信息
        file_info = next((f for f in UPLOADED_FILES if f['id'] == file_id), None)
        if not file_info:
            return jsonify({'error': 'File not found'}), 404
        
        # 获取GCS签名URL
        try:
            signed_url = gcs_manager.get_signed_url(
                file_id=file_id,
                file_name=file_info['name'],
                expiration_hours=1  # 1小时有效期
            )
            
            return jsonify({
                'download_url': signed_url,
                'file_name': file_info['name'],
                'expires_in': 3600  # 1小时
            })
            
        except Exception as e:
            print(f"Failed to generate download URL: {e}")
            return jsonify({'error': 'Failed to generate download URL'}), 500
        
    except Exception as e:
        print(f"Download error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/files/<file_id>/delete', methods=['DELETE'])
def delete_file(file_id):
    """删除文件"""
    global UPLOADED_FILES, CHUNK_MAP
    try:
        # 查找文件信息
        file_info = next((f for f in UPLOADED_FILES if f['id'] == file_id), None)
        if not file_info:
            return jsonify({'error': 'File not found'}), 404
        
        # 从GCS删除文件
        success = gcs_manager.delete_file(file_id, file_info['name'])
        
        if success:
            # 从内存中删除相关数据
            
            # 删除文件记录
            UPLOADED_FILES = [f for f in UPLOADED_FILES if f['id'] != file_id]
            
            # 删除相关的文本块
            chunk_keys_to_delete = [key for key in CHUNK_MAP.keys() if key.startswith(f"file_{file_id}_chunk_")]
            for key in chunk_keys_to_delete:
                del CHUNK_MAP[key]
            
            return jsonify({
                'success': True,
                'message': 'File deleted successfully',
                'deleted_chunks': len(chunk_keys_to_delete)
            })
        else:
            return jsonify({'error': 'Failed to delete file from storage'}), 500
        
    except Exception as e:
        print(f"Delete error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/files/<file_id>/chunks', methods=['GET'])
def get_file_chunks(file_id):
    """获取文件的分块信息"""
    try:
        # 查找文件信息
        file_info = next((f for f in UPLOADED_FILES if f['id'] == file_id), None)
        if not file_info:
            return jsonify({'error': 'File not found'}), 404
        
        # 获取分页参数
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        # 获取文件的所有文本块
        file_chunks = []
        for chunk_id, chunk_text in CHUNK_MAP.items():
            if chunk_id.startswith(f"file_{file_id}_chunk_"):
                chunk_index = int(chunk_id.split('_')[-1])
                file_chunks.append({
                    'id': chunk_id,
                    'index': chunk_index,
                    'content': chunk_text,
                    'length': len(chunk_text),
                    'wordCount': len(chunk_text.split())
                })
        
        # 按索引排序
        file_chunks.sort(key=lambda x: x['index'])
        
        # 分页处理
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_chunks = file_chunks[start_idx:end_idx]
        
        return jsonify({
            'fileId': file_id,
            'fileName': file_info['name'],
            'totalChunks': len(file_chunks),
            'page': page,
            'perPage': per_page,
            'totalPages': (len(file_chunks) + per_page - 1) // per_page,
            'chunks': paginated_chunks
        })
        
    except Exception as e:
        print(f"Chunks error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/debug/chunks', methods=['GET'])
def debug_chunks():
    """调试端点：查看所有chunk信息"""
    chunk_info = {}
    for chunk_id, chunk_text in CHUNK_MAP.items():
        has_embedding = chunk_id in CHUNK_EMBEDDINGS
        chunk_info[chunk_id] = {
            'preview': chunk_text[:100] + '...' if len(chunk_text) > 100 else chunk_text,
            'length': len(chunk_text),
            'has_embedding': has_embedding,
            'embedding_size': len(CHUNK_EMBEDDINGS[chunk_id]) if has_embedding else 0
        }
    
    return jsonify({
        'total_chunks': len(CHUNK_MAP),
        'total_embeddings': len(CHUNK_EMBEDDINGS),
        'chunks': chunk_info
    })

@app.route('/debug/embedding/<chunk_id>', methods=['GET'])
def debug_embedding(chunk_id):
    """调试端点：检查特定chunk的embedding"""
    if chunk_id not in CHUNK_MAP:
        return jsonify({'error': 'Chunk not found'}), 404
    
    chunk_text = CHUNK_MAP[chunk_id]
    has_embedding = chunk_id in CHUNK_EMBEDDINGS
    
    # 如果没有embedding，尝试重新计算
    if not has_embedding:
        print(f"Chunk {chunk_id} 没有embedding，重新计算...")
        try:
            from embedding_generation import get_text_embeddings
            embeddings = get_text_embeddings([chunk_text])
            if embeddings and embeddings[0]:
                CHUNK_EMBEDDINGS[chunk_id] = embeddings[0]
                has_embedding = True
                print(f"成功为 {chunk_id} 计算embedding")
            else:
                print(f"为 {chunk_id} 计算embedding失败")
        except Exception as e:
            print(f"计算embedding出错: {e}")
    
    return jsonify({
        'chunk_id': chunk_id,
        'chunk_text': chunk_text,
        'text_length': len(chunk_text),
        'has_embedding': has_embedding,
        'embedding_size': len(CHUNK_EMBEDDINGS[chunk_id]) if has_embedding else 0,
        'embedding_preview': CHUNK_EMBEDDINGS[chunk_id][:5] if has_embedding else None
    })

@app.route('/clear/all_embeddings', methods=['POST'])
def clear_all_embeddings():
    """清理所有embedding数据，重新开始"""
    try:
        global CHUNK_MAP, CHUNK_EMBEDDINGS, chunk_id_to_text_map, UPLOADED_FILES, DOCUMENTS_LOADED, cache_manager
        
        # 清理内存数据
        CHUNK_MAP.clear()
        CHUNK_EMBEDDINGS.clear()
        chunk_id_to_text_map.clear()
        UPLOADED_FILES.clear()
        
        # 重置加载状态
        DOCUMENTS_LOADED = False
        
        # 清理缓存
        if cache_manager:
            cache_manager.clear_cache()
        
        return jsonify({
            'success': True,
            'message': '所有embedding数据已清理',
            'cleared_data': {
                'chunks': len(CHUNK_MAP),
                'embeddings': len(CHUNK_EMBEDDINGS),
                'files': len(UPLOADED_FILES)
            }
        })
        
    except Exception as e:
        print(f"Clear embeddings error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/rebuild/embeddings', methods=['POST'])
def rebuild_embeddings():
    """重新构建所有embedding"""
    try:
        # 先清理
        global CHUNK_MAP, CHUNK_EMBEDDINGS, chunk_id_to_text_map, UPLOADED_FILES, DOCUMENTS_LOADED
        
        CHUNK_MAP.clear()
        CHUNK_EMBEDDINGS.clear()
        chunk_id_to_text_map.clear()
        UPLOADED_FILES.clear()
        DOCUMENTS_LOADED = False
        
        # 强制重新加载文档
        lazy_load_documents()
        
        return jsonify({
            'success': True,
            'message': '正在重新构建embedding，请稍候...',
            'status': 'rebuilding'
        })
        
    except Exception as e:
        print(f"Rebuild embeddings error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/create/clean_chunk', methods=['POST'])
def create_clean_chunk():
    """创建一个全新的纯净定金chunk"""
    try:
        # 创建一个完全纯净的定金chunk
        clean_text = """定金是指当事人约定由一方向对方给付的，作为债权担保的一定数额的货币，它属于一种法律上的担保方式，目的在于促使债务人履行债务，保障债权人的债权得以实现。

定金与订金的区别：
1. 定金具有担保性质，订金不具备担保性质
2. 定金受法律保护，订金可视为预付款
3. 定金有双倍返还规则，订金按过错承担责任
4. 定金必须以书面形式约定，订金形式相对灵活

定金的法律效力：
- 给付定金一方不履行债务，无权要求返还定金
- 接受定金一方不履行债务，需双倍返还定金
- 债务履行后，定金应抵作价款或收回"""
        
        # 创建新的chunk ID
        new_chunk_id = 'clean_dingjin_chunk'
        
        # 更新全局映射
        CHUNK_MAP[new_chunk_id] = clean_text
        chunk_id_to_text_map[new_chunk_id] = clean_text
        
        # 重新计算embedding
        from embedding_generation import get_text_embeddings
        embeddings = get_text_embeddings([clean_text])
        
        if embeddings and embeddings[0]:
            CHUNK_EMBEDDINGS[new_chunk_id] = embeddings[0]
            
            # 缓存更新
            if cache_manager:
                cache_manager.cache_embeddings({new_chunk_id: embeddings[0]})
            
            return jsonify({
                'success': True,
                'message': '创建了全新的纯净定金chunk',
                'chunk_id': new_chunk_id,
                'text_length': len(clean_text),
                'text_preview': clean_text[:200] + '...'
            })
        else:
            return jsonify({'error': 'Failed to generate embedding for clean text'}), 500
            
    except Exception as e:
        print(f"Create clean chunk error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/fix/chunk_0', methods=['POST'])
def fix_chunk_0():
    """修复chunk_0：创建纯净的定金相关chunk"""
    try:
        # 定金相关的纯净文本
        clean_text = """法律知识问答
1、问题：在法律中定金与订金的区别？
      答案："定金"是指当事人约定由一方向对方给付的，作为债权担保的一定数额的货币，它属于一种法律上的担保方式，目的在于促使债务人履行债务，保障债权人的债权得以实现。签合同时，对定金必需以书面形式进行约定，同时还应约定定金的数额和交付期限。给付定金一方如果不履行债务，无权要求另一方返还定金；接受定金的一方如果不履行债务，需向另一方双倍返还债务。债务人履行债务后，依照约定，定金应抵作价款或者收回。而"订金"目前我国法律没有明确规定，它不具备定金所具有的担保性质，可视为"预付款"，当合同不能履行时，除不可抗力外，应根据双方当事人的过错承担违约责任。"""
        
        # 更新chunk_0的文本
        CHUNK_MAP['chunk_0'] = clean_text
        
        # 重新计算embedding
        from embedding_generation import get_text_embeddings
        embeddings = get_text_embeddings([clean_text])
        
        if embeddings and embeddings[0]:
            CHUNK_EMBEDDINGS['chunk_0'] = embeddings[0]
            
            # 缓存更新后的数据
            if cache_manager:
                cache_manager.cache_embeddings({'chunk_0': embeddings[0]})
            
            return jsonify({
                'success': True,
                'message': 'chunk_0已修复为纯净的定金相关内容',
                'old_length': 500,
                'new_length': len(clean_text),
                'clean_text_preview': clean_text[:200] + '...'
            })
        else:
            return jsonify({'error': 'Failed to generate embedding for clean text'}), 500
            
    except Exception as e:
        print(f"Fix chunk_0 error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/debug/similarity', methods=['POST'])
def debug_similarity():
    """调试端点：测试查询与特定chunks的相似度"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        chunk_ids = data.get('chunk_ids', ['chunk_0', 'chunk_3'])
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # 生成查询embedding
        from embedding_generation import get_text_embeddings
        import numpy as np
        
        query_embeddings = get_text_embeddings([query])
        if not query_embeddings or not query_embeddings[0]:
            return jsonify({'error': 'Failed to generate query embedding'}), 500
        
        query_vec = np.array(query_embeddings[0])
        
        results = []
        for chunk_id in chunk_ids:
            if chunk_id not in CHUNK_MAP:
                continue
                
            chunk_text = CHUNK_MAP[chunk_id]
            
            # 获取或计算chunk embedding
            if chunk_id in CHUNK_EMBEDDINGS:
                chunk_embedding = CHUNK_EMBEDDINGS[chunk_id]
            else:
                chunk_embeddings = get_text_embeddings([chunk_text])
                if chunk_embeddings and chunk_embeddings[0]:
                    chunk_embedding = chunk_embeddings[0]
                    CHUNK_EMBEDDINGS[chunk_id] = chunk_embedding
                else:
                    continue
            
            chunk_vec = np.array(chunk_embedding)
            
            # 计算余弦相似度
            similarity = np.dot(query_vec, chunk_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec))
            distance = 1 - similarity
            
            results.append({
                'chunk_id': chunk_id,
                'similarity': float(similarity),
                'distance': float(distance),
                'text_preview': chunk_text[:200] + '...' if len(chunk_text) > 200 else chunk_text,
                'embedding_norm': float(np.linalg.norm(chunk_vec)),
                'query_norm': float(np.linalg.norm(query_vec))
            })
        
        # 按相似度排序
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        return jsonify({
            'query': query,
            'query_embedding_preview': query_embeddings[0][:5],
            'results': results
        })
        
    except Exception as e:
        print(f"Debug similarity error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 混合检索系统管理接口
@app.route('/hybrid/config', methods=['GET'])
def get_hybrid_config():
    """获取混合检索系统配置"""
    if not hybrid_retrieval:
        return jsonify({'error': '混合检索系统未初始化'}), 400
    
    try:
        stats = hybrid_retrieval.get_stats()
        return jsonify({
            'success': True,
            'config': stats.get('config', {}),
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/hybrid/config', methods=['POST'])
def update_hybrid_config():
    """更新混合检索系统配置"""
    if not hybrid_retrieval:
        return jsonify({'error': '混合检索系统未初始化'}), 400
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': '缺少配置数据'}), 400
        
        # 更新配置
        hybrid_retrieval.update_config(**data)
        
        # 获取更新后的配置
        stats = hybrid_retrieval.get_stats()
        
        return jsonify({
            'success': True,
            'message': '配置更新成功',
            'config': stats.get('config', {}),
            'updated_keys': list(data.keys())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/hybrid/stats', methods=['GET'])
def get_hybrid_stats():
    """获取混合检索系统统计信息"""
    if not hybrid_retrieval:
        return jsonify({'error': '混合检索系统未初始化'}), 400
    
    try:
        stats = hybrid_retrieval.get_stats()
        health = hybrid_retrieval.health_check()
        
        return jsonify({
            'success': True,
            'stats': stats,
            'health': health,
            'timestamp': int(time.time())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/hybrid/test', methods=['POST'])
def test_hybrid_retrieval():
    """测试混合检索系统"""
    if not hybrid_retrieval:
        return jsonify({'error': '混合检索系统未初始化'}), 400
    
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        strategy = data.get('strategy', 'hybrid_parallel')
        
        if not query:
            return jsonify({'error': '查询不能为空'}), 400
        
        # 将字符串策略转换为枚举
        strategy_map = {
            'fast_only': RetrievalStrategy.FAST_ONLY,
            'vertex_only': RetrievalStrategy.VERTEX_ONLY,
            'hybrid_parallel': RetrievalStrategy.HYBRID_PARALLEL,
            'adaptive': RetrievalStrategy.ADAPTIVE,
            'fallback': RetrievalStrategy.FALLBACK
        }
        
        strategy_enum = strategy_map.get(strategy, RetrievalStrategy.HYBRID_PARALLEL)
        
        # 执行测试检索
        start_time = time.time()
        results = hybrid_search(
            query=query,
            hybrid_retrieval=hybrid_retrieval,
            strategy=strategy_enum
        )
        elapsed_time = time.time() - start_time
        
        return jsonify({
            'success': True,
            'query': query,
            'strategy': strategy,
            'results': results,
            'elapsed_time': elapsed_time,
            'result_count': len(results),
            'stats': hybrid_retrieval.get_stats()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting RAG API Server (Fast Boot Mode)...")
    start_time = time.time()
    
    # 初始化GCS
    print("🔧 初始化GCS...")
    if not init_gcs():
        print("❌ Failed to initialize GCS. Exiting...")
        sys.exit(1)

    # 初始化Vertex AI
    print("🔧 初始化Vertex AI...")
    if not init_vertex_ai():
        print("❌ Failed to initialize Vertex AI. Exiting...")
        sys.exit(1)
    
    # 跳过向量搜索初始化，使用本地相似度搜索
    print("⚡ 跳过向量搜索初始化，使用本地相似度搜索...")
    
    # 初始化混合检索系统
    init_hybrid_retrieval()
    
    # 跳过文档加载，使用延迟加载
    print("⚡ 跳过文档加载，使用延迟加载机制...")
    
    # 初始化缓存管理器
    print("🔧 初始化缓存管理器...")
    cache_manager = CacheManager()
    
    startup_time = time.time() - start_time
    print(f"✅ 服务器启动完成 (耗时: {startup_time:.2f}秒)")
    
    print("📡 API endpoints:")
    print("  GET  /health - Health check (包含混合检索系统状态)")
    print("  POST /chat - Send message (使用混合检索系统)")
    print("  POST /upload - Upload file")
    print("  GET  /files - Get uploaded files")
    print("  GET  /upload/<id>/status - Get upload status")
    print("  GET  /files/<id>/preview - Preview file content")
    print("  GET  /files/<id>/chunks - Get file chunks")
    print("  GET  /files/<id>/download - Download file from GCS")
    print("  DELETE /files/<id>/delete - Delete file from GCS")
    print("  📊 混合检索系统管理:")
    print("    GET  /hybrid/config - 获取混合检索配置")
    print("    POST /hybrid/config - 更新混合检索配置")
    print("    GET  /hybrid/stats - 获取混合检索统计")
    print("    POST /hybrid/test - 测试混合检索系统")
    
    print(f"🌐 服务器运行在 http://localhost:8080")
    print(f"⚡ 文档将在首次API调用时自动加载")
    
    app.run(host='0.0.0.0', port=8080, debug=True) 