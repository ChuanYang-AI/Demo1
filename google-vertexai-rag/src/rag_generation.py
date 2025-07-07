import vertexai
from vertexai.generative_models import GenerativeModel
import time

def generate_answer_with_llm(query: str, retrieved_chunks: list[str], sources: list[dict] = None, similarity_threshold: float = 0.6) -> dict:
    """
    结合检索到的文本和用户查询，使用LLM生成回答。
    
    Args:
        query: 用户查询
        retrieved_chunks: 检索到的文本块
        sources: 检索结果的源信息（包含相似度等）
        similarity_threshold: 相关性阈值，低于此值将使用基础知识回答
        
    Returns:
        dict: 包含回答、答案来源、可信度等信息
    """
    print(f"[LLM] 开始生成回答，query: {query}")
    print(f"[LLM] 上下文块数: {len(retrieved_chunks)}，总长度: {sum(len(t) for t in retrieved_chunks)}")
    
    # 检查检索结果的相关性
    use_rag = False
    use_hybrid = False
    
    if sources:
        # 计算最高相似度
        max_similarity = max(source.get('similarity', 0) for source in sources)
        print(f"[LLM] 最高相似度: {max_similarity:.3f}，阈值: {similarity_threshold}")
        
        # 分层相似度策略
        if max_similarity >= 0.85:
            use_rag = True
            print(f"[LLM] ✅ 高相似度 (≥85%)，使用纯RAG检索回答")
        elif max_similarity >= similarity_threshold:
            use_hybrid = True
            print(f"[LLM] 🔄 中等相似度 ({similarity_threshold:.0%}-85%)，使用混合模式回答")
        else:
            print(f"[LLM] ❌ 低相似度 (<{similarity_threshold:.0%})，使用基础知识回答")
    
    if retrieved_chunks and use_rag:
        print(f"[LLM] 上下文预览: {retrieved_chunks[0][:100]} ...")
    
    start = time.time()
    model = GenerativeModel('gemini-2.0-flash-001')

    # 根据相似度选择不同的回答策略
    if use_rag and retrieved_chunks:
        # 高相似度：纯RAG模式
        context = "\n\n".join(retrieved_chunks)
        prompt = f"""
你是一个智能知识问答助手。检索到的文档内容与用户问题高度相关，请基于以下文档内容回答。

**检索到的文档内容：**
{context}

**用户问题：** {query}

**回答要求：**
- 基于文档内容进行回答
- 回答要清晰简洁，易于理解
- 使用简单的markdown格式（加粗、列表等）
- 避免过长的段落，适当分段
- 回答结尾添加："📖 *基于检索文档*"

**回答：**
"""
        answer_source = "rag"
        confidence = max_similarity
        
    elif use_hybrid and retrieved_chunks:
        # 中等相似度：混合模式
        context = "\n\n".join(retrieved_chunks)
        prompt = f"""
你是一个智能知识问答助手。检索到的文档内容与用户问题有一定相关性，请结合文档和知识回答。

**检索到的文档内容：**
{context}

**用户问题：** {query}

**回答要求：**
- 先分析文档中的相关信息
- 结合基础知识提供完整准确的答案
- 回答要清晰简洁，分点说明
- 使用简单的markdown格式（**加粗**、- 列表等）
- 避免过长的段落和复杂表格
- 回答结尾添加："🔄 *结合文档和知识*"

**回答：**
"""
        answer_source = "hybrid"
        confidence = max_similarity
        
    else:
        # 低相似度：基础知识模式
        prompt = f"""
你是一个智能知识问答助手。请基于你的知识回答用户的问题。

**用户问题：** {query}

**回答要求：**
- 提供准确、易懂的解释
- 分点说明关键信息
- 使用简单的markdown格式（**加粗**、- 列表等）
- 回答要简洁明了，避免冗长
- 如果是专业问题，提醒用户咨询专家
- 回答结尾添加："🧠 *基于AI知识*"

**回答：**
"""
        answer_source = "knowledge"
        confidence = 0.5  # 基础知识回答给予中等置信度
    
    mode_name = "纯RAG" if use_rag else ("混合模式" if use_hybrid else "基础知识")
    print(f"[LLM] 使用{mode_name}生成回答")
    
    try:
        response = model.generate_content(prompt)
        
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            answer = response.candidates[0].content.parts[0].text
            processing_time = time.time() - start
            
            # 构建返回结果
            result = {
                "answer": answer,
                "source": answer_source,
                "confidence": confidence,
                "processing_time": processing_time,
                "use_rag": use_rag or use_hybrid,
                "use_hybrid": use_hybrid,
                "max_similarity": max(source.get('similarity', 0) for source in sources) if sources else 0
            }
            
            print(f"[LLM] 生成回答: {answer[:200]} ...")
            print(f"[LLM] 回答来源: {answer_source}")
            print(f"[LLM] 置信度: {confidence:.3f}")
            print(f"[LLM] 生成耗时: {processing_time:.2f}秒")
            
            return result
        else:
            print("[LLM] LLM响应中没有可用的文本内容")
            return {
                "answer": "抱歉，我无法生成回答。",
                "source": "error",
                "confidence": 0,
                "processing_time": time.time() - start,
                "use_rag": False,
                "use_hybrid": False,
                "max_similarity": 0
            }
    except Exception as e:
        print(f"[LLM] 生成回答出错: {e}")
        import traceback
        traceback.print_exc()
        return {
            "answer": "抱歉，生成回答时出现错误。",
            "source": "error",
            "confidence": 0,
            "processing_time": time.time() - start,
            "use_rag": False,
            "use_hybrid": False,
            "max_similarity": 0
        }

# 保留原有的简单版本函数，用于向后兼容
def generate_answer_with_llm_simple(query: str, retrieved_chunks: list[str]) -> str:
    """
    简单版本的生成函数，保持向后兼容
    """
    result = generate_answer_with_llm(query, retrieved_chunks)
    return result["answer"]

if __name__ == "__main__":
    pass 
