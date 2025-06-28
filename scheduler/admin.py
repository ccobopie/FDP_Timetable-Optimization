from django.contrib import admin
from .models import Task, ScheduleAssignment, WeeklyTimeRange, CanvasProfile

admin.site.register(Task)
admin.site.register(ScheduleAssignment)
admin.site.register(WeeklyTimeRange)  
admin.site.register(CanvasProfile) 