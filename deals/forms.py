from django import forms
from .models import Deal, Company, Contact


class DocumentUploadForm(forms.Form):
    file = forms.FileField()

from django import forms


class DealForm(forms.ModelForm):
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Компании"
    )
    contacts = forms.ModelMultipleChoiceField(
        queryset=Contact.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Контакты"
    )

    class Meta:
        model = Deal
        fields = ["title", "stage", "owner", "companies", "contacts"]
