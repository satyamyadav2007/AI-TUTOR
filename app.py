# --- SQLITE BYPASS HACK FOR STREAMLIT CLOUD ---
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass # Local windows machine par error ignore karne ke liye
# ----------------------------------------------

import streamlit as st
import streamlit.components.v1 as components
import time

# ... (baaki aapke saare purane imports yahan se shuru honge) ...import streamlit as st
import streamlit.components.v1 as components
import time
import re
import sys
from io import StringIO
from streamlit_ace import st_ace

from models import QuestionModel
from math_engine import update_elo, get_next_difficulty
from database import init_db, create_user, login_user, update_user_progress, increment_usage


# Import functions from ai_engine
from ai_engine import (
    generate_single_question, 
    generate_concept_only, 
    evaluate_dsa_code, 
    generate_dsa_problem, 
    generate_pyq_variant,
    gemini_model # Import Gemini directly for Tab 10
)

# ----------------- DIAGRAM RENDERER -----------------
def render_diagram(mermaid_code, theme_mode='light'): 
    if not mermaid_code or mermaid_code.strip() == "" or mermaid_code.lower() == "none":
        return
    
    cleaned_code = re.sub(r'```[a-zA-Z]*\n?', '', mermaid_code)
    cleaned_code = cleaned_code.replace('```', '').strip()
    
    if not cleaned_code.startswith(("graph", "flowchart", "sequenceDiagram", "classDiagram", "stateDiagram")):
        cleaned_code = "graph TD\n" + cleaned_code

    mermaid_theme = 'light' if theme_mode == "Light Mode" else 'default'

    components.html(
        f"""
        <div class="mermaid" style="background-color: transparent;">
            {cleaned_code}
        </div>
        <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
        <script>
            mermaid.initialize({{
                startOnLoad: true,
                theme: 'default',
                securityLevel: 'loose'
            }});
        </script>
        """,
        height=650,          
        scrolling=True       
    )

st.set_page_config(page_title="Heizen Exam Portal", layout="wide", initial_sidebar_state="expanded")

# ----------------- SESSION STATES -----------------
init_db()

default_states = {
    "questions": [], "user_answers": {}, "current_q": 0,
    "exam_active": False, "exam_submitted": False,
    "start_time": None, "seen_hashes": set(), "weak_topics": {},
    "subject": "", "topic": "", "current_concept": None,
    "current_elo": 1200,
    "logged_in": False,   
    "username": "" ,  
    "dsa_solved": {"Easy": 0, "Medium": 0, "Hard": 0},
    "generations_used": 0,
    "is_pro": False
}

for key, value in default_states.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ==========================================
# 🔐 AUTHENTICATION UI (LOGIN/SIGNUP)
# ==========================================
if not st.session_state.logged_in:
    st.title("🧠 Welcome to Heizen")
    st.markdown("Your AI-Powered GATE CSE Mentor")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        auth_mode = st.radio("Choose Action", ["Login", "Sign Up"], horizontal=True)
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if auth_mode == "Sign Up":
            if st.button("Create Account"):
                if username and password:
                    if create_user(username, password):
                        st.success("Account created! You can now Login.")
                    else:
                        st.error("Username already exists. Try another one.")
                else:
                    st.warning("Please enter both username and password.")
                    
        elif auth_mode == "Login":
            if st.button("Login"):
                user_data = login_user(username, password)
                if user_data:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.current_elo = user_data["elo"]
                    st.session_state.weak_topics = user_data["weak_topics"]
                    st.session_state.generations_used = user_data.get("generations_used", 0)
                    st.session_state.is_pro = user_data.get("is_pro", False)
                    st.success(f"Welcome back, {username}!")
                    st.rerun()
                else:
                    st.error("Incorrect Username or Password.")
                    
    st.stop()

# ==========================================
# 🛡️ GLOBAL FREEMIUM LIMIT CHECKER
# ==========================================
def check_limit():
    """Checks if the user has free limits left. Returns True if allowed, False if locked."""
    is_pro = st.session_state.get('is_pro', False)
    usage_count = st.session_state.get('generations_used', 0)
    
    if not is_pro and usage_count >= 5:
        st.error("🔒 Free Limit Reached (5/5).")
        st.markdown("### 👑 Upgrade to Heizen PRO")
        st.write("Get Unlimited AI generations, Priority AI Doubt Solver, and Advanced Mock Interviews.")
        st.markdown("""
        <a href='https://razorpay.me/@yourupi' target='_blank'>
            <button style='background-color: #f0b90b; color: black; border: none; padding: 10px 20px; border-radius: 5px; font-weight: bold; cursor: pointer;'>💳 Upgrade Now for ₹99/month</button>
        </a>
        """, unsafe_allow_html=True)
        return False
    return True

