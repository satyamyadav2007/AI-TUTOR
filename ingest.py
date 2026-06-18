import os
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

def start_robust_batch_ingestion():
    print("🚀 Heizen's Main Theory Brain is waking up...")
    
    data_folder = "data/"
    all_documents = []
    
    # 1. Fault-Tolerant Loading (Ek-ek karke book padho)
    for filename in os.listdir(data_folder):
        if filename.endswith(".pdf"):
            file_path = os.path.join(data_folder, filename)
            print(f"📖 Processing: {filename}...")
            try:
                loader = PyMuPDFLoader(file_path)
                book_docs = loader.load()
                all_documents.extend(book_docs)
                print(f"   ✅ Success: Loaded {len(book_docs)} pages.")
            except Exception as e:
                print(f"   ❌ Failed to read {filename}. Skipping. Error: {e}")

    print(f"\n📚 Total successful pages loaded: {len(all_documents)}")

    if len(all_documents) == 0:
        print("No valid PDFs found in 'data' folder. Aborting.")
        return

    # 2. Text Splitting
    print("✂️ Splitting text into logical chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    docs = text_splitter.split_documents(all_documents)
    print(f"📊 Total theory chunks created: {len(docs)}")

    # 3. Generating Embeddings
    print("🧠 Generating embeddings (Using RTX 4050)...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # 4. THE FIX: Batch Insertion
    print("💾 Saving to Main Vector Database in batches (Max 5000 at a time)...")
    
    # Initialize the database
    vector_db = Chroma(persist_directory="./vector_db", embedding_function=embeddings)
    
    # Batch processing loop
    batch_size = 5000
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        vector_db.add_documents(batch)
        print(f"   -> Successfully synchronized batch {i//batch_size + 1} ({len(batch)} chunks)")
        
    print("✅ Success! Your AI Tutor now has a massive, stable theory knowledge base.")

if __name__ == "__main__":
    start_robust_batch_ingestion()