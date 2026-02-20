from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from langchain_community.document_loaders import TextLoader
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import CharacterTextSplitter

BASE_DIR = Path(__file__).resolve().parents[1]
POLICY_FILE = BASE_DIR / "data" / "policies" / "protocols.md"
INDEX_DIR = BASE_DIR / "data" / "faiss_index"


@lru_cache(maxsize=1)
def get_embedding_function() -> SentenceTransformerEmbeddings:
    return SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")


def initialize_rag(force_rebuild: bool = False) -> FAISS:
    """
    Load policies and build a FAISS index if needed.
    """
    if not POLICY_FILE.exists():
        raise FileNotFoundError(f"Policy file not found: {POLICY_FILE}")

    index_file = INDEX_DIR / "index.faiss"
    if not force_rebuild and index_file.exists():
        return FAISS.load_local(
            str(INDEX_DIR),
            get_embedding_function(),
            allow_dangerous_deserialization=True,
        )

    loader = TextLoader(str(POLICY_FILE), encoding="utf-8")
    documents = loader.load()
    splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_documents(documents)
    vectorstore = FAISS.from_documents(chunks, get_embedding_function())
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(INDEX_DIR))
    return vectorstore


@lru_cache(maxsize=1)
def get_vectorstore() -> FAISS:
    return initialize_rag(force_rebuild=False)


def retrieve_policy(query: str, k: int = 3) -> List[str]:
    """
    Return top-k relevant policy snippets.
    """
    if not query.strip():
        return []

    try:
        store = get_vectorstore()
        docs = store.similarity_search(query, k=k)
        return [doc.page_content.strip() for doc in docs if doc.page_content.strip()]
    except Exception:
        # Hard fallback: return plain sections from the policy file
        if not POLICY_FILE.exists():
            return []
        text = POLICY_FILE.read_text(encoding="utf-8")
        blocks = [item.strip() for item in text.split("\n\n") if item.strip()]
        return blocks[:k]


if __name__ == "__main__":
    initialize_rag(force_rebuild=False)
