import os
import sys
from unittest.mock import MagicMock, patch

# Add the project directory to sys.path so we can import app modules
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_dir)

# Import dependencies
from app.utils import generate_question_explanation

def run_mock_test():
    print("Running Mock Test of generate_question_explanation...")
    question_text = "What is the unit of electrical resistance?"
    student_answer = "Farad"
    correct_answer = "Ohm"
    
    # Mock explanation that is exactly 12 words (within the 10-15 word limit)
    mock_explanation = "Ohm is the unit of resistance; Farad is the unit of capacitance."
    
    # Create mock response structure
    mock_resp = MagicMock()
    mock_resp.text = mock_explanation
    
    # Mock GenerativeModel instance
    mock_model_instance = MagicMock()
    mock_model_instance.generate_content.return_value = mock_resp
    
    # Apply patches
    with patch('app.utils.GEMINI_API_KEY', 'AIzaSyFakeKey'):
        with patch('google.generativeai.GenerativeModel') as mock_generative_model:
            mock_generative_model.return_value = mock_model_instance
            
            result = generate_question_explanation(
                question_text=question_text,
                student_answer=student_answer,
                correct_answer=correct_answer
            )
            
            # Verify the model was initialized with correct name
            mock_generative_model.assert_called_once_with('gemini-3.6-flash')
            
            # Verify generate_content was called and prompt contains our instructions
            called_prompt = mock_model_instance.generate_content.call_args[0][0]
            assert "gemini-3.6-flash" not in called_prompt  # verifying only query/context is present
            assert "10 to 15 words" in called_prompt
            
            print("Mock test passed!")
            print(f"Mock Response generated: {result}")
            word_count = len(result.split())
            print(f"Word count: {word_count} words (within 10-15 words limit: {10 <= word_count <= 15})")

if __name__ == "__main__":
    run_mock_test()
