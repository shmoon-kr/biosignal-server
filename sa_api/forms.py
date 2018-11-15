from django import forms

class UploadFileForm(forms.Form):
    attachment = forms.FileField()