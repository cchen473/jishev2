import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import SentenceTransformerEmbeddings

# Use SentenceTransformer for local embeddings to avoid API costs during dev
# In production, you might switch to OpenAIEmbeddings
embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

def initialize_rag():
    """
    Initializes the RAG system by loading policies and creating a vector store.
    """
    print("Initializing RAG System...")
    
    # Load the policy document
    loader = TextLoader("./backend/data/policies/protocols.md")
    documents = loader.load()
    
    # Split text into chunks
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = text_splitter.split_documents(documents)
    
    # Create Vector Store (FAISS)
    db = FAISS.from_documents(docs, embedding_function)
    
    # Save locally
    db.save_local("./backend/data/faiss_index")
    
    print(f"RAG System Initialized with {len(docs)} document chunks.")
    return db

def retrieve_policy(query: str, k: int = 2):
    """
    Retrieves relevant policy sections based on a query.
    """
    try:
        db = FAISS.load_local(
            "./backend/data/faiss_index", 
            embedding_function,
            allow_dangerous_deserialization=True 
        )
        results = db.similarity_search(query, k=k)
        return [doc.page_content for doc in results]
    except Exception as e:
        print(f"Error retrieving policy: {e}")
        return []

if __name__ == "__main__":
    # Run initialization if executed directly
    initialize_rag()
