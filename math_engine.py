import math

def calculate_expected_score(rating_a, rating_b):
    """
    Calculates the probability of Player A (Student) winning against Player B (Question).
    """
    return 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))

def update_elo(student_rating, question_rating, is_correct, k_factor=32):
    """
    Updates the student's ELO rating based on their answer.
    k_factor determines how much a single question impacts the score.
    """
    # Expected probability of the student getting it right
    expected_score = calculate_expected_score(student_rating, question_rating)
    
    # Actual score: 1 if correct, 0 if wrong
    actual_score = 1 if is_correct else 0
    
    # Calculate new rating
    new_student_rating = student_rating + k_factor * (actual_score - expected_score)
    
    return int(new_student_rating)

def get_next_difficulty(student_rating):
    """Decides the difficulty of the next question based on current ELO."""
    if student_rating < 1300:
        return "Basic Foundation", 1000
    elif student_rating < 1700:
        return "GATE Standard", 1500
    else:
        return "Advanced (Tough)", 2000