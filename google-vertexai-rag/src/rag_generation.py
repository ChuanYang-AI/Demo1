import vertexai
from vertexai.generative_models import GenerativeModel
import time
import re
import html
import logging
try:
    from .prompt_templates import (
        get_prompt_template, 
        SECURITY_KEYWORDS, 
        PROFESSIONAL_FIELDS,
        SUPPORTED_LANGUAGES
    )
except ImportError:
    from prompt_templates import (
        get_prompt_template, 
        SECURITY_KEYWORDS, 
        PROFESSIONAL_FIELDS,
        SUPPORTED_LANGUAGES
    )
from datetime import datetime

def sanitize_input(text: str) -> str:
    """
    对输入文本进行安全过滤和清理
    
    Args:
        text: 原始输入文本
        
    Returns:
        str: 清理后的安全文本
    """
    if not text:
        return ""
    
    # 记录原始输入用于安全审计
    if len(text) > 100:  # 只记录较长的输入
        logging.info(f"[安全审计] 输入长度: {len(text)} 字符")
    
    # 移除潜在的恶意脚本标签（在HTML编码之前）
    text = re.sub(r'<script[^>]*>.*?</script>', '[FILTERED]', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<iframe[^>]*>.*?</iframe>', '[FILTERED]', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<object[^>]*>.*?</object>', '[FILTERED]', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<embed[^>]*>.*?</embed>', '[FILTERED]', text, flags=re.IGNORECASE | re.DOTALL)
    
    # 移除javascript协议
    text = re.sub(r'javascript:', '[FILTERED]', text, flags=re.IGNORECASE)
    
    # 移除alert等危险函数
    text = re.sub(r'\balert\s*\(', '[FILTERED]', text, flags=re.IGNORECASE)
    text = re.sub(r'\beval\s*\(', '[FILTERED]', text, flags=re.IGNORECASE)
    text = re.sub(r'\bonerror\s*=', '[FILTERED]', text, flags=re.IGNORECASE)
    text = re.sub(r'\bonload\s*=', '[FILTERED]', text, flags=re.IGNORECASE)
    
    # HTML实体编码，防止XSS攻击
    text = html.escape(text)
    
    # 移除潜在的SQL注入模式
    sql_patterns = [
        r'(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)',
        r'(\b(admin|root|password|passwd|user)\b)',
        r'(\b(or|and)\s+\d+\s*=\s*\d+)',
        r'(\b(union|select).*?from)',
        r'(\b(insert|update|delete).*?into)',
        r'(\bselect\s+\*.*?from)',
        r'(\bwhere\s+.*?=.*?\d+)',
        r'(\bfrom\s+\w+)',
        r'(\bwhere\s+\w+\s*=)'
    ]
    
    for pattern in sql_patterns:
        text = re.sub(pattern, '[FILTERED]', text, flags=re.IGNORECASE)
    
    # 移除潜在的命令注入模式
    cmd_patterns = [
        r'(\b(cmd|command|exec|system|eval|os\.|subprocess\.)\b)',
        r'(\b(rm\s+-rf|del|format|shutdown|reboot)\b)',
        r'(\b(wget|curl|nc|telnet|ssh|ftp)\b)',
        r'(\b(echo|cat|ls|dir|pwd|whoami)\b)'
    ]
    
    for pattern in cmd_patterns:
        text = re.sub(pattern, '[FILTERED]', text, flags=re.IGNORECASE)
    
    # 移除潜在的路径遍历攻击
    text = re.sub(r'\.\./', '[FILTERED]', text)
    text = re.sub(r'\.\.\\', '[FILTERED]', text)
    
    # 限制文本长度，防止过长的恶意输入
    max_length = 10000
    if len(text) > max_length:
        text = text[:max_length] + "...[截断]"
    
    return text

def validate_query_safety(query: str) -> tuple[bool, str]:
    """
    验证查询的安全性，使用优化的安全规则
    
    Args:
        query: 用户查询
        
    Returns:
        tuple: (是否安全, 错误信息)
    """
    if not query or not query.strip():
        return False, "查询内容不能为空"
    
    # 检查查询长度
    if len(query) > 2000:
        return False, "查询内容过长，请简化问题"
    
    # 使用优化的安全关键词检测
    query_lower = query.lower()
    
    # 检测各类恶意关键词
    for category, keywords in SECURITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in query_lower:
                category_names = {
                    "illegal": "违法内容",
                    "harmful": "有害内容", 
                    "inappropriate": "不当内容",
                    "system": "系统信息",
                    "privacy": "隐私信息",
                    "professional": "专业服务"
                }
                logging.warning(f"[安全审计] 检测到{category_names.get(category, '敏感内容')}: {keyword} in query: {query[:50]}...")
                return False, f"查询涉及{category_names.get(category, '敏感内容')}: {keyword}"
    
    # 检查是否包含过多的特殊字符（可能的编码攻击）
    special_char_ratio = len(re.findall(r'[^\w\s\u4e00-\u9fff]', query)) / len(query)
    if special_char_ratio > 0.3:
        return False, "查询包含过多特殊字符"
    
    # 检测重复字符模式（可能的DoS攻击）
    if len(query) > 10:
        char_counts = {}
        for char in query:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        for char, count in char_counts.items():
            if count / len(query) > 0.5:  # 单个字符占比超过50%
                return False, f"检测到异常字符模式: {char}"
    
    return True, ""

def create_safe_prompt(prompt_template: str, **kwargs) -> str:
    """
    创建安全的prompt，对所有输入进行安全处理
    
    Args:
        prompt_template: prompt模板
        **kwargs: 模板参数
        
    Returns:
        str: 安全的prompt
    """
    # 对所有输入参数进行安全清理
    safe_kwargs = {}
    for key, value in kwargs.items():
        if isinstance(value, str):
            safe_kwargs[key] = sanitize_input(value)
        elif isinstance(value, list):
            safe_kwargs[key] = [sanitize_input(str(item)) for item in value]
        else:
            safe_kwargs[key] = str(value)
    
    # 使用安全的参数填充模板
    try:
        safe_prompt = prompt_template.format(**safe_kwargs)
        
        # 最终安全检查
        if len(safe_prompt) > 50000:  # 限制prompt总长度
            print("[安全] Prompt过长，进行截断")
            safe_prompt = safe_prompt[:50000] + "...[截断]"
        
        return safe_prompt
    except Exception as e:
        print(f"[安全] Prompt模板填充失败: {e}")
        return "系统错误，请稍后重试"

def monitor_prompt_behavior(prompt: str, query: str) -> bool:
    """
    监控prompt行为，检测潜在的异常模式
    
    Args:
        prompt: 生成的prompt
        query: 原始查询
        
    Returns:
        bool: 是否检测到异常行为
    """
    # 检测重复字符模式（可能的DoS攻击）
    if len(prompt) > 0:
        char_counts = {}
        for char in prompt:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # 检查是否有字符占比过高
        for char, count in char_counts.items():
            if count / len(prompt) > 0.5:  # 单个字符占比超过50%
                print(f"[安全] 检测到异常字符模式: {char} 占比 {count/len(prompt):.2%}")
                return True
    
    # 检测潜在的prompt注入模式
    injection_patterns = [
        r'ignore\s+previous\s+instructions',
        r'forget\s+everything',
        r'you\s+are\s+now',
        r'act\s+as\s+if',
        r'pretend\s+to\s+be',
        r'system\s+prompt',
        r'ignore\s+above',
        r'disregard\s+previous'
    ]
    
    prompt_lower = prompt.lower()
    for pattern in injection_patterns:
        if re.search(pattern, prompt_lower):
            print(f"[安全] 检测到潜在的prompt注入模式: {pattern}")
            return True
    
    # 检测过长的查询（可能的资源消耗攻击）
    if len(query) > 5000:
        print(f"[安全] 查询过长: {len(query)} 字符")
        return True
    
    return False

def detect_professional_field(query: str) -> str:
    """
    检测查询是否涉及专业领域
    
    Args:
        query: 用户查询
        
    Returns:
        str: 专业领域类型，如果不涉及则返回空字符串
    """
    query_lower = query.lower()
    
    # 医疗相关关键词
    medical_keywords = ["症状", "疾病", "治疗", "药物", "诊断", "医院", "医生", "患者", "病情", "头痛", "发烧", "感冒", "咳嗽", "疼痛", "不舒服", "难受"]
    if any(keyword in query_lower for keyword in medical_keywords):
        return "medical"
    
    # 法律相关关键词
    legal_keywords = ["法律", "法规", "合同", "诉讼", "律师", "法院", "判决", "权利", "义务"]
    if any(keyword in query_lower for keyword in legal_keywords):
        return "legal"
    
    # 金融相关关键词
    financial_keywords = ["投资", "理财", "股票", "基金", "保险", "贷款", "财务", "税务", "经济"]
    if any(keyword in query_lower for keyword in financial_keywords):
        return "financial"
    
    # 心理相关关键词
    psychological_keywords = ["心理", "情绪", "抑郁", "焦虑", "咨询", "治疗", "压力", "心理健康"]
    if any(keyword in query_lower for keyword in psychological_keywords):
        return "psychological"
    
    return ""

def create_security_rejection_response(rejection_reason: str) -> str:
    """
    创建安全拒绝响应
    
    Args:
        rejection_reason: 拒绝原因
        
    Returns:
        str: 格式化的拒绝响应
    """
    template = get_prompt_template("security_rejection")
    return template.format(rejection_reason=rejection_reason)

def create_professional_advice_response(answer: str, professional_field: str) -> str:
    """
    创建专业建议响应
    
    Args:
        answer: 原始回答
        professional_field: 专业领域
        
    Returns:
        str: 格式化的专业建议响应
    """
    if professional_field in PROFESSIONAL_FIELDS:
        field_info = PROFESSIONAL_FIELDS[professional_field]
        template = get_prompt_template("professional_advice")
        return template.format(
            answer=answer,
            professional_field=field_info["field"],
            professional_type=field_info["type"],
            source_identifier="🧠 *基于AI知识*"
        )
    return answer

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
    # 安全验证
    is_safe, error_msg = validate_query_safety(query)
    if not is_safe:
        print(f"[安全] 查询安全检查失败: {error_msg}")
        security_response = create_security_rejection_response(error_msg)
        return {
            "answer": security_response,
            "source": "security_error",
            "confidence": 0,
            "processing_time": 0,
            "use_rag": False,
            "use_hybrid": False,
            "max_similarity": 0
        }
    
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

    # 根据相似度选择不同的回答策略，使用优化的prompt模板
    if use_rag and retrieved_chunks:
        # 高相似度：纯RAG模式
        context = "\n\n".join(retrieved_chunks)
        prompt_template = get_prompt_template("rag_high")
        prompt = create_safe_prompt(prompt_template, context=context, query=query)
        answer_source = "rag"
        confidence = max_similarity
        
    elif use_hybrid and retrieved_chunks:
        # 中等相似度：混合模式
        context = "\n\n".join(retrieved_chunks)
        prompt_template = get_prompt_template("hybrid")
        prompt = create_safe_prompt(prompt_template, context=context, query=query)
        answer_source = "hybrid"
        confidence = max_similarity
        
    else:
        # 低相似度：基础知识模式
        prompt_template = get_prompt_template("knowledge")
        prompt = create_safe_prompt(prompt_template, query=query)
        answer_source = "knowledge"
        confidence = 0.5  # 基础知识回答给予中等置信度
    
    mode_name = "纯RAG" if use_rag else ("混合模式" if use_hybrid else "基础知识")
    print(f"[LLM] 使用{mode_name}生成回答")
    
    # 行为监控
    if monitor_prompt_behavior(prompt, query):
        print("[安全] 检测到异常行为，返回安全响应")
        return {
            "answer": "抱歉，检测到异常输入模式。请重新输入您的问题。",
            "source": "security_monitor",
            "confidence": 0,
            "processing_time": time.time() - start,
            "use_rag": False,
            "use_hybrid": False,
            "max_similarity": 0
        }
    
    try:
        response = model.generate_content(prompt)
        
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            answer = response.candidates[0].content.parts[0].text
            processing_time = time.time() - start
            
            # 检测专业领域并添加相应提醒
            professional_field = detect_professional_field(query)
            if professional_field and answer_source == "knowledge":
                answer = create_professional_advice_response(answer, professional_field)
            
            # 构建返回结果
            result = {
                "answer": answer,
                "source": answer_source,
                "confidence": confidence,
                "processing_time": processing_time,
                "use_rag": use_rag or use_hybrid,
                "use_hybrid": use_hybrid,
                "max_similarity": max(source.get('similarity', 0) for source in sources) if sources else 0,
                "professional_field": professional_field
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

# 配置安全日志
def setup_security_logging():
    """配置安全日志记录"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('security.log'),
            logging.StreamHandler()
        ]
    )

if __name__ == "__main__":
    setup_security_logging()
    pass 
