# Generated by Django 3.2.12 on 2022-02-22 15:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('container', '0028_add_role_manage_permissions'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='blob',
            name='media_type',
        ),
    ]
