from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from ..models import Students, ExamSchedule, Exam, ExamQuestion, Submission, PublishedExam
from ..serializers import (
    StudentsSerializer, StudentLoginSerializer, ExamSubmissionSerializer,
    StudentLoginResponseSerializer, ExamSubmissionResponseSerializer
)
from ..authentication import CustomJWTAuthentication


@extend_schema(
    operation_id='student_login',
    summary="Student login",
    description="Authenticate student with username and password",
    tags=['Student App'],
    request=StudentLoginSerializer,
    responses={
        200: StudentLoginResponseSerializer,
        401: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    }
)
@csrf_exempt
@api_view(['POST'])
def student_login(request):
    """Student login endpoint"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response(
            {'error': 'Username and password are required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        student = Students.objects.get(username=username, password=password)
        return Response({
            'message': 'Login successful',
            'student': StudentsSerializer(student).data
        }, status=status.HTTP_200_OK)
    except Students.DoesNotExist:
        return Response(
            {'error': 'Invalid credentials'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )


@extend_schema(
    summary="Student available exams",
    description="Get all active exam schedules available to students",
    tags=['Student App'],
    responses={200: {
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'schedule_id': {'type': 'integer'},
                'exam_id': {'type': 'integer'},
                'exam_name': {'type': 'string'},
                'department': {'type': 'string'},
                'semester': {'type': 'string'},
                'total_questions': {'type': 'integer'},
                'duration_minutes': {'type': 'integer'},
                'start_time': {'type': 'string'},
                'end_time': {'type': 'string'},
                'is_active': {'type': 'boolean'}
            }
        }
    }}
)
class StudentAvailableExamsView(generics.ListAPIView):
    """List all available active exam schedules for students"""
    
    def get_queryset(self):
        return ExamSchedule.objects.filter(is_active=True).order_by('start_time')
    
    def list(self, request, *args, **kwargs):
        schedules = self.get_queryset()
        exam_list = []
        
        for schedule in schedules:
            exam_data = {
                'schedule_id': schedule.id,
                'exam_id': schedule.exam.id,
                'exam_name': f"{schedule.exam.department} - {schedule.exam.semester}",
                'department': schedule.exam.department,
                'semester': schedule.exam.semester,
                'total_questions': schedule.exam.total_questions,
                'duration_minutes': schedule.exam.duration_minutes,
                'start_time': schedule.start_time,
                'end_time': schedule.end_time,
                'is_active': schedule.is_active
            }
            exam_list.append(exam_data)
        
        return Response(exam_list, status=status.HTTP_200_OK)


@extend_schema(
    summary="Student exam questions",
    description="Get all questions for a specific exam",
    tags=['Student App'],
    responses={200: {
        'type': 'object',
        'properties': {
            'exam_id': {'type': 'integer'},
            'exam_details': {
                'type': 'object',
                'properties': {
                    'department': {'type': 'string'},
                    'semester': {'type': 'string'},
                    'total_questions': {'type': 'integer'},
                    'duration_minutes': {'type': 'integer'}
                }
            },
            'questions': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'question_id': {'type': 'integer'},
                        'question_text': {'type': 'string'},
                        'options': {'type': 'array', 'items': {'type': 'string'}},
                        'question_type': {'type': 'string'}
                    }
                }
            }
        }
    }}
)
class StudentExamQuestionsView(generics.RetrieveAPIView):
    """Get all questions for a specific exam (for students taking the exam)"""
    lookup_url_kwarg = 'exam_id'
    
    def retrieve(self, request, *args, **kwargs):
        exam_id = kwargs.get('exam_id')
        
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response(
                {'error': 'Exam not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all questions for this exam (ExamQuestion contains the question data directly)
        exam_questions = ExamQuestion.objects.filter(exam=exam).order_by('id')
        
        questions_data = []
        for eq in exam_questions:
            question_data = {
                'question_id': eq.id,
                'question_text': eq.question_text,
                'options': eq.options,
                'question_type': eq.type,
                'marks': eq.marks,
                'subject': eq.subject
            }
            questions_data.append(question_data)
        
        response_data = {
            'exam_id': exam.id,
            'exam_details': {
                'department': exam.department,
                'semester': exam.semester,
                'total_questions': exam.total_questions,
                'duration_minutes': exam.duration_minutes
            },
            'questions': questions_data
        }
        
        return Response(response_data, status=status.HTTP_200_OK)


import json

@extend_schema(
    operation_id='submit_exam',
    summary="Submit exam answers",
    description="Submit student answers for an exam",
    tags=['Student App'],
    request=ExamSubmissionSerializer,
    responses={
        201: ExamSubmissionResponseSerializer,
        400: {
            'type': 'object',
            'properties': {
                'error': {'type': 'string'}
            }
        }
    }
)
@csrf_exempt
@api_view(['POST'])
def submit_exam(request, exam_id):
    """Submit exam answers"""
    student_id = request.data.get('student_id')
    submissions = request.data.get('submissions', [])
    
    if not student_id:
        return Response(
            {'error': 'Student ID is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not submissions:
        return Response(
            {'error': 'At least one answer submission is required'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        student = Students.objects.get(id=student_id)
        exam = Exam.objects.get(id=exam_id)
    except (Students.DoesNotExist, Exam.DoesNotExist):
        return Response(
            {'error': 'Student or Exam not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    submissions_created = 0
    
    for submission_data in submissions:
        question_id = submission_data.get('question_id')
        answer = submission_data.get('answer', '').strip()
        
        if not question_id:
            continue
        
        try:
            # Get the ExamQuestion (not ScrappedQuestion)
            exam_question = ExamQuestion.objects.get(id=question_id, exam=exam)
            
            # Parse the correct answer which might be stored as a JSON string (e.g. '["গ"]')
            correct_answers_raw = exam_question.answer
            correct_answers = []
            
            if isinstance(correct_answers_raw, str):
                try:
                    parsed_answer = json.loads(correct_answers_raw)
                    if isinstance(parsed_answer, list):
                        correct_answers = [str(x).strip() for x in parsed_answer]
                    else:
                        correct_answers = [str(parsed_answer).strip()]
                except json.JSONDecodeError:
                    correct_answers = [str(correct_answers_raw).strip()]
            elif isinstance(correct_answers_raw, list):
                correct_answers = [str(x).strip() for x in correct_answers_raw]
            else:
                correct_answers = [str(correct_answers_raw).strip()]

            # Determine correctness
            def normalize_str(s):
                if not isinstance(s, str): return str(s)
                import re
                # replace smart quotes, normalize whitespace
                s = s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
                return re.sub(r'\s+', '', s.lower())

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
                            if opt_values.get(norm_sub_key) == norm_c_key:
                                is_correct = True
                                break
            else:
                is_correct = any(normalize_str(submitted_answer) == normalize_str(ca) for ca in correct_answers)
            # Add debug printing as per requirement
            print("========================================")
            print(f"DEBUG EXAM SUBMISSION")
            print(f"Question ID: {question_id}")
            print(f"Question Type: {exam_question.type}")
            print(f"User answer: '{submitted_answer}'")
            print(f"Correct answer(s) (raw): {repr(correct_answers_raw)}")
            print(f"Correct answer(s) (parsed): {correct_answers}")
            print(f"Is Correct?: {is_correct}")
            print("========================================")
            
            # Create or update submission
            submission, created = Submission.objects.update_or_create(
                student=student,
                exam=exam,
                question=exam_question,
                defaults={
                    'answer': answer,
                    'is_correct': is_correct
                }
            )
            
            if created:
                submissions_created += 1
                
        except ExamQuestion.DoesNotExist:
            continue
    
    return Response({
        'message': f'Exam submitted successfully',
        'total_submitted': submissions_created
    }, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Get exam result",
    description="Get student's exam result and performance details",
    tags=['Student App'],
    responses={200: {
        'type': 'object',
        'properties': {
            'student_id': {'type': 'integer'},
            'exam_id': {'type': 'integer'},
            'student_name': {'type': 'string'},
            'exam_details': {
                'type': 'object',
                'properties': {
                    'department': {'type': 'string'},
                    'semester': {'type': 'string'},
                    'total_questions': {'type': 'integer'}
                }
            },
            'results': {
                'type': 'object',
                'properties': {
                    'total_questions_attempted': {'type': 'integer'},
                    'correct_answers': {'type': 'integer'},
                    'wrong_answers': {'type': 'integer'},
                    'score_percentage': {'type': 'number'},
                    'grade': {'type': 'string'}
                }
            }
        }
    }}
)
@api_view(['GET'])
def get_exam_result(request, student_id, exam_id):
    """Get exam result for a specific student and exam"""
    try:
        student = Students.objects.get(id=student_id)
        exam = Exam.objects.get(id=exam_id)
    except (Students.DoesNotExist, Exam.DoesNotExist):
        return Response(
            {'error': 'Invalid student or exam ID'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if results are published
    try:
        published_exam = PublishedExam.objects.get(exam=exam)
        if not published_exam.is_published:
            return Response(
                {'error': 'Results are not published yet'}, 
                status=status.HTTP_403_FORBIDDEN
            )
    except PublishedExam.DoesNotExist:
        # If no PublishedExam record exists, treat as unpublished
        return Response(
            {'error': 'Results are not published yet'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get all submissions for this student and exam
    submissions = Submission.objects.filter(student=student, exam=exam)
    
    if not submissions.exists():
        return Response(
            {'error': 'No submissions found for this student and exam'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Calculate results
    total_attempted = submissions.count()
    correct_submissions = submissions.filter(is_correct=True)
    correct_answers = correct_submissions.count()
    wrong_answers = total_attempted - correct_answers
    
    total_questions = ExamQuestion.objects.filter(exam=exam).count()
    total_marks = sum(ExamQuestion.objects.filter(exam=exam).values_list('marks', flat=True))
    obtained_marks = sum(s.question.marks for s in correct_submissions)
    
    # Calculate percentage
    if total_marks > 0:
        score_percentage = round((obtained_marks / total_marks) * 100, 2)
    else:
        score_percentage = 0
    
    # Determine grade
    if score_percentage >= 90:
        grade = 'A+'
    elif score_percentage >= 80:
        grade = 'A'
    elif score_percentage >= 70:
        grade = 'B'
    elif score_percentage >= 60:
        grade = 'C'
    elif score_percentage >= 50:
        grade = 'D'
    else:
        grade = 'F'
    
    response_data = {
        'student_id': student.id,
        'exam_id': exam.id,
        'student_name': student.username,
        'exam_details': {
            'department': exam.department,
            'semester': exam.semester,
            'total_questions': exam.total_questions
        },
        'results': {
            'total_questions_attempted': total_attempted,
            'correct_answers': correct_answers,
            'wrong_answers': wrong_answers,
            'obtained_marks': obtained_marks,
            'total_marks': total_marks,
            'score_percentage': score_percentage,
            'grade': grade
        }
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


@extend_schema(
    summary="Calculate exam results",
    description="Calculate and display results for all students who took a specific exam",
    tags=['Student App'],
    responses={200: {
        'type': 'object',
        'properties': {
            'exam_id': {'type': 'integer'},
            'exam_details': {
                'type': 'object',
                'properties': {
                    'department': {'type': 'string'},
                    'semester': {'type': 'string'},
                    'total_questions': {'type': 'integer'}
                }
            },
            'results': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'student_id': {'type': 'integer'},
                        'student_name': {'type': 'string'},
                        'f_id': {'type': 'string'},
                        'total_questions_attempted': {'type': 'integer'},
                        'correct_answers': {'type': 'integer'},
                        'wrong_answers': {'type': 'integer'},
                        'score_percentage': {'type': 'number'},
                        'grade': {'type': 'string'}
                    }
                }
            },
            'class_statistics': {
                'type': 'object',
                'properties': {
                    'total_students': {'type': 'integer'},
                    'average_score': {'type': 'number'},
                    'highest_score': {'type': 'number'},
                    'lowest_score': {'type': 'number'}
                }
            }
        }
    }}
)
@api_view(['GET'])
def calculate_exam_result(request, exam_id):
    """Calculate results for all students who took a specific exam"""
    try:
        exam = Exam.objects.get(id=exam_id)
    except Exam.DoesNotExist:
        return Response(
            {'error': 'Exam not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all students who submitted answers for this exam
    students_with_submissions = Students.objects.filter(
        submission__exam=exam
    ).distinct()
    
    if not students_with_submissions.exists():
        return Response(
            {'error': 'No submissions found for this exam'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    results = []
    all_scores = []
    
    for student in students_with_submissions:
        # Get submissions for this student and exam
        submissions = Submission.objects.filter(student=student, exam=exam)
        
        total_attempted = submissions.count()
        correct_submissions = submissions.filter(is_correct=True)
        correct_answers = correct_submissions.count()
        wrong_answers = total_attempted - correct_answers
        
        total_questions = ExamQuestion.objects.filter(exam=exam).count()
        total_marks = sum(ExamQuestion.objects.filter(exam=exam).values_list('marks', flat=True))
        obtained_marks = sum(s.question.marks for s in correct_submissions)
        
        # Calculate percentage using obtained marks vs total marks
        if total_marks > 0:
            score_percentage = round((obtained_marks / total_marks) * 100, 2)
        else:
            score_percentage = 0
            
        all_scores.append(score_percentage)
        
        # Determine grade
        if score_percentage >= 90:
            grade = 'A+'
        elif score_percentage >= 80:
            grade = 'A'
        elif score_percentage >= 70:
            grade = 'B'
        elif score_percentage >= 60:
            grade = 'C'
        elif score_percentage >= 50:
            grade = 'D'
        else:
            grade = 'F'
        
        student_result = {
            'student_id': student.id,
            'student_name': student.username,
            'f_id': student.f_id,
            'total_questions_attempted': total_attempted,
            'correct_answers': correct_answers,
            'wrong_answers': wrong_answers,
            'obtained_marks': obtained_marks,
            'total_marks': total_marks,
            'score_percentage': score_percentage,
            'grade': grade
        }
        results.append(student_result)
    
    # Calculate class statistics
    class_stats = {
        'total_students': len(all_scores),
        'average_score': round(sum(all_scores) / len(all_scores), 2) if all_scores else 0,
        'highest_score': max(all_scores) if all_scores else 0,
        'lowest_score': min(all_scores) if all_scores else 0
    }
    
    # Sort results by score percentage (highest first)
    results.sort(key=lambda x: x['score_percentage'], reverse=True)
    
    response_data = {
        'exam_id': exam.id,
        'exam_details': {
            'department': exam.department,
            'semester': exam.semester,
            'total_questions': exam.total_questions
        },
        'results': results,
        'class_statistics': class_stats
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


def calculate_exam_result_helper(student_id, exam_id):
    """Helper function to calculate exam result for a specific student and exam"""
    try:
        student = Students.objects.get(id=student_id)
        exam = Exam.objects.get(id=exam_id)
        
        # Get all submissions for this student and exam
        submissions = Submission.objects.filter(student=student, exam=exam)
        
        if not submissions.exists():
            return None
        
        # Calculate overall stats
        total_questions = ExamQuestion.objects.filter(exam=exam).count()
        answered_questions = submissions.count()
        correct_answers = submissions.filter(is_correct=True).count()
        
        # Calculate marks
        total_marks = sum(ExamQuestion.objects.filter(exam=exam).values_list('marks', flat=True))
        obtained_marks = sum(s.question.marks for s in submissions if s.is_correct)
        percentage = (obtained_marks / total_marks * 100) if total_marks > 0 else 0
        
        return {
            'exam_id': exam_id,
            'student_id': student_id,
            'student_username': student.username,
            'total_questions': total_questions,
            'answered_questions': answered_questions,
            'correct_answers': correct_answers,
            'total_marks': total_marks,
            'obtained_marks': obtained_marks,
            'percentage': round(percentage, 2)
        }
        
    except (Students.DoesNotExist, Exam.DoesNotExist):
        return None


@extend_schema(
    operation_id='get_student_scheduled_exams',
    summary="Get student scheduled exams",
    description="Get all scheduled exams assigned to a specific student based on StudentAssignTeacherExam assignments",
    tags=['Student App'],
    responses={200: {
        'type': 'object',
        'properties': {
            'student_id': {'type': 'integer'},
            'student_info': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string'},
                    'f_id': {'type': 'string'},
                    'department_shortname': {'type': 'string'},
                    'registration_semester': {'type': 'string'}
                }
            },
            'scheduled_exams': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'assignment_id': {'type': 'integer'},
                        'schedule_id': {'type': 'integer'},
                        'exam_id': {'type': 'integer'},
                        'exam_details': {
                            'type': 'object',
                            'properties': {
                                'department': {'type': 'string'},
                                'semester': {'type': 'string'},
                                'total_questions': {'type': 'integer'},
                                'total_marks': {'type': 'integer'},
                                'duration_minutes': {'type': 'integer'},
                                'language': {'type': 'string'},
                                'faculty': {'type': 'string'}
                            }
                        },
                        'schedule_details': {
                            'type': 'object',
                            'properties': {
                                'start_time': {'type': 'string'},
                                'end_time': {'type': 'string'},
                                'is_active': {'type': 'boolean'}
                            }
                        },
                        'teacher_info': {
                            'type': 'object',
                            'properties': {
                                'teacher_id': {'type': 'integer'},
                                'teacher_name': {'type': 'string'}
                            }
                        },
                        'assigned_at': {'type': 'string'}
                    }
                }
            },
            'total_assigned_exams': {'type': 'integer'}
        }
    }}
)
@api_view(['GET'])
def get_student_scheduled_exams(request, student_id):
    """Get all scheduled exams assigned to a specific student"""
    try:
        student = Students.objects.get(id=student_id)
    except Students.DoesNotExist:
        return Response(
            {'error': 'Student not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all assignments for this student with related data
    from ..models import StudentAssignTeacherExam
    assignments = StudentAssignTeacherExam.objects.filter(
        student=student
    ).select_related(
        'exam', 'teacher', 'schedule'
    ).order_by('-created_at')
    
    if not assignments.exists():
        return Response({
            'student_id': student.id,
            'student_info': {
                'username': student.username,
                'f_id': student.f_id,
                'department_shortname': student.department_shortname,
                'registration_semester': student.registration_semester
            },
            'scheduled_exams': [],
            'total_assigned_exams': 0
        }, status=status.HTTP_200_OK)
    
    scheduled_exams = []
    
    for assignment in assignments:
        # Check if student has submitted any answers for this exam
        submission_count = Submission.objects.filter(
            student=student,
            exam=assignment.exam
        ).count()
        
        # Check if student has submitted for all questions in the exam
        total_exam_questions = assignment.exam.total_questions
        has_submitted_all = submission_count == total_exam_questions
        
        exam_data = {
            'assignment_id': assignment.id,
            'schedule_id': assignment.schedule.id,
            'exam_id': assignment.exam.id,
            'exam_details': {
                'department': assignment.exam.department,
                'semester': assignment.exam.semester,
                'total_questions': assignment.exam.total_questions,
                'total_marks': assignment.exam.total_marks,
                'duration_minutes': assignment.exam.duration_minutes,
                'language': assignment.exam.language,
                'faculty': assignment.exam.faculty
            },
            'schedule_details': {
                'start_time': assignment.schedule.start_time,
                'end_time': assignment.schedule.end_time,
                'is_active': assignment.schedule.is_active
            },
            'teacher_info': {
                'teacher_id': assignment.teacher.id,
                'teacher_name': assignment.teacher.username
            },
            'submission_status': {
                'number_of_submissions': submission_count,
                'total_questions': total_exam_questions,
                'has_submitted': submission_count > 0,
                'is_completed': has_submitted_all,
                'completion_percentage': round((submission_count / total_exam_questions * 100), 2) if total_exam_questions > 0 else 0
            },
            'assigned_at': assignment.created_at
        }
        scheduled_exams.append(exam_data)
    
    response_data = {
        'student_id': student.id,
        'student_info': {
            'username': student.username,
            'f_id': student.f_id,
            'department_shortname': student.department_shortname,
            'registration_semester': student.registration_semester
        },
        'scheduled_exams': scheduled_exams,
        'total_assigned_exams': len(scheduled_exams)
    }
    
    return Response(response_data, status=status.HTTP_200_OK)


@extend_schema(
    operation_id='get_student_schedule',
    tags=['Student API'],
    summary="Get student's exam schedule",
    description="""
    Retrieve all scheduled exams for a specific student by student ID.
    Returns comprehensive schedule information including exam details, timing, and teacher information.
    """,
    parameters=[
        OpenApiParameter(
            name='student_id',
            description='Student ID to get schedule for',
            required=True,
            type=int,
            location=OpenApiParameter.PATH
        )
    ],
    responses={
        200: OpenApiResponse(
            description="Student schedule retrieved successfully",
            response={
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'assignment_id': {'type': 'integer'},
                                'schedule_id': {'type': 'integer'},
                                'exam_id': {'type': 'integer'},
                                'exam_name': {'type': 'string'},
                                'exam_duration': {'type': 'integer'},
                                'total_questions': {'type': 'integer'},
                                'schedule_start_time': {'type': 'string', 'format': 'date-time'},
                                'schedule_end_time': {'type': 'string', 'format': 'date-time'},
                                'teacher_name': {'type': 'string'},
                                'teacher_department': {'type': 'string'},
                                'subject_name': {'type': 'string'},
                                'department_shortnames': {'type': 'array', 'items': {'type': 'string'}},
                                'assigned_at': {'type': 'string', 'format': 'date-time'}
                            }
                        }
                    },
                    'message': {'type': 'string'}
                }
            }
        ),
        404: OpenApiResponse(description="Student not found"),
        403: OpenApiResponse(description="Authentication required")
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CustomJWTAuthentication])
def get_student_schedule(request, student_id):
    """Get all scheduled exams for a specific student"""
    
    try:
        # Verify student exists
        student = Students.objects.get(id=student_id)
    except Students.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Student not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get all assignments for this student with related data
    from ..models import StudentAssignTeacherExam
    assignments = StudentAssignTeacherExam.objects.filter(
        student_id=student_id
    ).select_related(
        'student', 'teacher', 'exam', 'schedule'
    ).order_by('-created_at')
    
    if not assignments.exists():
        return Response({
            'success': True,
            'data': [],
            'message': f'No scheduled exams found for student {student.username}'
        })
    
    # Prepare response data
    schedule_data = []
    
    for assignment in assignments:
        # Get exam questions to find department shortnames
        exam_questions = ExamQuestion.objects.filter(exam=assignment.exam).first()
        department_shortnames = []
        if exam_questions and exam_questions.department_shortnames:
            department_shortnames = [name.strip() for name in exam_questions.department_shortnames.split(',')]
        
        # Get subject information
        subject_name = "N/A"
        if hasattr(assignment.exam, 'subject') and assignment.exam.subject:
            subject_name = assignment.exam.subject
        
        schedule_info = {
            'assignment_id': assignment.id,
            'schedule_id': assignment.schedule.id,
            'exam_id': assignment.exam.id,
            'exam_name': assignment.exam.name if hasattr(assignment.exam, 'name') else f"Exam {assignment.exam.id}",
            'exam_duration': assignment.exam.duration if hasattr(assignment.exam, 'duration') else assignment.exam.duration_minutes,
            'total_questions': assignment.exam.total_questions,
            'schedule_start_time': assignment.schedule.start_time.isoformat(),
            'schedule_end_time': assignment.schedule.end_time.isoformat(),
            'teacher_name': assignment.teacher.username,
            'teacher_department': assignment.teacher.department.department_name if assignment.teacher.department else 'N/A',
            'subject_name': subject_name,
            'department_shortnames': department_shortnames,
            'assigned_at': assignment.created_at.isoformat(),
            'is_active': assignment.schedule.is_active
        }
        
        schedule_data.append(schedule_info)
    
    return Response({
        'success': True,
        'data': schedule_data,
        'message': f'Found {len(schedule_data)} scheduled exams for student {student.username}'
    })
