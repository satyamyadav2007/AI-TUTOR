import os
import json
import re
import pdfplumber
from langchain_community.llms import Ollama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.schema import Document

# Initialize local LLM and Embeddings
llm = Ollama(model="qwen2.5:7b")
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
db_path = "./pyq_vector_db"

def extract_text_from_pdf(pdf_path):
    """Extracts raw text from a GATE PYQ PDF."""
    print(f"📄 Reading {pdf_path}...")
    full_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    return full_text

def chunk_into_questions(raw_text):
    """Splits the giant PDF text into individual raw questions."""
    # Assuming questions in PDF start with numbers like "1.", "2.", or "Q1"
    # This regex splits the text whenever a new question starts
    chunks = re.split(r'\n(?=\d+\. |Q\d+)', raw_text)
    return [chunk.strip() for chunk in chunks if len(chunk.strip()) > 20]

def structure_with_ai(raw_question, subject):
    """Uses Ollama to convert messy raw text into our clean JSON QuestionModel."""
    prompt = f"""
    Act as an expert GATE Data Entry Specialist. Convert the following raw text into a structured JSON format.
    SUBJECT: {subject}
    
    RAW TEXT:
    {raw_question}
    
    RETURN FORMAT (STRICT PURE JSON ONLY):
    {{
        "type": "MCQ", 
        "topic": "Infer the specific syllabus topic from the question",
        "question": "Cleaned up question text",
        "A": "Option A value",
        "B": "Option B value",
        "C": "Option C value",
        "D": "Option D value",
        "EXP": "Provide the detailed step-by-step solution if present in the text, otherwise write 'Derive mathematically'",
        "ANS": "Correct option letter"
    }}
    """
    
    try:
        output = llm.invoke(prompt).strip()
        # Non-greedy regex (.*?) ensures we only grab the FIRST complete JSON block
        match = re.search(r'\{.*?\}', output, re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str, strict=False)
        return None
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON Decode Error: {e}. Output was too messy.")
        return None
    except Exception as e:
        print(f"⚠️ AI Structuring Failed: {e}")
        return None

def ingest_pyq_pipeline(pdf_filename, subject):
    """Main pipeline to run the ingestion."""
    pdf_path = os.path.join("./pyq_data", pdf_filename)
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return

    raw_text = extract_text_from_pdf(pdf_path)
    raw_chunks = chunk_into_questions(raw_text)
    print(f"🔍 Found ~{len(raw_chunks)} raw questions. Starting AI structuring...")
    
    documents = []
    success_count = 0
    
    for i, chunk in enumerate(raw_chunks):
        print(f"⏳ Processing Q{i+1}/{len(raw_chunks)}...")
        structured_data = structure_with_ai(chunk, subject)
        
        if structured_data:
            # Create a searchable text representation for the Vector DB
            searchable_content = f"Subject: {subject}\nTopic: {structured_data.get('topic')}\nQuestion: {structured_data.get('question')}"
            
            # Store the full JSON in the metadata so we can retrieve it perfectly later
            doc = Document(
                page_content=searchable_content,
                metadata={
                    "source": pdf_filename,
                    "subject": subject,
                    "topic": structured_data.get("topic", "Unknown"),
                    "full_json": json.dumps(structured_data)
                }
            )
            documents.append(doc)
            success_count += 1
            
        # Optional: Save in batches to prevent RAM overload
        if len(documents) >= 50:
            print("💾 Saving batch to ChromaDB...")
            Chroma.from_documents(documents, embeddings, persist_directory=db_path)
            documents = []
            
    # Save remaining documents
    if documents:
        print("💾 Saving final batch to ChromaDB...")
        Chroma.from_documents(documents, embeddings, persist_directory=db_path)

    print(f"✅ Ingestion Complete! Successfully structured and saved {success_count} questions.")

# ---------------------------------------------------------
# RUN THE PIPELINE
# ---------------------------------------------------------
if __name__ == "__main__":
    # Ensure your PDF is inside the "pyq_data" folder
    target_pdf = "CS & IT PYQ Topic Wise.pdf" 
    target_subject = "Computer Science"
    
    print("🚀 Starting Heizen PYQ Ingestion Engine...")
    ingest_pyq_pipeline(target_pdf, target_subject)