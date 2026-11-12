# contabilidad/forms.py
from django import forms
from .models import ComprobanteBorrador, PeriodoContable

class ComprobanteBorradorForm(forms.ModelForm):
    class Meta:
        model = ComprobanteBorrador
        fields = ["periodo", "fecha", "concepto"]
        widgets = {
            "periodo": forms.Select(attrs={"class": "form-select"}),
            "fecha": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "concepto": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }