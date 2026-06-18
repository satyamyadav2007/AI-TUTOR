import json
import re
import random
import hashlib
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from models import QuestionModel
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage

def load_brains():
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    theory_db = Chroma(persist_directory="./vector_db", embedding_function=embeddings)
    pyq_db = Chroma(persist_directory="./pyq_vector_db", embedding_function=embeddings)
    
    # We switch to qwen2.5:7b or deepseek-r1:7b for premium logic
    llm = Ollama(model="qwen2.5:7b") 
    return theory_db, pyq_db, llm

theory_db, pyq_db, llm = load_brains()

# ==========================================
# 🛠️ HELPER: BULLETPROOF JSON PARSER
# ==========================================
def extract_json(raw_text):
    """Safely extracts JSON from AI output even if wrapped in markdown."""
    try:
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
        # Fix invalid escape characters for math equations
        raw_text = re.sub(r'\\(?![/"\\bfnrtu])', r'\\\\', raw_text)
        
        # Find the first { or [ and last } or ]
        start = min([i for i in [raw_text.find("{"), raw_text.find("[")] if i >= 0] + [0])
        end = max(raw_text.rfind("}"), raw_text.rfind("]")) + 1
        
        return json.loads(raw_text[start:end], strict=False)
    except Exception as e:
        print(f"JSON Parsing Error: {e}")
        return None

# ==========================================
# 🧠 CORE AI FUNCTIONS
# ==========================================
def verify_single_question(question_data, subject, difficulty):
    verification_prompt = f"""
    You are a strict IIT GATE examiner. Verify this {question_data.get('type', 'MCQ')} question.
    SUBJECT: {subject}
    DIFFICULTY: {difficulty}
    QUESTION: {question_data.get('question')}
    
    Is the answer factually correct and logic non-hallucinated? 
    RETURN ONLY: PASS or FAIL
    """
    try:
        result = llm.invoke(verification_prompt).strip().upper()
        return "PASS" in result
    except:
        return True

def generate_single_question(subject, topic, difficulty, seen_hashes):
    """Generates ONE high-quality GATE question and returns (data, hash)."""
    theory_docs = theory_db.similarity_search(f"{subject} {topic}", k=3)
    theory_context = "\n".join([d.page_content for d in theory_docs])
    
    prompt = f"""
    Act as an elite GATE Computer Science exam setter.
    Generate exactly ONE highly conceptual multiple-choice question on the topic: {topic}.
    Use this context if needed: {theory_context}
    
    STRICT RULES:
    1. NO TRIVIAL QUESTIONS. Must involve calculation or deep logic.
    2. NEVER use "None" as an option.
    3. Output MUST be a STRICT JSON object ONLY.
    
    EXPECTED JSON FORMAT:
    {{
        "type": "MCQ",
        "topic": "{topic}",
        "question": "Your tough question here?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "answer": "Option B",
        "explanation": "Detailed step-by-step solution."
    }}
    """
    try:
        response = llm.invoke(prompt)
        reply = response.strip() if isinstance(response, str) else response.content.strip()
        parsed = extract_json(reply)
        
        if parsed and "question" in parsed:
            q_hash = hashlib.md5(parsed["question"].encode()).hexdigest()
            if q_hash in seen_hashes:
                return None, None
            if verify_single_question(parsed, subject, difficulty):
                return parsed, q_hash
        return None, None
    except Exception as e:
        print(f"❌ Single Question Generation failed: {e}")
        return None, None

def generate_concept_only(subject, topic):
    theory_docs = theory_db.similarity_search(f"{subject} {topic}", k=2)
    theory_context = "\n".join([d.page_content for d in theory_docs])
    
    prompt = f"""
    Act as a Master EdTech Content Creator. Teach '{topic}' from '{subject}'.
    CONTEXT: {theory_context}
    
    STRICT JSON FORMAT:
    {{
        "concept_capsule": "TL;DR\\n\\nCore Logic\\n\\nGATE Trick",
        "mermaid_diagram_code": "graph TD\\nA-->B"
    }}
    """
    try:
        response = llm.invoke(prompt)
        reply = response.strip() if isinstance(response, str) else response.content.strip()
        parsed = extract_json(reply)
        if parsed and "concept_capsule" in parsed:
            parsed["concept_capsule"] = parsed["concept_capsule"].replace("\\n", "\n")
            return parsed
        return None
    except Exception as e:
        print(f"Concept extraction failed: {e}")
        return None

def evaluate_dsa_code(problem_title, problem_desc, user_code, language="Python"):
    """Evaluates the user's DSA code like a strict FAANG/LeetCode system."""
    
    prompt = f"""
    Act as the LeetCode Online Judge and an Expert FAANG Interviewer.
    Evaluate the following {language} code for the given problem.
    
    PROBLEM: {problem_title}
    DESCRIPTION: {problem_desc}
    USER'S {language} CODE:
    {user_code}
    
    RETURN FORMAT (STRICT JSON ONLY, NO MARKDOWN OUTSIDE):
    {{
        "status": "Accepted / Wrong Answer / Time Limit Exceeded / Syntax Error",
        "score": "Give a score out of 100",
        "time_complexity": "e.g., O(N) - Briefly explain why",
        "space_complexity": "e.g., O(1) - Briefly explain why",
        "edge_cases": "Did they handle empty inputs, negative numbers, or large constraints?",
        "detailed_feedback": "A detailed paragraph explaining logic flaws, praising the approach, and pointing out bugs.",
        "optimized_code": "Write the fully optimized, production-ready solution in {language}."
    }}
    """
    try:
        response = llm.invoke(prompt)
        reply = response.strip() if isinstance(response, str) else response.content.strip()
        return extract_json(reply)
    except Exception as e:
        print(f"Code evaluation failed: {e}")
        return None

def generate_dsa_problem(topic, difficulty):
    import random
    # Random seed add karne se AI har baar naya rasta sochne pe majboor hoga
    seed = random.randint(1, 100000)
    
    prompt = f"""
    Act as a strict FAANG Software Engineer. Generate a completely UNIQUE and RANDOM {difficulty} level DSA problem strictly focused on the topic: '{topic}'.
    Randomization Seed: {seed}.
    
    CRITICAL RULES:
    1. The problem MUST heavily involve the concept of {topic} (e.g., if Dynamic Programming, generate Knapsack, Longest Increasing Subsequence, Coin Change, or a novel variation).
    2. DO NOT COPY THE EXAMPLE PROVIDED BELOW. The example is ONLY for showing the JSON structure.
    
    RETURN FORMAT (STRICT JSON ONLY):
    {{
        "title": "<Unique Problem Title Here>",
        "description": "<Detailed problem statement, constraints, and edge cases.>",
        "test_cases": [
            {{"input": "nums = [1,2,3]", "output": "6"}},
            {{"input": "nums = [0,0]", "output": "0"}}
        ],
        "starter_code": "def solve(nums):\\n    # Write your code here\\n    pass"
    }}
    """
    try:
        response = llm.invoke(prompt)
        reply = response.strip() if isinstance(response, str) else response.content.strip()
        parsed = extract_json(reply)
        if parsed and "starter_code" in parsed:
            parsed["starter_code"] = parsed["starter_code"].replace("\\n", "\n")
            return parsed
        return None
    except Exception as e:
        print(f"DSA Problem generation failed: {e}")
        return None

