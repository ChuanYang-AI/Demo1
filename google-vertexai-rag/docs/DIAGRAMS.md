# 图表汇总

本文档汇总了 Google Vertex AI RAG 智能问答系统的所有架构图、流程图和技术图表，便于快速理解系统设计。

## 📋 图表索引

### 🏗️ 架构图表
1. [系统整体架构](#系统整体架构)
2. [技术架构栈](#技术架构栈)
3. [数据流架构](#数据流架构)
4. [向量数据库架构](#向量数据库架构)
5. [部署架构](#部署架构)

### 🔄 流程图表
1. [文档上传处理流程](#文档上传处理流程)
2. [智能问答流程](#智能问答流程)
3. [混合检索算法流程](#混合检索算法流程)
4. [部署流程](#部署流程)
5. [贡献流程](#贡献流程)

### 🌐 API图表
1. [API业务流程](#api业务流程)
2. [API请求响应流程](#api请求响应流程)

### 📊 性能与监控图表
1. [缓存架构](#缓存架构)
2. [负载均衡架构](#负载均衡架构)
3. [监控架构](#监控架构)
4. [安全架构](#安全架构)

---

## 🏗️ 架构图表

### 系统整体架构

```mermaid
graph TB
    subgraph "用户层 User Layer"
        U1[Web浏览器]
        U2[移动应用]
        U3[API客户端]
    end
    
    subgraph "前端层 Frontend Layer"
        FE[React应用]
        FE --> FE1[路由管理]
        FE --> FE2[状态管理]
        FE --> FE3[UI组件]
        FE --> FE4[API通信]
    end
    
    subgraph "网关层 Gateway Layer"
        LB[负载均衡器]
        RP[反向代理 Nginx]
        LB --> RP
    end
    
    subgraph "应用层 Application Layer"
        API[Flask API服务器]
        API --> API1[文件上传处理]
        API --> API2[智能问答引擎]
        API --> API3[健康检查]
        API --> API4[配置管理]
    end
    
    subgraph "业务逻辑层 Business Logic Layer"
        BL1[文档处理服务]
        BL2[混合检索引擎]
        BL3[向量生成服务]
        BL4[答案生成服务]
        BL5[缓存管理服务]
    end
    
    subgraph "数据访问层 Data Access Layer"
        DA1[FAISS接口]
        DA2[Vertex AI接口]
        DA3[GCS接口]
        DA4[缓存接口]
    end
    
    subgraph "存储层 Storage Layer"
        S1[FAISS向量数据库]
        S2[Google Cloud Storage]
        S3[本地缓存系统]
        S4[元数据存储]
    end
    
    subgraph "外部服务层 External Services"
        EX1[Google Vertex AI]
        EX2[Gemini Pro模型]
        EX3[Text Embedding模型]
        EX4[监控服务]
    end
    
    %% 连接关系
    U1 --> FE
    U2 --> FE
    U3 --> API
    FE --> LB
    LB --> API
    RP --> API
    
    API --> BL1
    API --> BL2
    API --> BL3
    API --> BL4
    API --> BL5
    
    BL1 --> DA3
    BL2 --> DA1
    BL2 --> DA2
    BL3 --> DA2
    BL4 --> DA2
    BL5 --> DA4
    
    DA1 --> S1
    DA2 --> EX1
    DA3 --> S2
    DA4 --> S3
    
    EX1 --> EX2
    EX1 --> EX3
    
    %% 样式
    classDef userLayer fill:#e1f5fe
    classDef frontendLayer fill:#f3e5f5
    classDef gatewayLayer fill:#e8f5e8
    classDef appLayer fill:#fff3e0
    classDef businessLayer fill:#fce4ec
    classDef dataLayer fill:#f1f8e9
    classDef storageLayer fill:#e3f2fd
    classDef externalLayer fill:#fff8e1
    
    class U1,U2,U3 userLayer
    class FE,FE1,FE2,FE3,FE4 frontendLayer
    class LB,RP gatewayLayer
    class API,API1,API2,API3,API4 appLayer
    class BL1,BL2,BL3,BL4,BL5 businessLayer
    class DA1,DA2,DA3,DA4 dataLayer
    class S1,S2,S3,S4 storageLayer
    class EX1,EX2,EX3,EX4 externalLayer
```

### 技术架构栈

```mermaid
graph LR
    subgraph "前端技术栈"
        F1[React 18]
        F2[TypeScript]
        F3[Tailwind CSS]
        F4[React Router]
        F5[Axios]
        F6[React Markdown]
    end
    
    subgraph "后端技术栈"
        B1[Python 3.9+]
        B2[Flask]
        B3[Flask-CORS]
        B4[Gunicorn]
        B5[Werkzeug]
    end
    
    subgraph "AI/ML技术栈"
        AI1[Google Vertex AI]
        AI2[Gemini Pro]
        AI3[Text Embedding Gecko]
        AI4[FAISS]
        AI5[Sentence Transformers]
        AI6[LangChain]
    end
    
    subgraph "存储技术栈"
        S1[Google Cloud Storage]
        S2[FAISS Vector DB]
        S3[SQLite]
        S4[Redis/内存缓存]
    end
    
    subgraph "基础设施"
        I1[Docker]
        I2[Docker Compose]
        I3[Nginx]
        I4[GitHub Actions]
        I5[Google Cloud Platform]
    end
    
    %% 连接关系
    F1 --> B2
    B2 --> AI1
    AI1 --> S1
    B2 --> S2
    I1 --> I2
    I3 --> B2
```

### 数据流架构

```mermaid
graph LR
    subgraph "数据输入层"
        D1[PDF文档]
        D2[Word文档] 
        D3[文本文件]
        D4[用户查询]
    end
    
    subgraph "数据处理层"
        P1[文本提取]
        P2[内容清理]
        P3[智能分块]
        P4[向量化处理]
        P5[查询理解]
    end
    
    subgraph "数据存储层"
        S1[原始文件存储<br/>GCS]
        S2[向量数据库<br/>FAISS]
        S3[元数据存储<br/>SQLite]
        S4[缓存层<br/>Redis]
        S5[云端向量索引<br/>Vertex AI]
    end
    
    subgraph "数据输出层"
        O1[检索结果]
        O2[生成回答]
        O3[相关文档]
        O4[置信度分数]
    end
    
    %% 数据流向
    D1 --> P1
    D2 --> P1
    D3 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> S1
    P4 --> S2
    P4 --> S3
    P4 --> S5
    
    D4 --> P5
    P5 --> S2
    P5 --> S5
    S2 --> O1
    S5 --> O1
    O1 --> O2
    O1 --> O3
    O2 --> O4
    
    S4 --> O1
    O1 --> S4
```

### 向量数据库架构

```mermaid
graph TB
    subgraph "FAISS本地索引"
        F1[IndexFlatIP<br/>小数据集]
        F2[IndexIVFFlat<br/>大数据集]
        F3[动态索引选择器]
        F4[元数据映射]
    end
    
    subgraph "Vertex AI云端索引"
        V1[Vector Search Index]
        V2[Deployed Endpoint]
        V3[Embedding Model]
        V4[搜索配置]
    end
    
    subgraph "索引管理"
        M1[索引构建器]
        M2[索引优化器]
        M3[版本控制]
        M4[备份恢复]
    end
    
    F3 --> F1
    F3 --> F2
    F1 --> F4
    F2 --> F4
    
    V3 --> V1
    V1 --> V2
    V2 --> V4
    
    M1 --> F3
    M1 --> V1
    M2 --> F3
    M2 --> V1
    M3 --> F4
    M3 --> V4
```

### 部署架构

```mermaid
graph TB
    subgraph "容器编排层"
        DC[Docker Compose]
        K8S[Kubernetes<br/>可选]
    end
    
    subgraph "应用容器"
        C1[Frontend Container<br/>Nginx + React]
        C2[Backend Container<br/>Python + Flask]
        C3[Reverse Proxy<br/>Nginx]
    end
    
    subgraph "数据容器"
        D1[Cache Volume]
        D2[Logs Volume]
        D3[Config Volume]
    end
    
    subgraph "外部服务"
        E1[Google Cloud Storage]
        E2[Vertex AI Services]
        E3[Monitoring Services]
    end
    
    DC --> C1
    DC --> C2
    DC --> C3
    DC --> D1
    DC --> D2
    DC --> D3
    
    C1 --> C3
    C2 --> C3
    C2 --> E1
    C2 --> E2
    C3 --> E3
```

---

## 🔄 流程图表

### 文档上传处理流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant FE as 前端应用
    participant API as API服务器
    participant DP as 文档处理服务
    participant EG as 向量生成服务
    participant VS as 向量存储
    participant GCS as 云存储
    
    U->>FE: 1. 选择文档上传
    FE->>API: 2. POST /upload (multipart/form-data)
    API->>DP: 3. 验证文件格式
    DP->>DP: 4. 提取文本内容
    DP->>DP: 5. 文本分块处理
    DP->>EG: 6. 生成文档向量
    EG->>VS: 7. 存储向量数据
    DP->>GCS: 8. 上传原始文件
    API->>FE: 9. 返回处理结果
    FE->>U: 10. 显示上传成功
```

### 智能问答流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant FE as 前端应用
    participant API as API服务器
    participant HR as 混合检索引擎
    participant FAISS as FAISS检索
    participant VAI as Vertex AI检索
    participant LLM as 大语言模型
    participant CACHE as 缓存系统
    
    U->>FE: 1. 输入问题
    FE->>API: 2. POST /chat
    API->>CACHE: 3. 检查缓存
    alt 缓存命中
        CACHE->>API: 返回缓存结果
    else 缓存未命中
        API->>HR: 4. 启动混合检索
        HR->>FAISS: 5. 本地向量检索
        HR->>VAI: 6. 云端向量检索
        FAISS->>HR: 7. 返回相关文档块
        VAI->>HR: 8. 返回相关文档块
        HR->>HR: 9. RRF融合算法
        HR->>LLM: 10. 发送检索结果
        LLM->>LLM: 11. 生成回答
        LLM->>API: 12. 返回生成结果
        API->>CACHE: 13. 更新缓存
    end
    API->>FE: 14. 返回回答结果
    FE->>U: 15. 显示回答
```

### 混合检索算法流程

```mermaid
flowchart TD
    A[用户查询] --> B[查询预处理]
    B --> C[生成查询向量]
    C --> D{并行检索}
    
    D --> E[FAISS本地检索]
    D --> F[Vertex AI云端检索]
    
    E --> E1[余弦相似度计算]
    E --> E2[TopK文档筛选]
    E1 --> E3[本地结果集]
    E2 --> E3
    
    F --> F1[语义相似度计算]
    F --> F2[关键词匹配增强]
    F1 --> F3[云端结果集]
    F2 --> F3
    
    E3 --> G[RRF融合算法]
    F3 --> G
    
    G --> H[权重分配<br/>FAISS: 60%<br/>Vertex AI: 40%]
    H --> I[重新排序]
    I --> J[相似度阈值过滤]
    J --> K[返回最终结果]
    
    K --> L{检索质量评估}
    L -->|高质量| M[纯RAG模式]
    L -->|中等质量| N[混合模式]
    L -->|低质量| O[基础知识模式]
    
    M --> P[基于检索内容生成回答]
    N --> Q[结合检索内容和基础知识]
    O --> R[使用AI基础知识回答]
    
    P --> S[返回最终回答]
    Q --> S
    R --> S
```

### 部署流程

```mermaid
graph TB
    subgraph "准备阶段 Preparation"
        A[环境检查] --> B[依赖安装]
        B --> C[配置设置]
        C --> D[凭据配置]
    end
    
    subgraph "构建阶段 Build"
        E[前端构建] --> F[后端打包]
        F --> G[Docker镜像构建]
        G --> H[镜像推送]
    end
    
    subgraph "部署阶段 Deploy"
        I[服务部署] --> J[健康检查]
        J --> K[负载均衡配置]
        K --> L[域名配置]
    end
    
    subgraph "验证阶段 Verification"
        M[功能测试] --> N[性能测试]
        N --> O[监控配置]
        O --> P[部署完成]
    end
    
    D --> E
    H --> I
    L --> M
    
    style A fill:#e1f5fe
    style E fill:#f3e5f5
    style I fill:#e8f5e8
    style M fill:#fff3e0
```

### 贡献流程

```mermaid
graph TB
    subgraph "准备阶段 Preparation"
        A[Fork仓库] --> B[克隆到本地]
        B --> C[设置开发环境]
        C --> D[创建功能分支]
    end
    
    subgraph "开发阶段 Development"
        E[编写代码] --> F[运行测试]
        F --> G[代码检查]
        G --> H[提交更改]
    end
    
    subgraph "提交阶段 Submission"
        I[推送到远程] --> J[创建Pull Request]
        J --> K[代码审查]
        K --> L[CI/CD检查]
    end
    
    subgraph "合并阶段 Merge"
        M[修复反馈] --> N[再次审查]
        N --> O[合并到主分支]
        O --> P[更新文档]
    end
    
    D --> E
    H --> I
    L --> M
    
    style A fill:#e1f5fe
    style E fill:#f3e5f5
    style I fill:#e8f5e8
    style M fill:#fff3e0
```

---

## 🌐 API图表

### API业务流程

```mermaid
sequenceDiagram
    participant Client as 客户端
    participant API as API服务器
    participant RAG as RAG引擎
    participant LLM as 大语言模型
    
    Note over Client,LLM: 文档上传流程
    Client->>API: POST /upload (文档文件)
    API->>API: 文档处理和向量化
    API->>RAG: 存储向量数据
    API->>Client: 返回上传结果
    
    Note over Client,LLM: 智能问答流程
    Client->>API: POST /chat (用户问题)
    API->>RAG: 检索相关文档
    RAG->>API: 返回相关文档块
    API->>LLM: 生成回答
    LLM->>API: 返回生成结果
    API->>Client: 返回最终回答
    
    Note over Client,LLM: 系统监控流程
    Client->>API: GET /health
    API->>API: 检查系统状态
    API->>Client: 返回健康信息
```

### API请求响应流程

```mermaid
flowchart TD
    A[客户端请求] --> B{"请求类型"}
    B -->|"GET /health"| C[健康检查]
    B -->|"POST /upload"| D[文档上传]
    B -->|"POST /chat"| E[智能问答]
    B -->|"GET /documents"| F[文档列表]
    B -->|"DELETE /documents/{id}"| G[删除文档]
    
    C --> H[返回系统状态]
    D --> I[处理文档]
    E --> J[RAG检索]
    F --> K[查询数据库]
    G --> L[删除数据]
    
    I --> M[向量化存储]
    J --> N[生成回答]
    K --> O[返回列表]
    L --> P[确认删除]
    
    H --> Q[JSON响应]
    M --> Q
    N --> Q
    O --> Q
    P --> Q
    
    style A fill:#e1f5fe
    style Q fill:#e8f5e8
```

---

## 📊 性能与监控图表

### 缓存架构

```mermaid
graph LR
    subgraph "多级缓存体系"
        L1[浏览器缓存<br/>静态资源]
        L2[CDN缓存<br/>全球分发]
        L3[应用缓存<br/>热点数据]
        L4[向量缓存<br/>嵌入向量]
        L5[结果缓存<br/>问答结果]
    end
    
    subgraph "缓存策略"
        S1[LRU淘汰策略]
        S2[TTL过期策略]
        S3[预热策略]
        S4[更新策略]
    end
    
    L1 --> S2
    L2 --> S2
    L3 --> S1
    L4 --> S1
    L5 --> S2
    
    S3 --> L3
    S3 --> L4
    S4 --> L3
    S4 --> L5
```

### 负载均衡架构

```mermaid
graph TB
    subgraph "流量分发"
        DNS[DNS解析]
        GLB[全局负载均衡]
        RLB[区域负载均衡]
    end
    
    subgraph "后端服务池"
        P1[服务池 1<br/>轻量查询]
        P2[服务池 2<br/>重度计算]
        P3[服务池 3<br/>文件处理]
    end
    
    subgraph "健康检查"
        HC1[HTTP健康检查]
        HC2[服务状态监控]
        HC3[自动故障转移]
    end
    
    DNS --> GLB
    GLB --> RLB
    RLB --> P1
    RLB --> P2
    RLB --> P3
    
    HC1 --> P1
    HC2 --> P2
    HC3 --> P3
```

### 监控架构

```mermaid
graph TB
    subgraph "用户体验监控"
        RUM[真实用户监控]
        PERF[性能监控]
        ERROR[错误监控]
    end
    
    subgraph "应用性能监控"
        APM[应用性能管理]
        TRACE[分布式追踪]
        METRIC[业务指标]
    end
    
    subgraph "基础设施监控"
        SYS[系统监控]
        NET[网络监控]
        STOR[存储监控]
    end
    
    subgraph "告警处理"
        ALERT[智能告警]
        NOTIFY[通知系统]
        AUTO[自动修复]
    end
    
    RUM --> APM
    PERF --> TRACE
    ERROR --> METRIC
    
    APM --> SYS
    TRACE --> NET
    METRIC --> STOR
    
    SYS --> ALERT
    NET --> NOTIFY
    STOR --> AUTO
```

### 安全架构

```mermaid
graph TB
    subgraph "网络安全层"
        WAF[Web应用防火墙]
        DDoS[DDoS防护]
        SSL[SSL/TLS加密]
    end
    
    subgraph "应用安全层"
        AUTH[身份认证]
        AUTHZ[权限控制]
        VALID[输入验证]
        SANITIZE[数据清理]
    end
    
    subgraph "数据安全层"
        ENCRYPT[数据加密]
        MASK[敏感数据脱敏]
        AUDIT[审计日志]
        BACKUP[安全备份]
    end
    
    subgraph "基础设施安全"
        VPC[私有网络]
        IAM[身份访问管理]
        SECRET[密钥管理]
        SCAN[安全扫描]
    end
    
    WAF --> AUTH
    DDoS --> AUTHZ
    SSL --> VALID
    
    AUTH --> ENCRYPT
    AUTHZ --> MASK
    VALID --> AUDIT
    
    ENCRYPT --> VPC
    MASK --> IAM
    AUDIT --> SECRET
```

---

## 📚 图表说明

### 图表类型说明

- **🏗️ 架构图**: 展示系统组件关系和技术栈
- **🔄 流程图**: 展示业务流程和数据流向
- **🌐 API图**: 展示API交互和调用关系
- **📊 性能图**: 展示性能优化和监控架构

### 阅读建议

1. **新手用户**: 建议先阅读 [系统整体架构](#系统整体架构) 和 [智能问答流程](#智能问答流程)
2. **开发者**: 重点关注 [技术架构栈](#技术架构栈) 和 [API流程图](#api业务流程)
3. **运维人员**: 关注 [部署架构](#部署架构) 和 [监控架构](#监控架构)
4. **贡献者**: 参考 [贡献流程](#贡献流程) 和相关开发流程

### 相关文档

- 📖 [系统架构详细文档](ARCHITECTURE.md)
- 🚀 [部署指南](DEPLOYMENT.md)
- 📝 [API文档](API.md)
- 🤝 [贡献指南](../CONTRIBUTING.md)

---

**💡 提示**: 所有图表都使用 Mermaid 格式编写，可以在支持 Mermaid 的工具中查看和编辑。 