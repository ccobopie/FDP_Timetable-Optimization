import datetime
import copy
from datetime import datetime, timedelta, date, time
from scheduler.models import ScheduleAssignment
from django.contrib import messages
# ---------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------
class Task:
    def __init__(self,id, name, deadline, estimated_minutes, max_daily_minutes, start_preference='ASAP'):
        self.id=id
        self.name = name
        self.deadline = deadline
        self.estimated_minutes = estimated_minutes
        self.remaining_minutes = estimated_minutes
        self.max_daily_minutes = max_daily_minutes
        self.start_preference = start_preference

    def clone(self):
        new_task = Task(self.id, self.name, self.deadline, self.estimated_minutes, self.max_daily_minutes, self.start_preference)
        new_task.remaining_minutes = self.remaining_minutes
        return new_task

    def __repr__(self):
        return f"Task({self.name}, deadline={self.deadline}, remaining={self.remaining_minutes})"

# ---------------------------------------------------------------------
# Calendar Building and Updating Functions
# ---------------------------------------------------------------------
def build_calendar(start_date, end_date, working_days, work_start, work_end):
    calendar = {}
    current = start_date
    while current <= end_date:
        if current.weekday() in working_days:
            calendar[current] = [(work_start, work_end)]
        else:
            calendar[current] = []
        current += timedelta(days=1)

    return calendar

def update_intervals(intervals, candidate):
    candidate_start, dur = candidate
    candidate_end = candidate_start + dur
    new_intervals = []
    for (start, end) in intervals:
        if candidate_end <= start or candidate_start >= end:
            new_intervals.append((start, end))
        else:
            if start < candidate_start:
                new_intervals.append((start, candidate_start))
            if candidate_end < end:
                new_intervals.append((candidate_end, end))
    return new_intervals

def add_fixed_event(calendar, event_date, start, duration, event_name, assignments, task_obj):
    if event_date in calendar:
        calendar[event_date] = update_intervals(calendar[event_date], (start, duration))
    else:
        calendar[event_date] = []
    assignments.append((event_date, start, start + duration, event_name, task_obj))
    return calendar