def generate_pyq_variant(subject, topic, difficulty):
    docs = pyq_db.similarity_search(f"Subject: {subject} Topic: {topic}", k=3)
    if not docs:
        return None
        
    selected_doc = random.choice(docs)
    original_q_json = selected_doc.metadata.get("full_json")
    if not original_q_json:
        return None

    prompt = f"""
    Act as an Expert IIT GATE Computer Science Exam Setter. I am giving you a REAL past year question.
    Your task is to create a BRAND NEW VARIANT of this question.
    
    STRICT RULES FOR THE NEW QUESTION:
    1. Keep the CORE COMPUTER SCIENCE LOGIC and CONCEPT exactly the same.
    2. Change the technical numerical values (e.g., memory addresses, process IDs, graph weights, string lengths) to create a new solvable problem.
    3. FATAL ERROR WARNING: ABSOLUTELY NO questions about page numbers, chapters, textbooks, or syllabus structure. It MUST be a highly technical CSE problem.
    4. Difficulty should be: {difficulty}.
    
    ORIGINAL QUESTION JSON:
    {original_q_json}
    
    RETURN FORMAT (STRICT JSON ONLY):
    {{
        "type": "MCQ",
        "topic": "{topic}",
        "question": "<Write the newly generated technical variant here>",
        "options": ["<Option 1 exact text>", "<Option 2 exact text>", "<Option 3 exact text>", "<Option 4 exact text>"],
        "answer": "<Write the EXACT FULL TEXT of the correct option here. DO NOT write just A, B, C, or D>",
        "explanation": "<Step-by-step technical derivation>"
    }}
    """
    try:
        response = llm.invoke(prompt)
        reply = response.strip() if isinstance(response, str) else response.content.strip()
        parsed = extract_json(reply)
        if parsed:
            parsed["is_variant"] = True
            return parsed
        return None
    except Exception as e:
        print(f"Variant generation failed: {e}")
        return None

def generate_study_plan(elo_rating, weak_topics_dict, days=21):
    weaknesses = ", ".join([f"{t} ({c} mistakes)" for t, c in weak_topics_dict.items()])
    if not weaknesses: weaknesses = "No specific weak topics. Focus on overall GATE CSE syllabus."
        
    prompt = f"""
    Act as an Elite GATE CSE Planner.
    ELO: {elo_rating}. Weaknesses: {weaknesses}.
    
    Create a {days}-day highly actionable study roadmap. You MUST focus 70% of the plan on the weak topics mentioned.
    
    RETURN FORMAT (STRICT JSON ARRAY ONLY, NO MARKDOWN):
    [
        {{
            "day": 1,
            "focus_topic": "Cache Memory Mapping (Weakness)",
            "tasks": [
                "Watch AI Explanation for Cache Mapping",
                "Read Short Notes",
                "Solve 10 MCQs on Direct Mapping",
                "Take Mini Topic Test"
            ]
        }},
        {{
            "day": 2,
            "focus_topic": "Paging & Segmentation",
            "tasks": [
                "Revise Page Table Entries",
                "Solve 5 PYQs on TLB",
                "Review Mistakes"
            ]
        }}
    ]
    """
    try:
        response = llm.invoke(prompt)
        reply = response.strip() if isinstance(response, str) else response.content.strip()
        # Use our bulletproof JSON extractor
        return extract_json(reply)
    except Exception as e:
        print(f"Study Plan failed: {e}")
        return None

import google.generativeai as genai
from PIL import Image

def solve_doubt_from_image(image_file):
    """Processes an uploaded image and solves the doubt using Google Gemini API."""
    print("📸 Analyzing Image Doubt using Google Gemini API...")
    
    try:
        # 1. Prepare Image
        img = Image.open(image_file)
        if img.mode != "RGB":
            img = img.convert("RGB")
            
        # 2. Configure API Key
        # YAHAN APNI COPIED API KEY PASTE KAREIN 👇
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=GEMINI_API_KEY)
        
        # 3. Load Gemini 1.5 Flash (Added '-latest' to fix the 404 error)
        model = genai.GenerativeModel('models/gemini-2.0-flash')
        
        # 4. Strict Master Prompt
        prompt = """
        Act as an Elite GATE CSE Mentor. Analyze this image very carefully.
        
        STEP 1: Transcribe the exact question text and mathematical formulas written in the image.
        STEP 2: Identify the core subject (e.g., Theory of Computation, Digital Logic, Engineering Math). DO NOT invent a programming/coding problem unless explicit code is shown.
        STEP 3: Provide a highly accurate, step-by-step mathematical or logical solution.
        STEP 4: State the final exact numerical or specific answer clearly in bold.
        """
        
        # 5. Get Magical Answer
        response = model.generate_content([prompt, img])
        return response.text
        
    except Exception as e:
        print(f"❌ Gemini API failed: {e}")
        return f"Error: {str(e)}. Please check your API key and internet connection."

