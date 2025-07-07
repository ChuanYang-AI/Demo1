import React, { createContext, useContext, useReducer, useEffect, ReactNode } from 'react';
import { ChatState, Conversation, Message, UploadedFile } from '../types/index';
import { chatAPI } from '../utils/api';
import { db } from '../utils/database';

interface ChatContextType {
  state: ChatState;
  createNewConversation: () => void;
  selectConversation: (id: string) => void;
  sendMessage: (content: string) => Promise<void>;
  uploadFile: (file: File) => Promise<void>;
  deleteConversation: (id: string) => void;
  deleteUploadedFile: (id: string) => void;
  clearError: () => void;
  syncFilesFromBackend: () => Promise<void>;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

type ChatAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'LOAD_CONVERSATIONS'; payload: Conversation[] }
  | { type: 'LOAD_UPLOADED_FILES'; payload: UploadedFile[] }
  | { type: 'ADD_CONVERSATION'; payload: Conversation }
  | { type: 'SELECT_CONVERSATION'; payload: string }
  | { type: 'UPDATE_CONVERSATION'; payload: { id: string; conversation: Partial<Conversation> } }
  | { type: 'DELETE_CONVERSATION'; payload: string }
  | { type: 'ADD_MESSAGE'; payload: { conversationId: string; message: Message } }
  | { type: 'UPDATE_MESSAGE'; payload: { conversationId: string; messageId: string; updates: Partial<Message> } }
  | { type: 'ADD_UPLOADED_FILE'; payload: UploadedFile }
  | { type: 'UPDATE_UPLOADED_FILE'; payload: { id: string; updates: Partial<UploadedFile> } }
  | { type: 'UPDATE_UPLOADED_FILE_ID'; payload: { oldId: string; newId: string; updates?: Partial<UploadedFile> } }
  | { type: 'DELETE_UPLOADED_FILE'; payload: string }
  | { type: 'SYNC_FILES_FROM_BACKEND'; payload: UploadedFile[] }
  | { type: 'LOAD_FILES'; payload: UploadedFile[] };

