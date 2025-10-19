from django import forms

from .models import Company, Contact, Deal, DealAction


class DocumentUploadForm(forms.Form):
    file = forms.FileField()


class DealForm(forms.ModelForm):
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Компании",
    )
    contacts = forms.ModelMultipleChoiceField(
        queryset=Contact.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Контакты",
    )

    class Meta:
        model = Deal
        fields = ["title", "stage", "owner", "cost", "description", "companies", "contacts"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        company_qs = Company.objects.all().order_by("name")
        contact_qs = Contact.objects.all().order_by("name")

        if user and not getattr(user, "is_superuser", False):
            company_qs = company_qs.filter(deals__owner=user).distinct()
            contact_qs = contact_qs.filter(owner=user)

        self.fields["companies"].queryset = company_qs
        self.fields["contacts"].queryset = contact_qs


class DealActionForm(forms.ModelForm):
    remind_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
        label="Напомнить",
    )

    notify_before_value = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control action-notify-before",
                "min": 0,
                "placeholder": "Например, 30",
            }
        ),
        label="Оповестить за",
        help_text="0 — без дополнительного оповещения",
    )
    notify_before_unit = forms.ChoiceField(
        required=False,
        choices=DealAction.NotifyUnit.choices,
        widget=forms.Select(attrs={"class": "form-select action-notify-unit"}),
        label="Единица",
        initial=DealAction.NotifyUnit.MINUTES,
    )

    class Meta:
        model = DealAction
        fields = [
            "description",
            "status",
            "remind_at",
            "notify_before_value",
            "notify_before_unit",
            "recurrence",
            "custom_interval_days",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "status": forms.Select(attrs={"class": "form-select action-status"}),
            "recurrence": forms.Select(attrs={"class": "form-select"}),
            "custom_interval_days": forms.NumberInput(
                attrs={"class": "form-control action-custom-interval", "min": 1}
            ),
        }
        labels = {
            "description": "Описание",
            "status": "Статус",
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

        notify_value = cleaned_data.get("notify_before_value")
        if notify_value in (None, "", 0):
            cleaned_data["notify_before_value"] = None
            cleaned_data["notify_before_unit"] = DealAction.NotifyUnit.MINUTES
        else:
            cleaned_data["notify_before_unit"] = (
                cleaned_data.get("notify_before_unit")
                or DealAction.NotifyUnit.MINUTES
            )

        return cleaned_data
