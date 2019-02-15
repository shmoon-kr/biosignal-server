from django import forms


class UploadFileForm(forms.Form):
    attachment = forms.FileField()


class UploadReviewForm(forms.Form):
    chart = forms.ImageField()