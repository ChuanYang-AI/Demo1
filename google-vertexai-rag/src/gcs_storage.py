#!/usr/bin/env python3
"""
Google Cloud Storage 文件管理模块
"""

import os
import io
import json
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from google.cloud import storage
from google.cloud.exceptions import NotFound
import google.api_core.retry

class GCSFileManager:
    """Google Cloud Storage 文件管理器"""
    
    def __init__(self, project_id: str, bucket_name: str, service_account_path: Optional[str] = None):
        """
        初始化GCS文件管理器
        
        Args:
            project_id: Google Cloud项目ID
            bucket_name: 存储桶名称
            service_account_path: 服务账号密钥文件路径（可选，如果为None则使用环境变量）
        """
        self.project_id = project_id
        self.bucket_name = bucket_name
        self.service_account_path = service_account_path
        
        # 设置服务账号认证（仅当提供了路径时）
        if service_account_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
        
        # 初始化客户端
        self.client = storage.Client(project=project_id)
        self.bucket = self._get_or_create_bucket()
        
    def _get_or_create_bucket(self) -> storage.Bucket:
        """获取或创建存储桶"""
        try:
            bucket = self.client.bucket(self.bucket_name)
            # 检查桶是否存在
            bucket.reload()
            print(f"Using existing bucket: {self.bucket_name}")
            return bucket
        except NotFound:
            # 创建新桶
            bucket = self.client.create_bucket(self.bucket_name, location="us-central1")
            print(f"Created new bucket: {self.bucket_name}")
            return bucket
    
    def upload_file(self, file_content: bytes, file_name: str, content_type: str, 
                   metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        上传文件到GCS
        
        Args:
            file_content: 文件内容（字节）
            file_name: 文件名
            content_type: 文件MIME类型
            metadata: 文件元数据
            
        Returns:
            上传结果信息
        """
        try:
            # 生成唯一的文件路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_id = f"{timestamp}_{hash(file_name) % 10000:04d}"
            blob_name = f"uploads/{file_id}/{file_name}"
            
            # 创建blob对象
            blob = self.bucket.blob(blob_name)
            
            # 设置元数据
            if metadata:
                blob.metadata = metadata
            
            # 上传文件 (添加超时和重试配置)
            blob.upload_from_string(
                file_content,
                content_type=content_type,
                timeout=120,  # 2分钟超时
                retry=google.api_core.retry.Retry(deadline=180)  # 3分钟总重试时间
            )
            
            # 生成签名URL（7天有效期）
            signed_url = blob.generate_signed_url(
                expiration=datetime.utcnow() + timedelta(days=7),
                method="GET"
            )
            
            upload_info = {
                'file_id': file_id,
                'blob_name': blob_name,
                'file_name': file_name,
                'size': len(file_content),
                'content_type': content_type,
                'uploaded_at': datetime.utcnow().isoformat(),
                'public_url': blob.public_url,
                'signed_url': signed_url,
                'gs_uri': f"gs://{self.bucket_name}/{blob_name}"
            }
            
            print(f"File uploaded successfully: {blob_name}")
            return upload_info
            
        except Exception as e:
            print(f"Upload error: {e}")
            raise
    
    def download_file(self, file_id: str, file_name: str) -> bytes:
        """
        从GCS下载文件
        
        Args:
            file_id: 文件ID
            file_name: 文件名
            
        Returns:
            文件内容（字节）
        """
        try:
            blob_name = f"uploads/{file_id}/{file_name}"
            blob = self.bucket.blob(blob_name)
            
            if not blob.exists():
                raise FileNotFoundError(f"File not found: {blob_name}")
            
            content = blob.download_as_bytes()
            print(f"File downloaded successfully: {blob_name}")
            return content
            
        except Exception as e:
            print(f"Download error: {e}")
            raise
    
    def get_file_info(self, file_id: str, file_name: str) -> Dict[str, Any]:
        """
        获取文件信息
        
        Args:
            file_id: 文件ID
            file_name: 文件名
            
        Returns:
            文件信息
        """
        try:
            blob_name = f"uploads/{file_id}/{file_name}"
            blob = self.bucket.blob(blob_name)
            
            if not blob.exists():
                raise FileNotFoundError(f"File not found: {blob_name}")
            
            blob.reload()
            
            # 生成新的签名URL
            signed_url = blob.generate_signed_url(
                expiration=datetime.utcnow() + timedelta(days=7),
                method="GET"
            )
            
            file_info = {
                'file_id': file_id,
                'blob_name': blob_name,
                'file_name': file_name,
                'size': blob.size,
                'content_type': blob.content_type,
                'created': blob.time_created.isoformat() if blob.time_created else None,
                'updated': blob.updated.isoformat() if blob.updated else None,
                'metadata': blob.metadata or {},
                'public_url': blob.public_url,
                'signed_url': signed_url,
                'gs_uri': f"gs://{self.bucket_name}/{blob_name}"
            }
            
            return file_info
            
        except Exception as e:
            print(f"Get file info error: {e}")
            raise
    
    def delete_file(self, file_id: str, file_name: str) -> bool:
        """
        删除文件
        
        Args:
            file_id: 文件ID
            file_name: 文件名
            
        Returns:
            删除是否成功
        """
        try:
            blob_name = f"uploads/{file_id}/{file_name}"
            blob = self.bucket.blob(blob_name)
            
            if blob.exists():
                blob.delete()
                print(f"File deleted successfully: {blob_name}")
                return True
            else:
                print(f"File not found for deletion: {blob_name}")
                return False
                
        except Exception as e:
            print(f"Delete error: {e}")
            return False
    
    def list_files(self, prefix: str = "uploads/") -> List[Dict[str, Any]]:
        """
        列出存储桶中的文件
        
        Args:
            prefix: 文件路径前缀
            
        Returns:
            文件列表
        """
        try:
            blobs = self.client.list_blobs(self.bucket, prefix=prefix)
            
            files = []
            for blob in blobs:
                # 解析文件路径获取file_id和文件名
                path_parts = blob.name.split('/')
                if len(path_parts) >= 3:  # uploads/file_id/filename
                    file_id = path_parts[1]
                    file_name = '/'.join(path_parts[2:])  # 支持嵌套路径
                    
                    files.append({
                        'file_id': file_id,
                        'file_name': file_name,
                        'blob_name': blob.name,
                        'size': blob.size,
                        'content_type': blob.content_type,
                        'created': blob.time_created.isoformat() if blob.time_created else None,
                        'updated': blob.updated.isoformat() if blob.updated else None,
                        'public_url': blob.public_url,
                        'gs_uri': f"gs://{self.bucket_name}/{blob.name}"
                    })
            
            return files
            
        except Exception as e:
            print(f"List files error: {e}")
            return []
    
    def save_to_temp_file(self, file_id: str, file_name: str) -> str:
        """
        将GCS文件下载到临时文件
        
        Args:
            file_id: 文件ID
            file_name: 文件名
            
        Returns:
            临时文件路径
        """
        try:
            content = self.download_file(file_id, file_name)
            
            # 创建临时文件
            suffix = os.path.splitext(file_name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            print(f"File saved to temp: {temp_path}")
            return temp_path
            
        except Exception as e:
            print(f"Save to temp error: {e}")
            raise
    
    def get_signed_url(self, file_id: str, file_name: str, expiration_hours: int = 24) -> str:
        """
        获取文件的签名URL
        
        Args:
            file_id: 文件ID
            file_name: 文件名
            expiration_hours: 过期时间（小时）
            
        Returns:
            签名URL
        """
        try:
            blob_name = f"uploads/{file_id}/{file_name}"
            blob = self.bucket.blob(blob_name)
            
            if not blob.exists():
                raise FileNotFoundError(f"File not found: {blob_name}")
            
            signed_url = blob.generate_signed_url(
                expiration=datetime.utcnow() + timedelta(hours=expiration_hours),
                method="GET"
            )
            
            return signed_url
            
        except Exception as e:
            print(f"Get signed URL error: {e}")
            raise 
 
 
 