import vertexai
from vertexai.language_models import TextEmbeddingModel, TextEmbeddingInput
import time

def initialize_vertex_ai(project_id: str, location: str):
    """
    初始化Vertex AI客户端。
    """
    vertexai.init(project=project_id, location=location)

def get_text_embeddings(texts):
    print(f"[Embedding] 开始生成embedding，输入文本数量: {len(texts)}")
    for i, t in enumerate(texts[:2]):
        print(f"[Embedding] 输入文本[{i}]: {t[:80]} ...")
    start = time.time()
    try:
        model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        embeddings = []
        batch_size = 16
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            # 修复：使用get_embeddings方法而不是encode方法
            batch_embeddings_response = model.get_embeddings(batch_texts)
            # 提取embedding值
            batch_embeddings = [embedding.values for embedding in batch_embeddings_response]
            print(f"[Embedding] 批次{i//batch_size+1}: 输入{len(batch_texts)}条，返回shape: {len(batch_embeddings)}x{len(batch_embeddings[0]) if batch_embeddings else 0}")
            embeddings.extend(batch_embeddings)
        print(f"[Embedding] 返回embedding数量: {len(embeddings)}，每个维度: {len(embeddings[0]) if embeddings else 0}")
        print(f"[Embedding] 总耗时: {time.time()-start:.2f}秒")
        return embeddings
    except Exception as e:
        print(f"[Embedding] 生成embedding出错: {e}")
        import traceback
        traceback.print_exc()
        return [[] for _ in texts]

if __name__ == "__main__":
    # 示例用法
    # 在运行此示例之前，请确保已通过 gcloud auth application-default login 或设置 GOOGLE_APPLICATION_CREDENTIALS 环境变量进行身份验证。
    # 并且替换为你的实际项目ID和区域。
    # project_id = "your-gcp-project-id"
    # location = "us-central1"

    # try:
    #     initialize_vertex_ai(project_id, location)
    #     sample_texts = [
    #         "这是一个关于机器学习的句子。",
    #         "这是另一个关于人工智能的句子，与第一个句子相关。",
    #         "狗是人类最好的朋友。"
    #     ]
    #     text_embeddings = get_text_embeddings(sample_texts)
    #     print(f"生成了 {len(text_embeddings)} 个嵌入。")
    #     if text_embeddings:
    #         print(f"第一个嵌入的维度：{len(text_embeddings[0])}")
    #         print(f"第一个嵌入的前5个值：{text_embeddings[0][:5]}...")
    # except Exception as e:
    #     print(f"运行示例时发生错误: {e}")
    pass     #         print(f"第一个嵌入的前5个值：{text_embeddings[0][:5]}...")
    # except Exception as e:
    #     print(f"运行示例时发生错误: {e}")
    pass 
