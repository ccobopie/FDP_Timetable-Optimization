from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.contrib.auth.views import PasswordResetConfirmView
urlpatterns = [
    path('login/', views.user_login, name='login'),
    path('signup/', views.user_signup, name='signup'),
    path("logout/", LogoutView.as_view(next_page='login'), name='logout'),
    path('activate/<uidb64>/<token>/', views.activate_account, name='activate_account'),
    path('activation-success/', views.activation_success, name='activation_success'),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='scheduler/password_reset_form.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='scheduler/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='scheduler/password_reset_confirm.html',success_url=reverse_lazy('login')), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='scheduler/password_reset_confirm.html'), name='password_reset_confirm'),
    path('tasks/', views.view_tasks, name='tasks'),
    path('timetable/', views.view_timetable, name='timetable'),
    path('create-task/', views.create_task, name='create_task'),  
    path('weekly-timetable/', views.weekly_timetable, name='weekly_timetable'),
    path('tasks/edit/<int:task_id>/', views.edit_task, name='edit_task'),
    path('tasks/delete/<int:task_id>/', views.delete_task, name='delete_task'),
    path('tasks/edit/<int:task_id>/', views.edit_task, name='edit_task'),
    path("timetable-adjustment/<int:task_id>/", views.timetable_adjustment, name="timetable_adjustment"),
    # Editar tareas por tipo
    path("edit-task/task/<int:task_id>/", views.edit_task_task, name="edit_task_task"),
    path("edit-task/weekly/<int:task_id>/", views.edit_task_weekly, name="edit_task_weekly"),
    path("edit-task/meeting/<int:task_id>/", views.edit_task_meeting, name="edit_task_meeting"),
    #api canvas
    path("canvas-config/", views.canvas_config, name="canvas_config"),
    path("canvas-import-tasks/", views.import_canvas_tasks, name="canvas_import_tasks"),
    path("review-imported-tasks/", views.review_imported_tasks, name="review_imported_tasks"),
    path("confirm-imported-tasks/", views.confirm_imported_tasks, name="confirm_imported_tasks"),
    path("canvas-settings/", views.canvas_settings, name="canvas_settings"),
    path("how-to-use/", views.how_to_use, name="how_to_use"),



    # Eliminar tarea
    path("delete-task/<int:task_id>/", views.delete_task, name="delete_task"),
    path('select-canvas-courses/', views.select_canvas_courses, name='select_canvas_courses'),
    path('import-canvas-tasks/', views.import_canvas_tasks, name='import_canvas_tasks'),
    path("resolve-meeting-conflict/", views.resolve_meeting_conflict, name="resolve_meeting_conflict"),
    


]