def add_weekly_activity(calendar, weekday, start_min, duration, start_date, end_date, occupied, name, assignments, task, request):
    for day, slots in calendar.items():
        if day.weekday() == weekday and start_date <= day <= end_date:
            conflict = False
            for t in range(start_min, start_min + duration, 30):
                if (day, time(t // 60, t % 60)) in occupied:
                    conflict = True
                    break

            if conflict:
                messages.warning(request, f"⚠️ Conflicto al asignar '{name}' el {day.strftime('%A %d')} a las {start_min // 60}:{start_min % 60:02d}. Ya hay eventos en esa franja.")
                continue

            slots.append((start_min, start_min + duration))
            assignments.append((day, start_min, start_min + duration, name, task))
    return calendar


# ---------------------------------------------------------------------
# Backtracking for Specific Tasks
# ---------------------------------------------------------------------
def generate_candidates_for_date(intervals, resolution, max_daily, remaining_minutes):
    candidates = []
    for start, end in intervals:
        for slot_start in range(start, end - resolution + 1, resolution):
            for dur in range(resolution, min(max_daily, end - slot_start, remaining_minutes) + 1, resolution):
                candidates.append((slot_start, dur))
    print(f"📍 Generados {len(candidates)} candidatos para {intervals}")
    return candidates

def backtrack_task(dates, index, task, calendar, assignments, resolution):
    print(f"🔄 backtrack_task: fecha={dates[index] if index < len(dates) else 'Fin'}, restantes={task.remaining_minutes}, asignaciones={assignments}")

    if task.remaining_minutes <= 0:
        return calendar, assignments
    if index >= len(dates):
        return None

    current_date = dates[index]
    intervals = calendar[current_date]
    candidates = generate_candidates_for_date(intervals, resolution, task.max_daily_minutes, task.remaining_minutes)

    if task.start_preference == 'ALAP':
        candidates.sort(key=lambda x: x[0], reverse=True)
    else:
        candidates.sort(key=lambda x: x[0])

    for candidate in candidates:
        new_calendar = copy.deepcopy(calendar)
        new_assignments = assignments.copy()
        start, dur = candidate
        new_calendar[current_date] = update_intervals(new_calendar[current_date], candidate)
        new_assignments.append((current_date, start, start + dur, task.name))
        
        new_task = task.clone()
        new_task.remaining_minutes -= dur

        result = backtrack_task(dates, index, new_task, new_calendar, new_assignments, resolution)
        if result is not None:
            print(f"Asignación parcial exitosa: {candidate} en {current_date}")
            return result

    return backtrack_task(dates, index + 1, task, calendar, assignments, resolution)

def assign_specific_task(calendar, task, resolution=30): 
    task.remaining_minutes = task.estimated_minutes
    available_dates = [d for d in sorted(calendar.keys()) if d <= task.deadline and calendar[d]]
    if task.start_preference == 'ALAP':
        available_dates = sorted(available_dates, reverse=True)

    result = backtrack_task(available_dates, 0, task, calendar, [], resolution)
    return result  




# ---------------------------------------------------------------------
# (Optional) Visual Schedule Grid
# ---------------------------------------------------------------------
def print_schedule_grid(assignments, start_date, end_date, work_start, work_end, resolution=30):
    current = start_date
    dates = []
    while current <= end_date:
        dates.append(current)
        current += timedelta(days=1)
    num_slots = (work_end - work_start) // resolution
    header = "Time".ljust(10) + "".join(str(d).ljust(18) for d in dates)
    print(header)
    grid = {}
    for assign_date, start, end, name in assignments:
        grid.setdefault(assign_date, {})
        slot_start = (start - work_start) // resolution
        slot_end = (end - work_start) // resolution
        for slot in range(slot_start, slot_end):
            grid[assign_date][slot] = name
    for i in range(num_slots):
        time_label = f"{(work_start + i * resolution)//60:02d}:{(work_start + i * resolution)%60:02d}"
        row = time_label.ljust(10)
        for d in dates:
            cell = grid.get(d, {}).get(i, "")
            row += cell.ljust(18)
        print(row)

def is_safe(schedule, day, start_time, task_duration, max_consecutive):
    end_time = (datetime.combine(datetime.today(), start_time) + timedelta(minutes=task_duration)).time()
    current_time = start_time
    consecutive = 0

    while current_time < end_time:
        if schedule.get((day, current_time), None):
            return False
        consecutive += 30
        if consecutive > max_consecutive:
            return False
        current_time = (datetime.combine(datetime.today(), current_time) + timedelta(minutes=30)).time()

    return True

def assign_task(schedule, day, start_time, task):
    task_duration = task.estimated_minutes
    current_time = start_time
    end_time = (datetime.combine(datetime.today(), start_time) + timedelta(minutes=task_duration)).time()

    while current_time < end_time:
        schedule[(day, current_time)] = task.name
        current_time = (datetime.combine(datetime.today(), current_time) + timedelta(minutes=30)).time()

from datetime import datetime, timedelta, time

def solve_schedule(tasks, days_of_week, start_hour, end_hour, resolution=30, occupied=None, active_days=None):
    if occupied is None:
        occupied = set()
    if active_days is None:
        active_days = list(range(7))  

    schedule = {}
    now = datetime.now().replace(second=0, microsecond=0)

    if not tasks:
        return schedule

    tasks = sorted(tasks, key=lambda t: t.deadline, reverse=(tasks[0].start_preference == "ALAP"))

    def round_up_to_resolution(dt):
        """Redondea hacia arriba al siguiente múltiplo de resolución."""
        total_minutes = dt.hour * 60 + dt.minute
        remainder = total_minutes % resolution
        if remainder == 0:
            return dt
        rounded_minutes = total_minutes + (resolution - remainder)
        return datetime.combine(dt.date(), time(rounded_minutes // 60, rounded_minutes % 60))

    def is_slot_available(day, current_time, duration):
        slots_needed = duration // resolution
        slot_time = current_time
        for _ in range(slots_needed):
            key = (day, slot_time.time())
            if key in schedule or key in occupied:
                return False
            slot_time += timedelta(minutes=resolution)
        return True

    def fill_slot(day, current_time, task_id, duration):
        slots_needed = duration // resolution
        slot_time = current_time
        for _ in range(slots_needed):
            schedule[(day, slot_time.time())] = task_id
            slot_time += timedelta(minutes=resolution)

    def backtrack(task_index):
        if task_index >= len(tasks):
            return True

        task = tasks[task_index]
        remaining = task.estimated_minutes
        max_per_day = task.max_daily_minutes

        date_range = [d for d in days_of_week if d.weekday() in active_days and d <= task.deadline]

        date_range = sorted(date_range, reverse=(task.start_preference == "ALAP"))

        for day in date_range:
            if day < now.date():
                continue

            start_time = datetime.combine(day, time(start_hour, 0))
            end_time = datetime.combine(day, time(end_hour, 0))

            if day == now.date():
                start_time = max(start_time, round_up_to_resolution(now))

            used_today = 0
            slot_time = start_time

            while (slot_time + timedelta(minutes=resolution) <= end_time and
                   remaining > 0 and used_today < max_per_day):

                block = min(resolution, max_per_day - used_today, remaining)

                if is_slot_available(day, slot_time, block):
                    fill_slot(day, slot_time, task.id, block)
                    used_today += block
                    remaining -= block

                slot_time += timedelta(minutes=resolution)

            if remaining == 0:
                return backtrack(task_index + 1)

        return False

    if backtrack(0):
        return schedule
    else:
        print("No se pudo asignar todas las tareas.")
        return {}