def log_usage():
    """Logs the API call and increments the user's limit meter."""
    try:
        increment_usage(st.session_state.username)
        st.session_state.generations_used += 1
    except Exception as e:
        print(f"Failed to log usage: {e}")

def update_weak_topics():
    for i, q in enumerate(st.session_state.questions):
        topic = q.get("topic", "Unknown")
        user_ans = st.session_state.user_answers.get(i)
        correct_ans = q.get("answer", "") 
        
        is_correct = False
        if q.get("type", "MCQ") == "MCQ" or "options" in q:
            is_correct = user_ans == correct_ans
        elif q.get("type") == "MSQ" and isinstance(user_ans, list):
            is_correct = set(user_ans) == set(correct_ans)
        elif q.get("type") == "NAT":
            is_correct = str(user_ans).strip() == str(correct_ans).strip()

        if not is_correct:
            st.session_state.weak_topics[topic] = st.session_state.weak_topics.get(topic, 0) + 1

# ----------------- SIDEBAR -----------------
st.sidebar.title("🧠 Heizen Portal")
if not st.session_state.get('is_pro', False):
    st.sidebar.markdown(f"**Free Limits:** {st.session_state.get('generations_used', 0)} / 5 Used")
    st.sidebar.progress(st.session_state.get('generations_used', 0) / 5.0)
    st.sidebar.warning("Upgrade to PRO for Unlimited Generations!")
else:
    st.sidebar.success("👑 PRO Member (Unlimited Access)")
st.sidebar.markdown("---")

