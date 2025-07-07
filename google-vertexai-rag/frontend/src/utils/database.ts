import { Conversation, Message, UploadedFile } from '../types/index';

const DB_NAME = 'VertexAI_RAG_DB';
const DB_VERSION = 1;

// 数据库表名
const STORES = {
  CONVERSATIONS: 'conversations',
  MESSAGES: 'messages',
  UPLOADED_FILES: 'uploadedFiles',
  APP_STATE: 'appState'
};

class DatabaseManager {
  private db: IDBDatabase | null = null;

  async init(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;

        // 创建对话表
        if (!db.objectStoreNames.contains(STORES.CONVERSATIONS)) {
          const conversationStore = db.createObjectStore(STORES.CONVERSATIONS, { keyPath: 'id' });
          conversationStore.createIndex('createdAt', 'createdAt', { unique: false });
        }

        // 创建消息表
        if (!db.objectStoreNames.contains(STORES.MESSAGES)) {
          const messageStore = db.createObjectStore(STORES.MESSAGES, { keyPath: 'id' });
          messageStore.createIndex('conversationId', 'conversationId', { unique: false });
          messageStore.createIndex('timestamp', 'timestamp', { unique: false });
        }

        // 创建上传文件表
        if (!db.objectStoreNames.contains(STORES.UPLOADED_FILES)) {
          const fileStore = db.createObjectStore(STORES.UPLOADED_FILES, { keyPath: 'id' });
          fileStore.createIndex('uploadedAt', 'uploadedAt', { unique: false });
          fileStore.createIndex('status', 'status', { unique: false });
        }

        // 创建应用状态表
        if (!db.objectStoreNames.contains(STORES.APP_STATE)) {
          db.createObjectStore(STORES.APP_STATE, { keyPath: 'key' });
        }
      };
    });
  }

  // 对话相关操作
  async saveConversation(conversation: Conversation): Promise<void> {
    const transaction = this.db!.transaction([STORES.CONVERSATIONS], 'readwrite');
    const store = transaction.objectStore(STORES.CONVERSATIONS);
    await store.put(conversation);
  }

  async getConversations(): Promise<Conversation[]> {
    const transaction = this.db!.transaction([STORES.CONVERSATIONS], 'readonly');
    const store = transaction.objectStore(STORES.CONVERSATIONS);
    const index = store.index('createdAt');
    
    return new Promise((resolve, reject) => {
      const request = index.getAll();
      request.onsuccess = () => resolve(request.result.sort((a, b) => b.createdAt - a.createdAt));
      request.onerror = () => reject(request.error);
    });
  }

  async deleteConversation(id: string): Promise<void> {
    const transaction = this.db!.transaction([STORES.CONVERSATIONS, STORES.MESSAGES], 'readwrite');
    
    // 删除对话
    const conversationStore = transaction.objectStore(STORES.CONVERSATIONS);
    await conversationStore.delete(id);
    
    // 删除相关消息
    const messageStore = transaction.objectStore(STORES.MESSAGES);
    const index = messageStore.index('conversationId');
    const request = index.openCursor(IDBKeyRange.only(id));
    
    request.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest).result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };
  }

  // 消息相关操作
  async saveMessage(message: Message): Promise<void> {
    const transaction = this.db!.transaction([STORES.MESSAGES], 'readwrite');
    const store = transaction.objectStore(STORES.MESSAGES);
    await store.put(message);
  }

  async getMessagesByConversation(conversationId: string): Promise<Message[]> {
    const transaction = this.db!.transaction([STORES.MESSAGES], 'readonly');
    const store = transaction.objectStore(STORES.MESSAGES);
    const index = store.index('conversationId');
    
    return new Promise((resolve, reject) => {
      const request = index.getAll(conversationId);
      request.onsuccess = () => resolve(request.result.sort((a, b) => a.timestamp - b.timestamp));
      request.onerror = () => reject(request.error);
    });
  }

  async updateMessage(message: Message): Promise<void> {
    await this.saveMessage(message);
  }

  // 文件相关操作
  async saveUploadedFile(file: UploadedFile): Promise<void> {
    const transaction = this.db!.transaction([STORES.UPLOADED_FILES], 'readwrite');
    const store = transaction.objectStore(STORES.UPLOADED_FILES);
    await store.put(file);
  }

  async getUploadedFiles(): Promise<UploadedFile[]> {
    const transaction = this.db!.transaction([STORES.UPLOADED_FILES], 'readonly');
    const store = transaction.objectStore(STORES.UPLOADED_FILES);
    const index = store.index('uploadedAt');
    
    return new Promise((resolve, reject) => {
      const request = index.getAll();
      request.onsuccess = () => resolve(request.result.sort((a, b) => b.uploadedAt - a.uploadedAt));
      request.onerror = () => reject(request.error);
    });
  }

  async updateUploadedFile(file: UploadedFile): Promise<void> {
    await this.saveUploadedFile(file);
  }

  async deleteUploadedFile(id: string): Promise<void> {
    const transaction = this.db!.transaction([STORES.UPLOADED_FILES], 'readwrite');
    const store = transaction.objectStore(STORES.UPLOADED_FILES);
    await store.delete(id);
  }

  async clearUploadedFiles(): Promise<void> {
    const transaction = this.db!.transaction([STORES.UPLOADED_FILES], 'readwrite');
    const store = transaction.objectStore(STORES.UPLOADED_FILES);
    await store.clear();
  }

  // 应用状态相关操作
  async saveAppState(key: string, value: any): Promise<void> {
    const transaction = this.db!.transaction([STORES.APP_STATE], 'readwrite');
    const store = transaction.objectStore(STORES.APP_STATE);
    await store.put({ key, value, timestamp: Date.now() });
  }

  async getAppState(key: string): Promise<any> {
    const transaction = this.db!.transaction([STORES.APP_STATE], 'readonly');
    const store = transaction.objectStore(STORES.APP_STATE);
    
    return new Promise((resolve, reject) => {
      const request = store.get(key);
      request.onsuccess = () => resolve(request.result?.value || null);
      request.onerror = () => reject(request.error);
    });
  }

  // 清理过期数据
  async cleanupOldData(daysToKeep: number = 30): Promise<void> {
    const cutoffDate = Date.now() - (daysToKeep * 24 * 60 * 60 * 1000);
    
    // 清理旧对话
    const conversationTransaction = this.db!.transaction([STORES.CONVERSATIONS], 'readwrite');
    const conversationStore = conversationTransaction.objectStore(STORES.CONVERSATIONS);
    const conversationIndex = conversationStore.index('createdAt');
    
    const conversationRequest = conversationIndex.openCursor(IDBKeyRange.upperBound(cutoffDate));
    conversationRequest.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest).result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };

    // 清理旧文件记录
    const fileTransaction = this.db!.transaction([STORES.UPLOADED_FILES], 'readwrite');
    const fileStore = fileTransaction.objectStore(STORES.UPLOADED_FILES);
    const fileIndex = fileStore.index('uploadedAt');
    
    const fileRequest = fileIndex.openCursor(IDBKeyRange.upperBound(cutoffDate));
    fileRequest.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest).result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };
  }

  // 获取数据库统计信息
  async getStats(): Promise<{
    conversations: number;
    messages: number;
    uploadedFiles: number;
    dbSize: string;
  }> {
    const conversations = await this.getConversations();
    const files = await this.getUploadedFiles();
    
    let messageCount = 0;
    for (const conv of conversations) {
      const messages = await this.getMessagesByConversation(conv.id);
      messageCount += messages.length;
    }

    return {
      conversations: conversations.length,
      messages: messageCount,
      uploadedFiles: files.length,
      dbSize: 'N/A' // IndexedDB 不提供直接的大小查询
    };
  }
}

// 创建全局数据库实例
export const db = new DatabaseManager();

// 初始化数据库
export const initDatabase = async (): Promise<void> => {
  try {
    await db.init();
    console.log('数据库初始化成功');
  } catch (error) {
    console.error('数据库初始化失败:', error);
    throw error;
  }
};

export default db; 