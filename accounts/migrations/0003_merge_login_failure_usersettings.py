from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_login_failure"),
        ("accounts", "0002_usersettings"),
    ]

    operations = []