const initialState: ChatState = {
  conversations: [],
  currentConversationId: null,
  uploadedFiles: [],
  isLoading: false,
  error: null,
};

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    
    case 'LOAD_CONVERSATIONS':
      return {
        ...state,
        conversations: action.payload,
      };
    
    case 'LOAD_UPLOADED_FILES':
      return {
        ...state,
        uploadedFiles: action.payload,
      };
    
    case 'ADD_CONVERSATION':
      return {
        ...state,
        conversations: [action.payload, ...state.conversations],
      };
    
    case 'SELECT_CONVERSATION':
      return { ...state, currentConversationId: action.payload };
    
    case 'UPDATE_CONVERSATION':
      return {
        ...state,
        conversations: state.conversations.map(conv =>
          conv.id === action.payload.id
            ? { ...conv, ...action.payload.conversation, updatedAt: Date.now() }
            : conv
        ),
      };
    
    case 'DELETE_CONVERSATION':
      const remainingConversations = state.conversations.filter(conv => conv.id !== action.payload);
      const newCurrentId = state.currentConversationId === action.payload 
        ? (remainingConversations.length > 0 ? remainingConversations[0].id : null)
        : state.currentConversationId;
      
      return {
        ...state,
        conversations: remainingConversations,
        currentConversationId: newCurrentId,
      };
    
    case 'ADD_MESSAGE':
      return {
        ...state,
        conversations: state.conversations.map(conv =>
          conv.id === action.payload.conversationId
            ? { ...conv, messages: [...conv.messages, action.payload.message], updatedAt: Date.now() }
            : conv
        ),
      };
    
    case 'UPDATE_MESSAGE':
      return {
        ...state,
        conversations: state.conversations.map(conv =>
          conv.id === action.payload.conversationId
            ? {
                ...conv,
                messages: conv.messages.map(msg =>
                  msg.id === action.payload.messageId
                    ? { ...msg, ...action.payload.updates }
                    : msg
                ),
                updatedAt: Date.now(),
              }
            : conv
        ),
      };
    
    case 'ADD_UPLOADED_FILE':
      return {
        ...state,
        uploadedFiles: [action.payload, ...state.uploadedFiles],
      };
    
    case 'UPDATE_UPLOADED_FILE':
      return {
        ...state,
        uploadedFiles: state.uploadedFiles.map(file =>
          file.id === action.payload.id
            ? { ...file, ...action.payload.updates }
            : file
        ),
      };
    
    case 'UPDATE_UPLOADED_FILE_ID':
      return {
        ...state,
        uploadedFiles: state.uploadedFiles.map(file =>
          file.id === action.payload.oldId
            ? { ...file, id: action.payload.newId, ...(action.payload.updates || {}) }
            : file
        ),
      };
    
    case 'DELETE_UPLOADED_FILE':
      return {
        ...state,
        uploadedFiles: state.uploadedFiles.filter(file => file.id !== action.payload),
      };
    
    case 'SYNC_FILES_FROM_BACKEND':
      return {
        ...state,
        uploadedFiles: action.payload,
      };
    case 'LOAD_FILES':
      return {
        ...state,
        uploadedFiles: action.payload,
      };
    
    default:
      return state;
  }
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(chatReducer, initialState);

  // 从后端获取文件列表
  const loadFilesFromBackend = async () => {
    try {
      console.log('正在从后端获取文件列表...');
      const response = await fetch('http://localhost:8080/files');
      if (!response.ok) {
        throw new Error('Failed to fetch files from backend');
      }
      
      const data = await response.json();
      const backendFiles = data.files || [];
      
      // 转换后端文件格式为前端格式
      const files: UploadedFile[] = backendFiles.map((file: any) => ({
        id: file.id,
        name: file.name,
        size: file.size,
        type: file.type,
        uploadedAt: file.uploadedAt,
        processed: file.chunks ? file.chunks > 0 : false,
        chunks: file.chunks || 0,
        status: file.status === 'pending' ? 'pending' : 
                file.status === 'processing' ? 'processing' : 
                file.status === 'completed' ? 'completed' : 
                file.status === 'error' ? 'error' : 'pending',
        uploadProgress: 100, // 文件已上传到GCS
        processingProgress: file.status === 'completed' ? 100 : 
                           file.status === 'processing' ? (file.progress || 0) : 0,
        gcsUri: file.gcs_info?.gcs_uri || '',
        signedUrl: file.gcs_info?.signed_url || '',
        downloadUrl: file.gcs_info?.download_url || ''
      }));
      
      console.log(`从后端获取到 ${files.length} 个文件`);
      dispatch({ type: 'LOAD_FILES', payload: files });
      
    } catch (error) {
      console.error('从后端获取文件失败:', error);
      dispatch({ type: 'SET_ERROR', payload: '获取文件列表失败' });
    }
  };

  // 从后端同步文件状态
  const syncFilesFromBackend = async () => {
    try {
      console.log('正在同步文件状态...');
      
      // 获取后端文件列表
      const response = await fetch('http://localhost:8080/files');
      if (!response.ok) {
        throw new Error('Failed to fetch files from backend');
      }
      
      const data = await response.json();
      const backendFiles = data.files || [];
      
      // 获取前端本地数据库中的文件
      const localFiles = await db.getUploadedFiles();
      
      // 创建后端文件ID集合
      const backendFileIds = new Set(backendFiles.map((file: any) => file.id));
      
      // 删除本地数据库中不存在于后端的文件记录
      for (const localFile of localFiles) {
        if (!backendFileIds.has(localFile.id)) {
          console.log(`删除不存在的文件记录: ${localFile.name} (ID: ${localFile.id})`);
          await db.deleteUploadedFile(localFile.id);
        }
      }
      
      // 转换后端文件格式为前端格式
      const files: UploadedFile[] = backendFiles.map((file: any) => ({
        id: file.id,
        name: file.name,
        size: file.size,
        type: file.type,
        uploadedAt: file.uploadedAt,
        processed: file.chunks ? file.chunks > 0 : false,
        chunks: file.chunks || 0,
        status: file.status === 'pending' ? 'pending' : 
                file.status === 'processing' ? 'processing' : 
                file.status === 'completed' ? 'completed' : 
                file.status === 'error' ? 'error' : 'pending',
        uploadProgress: 100, // 文件已上传到GCS
        processingProgress: file.status === 'completed' ? 100 : 
                           file.status === 'processing' ? (file.progress || 0) : 0,
        gcsUri: file.gcs_info?.gcs_uri || '',
        signedUrl: file.gcs_info?.signed_url || '',
        downloadUrl: file.gcs_info?.download_url || ''
      }));
      
      console.log(`同步完成: ${files.length} 个文件`);
      console.log('文件状态统计:', {
        pending: files.filter(f => f.status === 'pending').length,
        processing: files.filter(f => f.status === 'processing').length,
        completed: files.filter(f => f.status === 'completed').length,
        error: files.filter(f => f.status === 'error').length
      });
      
      // 完全替换前端文件列表
      dispatch({ type: 'SYNC_FILES_FROM_BACKEND', payload: files });
      
    } catch (error) {
      console.error('同步文件状态失败:', error);
      dispatch({ type: 'SET_ERROR', payload: '同步文件状态失败' });
    }
  };

  // 初始化数据库并加载数据
  useEffect(() => {
    const initializeData = async () => {
      try {
        // 初始化数据库
        await db.init();
        
        // 加载对话历史
        const conversations = await db.getConversations();
        dispatch({ type: 'LOAD_CONVERSATIONS', payload: conversations });
        
        // 直接从后端获取文件列表，不使用本地数据库
        await loadFilesFromBackend();
        
        // 恢复当前对话
        const savedCurrentId = await db.getAppState('currentConversationId');
        if (savedCurrentId && conversations.some(conv => conv.id === savedCurrentId)) {
          dispatch({ type: 'SELECT_CONVERSATION', payload: savedCurrentId });
        }
        
        console.log(`已加载 ${conversations.length} 个对话`);
      } catch (error) {
        console.error('数据初始化失败:', error);
        // 回退到localStorage
        const savedConversations = localStorage.getItem('conversations');
        if (savedConversations) {
          dispatch({ type: 'LOAD_CONVERSATIONS', payload: JSON.parse(savedConversations) });
        }
      }
    };

    initializeData();
  }, []);

  // 保存对话到数据库
  useEffect(() => {
    const saveConversations = async () => {
      try {
        for (const conversation of state.conversations) {
          await db.saveConversation(conversation);
          // 保存对话中的消息
          for (const message of conversation.messages) {
            await db.saveMessage(message);
          }
        }
      } catch (error) {
        console.error('保存对话失败:', error);
        // 回退到localStorage
        localStorage.setItem('conversations', JSON.stringify(state.conversations));
      }
    };

    if (state.conversations.length > 0) {
      saveConversations();
    }
  }, [state.conversations]);

  // 保存当前对话ID
  useEffect(() => {
    const saveCurrentConversationId = async () => {
      try {
        if (state.currentConversationId) {
          await db.saveAppState('currentConversationId', state.currentConversationId);
        }
      } catch (error) {
        console.error('保存当前对话ID失败:', error);
        // 回退到localStorage
        if (state.currentConversationId) {
          localStorage.setItem('currentConversationId', state.currentConversationId);
        }
      }
    };

    saveCurrentConversationId();
  }, [state.currentConversationId]);

  const createNewConversation = () => {
    const newConversation: Conversation = {
      id: Date.now().toString(),
      title: '新对话',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    dispatch({ type: 'ADD_CONVERSATION', payload: newConversation });
    dispatch({ type: 'SELECT_CONVERSATION', payload: newConversation.id });
  };

  const selectConversation = (id: string) => {
    dispatch({ type: 'SELECT_CONVERSATION', payload: id });
  };

  const sendMessage = async (content: string) => {
    let conversationId = state.currentConversationId;
    let isNewConversation = false;
    
    if (!conversationId) {
      // Create new conversation and get its ID
      const newConversation: Conversation = {
        id: Date.now().toString(),
        title: '新对话',
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      dispatch({ type: 'ADD_CONVERSATION', payload: newConversation });
      dispatch({ type: 'SELECT_CONVERSATION', payload: newConversation.id });
      conversationId = newConversation.id;
      isNewConversation = true;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      content,
      role: 'user',
      timestamp: Date.now(),
    };

    // Add user message
    dispatch({
      type: 'ADD_MESSAGE',
      payload: { conversationId, message: userMessage },
    });

    // Update conversation title if it's the first message in a new conversation
    if (isNewConversation) {
      const title = content.length > 20 ? content.substring(0, 20) + '...' : content;
      dispatch({
        type: 'UPDATE_CONVERSATION',
        payload: { id: conversationId, conversation: { title } },
      });
    }

    // Add loading message
    const loadingMessage: Message = {
      id: (Date.now() + 1).toString(),
      content: '正在思考中...',
      role: 'assistant',
      timestamp: Date.now(),
      isLoading: true,
    };

    dispatch({
      type: 'ADD_MESSAGE',
      payload: { conversationId, message: loadingMessage },
    });

    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const response = await chatAPI.sendMessage(content);
      
      // Update loading message with response
      const transformedSources = response.sources?.map((source: any, index: number) => ({
        id: source.chunk_id || source.id || `source_${index}`,
        content: source.content_preview || source.content || '',
        score: source.similarity || source.score || 0,
        fileName: source.file_name || source.fileName || '法律知识问答.docx',
        chunkIndex: source.chunk_id ? parseInt(source.chunk_id.split('_').pop() || '0') : index,
      })) || [];

      dispatch({
        type: 'UPDATE_MESSAGE',
        payload: {
          conversationId,
          messageId: loadingMessage.id,
          updates: {
            content: response.answer,
            isLoading: false,
            sources: transformedSources,
            processingTime: response.processingTime,
            // 新增答案来源信息
            answerSource: response.answerSource || 'error',
            confidence: response.confidence || 0,
            useRag: response.useRag || false,
            maxSimilarity: response.maxSimilarity || 0,
            qualityMetrics: response.qualityMetrics || {
              relevanceScore: 0,
              sourceCount: 0,
              avgSimilarity: 0
            },
          },
        },
      });
    } catch (error: any) {
      console.error('Failed to send message:', error);
      let errorMessage = '发送消息失败';
      
      if (error.error) {
        errorMessage = error.error;
      } else if (error.message) {
        errorMessage = error.message;
      } else if (typeof error === 'string') {
        errorMessage = error;
      }
      
      dispatch({
        type: 'UPDATE_MESSAGE',
        payload: {
          conversationId,
          messageId: loadingMessage.id,
          updates: {
            content: `抱歉，发生了错误：${errorMessage}`,
            isLoading: false,
          },
        },
      });
      dispatch({ type: 'SET_ERROR', payload: errorMessage });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const uploadFile = async (file: File) => {
    const uploadedFile: UploadedFile = {
      id: Date.now().toString(),
      name: file.name,
      size: file.size,
      type: file.type,
      uploadedAt: Date.now(),
      processed: false,
      uploadProgress: 0,
      processingProgress: 0,
      status: 'uploading',
    };

    // 添加文件到列表
    dispatch({ type: 'ADD_UPLOADED_FILE', payload: uploadedFile });

    try {
      dispatch({ type: 'SET_ERROR', payload: null });

      // 开始上传，带进度回调
      const response = await chatAPI.uploadFile(file, (progress) => {
        dispatch({
          type: 'UPDATE_UPLOADED_FILE',
          payload: {
            id: uploadedFile.id,
            updates: {
              uploadProgress: progress,
            },
          },
        });
      });

      // 上传完成，更新为后端返回的真实文件ID，并开始处理
      dispatch({
        type: 'UPDATE_UPLOADED_FILE_ID',
        payload: {
          oldId: uploadedFile.id,
          newId: response.fileId,
          updates: {
            uploadProgress: 100,
            status: 'processing',
            processingProgress: 0,
            // 保存GCS信息
            gcsUri: response.gcs_uri,
            signedUrl: response.signed_url,
          },
        },
      });

      // 开始轮询处理状态
      const pollProcessingStatus = async () => {
        let attempts = 0;
        const maxAttempts = 120; // 最多轮询2分钟 (120 * 1000ms)
        
        const poll = async () => {
          try {
            const statusResponse = await chatAPI.getUploadStatus(response.fileId);
            
            // 更新处理进度
            dispatch({
              type: 'UPDATE_UPLOADED_FILE',
              payload: {
                id: response.fileId,
                updates: {
                  processingProgress: statusResponse.progress || 0,
                  status: statusResponse.status === 'completed' ? 'completed' : 
                         statusResponse.status === 'error' ? 'error' : 'processing',
                  chunks: statusResponse.chunks || 0,
                  error: statusResponse.error || undefined,
                },
              },
            });

            // 检查是否完成
            if (statusResponse.status === 'completed') {
              dispatch({
                type: 'UPDATE_UPLOADED_FILE',
                payload: {
                  id: response.fileId,
                  updates: {
                    processed: true,
                    processingProgress: 100,
                    status: 'completed',
                  },
                },
              });
              console.log(`文件处理完成: ${response.fileName} - ${statusResponse.chunks} 个文本块`);
              return; // 完成，停止轮询
            }

            // 检查是否出错
            if (statusResponse.status === 'error') {
              dispatch({
                type: 'UPDATE_UPLOADED_FILE',
                payload: {
                  id: response.fileId,
                  updates: {
                    status: 'error',
                    error: statusResponse.error || '处理失败',
                  },
                },
              });
              return; // 出错，停止轮询
            }

            // 继续轮询
            attempts++;
            if (attempts < maxAttempts) {
              setTimeout(poll, 1000); // 1秒后再次查询
            } else {
              // 超时处理
              dispatch({
                type: 'UPDATE_UPLOADED_FILE',
                payload: {
                  id: response.fileId,
                  updates: {
                    status: 'error',
                    error: '处理超时，请重试',
                  },
                },
              });
            }
          } catch (error) {
            console.error('状态查询失败:', error);
            attempts++;
            if (attempts < maxAttempts) {
              setTimeout(poll, 2000); // 出错时等待2秒再重试
            } else {
              dispatch({
                type: 'UPDATE_UPLOADED_FILE',
                payload: {
                  id: response.fileId,
                  updates: {
                    status: 'error',
                    error: '无法获取处理状态',
                  },
                },
              });
            }
          }
        };

        // 开始轮询
        setTimeout(poll, 1000); // 1秒后开始第一次查询
      };

      pollProcessingStatus();

    } catch (error: any) {
      console.error('Failed to upload file:', error);
      dispatch({
        type: 'UPDATE_UPLOADED_FILE',
        payload: {
          id: uploadedFile.id,
          updates: {
            status: 'error',
            error: error.error || '文件上传失败',
          },
        },
      });
      dispatch({ type: 'SET_ERROR', payload: error.error || '文件上传失败' });
    }
  };

  const deleteConversation = async (id: string) => {
    dispatch({ type: 'DELETE_CONVERSATION', payload: id });
    try {
      await db.deleteConversation(id);
    } catch (error) {
      console.error('删除对话失败:', error);
    }
  };

  const deleteUploadedFile = async (id: string) => {
    dispatch({ type: 'DELETE_UPLOADED_FILE', payload: id });
    try {
      await db.deleteUploadedFile(id);
    } catch (error) {
      console.error('删除文件记录失败:', error);
    }
  };

  const clearError = () => {
    dispatch({ type: 'SET_ERROR', payload: null });
  };

  return (
    <ChatContext.Provider
      value={{
        state,
        createNewConversation,
        selectConversation,
        sendMessage,
        uploadFile,
        deleteConversation,
        deleteUploadedFile,
        clearError,
        syncFilesFromBackend,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext() {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
} 