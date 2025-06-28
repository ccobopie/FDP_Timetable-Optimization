from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm
from .forms import CustomUserCreationForm
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Task, ScheduleAssignment, WeeklyTimeRange
from .optimization import solve_schedule
from datetime import datetime, date, time, timedelta
from django.db.models import F
from django.utils.timezone import now, make_aware
from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.conf import settings
from .optimization import Task as AlgoTask, solve_schedule, add_weekly_activity
from .utils import save_assignments_to_db
from .models import ImportedTask
from django.shortcuts import get_object_or_404
from django.conf import settings
from .canvas_api import CanvasAPI
from django.shortcuts import redirect
from .models import Task
from datetime import datetime
from datetime import timezone
# Horario semanal
from django.contrib import messages  
from .models import IgnoredWeeklyInstance
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.urls import reverse
from .models import CanvasProfile


@login_required
def import_canvas_tasks(request):
    profile = CanvasProfile.objects.get(user=request.user)
    token = profile.canvas_token
    base_url = profile.canvas_base_url
    selected_courses = [int(c.strip()) for c in profile.canvas_course_ids.split(",") if c.strip().isdigit()]

    if not token or not base_url or not selected_courses:
        messages.error(request, "Debes configurar Canvas correctamente.")
        return redirect("canvas_config")

    canvas = CanvasAPI(token, base_url)

    for course_id in selected_courses:
        try:
            course = canvas.get_course(course_id)
            if not course:
                continue

            assignments = canvas.get_assignments(course_id)
            course_name = getattr(course, "name", "Sin curso")
            for assignment in assignments:
                if not ImportedTask.objects.filter(canvas_id=assignment["id"]).exists():
                    ImportedTask.objects.create(
                        canvas_id=assignment["id"],
                        name=assignment["name"],
                        due_date=assignment.get("due_at"),
                        course_name=course.get("name", "Sin curso"),
                        course_id=course_id,
                        user=request.user
                    )
        except Exception as e:
            messages.error(request, f"Error accediendo al curso {course_id}: {str(e)}")
            continue

    messages.success(request, "Tareas importadas correctamente. Puedes seguir añadiendo cursos o revisar las tareas.")
    return redirect("review_imported_tasks")


@login_required
def canvas_settings(request):
    profile, _ = CanvasProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        token = request.POST.get("canvas_token")
        base_url = request.POST.get("canvas_base_url")

        if not token or not base_url:
            return render(request, "scheduler/canvas_settings.html", {
                "error": "Todos los campos son obligatorios.",
                "token": token,
                "base_url": base_url,
            })

        profile.canvas_token = token
        profile.canvas_base_url = base_url
        profile.save()

        messages.success(request, "Configuración de acceso actualizada.")
        return redirect("canvas_config")

    context = {
        "token": profile.canvas_token,
        "base_url": profile.canvas_base_url,
    }
    return render(request, "scheduler/canvas_settings.html", context)



@login_required
def select_canvas_courses(request):
    if request.method == "POST":
        raw_ids = request.POST.get("course_ids", "")
        course_ids = [int(c.strip()) for c in raw_ids.split(",") if c.strip().isdigit()]
        request.session["selected_canvas_courses"] = course_ids
        return redirect("import_canvas_tasks")
    
    return render(request, "scheduler/select_canvas_courses.html")


