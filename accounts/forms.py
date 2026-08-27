from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import UserProfile


class RegistrationForm(UserCreationForm):

    full_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            "placeholder": "Enter your full name",
            "autocomplete": "name",
        }),
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "placeholder": "you@example.com",
            "autocomplete": "email",
        }),
    )

    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TelInput(attrs={
            "placeholder": "+91 9876543210",
            "autocomplete": "tel",
        }),
    )

    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={
            "type": "date",
            "autocomplete": "bday",
        }),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "full_name",
            "email",
            "phone_number",
            "date_of_birth",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        today = date.today()

        self.fields["date_of_birth"].widget.attrs.update({
            "max": today.replace(year=today.year - 13).isoformat(),
            "min": today.replace(year=today.year - 100).isoformat(),
        })

        self.fields["username"].widget.attrs.update({
            "placeholder": "Choose a username",
            "autocomplete": "username",
        })

        self.fields["password1"].widget.attrs.update({
            "placeholder": "Create a strong password",
            "autocomplete": "new-password",
        })

        self.fields["password2"].widget.attrs.update({
            "placeholder": "Confirm your password",
            "autocomplete": "new-password",
        })

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        today = date.today()

        age = (
            today.year
            - dob.year
            - ((today.month, today.day) < (dob.month, dob.day))
        )

        if age < 13:
            raise forms.ValidationError(
                "You must be at least 13 years old."
            )

        if age > 100:
            raise forms.ValidationError(
                "Please enter a valid date of birth."
            )

        return dob

    def save(self, commit=True):
        user = super().save(commit=False)

        user.email = self.cleaned_data["email"]

        if commit:
            user.save()

            UserProfile.objects.create(
                user=user,
                full_name=self.cleaned_data["full_name"],
                email=self.cleaned_data["email"],
                phone_number=self.cleaned_data["phone_number"],
                date_of_birth=self.cleaned_data["date_of_birth"],
            )

        return user


class EditProfileForm(forms.ModelForm):

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            "placeholder": "Choose a username",
            "autocomplete": "username",
        }),
    )

    class Meta:
        model = UserProfile
        fields = (
            "full_name",
            "email",
            "phone_number",
            "date_of_birth",
        )

        widgets = {
            "full_name": forms.TextInput(attrs={
                "placeholder": "Enter your full name",
                "autocomplete": "name",
            }),
            "email": forms.EmailInput(attrs={
                "placeholder": "you@example.com",
                "autocomplete": "email",
            }),
            "phone_number": forms.TelInput(attrs={
                "placeholder": "+91 9876543210",
                "autocomplete": "tel",
            }),
            "date_of_birth": forms.DateInput(attrs={
                "type": "date",
                "autocomplete": "bday",
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.user = user

        if user:
            self.fields["username"].initial = user.username

        today = date.today()

        self.fields["date_of_birth"].widget.attrs.update({
            "max": today.replace(year=today.year - 13).isoformat(),
            "min": today.replace(year=today.year - 100).isoformat(),
        })

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.filter(
            username__iexact=username
        ).exclude(
            pk=self.user.pk
        ).exists():
            raise forms.ValidationError(
                "This username is already taken. Please choose another."
            )

        return username

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]

        if not dob:
            return dob

        today = date.today()

        age = (
            today.year
            - dob.year
            - ((today.month, today.day) < (dob.month, dob.day))
        )

        if age < 13:
            raise forms.ValidationError(
                "You must be at least 13 years old."
            )

        if age > 100:
            raise forms.ValidationError(
                "Please enter a valid date of birth."
            )

        return dob

    def save(self, commit=True):
        profile = super().save(commit=False)

        user = self.user
        user.username = self.cleaned_data["username"]
        user.email = self.cleaned_data["email"]

        profile.email = self.cleaned_data["email"]

        if commit:
            user.save()
            profile.save()

        return profile


class TelegramPhoneForm(forms.Form):
    phone = forms.CharField(
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "placeholder": "+91 9876543210",
                "autocomplete": "tel",
                "inputmode": "tel",
            }
        ),
    )


class TelegramCodeForm(forms.Form):
    code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter Telegram code",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
            }
        ),
    )


class Telegram2FAForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Telegram 2FA password",
                "autocomplete": "current-password",
            }
        ),
    )
