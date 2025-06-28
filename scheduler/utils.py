from scheduler.models import ScheduleAssignment
from datetime import time


def save_assignments_to_db(assignments, user):
    print("ASSIGNMENTS A GUARDAR:", assignments)
    for day, start_min, end_min, task_name, task_obj in assignments:
        if not task_obj:
            print(f" Task obj is None for {task_name}")
            continue
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
            ScheduleAssignment.objects.create(
                user=user,
                task=task_obj,
                date=day,
                start_time=start_time,
                end_time=end_time,
                event_name=task_name
            )