@login_required
def confirm_imported_tasks(request):
    if request.method == "POST":
        task_ids = request.POST.getlist("task_ids")  
        tasks_created = False

        for task_id in task_ids:
            try:
                task = ImportedTask.objects.get(id=task_id, user=request.user, reviewed=False)
                est = request.POST.get(f"estimated_minutes_{task.id}")
                max_daily = request.POST.get(f"max_daily_minutes_{task.id}")

                if not est or not max_daily:
                    continue  

                estimated = int(est)
                max_daily = int(max_daily)

                new_task = Task.objects.create(
                    name=task.name,
                    deadline=task.due_date,
                    estimated_minutes=estimated,
                    max_daily_minutes=max_daily,
                    start_preference="ASAP",
                    task_type="TASK",
                    user=task.user
                )

                task.reviewed = True
                task.estimated_minutes = estimated
                task.max_daily_minutes = max_daily
                task.save()
                tasks_created = True

            except ImportedTask.DoesNotExist:
                continue

        if tasks_created:
            # 1. Obtener tareas tipo TASK no vencidas
            tasks = Task.objects.filter(user=request.user, task_type='TASK', deadline__gte=date.today())

            # 2. Obtener los próximos 7 días
            today = date.today()
            days_of_week = [today + timedelta(days=i) for i in range(7)]

            # 3. Llamar al algoritmo
            schedule = solve_schedule(
                tasks=tasks,
                days_of_week=days_of_week,
                start_hour=8,
                end_hour=22,
                resolution=30,
                occupied=set(),
                active_days=[0, 1, 2, 3, 4, 5, 6]
            )

            # 4. Guardar el resultado del horario
            for (day, start_time), task_id in schedule.items():  
                task_obj = Task.objects.filter(user=request.user, id=task_id).first()
                if task_obj:
                    ScheduleAssignment.objects.create(
                        user=request.user,
                        task=task_obj,
                        date=day,
                        start_time=start_time,
                        end_time=(datetime.combine(day, start_time) + timedelta(minutes=30)).time(),
                        event_name=task_obj.name
                    )

        messages.success(request, "Tareas añadidas al sistema correctamente.")
        return redirect("weekly_timetable")


@login_required
def review_imported_tasks(request):
    profile = CanvasProfile.objects.get(user=request.user)
    token = profile.canvas_token
    base_url = profile.canvas_base_url
    course_ids = [int(c.strip()) for c in profile.canvas_course_ids.split(",") if c.strip().isdigit()]

    if not token or not base_url or not course_ids:
        messages.error(request, "Debes configurar Canvas correctamente.")
        return redirect("canvas_config")

    canvas = CanvasAPI(token, base_url)
    upcoming_imported = []

    for course_id in course_ids:
        try:
            course = canvas.get_course(course_id)
            course_name = course.get("name", "Sin curso")
            assignments = canvas.get_assignments(course_id)

            for assignment in assignments:
                due_raw = assignment.get("due_at")
                if not due_raw:
                    continue

                due_dt = datetime.fromisoformat(due_raw.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                if due_dt < datetime.now():
                    continue  # solo tareas futuras

                # Verificar si ya está en Task
                exists = Task.objects.filter(
                    user=request.user,
                    name=assignment["name"],
                    deadline=due_dt.date()
                ).exists()

                if exists:
                    continue

                # Crear en ImportedTask si no está
                imported, created = ImportedTask.objects.get_or_create(
                    canvas_id=assignment["id"],
                    defaults={
                        "name": assignment["name"],
                        "due_date": due_dt,
                        "course_name": course_name,
                        "course_id": course_id,
                        "user": request.user
                    }
                )

                if not imported.reviewed:
                    upcoming_imported.append(imported)

        except Exception as e:
            messages.warning(request, f"Error accediendo al curso {course_id}: {str(e)}")

    return render(request, "scheduler/review_imported_tasks.html", {"tasks": upcoming_imported})



@login_required
def canvas_config(request):
    profile = CanvasProfile.objects.get(user=request.user)

    if request.method == "POST":
        new_ids_raw = request.POST.get("canvas_course_ids", "")
        new_ids = [c.strip() for c in new_ids_raw.split(",") if c.strip().isdigit()]
        existing_ids = profile.canvas_course_ids.split(",") if profile.canvas_course_ids else []
        merged_ids = list(set(existing_ids + new_ids))

        profile.canvas_course_ids = ",".join(sorted(merged_ids, key=int))
        profile.save()

        messages.success(request, "Cursos guardados correctamente.")
        return redirect("review_imported_tasks")

    context = {
        "course_ids": profile.canvas_course_ids,
    }
    return render(request, "scheduler/canvas_config.html", context)


# Login
def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('tasks')
    else:
        form = AuthenticationForm()
    return render(request, 'scheduler/login.html', {'form': form})

# Signup

def user_signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  
            user.save()
            send_activation_email(user, request)
            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'scheduler/signup.html', {'form': form})

