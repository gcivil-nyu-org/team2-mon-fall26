from django.contrib import admin

from .forms import AdminLoginForm

admin.site.login_form = AdminLoginForm
