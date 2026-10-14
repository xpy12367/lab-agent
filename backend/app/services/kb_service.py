from pydoc import doc
from typing import final
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions
import chromadb
from app.config import BASE_DIR

# 知识库原始文档目录：存放待入库的 .md 文件
KB_DIR = BASE_DIR / "data" / "kb"
# Chroma 持久化目录：向量数据落盘保存在这里，重启后不会丢
CHROMA_DIR = BASE_DIR / "data" / "chroma"

# 模块级缓存：保存已初始化好的 collection，避免每次请求都重新连接数据库
_collection = None

# 统一的向量化模型：把文本转成向量（中文场景用 bge-small-zh）
# 注意：入库和检索必须用同一个模型，否则向量不在同一空间，检索结果没有意义
_embedding_fn = None


def get_embedding_fn():
    """懒加载 embedding 模型：只加载一次，之后复用同一个实例"""
    global _embedding_fn
    if _embedding_fn is not None:
        return _embedding_fn
    # SentenceTransformerEmbeddingFunction 自带类级缓存，同名模型也不会重复加载
    _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-small-zh-v1.5"
    )
    return _embedding_fn


def get_collcetion() -> Collection:
    """向量库的初始化"""

    global _collection
    # 已初始化过就直接复用，保证整个进程只创建一个 collection
    if _collection is not None:
        return _collection
    # 确保目录存在，否则 Chroma 或文件读取会报错
    KB_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    # 持久化客户端：数据保存到 CHROMA_DIR，而不是只存在内存里
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    # 拿到（没有就创建）名为 lab_kb 的集合，并绑定向量化模型
    col = client.get_or_create_collection(
        name="lab_kb", embedding_function=get_embedding_fn()
    )
    # 集合为空时，把 KB_DIR 下的 md 文档首次导入向量库
    # 这里用 count() == 0 做判断，所以后续新增/修改文件不会自动同步
    if col.count() == 0:
        ids = []  # 序号
        docs = []  # 文档
        metas = []  # 元数据
        for path in sorted(
            KB_DIR.glob("*.md")
        ):  # glob("*.md"):拿文档,*.md 表示所有的md文档   sorted():排序
            text = path.read_text(encoding="UTF-8").strip()  # read_text()读文件的内容
            # 跳过空文件，避免存入无意义内容
            if not text:
                continue
            docs.append(text)  # 文档正文
            ids.append(path.stem)  # .stem:文件名（不含扩展名）去掉后缀
            metas.append({"source": path.name}) # 记录来源文件名(含扩展名)，便于检索后展示出处
        if docs:
            col.add(ids=ids, documents=docs, metadatas=metas)
    # 缓存起来，供后续调用复用
    _collection = col
    return col


def warmup():
    """启动时预热：把模型加载 + 首次检索的开销付在启动阶段，别落在第一个用户请求上"""
    col = get_collcetion()
    if col.count() > 0:
        col.query(query_texts=["预热"], n_results=1)
        #查询出什么的都可以,只是让他预热


def search(query: str):
    """根据关键字去检索向量库"""
    col = get_collcetion()
    # 知识库为空，没有可检索的内容，直接返回空字符串
    if col.count() == 0:
        return ""
    # 最多返回 5 条，但不能超过库里实际数量（n_results 超了会报错）
    limit = min(5, col.count())  # min():取两个值里面较小的那个
    # 用 query 做向量检索，返回最相似的 limit 条结果
    res = col.query(query_texts=[query], n_results=limit)
    # 结果按批次组织，这里只有一次查询，所以取第 [0] 批
    docs = (res.get("documents") or [[]])[0]  # 命中的文档正文
    metas = (res.get("metadatas") or [[]])[0]  # 对应的元数据（来源文件名）
    distances = (res.get("distances") or [[]])[0]  # 向量距离，越小越相似

    """
    以下是检索出来的资料：
    [预约规则.md]

    # 实验室预约规则...

    
    [安全规范.md]

    安全规范....
    """
    score_parts = []
    for doc, metas, dist in zip(docs, metas, distances):  # zip:把多个列表「按位置一一配对」
        # 把距离换算成 0-1 的相似度分数：0-1 越接近1表示越相关
        score = 1 / (1 + dist)
        # 过滤掉相关性太低的片段，避免给模型塞入噪声
        if score < 0.5:
            continue
        name = metas.get("source") or ""
        score_parts.append({"score": score, "content": f"[{name}]\n{doc}"})
    print(f"检索出来的 score_parts：{score_parts}")
    # 按相似度从高到低排序，保证最相关的排前面
    score_parts.sort(key=lambda x: x["score"], reverse=True)  # reverse=True:倒序排序
    # key=lambda x: x["score"]:表示拿每个元素的 score 字段当排序依据。
    # 只取前 2 条拼成最终上下文返回
    final_parts = [item["content"] for item in score_parts[:2]]
    return "\n\n".join(final_parts)