def send_activation_email(user, request):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    activation_link = request.build_absolute_uri(f'/activate/{uid}/{token}/')

    subject = 'Activate your account'
    message = render_to_string('scheduler/emails/activation_email.txt', {
        'user': user,
        'activation_link': activation_link,
    })

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False
    )

def activate_account(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return render(request, 'scheduler/activation_success.html')
    else:
        return render(request, 'scheduler/activation_invalid.html')
    
def activation_success(request):
    return render(request, 'scheduler/activation_success.html')

def how_to_use(request):
    return render(request, 'scheduler/how_to_use.html')

# Ver tareas

@login_required
def view_tasks(request):
    tasks = Task.objects.filter(user=request.user).order_by('deadline')
    today = now().date()

    unique_tasks = []
    seen = set()
    for task in tasks:
        if task.id not in seen:
            seen.add(task.id)
            task.calculated_status = (
                "Completado" if task.deadline and task.deadline < today else "Pendiente"
            )
            unique_tasks.append(task)

    return render(request, 'scheduler/tasks.html', {'tasks': unique_tasks})

# Ver horario 
@login_required
def view_timetable(request):
    assignments = ScheduleAssignment.objects.filter(user=request.user).order_by('date', 'start_time')
    return render(request, 'scheduler/timetable.html', {'assignments': assignments})



@login_required
def create_task(request):
    if request.method == "POST":
        name = request.POST.get("name")
        task_type = request.POST.get("task_type")
        user = request.user

        if task_type == "TASK":
            deadline_str = request.POST.get("deadline")
            if not deadline_str:
                return HttpResponseBadRequest("Debes introducir una fecha límite.")
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except ValueError:
                return HttpResponseBadRequest("El formato de fecha es inválido. Debe ser YYYY-MM-DD.")

            hours_needed = int(request.POST.get("hours_needed", 0))
            max_daily_hours = int(request.POST.get("max_daily_hours", 0))
            max_daily_minutes = max_daily_hours * 60
            start_preference = request.POST.get("start_preference")

            if hours_needed < max_daily_hours:
                return HttpResponseBadRequest("Las horas necesarias deben ser mayores o iguales que el máximo de horas seguidas.")

            if max_daily_minutes < 30:
                return HttpResponseBadRequest("El máximo de minutos seguidos debe ser al menos de 30.")

            days_left = (deadline - date.today()).days + 1
            total_possible = days_left * max_daily_minutes

            if hours_needed * 60 > total_possible:
                return HttpResponseBadRequest("No hay tiempo suficiente antes del deadline.")

            Task.objects.create(
                user=user,
                name=name,
                task_type=task_type,
                deadline=deadline,
                estimated_minutes=hours_needed * 60,
                max_daily_minutes=max_daily_minutes,
                start_preference=start_preference
            )

        elif task_type == "WEEKLY":
            weekly_start_date = request.POST.get("weekly_start_date")
            weekly_end_date = request.POST.get("weekly_end_date")
            weekly_start_time = request.POST.get("weekly_start_time")
            weekly_end_time = request.POST.get("weekly_end_time")
            weekly_day = request.POST.get("weekly_day")

            if weekly_start_date > weekly_end_date:
                return HttpResponseBadRequest("La fecha de inicio debe ser anterior a la de fin.")
            if weekly_start_time >= weekly_end_time:
                return HttpResponseBadRequest("La hora de inicio debe ser anterior a la de fin.")

            Task.objects.create(
                user=user,
                name=name,
                task_type=task_type,
                weekly_start_date=weekly_start_date,
                weekly_end_date=weekly_end_date,
                weekly_start_time=weekly_start_time,
                weekly_end_time=weekly_end_time,
                weekly_day=weekly_day
            )

        elif task_type == "MEETING":
            meeting_date = request.POST.get("meeting_date")
            meeting_start_time = request.POST.get("meeting_start_time")
            meeting_end_time = request.POST.get("meeting_end_time")

            if meeting_start_time >= meeting_end_time:
                return HttpResponseBadRequest("La hora de inicio debe ser anterior a la de fin.")

            try:
                meeting_datetime_str = f"{meeting_date} {meeting_start_time}"
                meeting_datetime = datetime.strptime(meeting_datetime_str, "%Y-%m-%d %H:%M")
            except ValueError:
                return HttpResponseBadRequest("La fecha y hora de la reunión no son válidas.")

            Task.objects.create(
                user=user,
                name=name,
                task_type=task_type,
                meeting_datetime=meeting_datetime,
                meeting_end_time=meeting_end_time
            )

        return redirect("tasks")

    return render(request, "scheduler/create_task.html")


@login_required
def weekly_timetable(request):
    from .models import IgnoredWeeklyInstance

    try:
        week_offset = int(request.GET.get('week', 0))
    except ValueError:
        week_offset = 0
    force = request.GET.get("force", "false") == "true"
    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)
    days_of_week = [monday + timedelta(days=i) for i in range(7)]

    weekly_range, _ = WeeklyTimeRange.objects.get_or_create(
        user=request.user,
        week_start=monday,
        defaults={'start_hour': 10, 'end_hour': 19, 'active_days': list(range(7))}
    )

    if request.method == 'POST':
        weekly_range.start_hour = int(request.POST.get('start_hour'))
        weekly_range.end_hour = int(request.POST.get('end_hour'))
        weekly_range.active_days = [int(i) for i in request.POST.getlist('active_days')]
        weekly_range.save()
        return redirect(f'/weekly-timetable/?week={week_offset}')

    calendar = {
        day: [(weekly_range.start_hour * 60, weekly_range.end_hour * 60)]
        if day.weekday() in weekly_range.active_days else []
        for day in days_of_week
    }

    assignments = []
    occupied = set()

    # Como resolver conflictos
    meetings = Task.objects.filter(user=request.user, task_type="MEETING")
    ignored_instances = IgnoredWeeklyInstance.objects.filter(user=request.user)
    ignored_map = {(i.weekly_task.id, i.date) for i in ignored_instances}
    conflict_meeting = None
    conflict_with = None

    for m in meetings:
        if m.meeting_datetime and m.meeting_end_time:
            d = m.meeting_datetime.date()
            if monday <= d <= sunday:
                start = m.meeting_datetime.hour * 60 + m.meeting_datetime.minute
                end = m.meeting_end_time.hour * 60 + m.meeting_end_time.minute
                for w in Task.objects.filter(user=request.user, task_type="WEEKLY"):
                    if (w.id, d) in ignored_map:
                        continue
                    weekday = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"].index(w.weekly_day)
                    if d.weekday() == weekday and w.weekly_start_date <= d <= w.weekly_end_date:
                        w_start = w.weekly_start_time.hour * 60 + w.weekly_start_time.minute
                        w_end = w.weekly_end_time.hour * 60 + w.weekly_end_time.minute
                        if max(start, w_start) < min(end, w_end):
                            conflict_meeting = m
                            conflict_with = w
                            break
            if conflict_meeting:
                break

    if conflict_meeting and conflict_with:
        request.session['conflict_meeting_id'] = conflict_meeting.id
        request.session['conflict_weekly_id'] = conflict_with.id
        return redirect("resolve_meeting_conflict")

    # Reuniones
    for m in meetings:
        if m.meeting_datetime and m.meeting_end_time:
            d = m.meeting_datetime.date()
            if monday <= d <= sunday:
                start = m.meeting_datetime.hour * 60 + m.meeting_datetime.minute
                end = m.meeting_end_time.hour * 60 + m.meeting_end_time.minute
                assignments.append((d, start, end, m.name, m))
                for t in range(start, end, 30):
                    occupied.add((d, time(t // 60, t % 60)))

    # Actividades semanales
    weeklys = Task.objects.filter(user=request.user, task_type="WEEKLY")
    for w in weeklys:
        weekday = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"].index(w.weekly_day)
        for i in range(7):
            d = monday + timedelta(days=i)
            if d.weekday() != weekday:
                continue
            if not (w.weekly_start_date <= d <= w.weekly_end_date):
                continue

            full_start = w.weekly_start_time.hour * 60 + w.weekly_start_time.minute
            full_end = w.weekly_end_time.hour * 60 + w.weekly_end_time.minute


            if (w.id, d) not in ignored_map:
                calendar = add_weekly_activity(calendar, weekday, full_start, full_end - full_start,
                                            w.weekly_start_date, w.weekly_end_date, occupied, w.name,
                                            assignments, w, request)
                for t in range(full_start, full_end, 30):
                    occupied.add((d, time(t // 60, t % 60)))
            else:
                meeting = Task.objects.filter(user=request.user, task_type="MEETING",
                                            meeting_datetime__date=d).first()
                if meeting:
                    m_start = meeting.meeting_datetime.hour * 60 + meeting.meeting_datetime.minute
                    m_end = meeting.meeting_end_time.hour * 60 + meeting.meeting_end_time.minute

                    if full_start < m_start:
                        dur = m_start - full_start
                        calendar = add_weekly_activity(calendar, weekday, full_start, dur,
                                                    w.weekly_start_date, w.weekly_end_date, occupied, w.name,
                                                    assignments, w, request)
                        for t in range(full_start, m_start, 30):
                            occupied.add((d, time(t // 60, t % 60)))

                    if m_end < full_end:
                        dur = full_end - m_end
                        calendar = add_weekly_activity(calendar, weekday, m_end, dur,
                                                    w.weekly_start_date, w.weekly_end_date, occupied, w.name,
                                                    assignments, w, request)
                        for t in range(m_end, full_end, 30):
                            occupied.add((d, time(t // 60, t % 60)))


    # Tareas
    task_objs = Task.objects.filter(user=request.user, task_type="TASK", deadline__gte=today)

    if force:
        ScheduleAssignment.objects.filter(user=request.user, task__task_type="TASK").delete()
    else:
        ScheduleAssignment.objects.filter(
            user=request.user,
            task__task_type="TASK",
            date__range=(monday, sunday),
            date__gte=today
        ).delete()

    algo_tasks = []
    for t in task_objs:
        already_assigned = ScheduleAssignment.objects.filter(user=request.user, task=t).count()
        total_assigned = already_assigned * 30
        remaining = t.estimated_minutes - total_assigned
        if remaining > 0:
            algo_tasks.append(
                AlgoTask(
                    id=t.id,
                    name=t.name,
                    deadline=t.deadline,
                    estimated_minutes=remaining,
                    max_daily_minutes=t.max_daily_minutes,
                    start_preference=t.start_preference
                )
            )

    schedule_result = solve_schedule(
        algo_tasks,
        days_of_week,
        weekly_range.start_hour,
        weekly_range.end_hour,
        resolution=30,
        occupied=occupied,
        active_days=weekly_range.active_days
    )

    if not schedule_result and week_offset == 0:
        for t in algo_tasks:
            if t.estimated_minutes > 0 and t.deadline >= today:
                failing = Task.objects.filter(user=request.user, name=t.name).first()
                if failing:
                    return redirect("timetable_adjustment", task_id=failing.id)

    for (day, hour), task_id in schedule_result.items():
        start_min = hour.hour * 60 + hour.minute
        end_min = start_min + 30
        t = Task.objects.filter(id=task_id, user=request.user).first()
        if t:
            assignments.append((day, start_min, end_min, t.name, t))

    save_assignments_to_db(assignments, request.user)

    schedule_grid = {}
    for d, s, e, name, _ in assignments:
        for t in range(s, e, 30):
            schedule_grid[(d, time(t // 60, t % 60))] = name

    time_slots = []
    current_minutes = weekly_range.start_hour * 60
    end_minutes = weekly_range.end_hour * 60 + 30
    while current_minutes <= end_minutes:
        time_slots.append(time(current_minutes // 60, current_minutes % 60))
        current_minutes += 30

    timetable = []
    for slot in time_slots:
        row = {'time': slot, 'events': [schedule_grid.get((d, slot), '') for d in days_of_week]}
        timetable.append(row)

    return render(request, 'scheduler/weekly_timetable.html', {
        'timetable': timetable,
        'days_of_week': days_of_week,
        'previous_week': week_offset - 1,
        'next_week': week_offset + 1,
        'weekly_range': weekly_range,
        'force': force,
    })



@login_required
def resolve_meeting_conflict(request):
    meeting_id = request.session.get('conflict_meeting_id')
    weekly_id = request.session.get('conflict_weekly_id')

    meeting = get_object_or_404(Task, id=meeting_id, user=request.user)
    weekly = get_object_or_404(Task, id=weekly_id, user=request.user)

    if request.method == 'POST':
        decision = request.POST.get('decision')
        if decision == "overwrite":
            conflict_date = meeting.meeting_datetime.date()

            IgnoredWeeklyInstance.objects.get_or_create(
                user=request.user,
                weekly_task=weekly,
                date=conflict_date
            )

            request.session.pop('conflict_meeting_id', None)
            request.session.pop('conflict_weekly_id', None)

            return redirect("weekly_timetable")

        elif decision == "edit":
            return redirect("edit_task", task_id=meeting.id)

    return render(request, "scheduler/resolve_meeting_conflict.html", {
        "meeting": meeting,
        "weekly": weekly
    })


@login_required
def timetable_adjustment(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    today = date.today()
    monday = today - timedelta(days=today.weekday())

    weekly_range, _ = WeeklyTimeRange.objects.get_or_create(
        user=request.user,
        week_start=monday,
        defaults={'start_hour': 10, 'end_hour': 19, 'active_days': list(range(7))}
    )

    if request.method == 'POST':
        action = request.POST.get("action")
        if action == "edit_task":
            return redirect("edit_task", task_id=task.id)

        if action == "adjust_hours_days":
            weekly_range.start_hour = int(request.POST.get("start_hour"))
            weekly_range.end_hour = int(request.POST.get("end_hour"))
            weekly_range.active_days = [int(i) for i in request.POST.getlist('active_days')]
            weekly_range.save()
            return redirect("weekly_timetable")

    return render(request, "scheduler/timetable_adjustment.html", {
        "task": task,
        "weekly_range": weekly_range,
        "days": [
            ("Lunes", 0), ("Martes", 1), ("Miércoles", 2),
            ("Jueves", 3), ("Viernes", 4), ("Sábado", 5), ("Domingo", 6)
        ]
    })


# Editar tarea
DAYS_OF_WEEK = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
days_of_week = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

@login_required
def edit_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)

    if task.task_type == 'TASK':
        return redirect('edit_task_task', task_id=task.id)
    elif task.task_type == 'WEEKLY':
        return redirect('edit_task_weekly', task_id=task.id)
    elif task.task_type == 'MEETING':
        return redirect('edit_task_meeting', task_id=task.id)
    else:
        messages.error(request, "Tipo de tarea no válido.")
        return redirect('tasks')


@login_required
def edit_task_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)

    if request.method == "POST":
        name = request.POST.get('name')
        deadline = request.POST.get('deadline')
        hours_needed = request.POST.get('hours_needed')
        max_daily_hours = request.POST.get('max_daily_hours')

        start_preference = request.POST.get('start_preference')

        if not all([name, deadline, hours_needed, max_daily_hours, start_preference]):
            messages.error(request, "Todos los campos son obligatorios.")
        elif int(hours_needed) <= int(max_daily_hours):
            messages.error(request, "Horas necesarias debe ser mayor que el máximo de horas por día.")
        else:
            task.name = name
            task.deadline = deadline
            task.estimated_minutes = int(hours_needed)
            task.max_daily_minutes = int(max_daily_hours)*60

            task.start_preference = start_preference
            task.save()
            messages.success(request, "Tarea actualizada correctamente.")
            return redirect("tasks")

    return render(request, "scheduler/edit_task_task.html", {"task": task})



DAYS_OF_WEEK = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

@login_required
def edit_task_weekly(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)

    if request.method == "POST":
        task.name = request.POST.get("name")
        task.weekly_start_date = request.POST.get("weekly_start_date")
        task.weekly_end_date = request.POST.get("weekly_end_date")
        task.weekly_start_time = request.POST.get("weekly_start_time")
        task.weekly_end_time = request.POST.get("weekly_end_time")
        task.weekly_day = request.POST.get("weekly_day")

        if not all([task.name, task.weekly_start_date, task.weekly_end_date, task.weekly_start_time, task.weekly_end_time, task.weekly_day]):
            messages.error(request, "Todos los campos son obligatorios.")
        elif task.weekly_start_date > task.weekly_end_date:
            messages.error(request, "La fecha de inicio debe ser anterior a la de fin.")
        elif task.weekly_start_time >= task.weekly_end_time:
            messages.error(request, "La hora de inicio debe ser anterior a la de fin.")
        else:
            task.ignored_by_meeting = False
            task.save()
            messages.success(request, "Actividad semanal actualizada.")
            return redirect("tasks")

    return render(request, "scheduler/edit_task_weekly.html", {"task": task})



@login_required
def edit_task_meeting(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)

    if request.method == "POST":
        name = request.POST.get("name")
        meeting_date = request.POST.get("meeting_date")
        meeting_start_time = request.POST.get("meeting_start_time")
        meeting_end_time = request.POST.get("meeting_end_time")

        if not all([name, meeting_date, meeting_start_time, meeting_end_time]):
            messages.error(request, "Todos los campos son obligatorios.")
        elif meeting_start_time >= meeting_end_time:
            messages.error(request, "La hora de inicio debe ser antes que la de fin.")
        else:
            task.name = name
            task.meeting_datetime = f"{meeting_date} {meeting_start_time}"
            task.meeting_end_time = meeting_end_time
            task.save()
            messages.success(request, "Reunión actualizada.")
            return redirect("tasks")

    meeting_date = task.meeting_datetime.date() if task.meeting_datetime else ''
    meeting_start_time = task.meeting_datetime.time() if task.meeting_datetime else ''

    return render(request, "scheduler/edit_task_meeting.html", {
        "task": task,
        "meeting_date": meeting_date,
        "meeting_start_time": meeting_start_time
    })



# Eliminar tarea
@login_required
def delete_task(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)

    if request.method == 'POST':
        task.delete()
        return redirect('tasks')

    return render(request, 'scheduler/delete_task.html', {'task': task})

def save_assignments_to_db(assignments, user):
    for day, start_min, end_min, task_name, task_obj in assignments:
        start_time = time(start_min // 60, start_min % 60)
        end_time = time(end_min // 60, end_min % 60)

        if not ScheduleAssignment.objects.filter(
            user=user,
            date=day,
            start_time=start_time,
            end_time=end_time,
            event_name=task_name,
            task=task_obj
        ).exists():
            print(f"Guardando {task_name} ({task_obj.id}) el {day} de {start_time} a {end_time}")
            ScheduleAssignment.objects.create(
                user=user,
                date=day,
                start_time=start_time,
                end_time=end_time,
                event_name=task_name,
                task=task_obj
            )


def round_up_minutes(minutes, base=30):
    return ((minutes + base - 1) // base) * base