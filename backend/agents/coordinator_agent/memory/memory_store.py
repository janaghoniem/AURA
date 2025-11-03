from langchain.memory import ConversationBufferMemory
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

def get_short_term_memory():
    return ConversationBufferMemory(memory_key="conversation_history", return_messages=True)

def get_long_term_memory():
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    texts = [
        "User prefers minimalistic UIs.",
        "Assistive commands should be simple and voice-driven.",
        "YUSR is built for users with sight and mobility disabilities."
    ]
    vectorstore = FAISS.from_texts(texts, embeddings)
    return vectorstore.as_retriever()