def get_interview_response(topic, chat_history):
    prompt = f"You are a strict technical interviewer for {topic}. Ask ONE question. Wait for answer.\n\n"
    for msg in chat_history:
        role = "Candidate" if msg["role"] == "user" else "Interviewer"
        prompt += f"{role}: {msg['content']}\n"
    prompt += "Interviewer: "
    
    try:
        response = llm.invoke(prompt)
        reply = response.strip() if isinstance(response, str) else response.content.strip()
        return reply.replace("Interviewer:", "").strip()
    except Exception as e:
        print(f"Interview engine failed: {e}")
        return "System error."

def extract_text_from_pdf(pdf_file):
    import PyPDF2
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        return "".join([page.extract_text() + "\n" for page in pdf_reader.pages])
    except:
        return None

def analyze_resume(resume_text, target_role="Software Engineering Intern"):
    prompt = f"""
    Act as an Expert ATS. Analyze this resume for {target_role}.
    Provide Markdown output with: 1. ATS Score 2. Strengths 3. Weaknesses 4. Actionable Steps.
    RESUME: {resume_text}
    """
    try:
        response = llm.invoke(prompt)
        return response.strip() if isinstance(response, str) else response.content.strip()
    except Exception as e:
        print(f"Resume analysis failed: {e}")
        return None

def generate_placement_prediction(elo_rating, weak_topics_dict):
    base_score = max(0, min(100, int(((elo_rating - 1000) / 1000) * 100)))
    weaknesses = ", ".join([f"{t}" for t, c in weak_topics_dict.items()])
    if not weaknesses: weaknesses = "None"
        
    prompt = f"""
    Act as a Hiring Manager. ELO: {elo_rating}. Weaknesses: {weaknesses}. Score: {base_score}%.
    Generate an improvement roadmap in pure Markdown.
    """
    try:
        response = llm.invoke(prompt)
        reply = response.strip() if isinstance(response, str) else response.content.strip()
        return base_score, reply
    except Exception as e:
        print(f"Prediction failed: {e}")
        return base_score, "System error."
import json

def process_interview_answer(role, current_question, user_answer, current_difficulty):
    """Evaluates the user's answer and generates an adaptive next question."""
    
    prompt = f"""
    Act as a strict Senior FAANG Interviewer hiring for a {role} role.
    
    Current Difficulty Level: {current_difficulty}
    Question Asked: {current_question}
    Candidate's Answer: {user_answer}
    
    EVALUATION & ADAPTATION RULES:
    1. Score the answer strictly out of 10.
    2. Identify what was good and what was explicitly missing (Edge cases, optimizations, etc.).
    3. ADAPTIVE QUESTIONING: 
       - If Technical Score >= 7: Increase difficulty or ask a deep follow-up.
       - If Technical Score < 7: Keep the same difficulty or simplify the concept.
    
    RETURN FORMAT (STRICT JSON ONLY):
    {{
        "technical_score": <int 1-10>,
        "communication_score": <int 1-10>,
        "positive_feedback": "<1 short sentence on what they did right>",
        "improvement_feedback": "<1 short sentence on what they missed>",
        "next_question": "<Write the next adaptive interview question here>",
        "new_difficulty": "<Easy/Medium/Hard>"
    }}
    """
    
    try:
        # Assuming you are using the Gemini setup we configured earlier
        response = model.generate_content(prompt)
        reply = response.text.strip()
        
        # Using your existing extract_json utility
        parsed_data = extract_json(reply)
        return parsed_data
    except Exception as e:
        print(f"Interview evaluation failed: {e}")
        return None        