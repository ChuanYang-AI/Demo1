"""
缓存管理器 - 提供文档块和embedding的持久化缓存
"""
import os
import json
import pickle
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

class CacheManager:
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = cache_dir
        self.chunks_cache_file = os.path.join(cache_dir, "chunks_cache.json")
        self.embeddings_cache_file = os.path.join(cache_dir, "embeddings_cache.pkl")
        self.file_metadata_cache = os.path.join(cache_dir, "file_metadata.json")
        
        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)
        
        # 初始化缓存数据
        self.chunks_cache = self._load_chunks_cache()
        self.embeddings_cache = self._load_embeddings_cache()
        self.file_metadata = self._load_file_metadata()
    
    def _load_chunks_cache(self) -> Dict[str, Any]:
        """加载文档块缓存"""
        try:
            if os.path.exists(self.chunks_cache_file):
                with open(self.chunks_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load chunks cache: {e}")
        return {}
    
    def _load_embeddings_cache(self) -> Dict[str, List[float]]:
        """加载embedding缓存"""
        try:
            if os.path.exists(self.embeddings_cache_file):
                with open(self.embeddings_cache_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            print(f"Failed to load embeddings cache: {e}")
        return {}
    
    def _load_file_metadata(self) -> Dict[str, Any]:
        """加载文件元数据缓存"""
        try:
            if os.path.exists(self.file_metadata_cache):
                with open(self.file_metadata_cache, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Failed to load file metadata: {e}")
        return {}
    
    def _save_chunks_cache(self):
        """保存文档块缓存"""
        try:
            with open(self.chunks_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.chunks_cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save chunks cache: {e}")
    
    def _save_embeddings_cache(self):
        """保存embedding缓存"""
        try:
            with open(self.embeddings_cache_file, 'wb') as f:
                pickle.dump(self.embeddings_cache, f)
        except Exception as e:
            print(f"Failed to save embeddings cache: {e}")
    
    def _save_file_metadata(self):
        """保存文件元数据缓存"""
        try:
            with open(self.file_metadata_cache, 'w', encoding='utf-8') as f:
                json.dump(self.file_metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save file metadata: {e}")
    
    def get_file_hash(self, file_path: str) -> str:
        """计算文件hash用于缓存key"""
        try:
            with open(file_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            return file_hash
        except Exception as e:
            print(f"Failed to calculate file hash: {e}")
            return ""
    
    def get_text_hash(self, text: str) -> str:
        """计算文本hash用于缓存key"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def cache_chunks(self, file_id: str, chunks: List[str], file_hash: str = None):
        """缓存文档块"""
        cache_key = file_id
        cache_data = {
            "chunks": chunks,
            "chunk_count": len(chunks),
            "file_hash": file_hash,
            "cached_at": datetime.now().isoformat(),
            "timestamp": int(time.time())
        }
        
        self.chunks_cache[cache_key] = cache_data
        self._save_chunks_cache()
        print(f"Cached {len(chunks)} chunks for {file_id}")
    
    def get_cached_chunks(self, file_id: str, file_hash: str = None) -> Optional[List[str]]:
        """获取缓存的文档块"""
        cache_key = file_id
        
        if cache_key in self.chunks_cache:
            cached_data = self.chunks_cache[cache_key]
            
            # 如果提供了文件hash，验证缓存是否有效
            if file_hash and cached_data.get("file_hash") != file_hash:
                print(f"Cache invalid for {file_id}: hash mismatch")
                return None
            
            chunks = cached_data.get("chunks", [])
            print(f"Retrieved {len(chunks)} cached chunks for {file_id}")
            return chunks
        
        return None
    
    def cache_embeddings(self, chunk_embeddings: Dict[str, List[float]]):
        """缓存embeddings"""
        self.embeddings_cache.update(chunk_embeddings)
        self._save_embeddings_cache()
        print(f"Cached embeddings for {len(chunk_embeddings)} chunks")
    
    def get_cached_embeddings(self, chunk_ids: List[str]) -> Dict[str, List[float]]:
        """获取缓存的embeddings"""
        cached_embeddings = {}
        for chunk_id in chunk_ids:
            if chunk_id in self.embeddings_cache:
                cached_embeddings[chunk_id] = self.embeddings_cache[chunk_id]
        
        if cached_embeddings:
            print(f"Retrieved {len(cached_embeddings)} cached embeddings")
        
        return cached_embeddings
    
    def cache_file_metadata(self, file_id: str, metadata: Dict[str, Any]):
        """缓存文件元数据"""
        metadata["cached_at"] = datetime.now().isoformat()
        metadata["timestamp"] = int(time.time())
        self.file_metadata[file_id] = metadata
        self._save_file_metadata()
    
    def get_cached_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存的文件元数据"""
        return self.file_metadata.get(file_id)
    
    def has_cached_data(self, file_id: str) -> bool:
        """检查是否有缓存数据"""
        return file_id in self.chunks_cache
    
    def clear_cache(self, file_id: str = None):
        """清理缓存"""
        if file_id:
            # 清理特定文件的缓存
            if file_id in self.chunks_cache:
                del self.chunks_cache[file_id]
            
            # 清理相关的embedding缓存
            keys_to_remove = [k for k in self.embeddings_cache.keys() 
                             if k.startswith(f"file_{file_id}_")]
            for key in keys_to_remove:
                del self.embeddings_cache[key]
            
            if file_id in self.file_metadata:
                del self.file_metadata[file_id]
            
            self._save_chunks_cache()
            self._save_embeddings_cache()
            self._save_file_metadata()
            print(f"Cleared cache for {file_id}")
        else:
            # 清理所有缓存
            self.chunks_cache.clear()
            self.embeddings_cache.clear()
            self.file_metadata.clear()
            self._save_chunks_cache()
            self._save_embeddings_cache()
            self._save_file_metadata()
            print("Cleared all cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "cached_files": len(self.chunks_cache),
            "cached_embeddings": len(self.embeddings_cache),
            "cached_metadata": len(self.file_metadata),
            "cache_size": {
                "chunks": sum(len(data.get("chunks", [])) for data in self.chunks_cache.values()),
                "embeddings": len(self.embeddings_cache),
                "metadata": len(self.file_metadata)
            }
        }
    
    def cleanup_old_cache(self, max_age_days: int = 30):
        """清理过期缓存"""
        current_time = int(time.time())
        max_age_seconds = max_age_days * 24 * 60 * 60
        
        # 清理过期的chunks缓存
        expired_chunks = []
        for file_id, data in self.chunks_cache.items():
            if current_time - data.get("timestamp", 0) > max_age_seconds:
                expired_chunks.append(file_id)
        
        for file_id in expired_chunks:
            del self.chunks_cache[file_id]
        
        # 清理过期的文件元数据
        expired_metadata = []
        for file_id, data in self.file_metadata.items():
            if current_time - data.get("timestamp", 0) > max_age_seconds:
                expired_metadata.append(file_id)
        
        for file_id in expired_metadata:
            del self.file_metadata[file_id]
        
        if expired_chunks or expired_metadata:
            self._save_chunks_cache()
            self._save_file_metadata()
            print(f"Cleaned up {len(expired_chunks)} expired chunk caches and {len(expired_metadata)} expired metadata") 