import django.contrib.postgres.fields
from django.db import migrations, models


def migrate_to_includes_excludes(apps, schema_editor):
    """Copy include_tags -> includes, exclude_tags -> excludes."""
    ContainerRemote = apps.get_model("container", "ContainerRemote")
    for remote in ContainerRemote.objects.all():
        remote.includes = remote.include_tags or None
        remote.excludes = remote.exclude_tags or None
        remote.save(update_fields=["includes", "excludes"])

def down_migrate_to_include_exclude_tags(apps, schema_editor):
    """Copy includes + excludes -> include_tags + exclude_tags."""
    ContainerRemote = apps.get_model("container", "ContainerRemote")
    for remote in ContainerRemote.objects.all():
        remote.include_tags = remote.includes or None
        remote.exclude_tags = remote.excludes or None
        remote.save(update_fields=["include_tags", "exclude_tags"])


class Migration(migrations.Migration):

    dependencies = [
        ("container", "0047_containernamespace_pulp_labels"),
    ]

    operations = [
        migrations.AddField(
            model_name="containerremote",
            name="includes",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.TextField(null=True),
                null=True,
                size=None,
            ),
        ),
        migrations.AddField(
            model_name="containerremote",
            name="excludes",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.TextField(null=True),
                null=True,
                size=None,
            ),
        ),
        # 2. Copy existing data.
        migrations.RunPython(
            migrate_to_includes_excludes,
            down_migrate_to_include_exclude_tags,
        ),
    ]
