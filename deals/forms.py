from django import forms

from .models import Company, Contact, Deal, DealAction


class DocumentUploadForm(forms.Form):
    file = forms.FileField()


class DealForm(forms.ModelForm):
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Компании",
    )
    contacts = forms.ModelMultipleChoiceField(
        queryset=Contact.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Контакты",
    )

    class Meta:
        model = Deal
        fields = ["title", "stage", "owner", "companies", "contacts"]


class DealActionForm(forms.ModelForm):
    remind_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
        label="Напомнить",
    )

    class Meta:
        model = DealAction
        fields = ["description", "remind_at", "recurrence", "custom_interval_days"]
        widgets = {
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "recurrence": forms.Select(attrs={"class": "form-select"}),
            "custom_interval_days": forms.NumberInput(
                attrs={"class": "form-control action-custom-interval", "min": 1}
            ),
        }
        labels = {
            "description": "Описание",
            "recurrence": "Периодичность",
            "custom_interval_days": "Интервал (дни)",
        }

    def clean(self):
        cleaned_data = super().clean()
        recurrence = cleaned_data.get("recurrence")
        custom_interval = cleaned_data.get("custom_interval_days")

        if recurrence == DealAction.Recurrence.CUSTOM:
            if not custom_interval:
                self.add_error("custom_interval_days", "Укажите интервал в днях")
        else:
            cleaned_data["custom_interval_days"] = None

        return cleaned_data
