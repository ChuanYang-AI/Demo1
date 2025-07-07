import pdfplumber
from docx import Document

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    从PDF文件中提取所有文本。
    """
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() if page.extract_text() else ""
    return text

def extract_text_from_docx(docx_path: str) -> str:
    """
    从DOCX文件中提取所有文本。
    """
    document = Document(docx_path)
    text = []
    for paragraph in document.paragraphs:
        text.append(paragraph.text)
    return "\n".join(text)

def chunk_text(text: str, chunk_size: int = 1000, overlap_size: int = 100) -> list[str]:
    """
    将文本分割成指定大小的块，并带有重叠。
    """
    chunks = []
    if not text:
        return chunks

    start_index = 0
    while start_index < len(text):
        end_index = min(start_index + chunk_size, len(text))
        chunk = text[start_index:end_index]
        chunks.append(chunk)

        if end_index == len(text):
            break
        
        start_index += chunk_size - overlap_size
        # 确保start_index不会倒退
        if start_index < 0:
            start_index = 0

    return chunks

if __name__ == "__main__":
    # 示例用法
    # 为了运行这些示例，你需要准备一个sample.pdf和一个sample.docx文件
    # 并将它们放在与此脚本相同的目录下，或者提供完整路径。

    # PDF文件示例
    # try:
    #     pdf_text = extract_text_from_pdf("sample.pdf")
    #     print("从PDF提取的文本：")
    #     print(pdf_text[:500] + "..." if len(pdf_text) > 500 else pdf_text)
    #     pdf_chunks = chunk_text(pdf_text)
    #     print(f"PDF分块数量：{len(pdf_chunks)}")
    #     print("第一个PDF块：")
    #     print(pdf_chunks[0])
    # except Exception as e:
    #     print(f"处理PDF时发生错误: {e}")

    # DOCX文件示例
    # try:
    #     docx_text = extract_text_from_docx("sample.docx")
    #     print("\n从DOCX提取的文本：")
    #     print(docx_text[:500] + "..." if len(docx_text) > 500 else docx_text)
    #     docx_chunks = chunk_text(docx_text)
    #     print(f"DOCX分块数量：{len(docx_chunks)}")
    #     print("第一个DOCX块：")
    #     print(docx_chunks[0])
    # except Exception as e:
    #     print(f"处理DOCX时发生错误: {e}")
    pass 