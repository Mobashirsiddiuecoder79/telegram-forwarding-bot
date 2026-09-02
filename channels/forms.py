from django import forms
from .models import ForwardingRule


class ForwardingRuleForm(forms.ModelForm):
    keywords = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Enter keywords separated by commas'
        })
    )

    blocked_keywords = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Enter blocked keywords separated by commas'
        })
    )

    class Meta:
        model = ForwardingRule
        fields = [
            'enabled',
            'keywords',
            'blocked_keywords',
            'allow_text',
            'allow_photos',
            'allow_videos',
            'allow_documents',
            'allow_audio',
            'allow_forwarded',
            'allow_normal',
            'filter_captions',
        ]
