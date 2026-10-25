from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .roles import CONTRIBUTORS_GROUP, add_to_group

User = get_user_model()


class SignUpForm(UserCreationForm):
    """US06: the minimum needed for an account: username, email and password."""

    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
        help_text="We won't show your email publicly.",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = (
            "Shown with your reviews. Up to 150 characters: letters, numbers and @ . + - _ only."
        )
        self.fields["password1"].help_text = (
            "At least 8 characters. Avoid common or all-number passwords, "
            "and don't reuse your username or email."
        )

    # Username uniqueness: UserCreationForm.clean_username already rejects names
    # that differ only in case ("Alice" vs "alice"), matching MySQL's
    # case-insensitive unique index, so a duplicate gets a form error, not a crash.

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists. Try logging in instead.",
                code="unique",
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            add_to_group(user, CONTRIBUTORS_GROUP)
        return user


class LoginForm(AuthenticationForm):
    """US07: one generic error that never reveals which field was wrong."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "The username or password is incorrect. Please try again.",
        "inactive": "The username or password is incorrect. Please try again.",
    }
