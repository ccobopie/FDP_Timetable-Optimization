from django.db import models
from django.contrib.auth.models import User
from datetime import date, datetime, time

# COpciones de días de la semana
DAYS_OF_WEEK = [
    ('MON', 'Lunes'),
    ('TUE', 'Martes'),
    ('WED', 'Miércoles'),
    ('THU', 'Jueves'),
    ('FRI', 'Viernes'),
    ('SAT', 'Sábado'),
    ('SUN', 'Domingo'),
]

class Task(models.Model):
    TASK_TYPES = [
        ('TASK', 'Task'),
        ('WEEKLY', 'Weekly Activity'),
        ('MEETING', 'Meeting'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    task_type = models.CharField(max_length=10, choices=TASK_TYPES)

    # Campos para TASK
    deadline = models.DateField(null=True, blank=True)
    estimated_minutes = models.IntegerField(null=True, blank=True)
    max_daily_minutes  = models.IntegerField(null=True, blank=True)
    start_preference = models.CharField(max_length=4, choices=[('ASAP', 'ASAP'), ('ALAP', 'ALAP')], null=True, blank=True)

    ignored_by_meeting = models.BooleanField(default=False)


    # Campos para MEETING
    meeting_datetime = models.DateTimeField(null=True, blank=True)
    meeting_end_time = models.TimeField(null=True, blank=True)

    # Campos para WEEKLY
    weekly_start_date = models.DateField(null=True, blank=True)
    weekly_end_date = models.DateField(null=True, blank=True)
    weekly_start_time = models.TimeField(null=True, blank=True)
    weekly_end_time = models.TimeField(null=True, blank=True)
    weekly_day = models.CharField(max_length=3, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.task_type})"

    @property
    def status(self):
        today = date.today()
        if self.task_type == 'MEETING' and self.meeting_datetime:
            return "Completado" if self.meeting_datetime.date() < today else "Pendiente"
        elif self.task_type == 'WEEKLY' and self.weekly_end_date:
            return "Completado" if self.weekly_end_date < today else "Pendiente"
        elif self.deadline:
            return "Completado" if self.deadline < today else "Pendiente"
        return "Desconocido"


class ScheduleAssignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True)

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    event_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.event_name} on {self.date} from {self.start_time} to {self.end_time}"





class WeeklyTimeRange(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    week_start = models.DateField()  # Lunes de la semana
    start_hour = models.IntegerField(default=10)
    end_hour = models.IntegerField(default=19)
    active_days = models.JSONField(default=list)  # Lista de días activos (0-6)

    def clean(self):
        for day in self.active_days:
            if day < 0 or day > 6:
                raise ValidationError("Los días activos deben estar entre 0 (lunes) y 6 (domingo).")

    class Meta:
        unique_together = ('user', 'week_start')

    def __str__(self):
        return f"{self.user.username} - Week of {self.week_start}"



class ImportedTask(models.Model):
    canvas_id = models.BigIntegerField(unique=True)
    course_id = models.BigIntegerField()
    course_name = models.CharField(max_length=255, default="Sin curso")  # <- importante
    name = models.CharField(max_length=255)
    due_date = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reviewed = models.BooleanField(default=False)
    estimated_minutes = models.IntegerField(null=True, blank=True)
    max_daily_minutes = models.IntegerField(null=True, blank=True)


    def __str__(self):
        return f"{self.name} ({self.course_name})"

class IgnoredWeeklyInstance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    weekly_task = models.ForeignKey(Task, on_delete=models.CASCADE)
    date = models.DateField()  # Día concreto ignorado

    class Meta:
        unique_together = ('user', 'weekly_task', 'date')

class CanvasProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    canvas_token = models.CharField(max_length=255)
    canvas_base_url = models.URLField(default="https://ufv-es.instructure.com/api/v1")
    canvas_course_ids = models.CharField(max_length=500, blank=True, default="") 
