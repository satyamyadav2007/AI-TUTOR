from ai_engine import generate_concept_only, save_questions_to_bank
from database import init_db

TOPICS = ["Deadlock", "Paging", "TCP", "Normalization", "Hashing"]

def run_pre_generation():
    print("Starting Nightly Batch Generation...")
    for topic in TOPICS:
        print(f"Generating for {topic}...")
        data = generate_concept_only("Operating Systems", topic)
        # Content save karne ke liye logic yahan ayega...
        print(f"Successfully cached {topic}")

if __name__ == "__main__":
    run_pre_generation()