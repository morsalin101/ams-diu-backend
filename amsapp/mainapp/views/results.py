from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Case, When, IntegerField
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from ..models import (
    PublishedExam, Exam, Students, Submission, Subject, 
    StudentAssignTeacherExam, User, ExamQuestion
)
from ..models.viva_marks import VivaMarks
from ..serializers.results import (
    PublishedExamSerializer, TogglePublishSerializer, 
    EnhancedExamResultSerializer, ResultsSummarySerializer
)
from ..authentication import CustomJWTAuthentication


@extend_schema(
    operation_id='toggle_exam_publication',
    tags=['Exam Results'],
    summary="Toggle exam result publication status",
    description="Toggle the publication status of exam results. Same endpoint handles both publish and unpublish actions.",
    request=TogglePublishSerializer,
    responses={
        200: OpenApiResponse(
            response=PublishedExamSerializer,
            description="Publication status toggled successfully"
        ),
        404: OpenApiResponse(description="Exam not found"),
        400: OpenApiResponse(description="Invalid request data")
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@authentication_classes([CustomJWTAuthentication])
def toggle_exam_publication(request):
    """Toggle exam result publication status"""
    
    serializer = TogglePublishSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'message': 'Invalid request data',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    exam_id = serializer.validated_data['exam_id']
    
    try:
        exam = Exam.objects.get(id=exam_id)
        
        # Get or create published exam record
        published_exam, created = PublishedExam.objects.get_or_create(
            exam=exam,
            defaults={'is_published': False}
        )
        
        # Toggle the publication status
        published_exam.is_published = not published_exam.is_published
        published_exam.save()
        
        action = "published" if published_exam.is_published else "unpublished"
        
        return Response({
            'success': True,
            'message': f'Exam results {action} successfully',
            'data': PublishedExamSerializer(published_exam).data
        })
        
    except Exam.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Exam not found'
        }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    operation_id='get_student_exam_result_enhanced',
    tags=['Exam Results'],
    summary="Get enhanced student exam result with subject breakdown",
    description="Get detailed exam result for a student including subject-wise breakdown. Results are only available if published.",
    responses={
        200: OpenApiResponse(
            response=EnhancedExamResultSerializer,
            description="Exam result retrieved successfully"
        ),
        403: OpenApiResponse(description="Results not published yet"),
        404: OpenApiResponse(description="Student or exam not found")
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CustomJWTAuthentication])
def get_student_exam_result_enhanced(request, exam_id, student_id):
    """Get enhanced student exam result with subject breakdown"""
    
    try:
        exam = Exam.objects.get(id=exam_id)
        student = Students.objects.get(id=student_id)
        
        # Check if results are published
        try:
            published_exam = PublishedExam.objects.get(exam=exam)
            if not published_exam.is_published:
                return Response({
                    'success': False,
                    'message': 'Results are not published yet'
                }, status=status.HTTP_403_FORBIDDEN)
        except PublishedExam.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Results are not published yet'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get student's submissions for this exam
        submissions = Submission.objects.filter(
            student=student,
            exam=exam
        ).select_related('question')
        
        if not submissions.exists():
            return Response({
                'success': False,
                'message': 'No submissions found for this student and exam'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Calculate overall results
        total_submissions = submissions.count()
        correct_submissions = submissions.filter(is_correct=True).count()
        wrong_submissions = total_submissions - correct_submissions
        score_percentage = (correct_submissions / total_submissions * 100) if total_submissions > 0 else 0
        
        # Get all subjects from this exam first
        exam_subjects = ExamQuestion.objects.filter(exam=exam).values_list('subject', flat=True).distinct()
        
        # Initialize subjects_data with all subjects from the exam
        subjects_data = {}
        for subject_name in exam_subjects:
            subjects_data[subject_name] = {
                'subject_id': subject_name,
                'subject_name': subject_name,
                'total_questions': 0,
                'correct_answers': 0,
                'wrong_answers': 0,
            }
        
        # Count total questions per subject in the exam
        for subject_name in exam_subjects:
            total_questions_in_subject = ExamQuestion.objects.filter(exam=exam, subject=subject_name).count()
            subjects_data[subject_name]['total_questions'] = total_questions_in_subject
        
        # Calculate subject-wise results from submissions
        for submission in submissions:
            subject_name = submission.question.subject
            if submission.is_correct:
                subjects_data[subject_name]['correct_answers'] += 1
            else:
                subjects_data[subject_name]['wrong_answers'] += 1
        
        # Calculate percentage for each subject
        for subject_name in subjects_data:
            subject_data = subjects_data[subject_name]
            total = subject_data['total_questions']
            correct = subject_data['correct_answers']
            subject_data['score_percentage'] = (correct / total * 100) if total > 0 else 0
        
        # Prepare response
        response_data = {
            'student_id': student.id,
            'exam_id': exam.id,
            'student_name': student.full_name or student.username,
            'exam_details': {
                'department': exam.department,
                'semester': exam.semester,
                'total_questions': exam.total_questions
            },
            'results': {
                'correct_answers': correct_submissions,
                'wrong_answers': wrong_submissions,
                'score_percentage': round(score_percentage, 2)
            },
            'subjects': list(subjects_data.values())
        }
        
        return Response({
            'success': True,
            'data': response_data
        })
        
    except Exam.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Exam not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Students.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Student not found'
        }, status=status.HTTP_404_NOT_FOUND)


class ResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema(
    operation_id='get_all_results_by_teacher',
    tags=['Exam Results'],
    summary="Get all exam results summary for a teacher",
    description="Get paginated results summary for all students under a teacher. Superadmin sees all results, others see results based on teacher_id.",
    parameters=[
        OpenApiParameter(name='semester', description='Filter by semester', required=False, type=str),
        OpenApiParameter(name='page', description='Page number', required=False, type=int),
        OpenApiParameter(name='page_size', description='Number of results per page', required=False, type=int),
    ],
    responses={
        200: OpenApiResponse(
            response=ResultsSummarySerializer,
            description="Results summary retrieved successfully"
        ),
        404: OpenApiResponse(description="Teacher not found")
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CustomJWTAuthentication])
def get_all_results_by_teacher(request, teacher_id):
    """Get all exam results summary for a teacher with pagination and filtering"""
    
    user = request.user
    semester_filter = request.query_params.get('semester', None)
    
    # Check permissions
    if hasattr(user, 'custom_user'):
        custom_user = user.custom_user
        
        # Check if user has a role
        if custom_user.role:
            role_name = custom_user.role.role_name.lower()
            
            # If not superadmin, ensure they can only see their own results
            if role_name != 'superadmin' and custom_user.id != teacher_id:
                return Response({
                    'success': False,
                    'message': 'You can only view your own results'
                }, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({
                'success': False,
                'message': 'Access denied'
            }, status=status.HTTP_403_FORBIDDEN)
    else:
        return Response({
            'success': False,
            'message': 'Access denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        teacher = User.objects.get(id=teacher_id)

        # Find all exam_ids assigned by this teacher
        exam_ids = StudentAssignTeacherExam.objects.filter(
            teacher=teacher
        ).values_list('exam_id', flat=True).distinct()

        # Apply semester filter if provided
        if semester_filter:
            exams = Exam.objects.filter(id__in=exam_ids, semester__icontains=semester_filter)
        else:
            exams = Exam.objects.filter(id__in=exam_ids)

        from collections import defaultdict

        exams_list = list(exams)
        exam_ids_list = [e.id for e in exams_list]

        assignments = list(StudentAssignTeacherExam.objects.filter(
            teacher=teacher, exam_id__in=exam_ids_list
        ))
        
        assigned_student_ids = list(set([a.student_id for a in assignments]))
        students_dict = {s.id: s for s in Students.objects.filter(id__in=assigned_student_ids)}

        exam_student_map = defaultdict(list)
        for a in assignments:
            exam_student_map[a.exam_id].append(a.student_id)

        exam_subject_counts = defaultdict(lambda: defaultdict(int))
        for eq in ExamQuestion.objects.filter(exam_id__in=exam_ids_list):
            exam_subject_counts[eq.exam_id][eq.subject] += 1

        submissions_list = list(Submission.objects.filter(
            exam_id__in=exam_ids_list,
            student_id__in=assigned_student_ids
        ).select_related('question'))

        submissions_dict = defaultdict(lambda: defaultdict(list))
        for sub in submissions_list:
            submissions_dict[sub.exam_id][sub.student_id].append(sub)

        viva_marks_dict = {v.student_id: v for v in VivaMarks.objects.filter(student_id__in=assigned_student_ids)}

        results_data = []

        for exam in exams_list:
            student_ids = exam_student_map.get(exam.id, [])
            exam_subjects_dict = exam_subject_counts.get(exam.id, {})

            for s_id in student_ids:
                if s_id not in students_dict: continue
                student = students_dict[s_id]

                student_submissions = submissions_dict.get(exam.id, {}).get(s_id, [])

                if student_submissions:
                    total_submissions = len(student_submissions)
                    correct_submissions = sum(1 for s in student_submissions if s.is_correct)
                    wrong_submissions = total_submissions - correct_submissions
                    score_percentage = (correct_submissions / total_submissions * 100) if total_submissions > 0 else 0

                    subjects_data = {}
                    for subject_name, total_q in exam_subjects_dict.items():
                        subjects_data[subject_name] = {
                            'subject_id': subject_name,
                            'subject_name': subject_name,
                            'total_questions': total_q,
                            'correct_answers': 0,
                            'wrong_answers': 0,
                        }

                    for s in student_submissions:
                        subject_name = s.question.subject
                        if subject_name not in subjects_data:
                            subjects_data[subject_name] = {
                                'subject_id': subject_name,
                                'subject_name': subject_name,
                                'total_questions': 0,
                                'correct_answers': 0,
                                'wrong_answers': 0,
                            }
                        if s.is_correct:
                            subjects_data[subject_name]['correct_answers'] += 1
                        else:
                            subjects_data[subject_name]['wrong_answers'] += 1

                    for s_data in subjects_data.values():
                        total = s_data['total_questions']
                        correct = s_data['correct_answers']
                        s_data['score_percentage'] = (correct / total * 100) if total > 0 else 0

                    viva = viva_marks_dict.get(s_id)
                    if viva:
                        viva_marks_data = {
                            'marks': viva.marks,
                            'rubrics_marks': viva.rubrics_marks,
                            'remarks': viva.remarks
                        }
                    else:
                        viva_marks_data = {
                            'marks': 0,
                            'rubrics_marks': {},
                            'remarks': None
                        }

                    result_item = {
                        'student_id': student.id,
                        'exam_id': exam.id,
                        'student_name': student.full_name or student.username,
                        'exam_details': {
                            'department': exam.department,
                            'semester': exam.semester,
                            'total_questions': exam.total_questions
                        },
                        'results': {
                            'correct_answers': correct_submissions,
                            'wrong_answers': wrong_submissions,
                            'score_percentage': round(score_percentage, 2)
                        },
                        'subjects': list(subjects_data.values()),
                        'viva_marks': viva_marks_data
                    }
                    results_data.append(result_item)


        # Apply pagination
        paginator = ResultsPagination()
        page = paginator.paginate_queryset(results_data, request)

        # Prepare pagination info
        pagination_info = {
            'count': len(results_data),
            'current_page': paginator.page.number,
            'total_pages': paginator.page.paginator.num_pages,
            'page_size': paginator.page_size,
            'has_next': paginator.page.has_next(),
            'has_previous': paginator.page.has_previous()
        }

        # Prepare filters info
        filters_info = {
            'semester': semester_filter,
            'teacher_id': teacher_id,
            'teacher_name': teacher.username
        }

        response_data = {
            'pagination': pagination_info,
            'results': page if page is not None else results_data,
            'filters': filters_info
        }

        return Response({
            'success': True,
            'data': response_data,
            'message': f'Found {len(results_data)} results for teacher {teacher.username}'
        })

    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Teacher not found'
        }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    operation_id='get_published_exams',
    tags=['Exam Results'],
    summary="Get all published exams",
    description="Get list of all exams with their publication status",
    responses={
        200: OpenApiResponse(
            response=PublishedExamSerializer(many=True),
            description="Published exams retrieved successfully"
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@authentication_classes([CustomJWTAuthentication])
def get_published_exams(request):
    """Get all published exams"""
    
    user = request.user
    
    # Role-based filtering
    if hasattr(user, 'custom_user'):
        custom_user = user.custom_user
        
        if custom_user.role:
            role_name = custom_user.role.role_name.lower()
            
            if role_name == 'superadmin':
                # Superadmin sees all published exams
                published_exams = PublishedExam.objects.all().select_related('exam')
            else:
                # Non-superadmin sees exams filtered by department
                if custom_user.department:
                    user_dept_shortname = custom_user.department.department_shortname
                    
                    # Get exam IDs that match user's department
                    from ..models.exam_question import ExamQuestion
                    exam_ids = ExamQuestion.objects.filter(
                        department_shortname__icontains=user_dept_shortname
                    ).values_list('exam_id', flat=True).distinct()
                    
                    published_exams = PublishedExam.objects.filter(
                        exam_id__in=exam_ids
                    ).select_related('exam')
                else:
                    published_exams = PublishedExam.objects.none()
        else:
            published_exams = PublishedExam.objects.none()
    else:
        published_exams = PublishedExam.objects.none()
    
    serializer = PublishedExamSerializer(published_exams, many=True)
    return Response({
        'success': True,
        'data': serializer.data,
        'message': 'Published exams retrieved successfully'
    })