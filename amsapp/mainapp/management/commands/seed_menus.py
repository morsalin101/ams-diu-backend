from django.core.management.base import BaseCommand
from mainapp.models import Menu, Role, RoleMenu
from django.db import transaction


class Command(BaseCommand):
    help = 'Seed menu data and create superadmin role with full permissions'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Menu data based on your frontend structure
            menu_data = [
                # Dashboard
                {
                    'label': 'Dashboard',
                    'icon': 'LayoutDashboard',
                    'link': '/dashboard',
                    'component': 'Dashboard'
                },

                # Question Management
                {
                    'label': 'Create Question Set',
                    'icon': 'Plus',
                    'link': '/create-questions',
                    'component': 'CreateQuestions'
                },
                {
                    'label': 'All Question Sets',
                    'icon': 'FileText',
                    'link': '/all-questions',
                    'component': 'AllQuestions'
                },
                {
                    'label': 'Upload Questions(DB)',
                    'icon': 'FilePlus',
                    'link': '/insert-questions',
                    'component': 'InsertQuestions'
                },
                {
                    'label': 'Delete Questions(DB)',
                    'icon': 'Trash2',
                    'link': '/deletequestions',
                    'component': 'DeleteQuestions'
                },
                {
                    'label': 'Blocked Questions',
                    'icon': 'Slash',
                    'link': '/blocked-questions',
                    'component': 'BlockedQuestions'
                },
                {
                    'label': 'AI Question Scrapper',
                    'icon': 'Cpu',
                    'link': '/ai-question-scrapper',
                    'component': 'AiQuestionScrapper'
                },

                # Exam Controls and Mapping
                {
                    'label': 'Faculty Management',
                    'icon': 'Landmark',
                    'link': '/faculty-management',
                    'component': 'FacultyManagement'
                },
                {
                    'label': 'Department Management',
                    'icon': 'Building',
                    'link': '/department-management',
                    'component': 'DepartmentManagement'
                },
                {
                    'label': 'Faculty Department Mapping',
                    'icon': 'Layers',
                    'link': '/faculty-department-mapping',
                    'component': 'FacultyDepartmentMapping'
                },
                {
                    'label': 'Subject Management',
                    'icon': 'BookOpen',
                    'link': '/subject-management',
                    'component': 'SubjectManagement'
                },
                {
                    'label': 'Subject Faculty Mapping',
                    'icon': 'Layers',
                    'link': '/subject-department-mapping',
                    'component': 'SubjectDepartmentMapping'
                },
                {
                    'label': 'Subject Priority Mapping',
                    'icon': 'ArrowDownUp',
                    'link': '/subject-priority-mapping',
                    'component': 'SubjectPriorityMapping'
                },
                {
                    'label': 'Viva Rubrics Management',
                    'icon': 'Mic',
                    'link': '/viva-rubrics-management',
                    'component': 'VivaManagement'
                },
                {
                    'label': 'Marks Distribution Management',
                    'icon': 'Percent',
                    'link': '/marks-distribution',
                    'component': 'MarksDistribution'
                },
                {
                    'label': 'Report Signatories',
                    'icon': 'UserCheck',
                    'link': '/report-signatories',
                    'component': 'ReportSignatories'
                },

                # Departmental Controls
                {
                    'label': 'Student Acceptance Criteria',
                    'icon': 'Sliders',
                    'link': '/student-acceptance-criteria',
                    'component': 'ThresholdManagement'
                },
                {
                    'label': 'Publish Exam',
                    'icon': 'FileCheck',
                    'link': '/published-exams',
                    'component': 'PublishedExams'
                },
                {
                    'label': 'Exam Schedule',
                    'icon': 'Calendar',
                    'link': '/exam-schedule',
                    'component': 'ExamSchedule'
                },
                {
                    'label': 'Student Assign',
                    'icon': 'UserPlus',
                    'link': '/student-assign-teacher-exam',
                    'component': 'StudentAssignTeacherExam'
                },
                {
                    'label': 'Override Selection',
                    'icon': 'FileCheck',
                    'link': '/override-selection',
                    'component': 'ExamineeResult'
                },
                {
                    'label': 'Results',
                    'icon': 'FileText',
                    'link': '/results',
                    'component': 'AcceptedStudents'
                },

                # Faculty Controls
                {
                    'label': 'My Schedule',
                    'icon': 'FileSearch',
                    'link': '/my-schedule',
                    'component': 'MySchedule'
                },
                {
                    'label': 'Viva Marks Entry',
                    'icon': 'FilePlus',
                    'link': '/viva-marks-entry',
                    'component': 'Results'
                },
                {
                    'label': 'Viva marks',
                    'icon': 'Edit',
                    'link': '/viva-marks',
                    'component': 'VivaMarks'
                },
                {
                    'label': 'My Students',
                    'icon': 'UserGroup',
                    'link': '/my-students',
                    'component': 'MyStudents'
                },

                # Admission Office
                {
                    'label': 'Students',
                    'icon': 'Users',
                    'link': '/students',
                    'component': 'Students'
                },
                {
                    'label': 'All Results',
                    'icon': 'FileText',
                    'link': '/all-results',
                    'component': 'AllResults'
                },

                # Users & Roles
                {
                    'label': 'Menu Management',
                    'icon': 'Menu',
                    'link': '/menu-management',
                    'component': 'MenuManagement'
                },
                {
                    'label': 'Menu Access Management',
                    'icon': 'Key',
                    'link': '/menu-access-management',
                    'component': 'MenuAccessManagement'
                },
                {
                    'label': 'Role Management',
                    'icon': 'Shield',
                    'link': '/role-management',
                    'component': 'RoleManagement'
                },
                {
                    'label': 'Users Management',
                    'icon': 'UserCheck',
                    'link': '/users-management',
                    'component': 'UsersManagement'
                }
            ]

            # Create or update menus using component as the stable identity
            created_menus = []
            for menu_item in menu_data:
                menu, created = Menu.objects.update_or_create(
                    component=menu_item['component'],
                    defaults={
                        'label': menu_item['label'],
                        'icon': menu_item['icon'],
                        'link': menu_item['link']
                    }
                )
                created_menus.append(menu)
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created menu: {menu.label}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Updated menu: {menu.label}')
                    )

            # Create or get superadmin role
            superadmin_role, created = Role.objects.get_or_create(
                role_name='superadmin'
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS('Created superadmin role')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('Superadmin role already exists')
                )

            # Assign all menus to superadmin with full permissions
            full_permissions = {
                "read": True,
                "write": True,
                "edit": True,
                "delete": True
            }

            for menu in created_menus:
                role_menu, created = RoleMenu.objects.get_or_create(
                    role=superadmin_role,
                    menu=menu,
                    defaults={'permissions': full_permissions}
                )
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Assigned {menu.label} to superadmin with full permissions'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Menu {menu.label} already assigned to superadmin'
                        )
                    )

            # Clean up legacy menu rows that are no longer in the seed list.
            # The old "Student Assign(Viva)" menu (component='VivaAssign') was
            # removed when the page was merged into "Student Assign"; delete
            # any leftover row here so it stops appearing in user menus.
            seed_components = {m['component'] for m in menu_data}
            legacy_qs = Menu.objects.exclude(component__in=seed_components)
            for legacy in legacy_qs:
                self.stdout.write(
                    self.style.WARNING(
                        f'Removing legacy menu: {legacy.label} (component={legacy.component})'
                    )
                )
                legacy.delete()

            self.stdout.write(
                self.style.SUCCESS('\nSeeding completed successfully!')
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Created {len(created_menus)} menus and assigned to superadmin role'
                )
            )