# Permanent Light Mode CSS
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden;}
    .stApp { background-color: #FFFFFF; color: #000000; }
    .stButton>button { background: linear-gradient(135deg, #4A90E2 0%, #50E3C2 100%); color: white; border-radius: 8px; border: none; font-weight: bold; }
    div.stExpander > details > summary { color: #000000; }
    </style>
    """, unsafe_allow_html=True)

if st.session_state.weak_topics:
    st.sidebar.markdown("## 🔥 Weak Topics")
    for topic, mistakes in sorted(st.session_state.weak_topics.items(), key=lambda x: x[1], reverse=True):
        st.sidebar.warning(f"{topic} → {mistakes} mistakes")

# GLOBAL SUBJECT LIST
GATE_SUBJECTS = [
    "Engineering Mathematics (Linear Algebra, Calculus, Probability)",
    "Discrete Mathematics (Logic, Sets, Graph Theory)",
    "Digital Logic",
    "Computer Organization and Architecture (COA)",
    "Programming and Data Structures",
    "Algorithms",
    "Theory of Computation (TOC)",
    "Compiler Design",
    "Operating Systems",
    "Databases (DBMS)",
    "Computer Networks",
    "General Aptitude"
]

# ----------------- SETUP UI ROUTER -----------------

if st.session_state.exam_active:
    # ==========================================
    # 📝 1. EXAM RUNNING UI
    # ==========================================
    try:
        q_index = int(st.session_state.current_q)
    except ValueError: 
        q_index = 0
        st.session_state.current_q = 0
            
    q_data = st.session_state.questions[q_index]        
    
    st.subheader(f"Question {q_index + 1} | MCQ")
    st.info("Select ONE answer")
    st.markdown(f"**{q_data['question']}**")
    
    choice = st.radio("Options:", q_data.get('options', []), index=None, key=f"radio_{q_index}", label_visibility="collapsed")
    if choice:
        st.session_state.user_answers[q_index] = choice
        
    st.markdown("---")
    col_prev, col_empty, col_next = st.columns([1, 2, 1])
    
    with col_prev:
        if q_index > 0:
            if st.button("⬅️ Previous", use_container_width=True):
                st.session_state.current_q -= 1
                st.rerun()
                
    with col_next:
        if q_index < len(st.session_state.questions) - 1:
            if st.button("Next ➡️", use_container_width=True):
                st.session_state.current_q += 1
                st.rerun()
        else:
            if st.button("✅ Submit Exam", use_container_width=True):
                st.session_state.exam_active = False
                st.session_state.exam_submitted = True
                st.rerun()

elif st.session_state.exam_submitted:
    # ==========================================
    # 📊 2. EXAM RESULT UI
    # ==========================================
    st.success("Test Submitted Successfully!")
    st.markdown("---")
    st.subheader("📊 Detailed Result Analysis")
    
    total_q = len(st.session_state.questions)
    correct_ans = 0
    unattempted = 0
    
    for i, q in enumerate(st.session_state.questions):
        user_ans = st.session_state.user_answers.get(i)
        correct_solution = q.get('answer', q.get('ANS'))
        
        if user_ans == correct_solution:
            correct_ans += 1
        elif user_ans in [None, "", []]:
            unattempted += 1
            
    incorrect_ans = total_q - (correct_ans + unattempted)
    accuracy = (correct_ans / (total_q - unattempted) * 100) if (total_q - unattempted) > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ Correct", correct_ans)
    col2.metric("❌ Incorrect", incorrect_ans)
    col3.metric("⚠️ Unattempted", unattempted)
    col4.metric("🎯 Accuracy", f"{accuracy:.1f}%")
    st.markdown("---")
    
    if st.button("🏠 Back to Dashboard"):
        st.session_state.exam_submitted = False
        st.session_state.questions = []
        st.session_state.user_answers = {}
        st.session_state.current_q = 0
        st.rerun()
        
    st.subheader("📝 Question-wise Solutions")
    for i, q in enumerate(st.session_state.questions):
        st.markdown(f"**Q{i+1}: {q.get('question')}**")
        user_ans = st.session_state.user_answers.get(i)
        correct_solution = q.get('answer', q.get('ANS'))
        
        if user_ans == correct_solution:
            st.success(f"Your Answer: {user_ans} (Correct)")
        elif user_ans in [None, "", []]:
            st.warning(f"Unattempted. Correct Answer was: {correct_solution}")
        else:
            st.error(f"Your Answer: {user_ans} (Incorrect)")
            st.success(f"Correct Answer: {correct_solution}")
            
        with st.expander("💡 View Concept & Detailed Solution"):
            st.write(q.get('explanation', 'Explanation not found.'))
        st.markdown("<br>", unsafe_allow_html=True)

else:
    # ==========================================
    # 🏠 3. MAIN DASHBOARD (TABS)
    # ==========================================
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
        "📝 Mock Test", "🔥 Weak Topics", "💻 DSA Arena", 
        "📅 Study Planner", "📸 AI Doubt Solver", "🎤 AI Interviewer", 
        "📄 Resume Analyzer", "🎯 Placement Predictor", "🏆 Leaderboard", "🧠 AI Mentor Dashboard"
    ])
    
    with tab10:
        st.title("🧠 Core AI Mentor & Knowledge Graph")
        st.markdown("Your ultimate performance dashboard for fine-grained tracking and strategic guidance.")
        
        col_graph, col_mentor = st.columns([1.5, 1])
        
        with col_graph:
            st.subheader("🕸️ Knowledge Graph Engine")
            st.markdown("Visualizing your mastery across GATE CSE concepts.")
            import pandas as pd
            
            mastery_data = {
                "Topic": ["Operating Systems", "DBMS", "Computer Networks", "Data Structures", "Algorithms", "TOC"],
                "Mastery Level (%)": [85, 70, 45, 92, 60, 50]
            }
            
            df_graph = pd.DataFrame(mastery_data)
            st.bar_chart(df_graph.set_index("Topic"), color="#f0b90b")
            st.caption("Lower bars indicate weak nodes in your Knowledge Graph that need immediate remediation.")
            
        with col_mentor:
            st.subheader("🤖 Strategic AI Mentor")
            st.markdown("Ask for mistake diagnosis and performance analysis.")
            
            mentor_query = st.text_area("What do you need help with today?", placeholder="e.g., Why am I struggling with Computer Networks?")
            
            if st.button("💡 Get Strategic Guidance"):
                if mentor_query:
                    if check_limit(): # 🛡️ Limit Checker
                        with st.spinner("Analyzing your Knowledge Graph..."):
                            try:
                                prompt = f"""
                                Act as the Ultimate GATE CSE AI Mentor.
                                The student has an ELO of {st.session_state.current_elo}.
                                Their weak topics are: {st.session_state.weak_topics}.
                                Student Query: {mentor_query}
                                Provide a highly strategic, encouraging, and data-driven response.
                                """
                                response = gemini_model.generate_content(prompt)
                                reply = response.text.strip()
                                
                                st.success("Diagnosis Complete:")
                                st.markdown(reply)
                                log_usage() # 🛡️ Log usage after success
                            except Exception as e:
                                st.error(f"Mentor engine offline: {e}")
                else:
                    st.warning("Please enter a query first.")
                    
    with tab9:
        st.title("🏆 Hall of Fame & Rewards")
        st.markdown("Compete with other GATE aspirants and unlock verified Heizen certificates.")
        
        col_lead, col_cert = st.columns([1.2, 1])
        
        with col_lead:
            st.subheader("🌍 Global Leaderboard")
            import pandas as pd
            
            leaderboard_data = [
                {"Username": "GATE_Cracker", "ELO Rating": 1950, "Tier": "Grandmaster 👑"},
                {"Username": "OS_Wizard", "ELO Rating": 1820, "Tier": "Master 💎"},
                {"Username": "CodeNinja", "ELO Rating": 1750, "Tier": "Diamond 🏅"},
                {"Username": "TOC_King", "ELO Rating": 1450, "Tier": "Platinum 🥈"},
                {"Username": st.session_state.username, "ELO Rating": st.session_state.current_elo, "Tier": "Your Rank 🎯"},
                {"Username": "Newbie_Coder", "ELO Rating": 1100, "Tier": "Bronze 🥉"}
            ]
            
            df = pd.DataFrame(leaderboard_data)
            df = df.sort_values(by="ELO Rating", ascending=False).reset_index(drop=True)
            df.index = df.index + 1 
            
            st.dataframe(df, use_container_width=True)
            
        with col_cert:
            st.subheader("🎓 Your Certificates")
            if st.session_state.current_elo >= 1200:
                st.success("Achievement Unlocked: Foundation Scholar!")
                cert_html = f"""
                <div style="background-color: #ffffff; border: 8px solid #f0b90b; padding: 25px; text-align: center; border-radius: 8px; color: #333333; box-shadow: 0px 5px 15px rgba(0,0,0,0.08);">
                    <h2 style="color: #f0b90b; margin-bottom: 5px; font-family: 'Times New Roman', serif; font-size: 24px;">CERTIFICATE OF EXCELLENCE</h2>
                    <p style="font-size: 14px; margin-bottom: 15px; color: #666666;">This is proudly presented to</p>
                    <h1 style="color: #2c3e50; margin: 10px 0; font-family: Arial, sans-serif; text-transform: uppercase; font-size: 28px;">{st.session_state.username}</h1>
                    <p style="font-size: 16px; margin-bottom: 15px;">For demonstrating outstanding proficiency and achieving an ELO Rating of <b>{st.session_state.current_elo}</b></p>
                    <p style="font-size: 13px; font-style: italic; color: #777777;">Mathematically Verified by Heizen Adaptive AI Core</p>
                </div>
                """
                st.markdown(cert_html, unsafe_allow_html=True)
            else:
                st.info("Reach 1200 ELO to unlock your first verified certificate!")

    # --- TAB 3: DSA ARENA ---
    with tab3:
        st.title("💻 LeetCode Style DSA Arena")
        
        if "dsa_solved" not in st.session_state:
            st.session_state.dsa_solved = {"Easy": 0, "Medium": 0, "Hard": 0}
            
        total_solved = sum(st.session_state.dsa_solved.values())
        
        st.markdown("### 📊 Your Progress Dashboard")
        col_dash1, col_dash2, col_dash3, col_dash4 = st.columns(4)
        col_dash1.metric("🔥 Total Solved", total_solved)
        col_dash2.metric("🟢 Easy", st.session_state.dsa_solved["Easy"])
        col_dash3.metric("🟡 Medium", st.session_state.dsa_solved["Medium"])
        col_dash4.metric("🔴 Hard", st.session_state.dsa_solved["Hard"])
        st.markdown("---")
        
        col_topic, col_diff, col_btn = st.columns([2, 2, 1])
        with col_topic:
            dsa_topic = st.selectbox("Select Topic", ["Arrays & Hashing", "Two Pointers", "Sliding Window", "Dynamic Programming", "Graphs", "Trees"])
        with col_diff:
            dsa_diff = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
        
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⚡ Generate Problem"):
                if check_limit(): # 🛡️ Limit Checker
                    with st.spinner("Crafting a problem..."):
                        problem_data = generate_dsa_problem(dsa_topic, dsa_diff)
                        if problem_data:
                            st.session_state.current_dsa_problem = problem_data
                            st.session_state.current_dsa_diff = dsa_diff 
                            log_usage() # 🛡️ Log usage after success
                        else:
                            st.error("Failed to generate problem. Try again.")

        if "current_dsa_problem" in st.session_state and st.session_state.current_dsa_problem:
            active_prob = st.session_state.current_dsa_problem
            
            st.markdown("---")
            col_desc, col_editor = st.columns([1, 1.2])
            
            with col_desc:
                diff_color = "🟢" if st.session_state.current_dsa_diff == "Easy" else "🟡" if st.session_state.current_dsa_diff == "Medium" else "🔴"
                st.subheader(f"{diff_color} {active_prob.get('title', 'Coding Problem')}")
                st.write(active_prob.get("description", ""))
                st.markdown("**Example Test Cases:**")
                for tc in active_prob.get("test_cases", []):
                    st.code(f"Input: {tc.get('input')}\nOutput: {tc.get('output')}", language="text")
                    
            with col_editor:
                lang_map = {"Python": "python", "C++": "c_cpp", "Java": "java", "C": "c_cpp"}
                selected_lang = st.selectbox("Programming Language", ["Python", "C++", "Java", "C"], index=0)
                st.subheader("👨‍💻 Code Editor")
                
                default_code = active_prob.get("starter_code", "// Write your code here")
                if selected_lang != "Python" and "def" in default_code:
                    default_code = "// Write your code here\n"
                
                user_code = st_ace(
                    value=default_code, language=lang_map[selected_lang], theme='chrome', keybinding='vscode',
                    font_size=14, tab_size=4, height=350, key="dsa_editor"
                )
                
                if selected_lang != "Python":
                    st.caption("⚠️ Local 'Run Code' execution only supports Python. Use '🤖 Submit to AI Judge' for C++/Java/C.")
                
                col_run, col_analyze = st.columns(2)
                
                with col_run:
                    if st.button(f"▶️ Compile & Run ({selected_lang})", width="stretch"):
                        st.markdown("### 🖥️ Console Output:")
                        with st.spinner(f"Compiling {selected_lang} code completely for FREE..."):
                            import requests
                            url = "https://emkc.org/api/v2/piston/execute"
                            piston_langs = {
                                "Python": {"language": "python", "version": "3.10.0"},
                                "C++": {"language": "c++", "version": "10.2.0"},
                                "Java": {"language": "java", "version": "15.0.2"},
                                "C": {"language": "c", "version": "10.2.0"}
                            }
                            payload = {
                                "language": piston_langs[selected_lang]["language"], "version": piston_langs[selected_lang]["version"],
                                "files": [{"content": user_code}], "stdin": "" 
                            }
                            try:
                                response = requests.post(url, json=payload)
                                result = response.json()
                                if "compile" in result and result["compile"]["code"] != 0:
                                    st.error("❌ Compilation Error:")
                                    st.code(result["compile"]["output"], language="text")
                                elif "run" in result:
                                    run_data = result["run"]
                                    if run_data["code"] == 0:
                                        st.success("✅ Execution Successful!")
                                        st.code(run_data["output"], language="text")
                                    else:
                                        st.error("❌ Runtime Error:")
                                        st.code(run_data["output"], language="text")
                                else:
                                    st.error("⚠️ Unknown Error occurred.")
                            except Exception as e:
                                st.error(f"Execution Engine Connection Failed: {e}")

                with col_analyze:
                    if st.button("🤖 Submit to AI Judge"):
                        if check_limit(): # 🛡️ Limit Checker
                            with st.spinner(f"Heizen is evaluating your {selected_lang} code... 🕵️‍♂️"):
                                analysis = evaluate_dsa_code(active_prob.get("title", ""), active_prob.get("description", ""), user_code, selected_lang)
                                if analysis:
                                    log_usage() # 🛡️ Log usage after success
                                    st.markdown("---")
                                    status_str = analysis.get('status', '')
                                    status_color = "🟢" if "Accepted" in status_str else "🔴"
                                    st.subheader(f"{status_color} Status: {status_str} (Score: {analysis.get('score', 'N/A')})")
                                    
                                    if "Accepted" in status_str:
                                        st.session_state.dsa_solved[st.session_state.current_dsa_diff] += 1
                                        st.balloons()
                                    
                                    m1, m2 = st.columns(2)
                                    m1.metric("⏱️ Time Complexity", analysis.get('time_complexity', 'N/A'))
                                    m2.metric("💾 Space Complexity", analysis.get('space_complexity', 'N/A'))
                                    
                                    st.info(f"**Edge Cases Checked:**\n{analysis.get('edge_cases', 'N/A')}")
                                    st.warning(f"**Mentor's Detailed Feedback:**\n{analysis.get('detailed_feedback', '')}")
                                    with st.expander("💡 View Highly Optimized Code"):
                                        st.code(analysis.get('optimized_code', '// Not available'), language=lang_map[selected_lang])
                                else:
                                    st.error("AI Evaluation failed. Please try again.")

    # --- TAB 8: PLACEMENT PREDICTOR ---
    with tab8:
        st.title("🎯 Placement Predictor")
        st.markdown("Calculate your exact readiness score for tech placements and get a customized action plan.")
        st.info("💡 Heizen uses your current ELO Rating and Weak Topics history to predict your readiness.")
        
        if st.button("📊 Calculate My Placement Readiness"):
            if check_limit(): # 🛡️ Limit Checker
                with st.spinner("Analyzing your entire Heizen profile..."):
                    from ai_engine import generate_placement_prediction
                    score, roadmap = generate_placement_prediction(st.session_state.current_elo, st.session_state.weak_topics)
                    log_usage() # 🛡️ Log usage after success
                    
                    st.markdown("---")
                    col_score1, col_score2 = st.columns([1, 3])
                    with col_score1:
                        st.metric("Readiness Score", f"{score}%")
                    with col_score2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.progress(score / 100.0)
                        if score < 50: st.error("Needs significant improvement before applying.")
                        elif score < 80: st.warning("On the right track, but needs more practice.")
                        else: st.success("Highly competitive! Ready for interviews.")
                            
                    st.markdown("### 🗺️ Your Personalized Placement Roadmap")
                    st.markdown(roadmap)
                
    # --- TAB 6: AI INTERVIEWER ---
    with tab6:
        st.title("👔 Adaptive AI Mock Interviewer")
        st.markdown("FAANG-level evaluation with real-time feedback and dynamic difficulty.")
        
        if "interview_started" not in st.session_state:
            st.session_state.interview_started = False
            st.session_state.interview_history = []
            st.session_state.current_q = ""
            st.session_state.current_diff = "Medium"
            
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            target_role = st.selectbox("Target Role", ["SDE-1", "Frontend Developer", "Data Scientist", "Backend Engineer"])
        with col2:
            start_topic = st.selectbox("Focus Area", ["Data Structures", "System Design", "HR/Behavioral", "Core CS Subjects"])
            
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 Start Interview", width="stretch") and not st.session_state.interview_started:
                if check_limit(): # 🛡️ Limit Checker
                    st.session_state.interview_started = True
                    st.session_state.current_q = f"Welcome! To start, can you explain a complex concept in {start_topic} that you are comfortable with?"
                    st.session_state.interview_history = []
                    log_usage() # 🛡️ Log usage after success
                    st.rerun()

        st.markdown("---")
        
        if st.session_state.interview_started:
            for turn in st.session_state.interview_history:
                with st.chat_message("user", avatar="👤"):
                    st.write(f"**You:** {turn['answer']}")
                    
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown("### 📊 Evaluation Scorecard")
                    score_col1, score_col2 = st.columns(2)
                    score_col1.metric("⚙️ Technical Accuracy", f"{turn['scores'].get('technical_score', 'N/A')}/10")
                    score_col2.metric("🗣️ Communication", f"{turn['scores'].get('communication_score', 'N/A')}/10")
                    st.success(f"**✓ Strong Point:** {turn['scores'].get('positive_feedback', '')}")
                    st.error(f"**✗ Area to Improve:** {turn['scores'].get('improvement_feedback', '')}")
                    st.markdown("---")
                    st.write(f"**Interviewer:** {turn['next_q']}")

            if not st.session_state.interview_history:
                with st.chat_message("assistant", avatar="🤖"):
                    st.write(f"**Interviewer:** {st.session_state.current_q}")
                    st.caption(f"Current Difficulty: {st.session_state.current_diff}")

            user_answer = st.text_area("Your Answer:", height=150, placeholder="Type your answer here or explain your logic...")
            
            if st.button("Submit Answer & Continue ➡️"):
                if user_answer.strip():
                    if check_limit(): # 🛡️ Limit Checker
                        with st.spinner("Evaluating your response..."):
                            from ai_engine import process_interview_answer
                            evaluation = process_interview_answer(target_role, st.session_state.current_q, user_answer, st.session_state.current_diff)
                            
                            if evaluation:
                                log_usage() # 🛡️ Log usage after success
                                st.session_state.interview_history.append({
                                    "question": st.session_state.current_q, "answer": user_answer,
                                    "scores": evaluation, "next_q": evaluation.get("next_question", "Let's move on.")
                                })
                                st.session_state.current_q = evaluation.get("next_question", "Could you elaborate more?")
                                st.session_state.current_diff = evaluation.get("new_difficulty", st.session_state.current_diff)
                                st.rerun()
                            else:
                                st.error("Evaluation failed. Please try submitting again.")
                else:
                    st.warning("Please type an answer before submitting.")

    # --- TAB 5: AI DOUBT SOLVER ---
    with tab5:
        st.title("📸 AI Doubt Solver")
        st.markdown("Stuck on a tricky graph, logic circuit, or equation? Upload a photo and let Heizen solve it!")
        
        uploaded_file = st.file_uploader("Upload your doubt (JPG, PNG)", type=["jpg", "jpeg", "png"])
        
        if uploaded_file is not None:
            st.image(uploaded_file, caption="Your Doubt")
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("🧠 Solve this Doubt"):
                if check_limit(): # 🛡️ Limit Checker
                    with st.spinner("Heizen is analyzing the image and generating a step-by-step solution..."):
                        from ai_engine import solve_doubt_from_image
                        solution = solve_doubt_from_image(uploaded_file)
                        
                        if solution.startswith("Error"):
                            st.error(solution)
                        else:
                            log_usage() # 🛡️ Log usage after success
                            st.success("Doubt Solved!")
                            st.markdown("### Solution:")
                            st.markdown(solution)
                        
    # --- TAB 7: RESUME ANALYZER ---
    with tab7:
        st.title("📄 AI Resume Analyzer")
        st.markdown("Upload your resume to get an ATS score, weakness detection, and improvement roadmap. ")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            target_role = st.text_input("Target Job Role", value="Software Engineering Intern")
            
        uploaded_resume = st.file_uploader("Upload Resume (PDF format only)", type=["pdf"])
        
        if uploaded_resume is not None:
            if st.button("🔍 Scan & Analyze Resume"):
                if check_limit(): # 🛡️ Limit Checker
                    with st.spinner("Heizen ATS is scanning your resume for keywords and impact..."):
                        from ai_engine import extract_text_from_pdf, analyze_resume
                        resume_text = extract_text_from_pdf(uploaded_resume)
                        
                        if resume_text and len(resume_text.strip()) > 50:
                            analysis_result = analyze_resume(resume_text, target_role)
                            if analysis_result:
                                log_usage() # 🛡️ Log usage after success
                                st.success("Analysis Complete!")
                                st.markdown("---")
                                st.markdown(analysis_result)
                            else:
                                st.error("AI failed to analyze the resume. Please try again.")
                        else:
                            st.error("Could not extract text. Please ensure it is a text-based PDF.")                    
                        
    # --- TAB 4: AI PERSONALIZED STUDY PLANNER ---
    with tab4:
        st.title("📅 AI Personalized Study Planner")
        st.markdown("Your gamified, daily-actionable roadmap to crack GATE.")
        
        st.markdown("### 📊 Your Progress Dashboard")
        if "streak" not in st.session_state: st.session_state.streak = 3
        
        col_dash1, col_dash2, col_dash3 = st.columns([1, 1, 2])
        with col_dash1: st.metric("🔥 Study Streak", f"{st.session_state.streak} Days", "+1 Today")
        with col_dash2: st.metric("🎯 Current ELO", st.session_state.current_elo)
        with col_dash3:
            st.markdown("**Topic Mastery**")
            st.progress(0.8, text="Data Structures (80%)")
            st.progress(0.3, text="Computer Networks (30% - Needs Work)")
            st.progress(0.65, text="Operating Systems (65%)")
            
        st.markdown("---")
        
        col_slider, col_btn = st.columns([2, 1])
        with col_slider:
            plan_days = st.slider("Select Plan Duration (Days)", 7, 30, 15)
            
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗺️ Generate My Dynamic Roadmap", width="stretch"):
                if check_limit(): # 🛡️ Limit Checker
                    with st.spinner("Heizen is analyzing your weak topics and building a master plan..."):
                        from ai_engine import generate_study_plan
                        plan_data = generate_study_plan(st.session_state.current_elo, st.session_state.weak_topics, days=plan_days)
                        
                        if plan_data:
                            log_usage() # 🛡️ Log usage after success
                            st.session_state.study_plan_json = plan_data
                            st.session_state.checkbox_states = {}
                            st.success("Plan generated successfully!")
                        else:
                            st.error("Failed to generate plan.")
                        
        if "study_plan_json" in st.session_state and isinstance(st.session_state.study_plan_json, list):
            st.markdown("---")
            st.subheader("📝 Your Daily Action Items")
            for day_plan in st.session_state.study_plan_json:
                day_num = day_plan.get('day', '?')
                focus = day_plan.get('focus_topic', 'General Revision')
                tasks = day_plan.get('tasks', [])
                
                with st.expander(f"📅 Day {day_num}: {focus}", expanded=(day_num == 1)):
                    for task_idx, task in enumerate(tasks):
                        task_key = f"task_{day_num}_{task_idx}"
                        if task_key not in st.session_state.get("checkbox_states", {}):
                            if "checkbox_states" not in st.session_state: st.session_state.checkbox_states = {}
                            st.session_state.checkbox_states[task_key] = False
                            
                        checked = st.checkbox(task, key=task_key)
                        st.session_state.checkbox_states[task_key] = checked
                        
                    day_tasks_total = len(tasks)
                    day_tasks_done = sum(1 for i in range(day_tasks_total) if st.session_state.checkbox_states.get(f"task_{day_num}_{i}"))
                    if day_tasks_total > 0:
                        day_progress = day_tasks_done / day_tasks_total
                        st.progress(day_progress)
                        if day_progress == 1.0: st.success("🎉 Day Complete! Streak Maintained.")       
                            
    # --- TAB 1: NORMAL TEST ---
    
    with tab1:
        st.title("🎯 Create Mock Test")
        col1, col2 = st.columns(2)
        with col1: subject = st.selectbox("Subject", GATE_SUBJECTS, key="tab1_sub")
        with col2: difficulty = st.selectbox("Difficulty", ["Basic Foundation", "GATE Standard", "Advanced (Tough)"])
            
        topic = st.text_input("Enter Topic")
        num_questions = st.slider("Questions", 3, 15, 5, key="tab1_slider")

        if st.button("🚀 Generate Infinite PYQ Test"):
            if check_limit(): # 🛡️ Limit Checker
                st.session_state.subject = subject
                st.session_state.topic = topic
                
                with st.spinner(f"Heizen is batch-crafting {num_questions} GATE PYQs at lightning speed... ⚡"):
                    
                    # Naya Batch function import karein
                    from ai_engine import generate_batch_pyq_variants
                    
                    # Sirf EK API Call! Koi loop nahi, koi time.sleep nahi!
                    batch_data = generate_batch_pyq_variants(
                        subject=st.session_state.subject, 
                        topic=st.session_state.topic, 
                        difficulty=difficulty,
                        num_questions=num_questions
                    )
                    
                    if batch_data and len(batch_data) > 0:
                        log_usage() # 🛡️ Sirf ek baar limit meter badhega
                        st.session_state.questions = batch_data
                        st.session_state.user_answers = {i: None for i in range(len(st.session_state.questions))}
                        st.session_state.exam_active = True
                        st.session_state.exam_submitted = False
                        st.session_state.start_time = time.time()
                        
                        st.success("Test Generated Successfully! Scroll down to start.")
                        st.rerun()
                    else:
                        st.error("Engine failed to generate data. Please try again.")
    # --- TAB 2: WEAK TOPIC REMEDIATION ---
    with tab2:
        st.title("🩺 Targeted Remediation")
        st.markdown("Instantly learn any concept, then practice at your own pace.")
        
        col_sub, col_top = st.columns([1, 2])
        with col_sub: weak_subject = st.selectbox("Select Subject", GATE_SUBJECTS, key="weak_sub")
        with col_top: weak_topic = st.text_input("Enter the exact topic (e.g., Banker's Algorithm)", key="weak_top")

        if st.button("🧠 Explain Concept Instantly"):
            if weak_topic.strip():
                if check_limit(): # 🛡️ Limit Checker
                    with st.spinner("Fetching concept... ⚡"):
                        concept_data = generate_concept_only(weak_subject, weak_topic)
                        if concept_data:
                            log_usage() # 🛡️ Log usage after success
                            st.session_state.current_concept = concept_data
                        else:
                            st.error("Failed to load concept. Try rephrasing.")
            else:
                st.error("Please enter a topic first.")

        if st.session_state.current_concept:
            st.markdown("---")
            st.markdown(f"### 📖 Concept: {weak_topic}")
            st.markdown(st.session_state.current_concept.get("concept_capsule", "No explanation provided."))
            
            diagram_code = st.session_state.current_concept.get("mermaid_diagram_code")
            if diagram_code: render_diagram(diagram_code, "Light Mode")
                
            st.markdown("---")
            st.markdown("#### Ready to test your knowledge?")
            
            col_btn, col_slider = st.columns([1, 2])
            with col_slider: practice_count = st.slider("Number of questions to generate", 1, 5, 2, key="prac_count")
            
            with col_btn:
                if st.button("⚙️ Generate Practice Questions"):
                    if check_limit(): # 🛡️ Limit Checker
                        st.info(f"Crafting {practice_count} GATE-level questions... Please wait.")
                        progress_bar = st.progress(0)
                        
                        generated_list = []
                        for idx in range(practice_count):
                            q, q_hash = generate_single_question(weak_subject, weak_topic, "GATE Standard", st.session_state.seen_hashes)
                            time.sleep(5)
                            
                            if q:
                                q["concept_capsule"] = st.session_state.current_concept.get("concept_capsule", "")
                                q["mermaid_diagram_code"] = st.session_state.current_concept.get("mermaid_diagram_code", "")
                                generated_list.append(q)
                                st.session_state.seen_hashes.add(q_hash)
                            progress_bar.progress(int(((idx + 1) / practice_count) * 100))
                        
                        if generated_list:
                            log_usage() # 🛡️ Log usage after success
                            st.success("Questions Ready!")
                            st.session_state.questions = generated_list
                            st.session_state.user_answers = {i: None for i in range(len(generated_list))}
                            st.session_state.exam_active = True
                            st.session_state.start_time = time.time()
                            st.session_state.current_concept = None 
                            time.sleep(1)
                            st.rerun()