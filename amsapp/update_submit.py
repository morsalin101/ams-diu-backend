import re

with open("c:/Users/ASUS/Desktop/ams/ams-diu-backend/amsapp/mainapp/views/student_app.py", "r") as f:
    text = f.read()

def normalize_compare_code():
    return """
            def normalize_str(s):
                if not isinstance(s, str): return str(s)
                import re
                return re.sub(r'\\s+', '', s.lower())

            # Determine correctness
            is_correct = False
            submitted_answer = str(answer).strip()

            if exam_question.type == 'option':
                # Check normal key
                is_correct = normalize_str(submitted_answer) in [normalize_str(c) for c in correct_answers]
                # Also check value just in case they sent the text value
                if not is_correct and isinstance(exam_question.options, dict):
                    opt_values = {normalize_str(k): normalize_str(v) for k, v in exam_question.options.items()}
                    if normalize_str(submitted_answer) in opt_values.values():
                        # user sent the value text!
                        # verify if the value matches the correct options value
                        for c_key in correct_answers:
                            norm_c_key = normalize_str(c_key)
                            if opt_values.get(norm_c_key) == normalize_str(submitted_answer):
                                is_correct = True
                                break
                    else:
                        # user sent a key, verify it
                        norm_sub_key = normalize_str(submitted_answer)
                        for c_key in correct_answers:
                            norm_c_key = normalize_str(c_key)
                            # Maybe the correct answers array stores textual values instead of keys?
                            if opt_values.get(norm_sub_key) == norm_c_key:
                                is_correct = True
                                break
            else:
                is_correct = any(normalize_str(submitted_answer) == normalize_str(ca) for ca in correct_answers)
"""

# replace 
text = re.sub(r"""\s*# Determine correctness\s*is_correct = False\s*submitted_answer = str\(answer\)\.strip\(\).*?if exam_question\.type.*?is_correct.*?\n.*?(?:elif|else):.*?is_correct.*?for ca in correct_answers\)""", normalize_compare_code(), text, flags=re.DOTALL)

with open("c:/Users/ASUS/Desktop/ams/ams-diu-backend/amsapp/mainapp/views/student_app.py", "w") as f:
    f.write(text)
