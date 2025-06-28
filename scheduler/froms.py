class TaskForm(forms.ModelForm):
    estimated_minutes = forms.IntegerField(label="Horas necesarias", min_value=1)
    max_daily_minutes = forms.IntegerField(label="Máx. de horas al día", min_value=1)  

    class Meta:
        model = Task
        fields = [
            'name', 'task_type', 'deadline', 'meeting_datetime',
            'weekly_start_date', 'weekly_end_date',
            'weekly_start_time', 'weekly_end_time',
            'estimated_minutes', 'max_daily_minutes',
            'start_preference'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['weekly_start_date'].widget = forms.DateInput(attrs={'type': 'date'})
        self.fields['weekly_end_date'].widget = forms.DateInput(attrs={'type': 'date'})
        self.fields['weekly_start_time'].widget = forms.TimeInput(attrs={'type': 'time'})
        self.fields['weekly_end_time'].widget = forms.TimeInput(attrs={'type': 'time'})
        self.fields['meeting_datetime'].widget = forms.DateTimeInput(attrs={'type': 'datetime-local'})

        self.fields['deadline'].required = False
        self.fields['meeting_datetime'].required = False
        self.fields['weekly_start_date'].required = False
        self.fields['weekly_end_date'].required = False
        self.fields['weekly_start_time'].required = False
        self.fields['weekly_end_time'].required = False

    def clean_estimated_minutes(self):
        # Convertir  horas a minutos
        return self.cleaned_data['estimated_minutes'] * 60

    def clean_max_daily_minutes(self):
        # Convertir de horas a minutos
        return self.cleaned_data['max_daily_minutes'] * 60
