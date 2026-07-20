# Generated manually to migrate description fields from subclasses to parent Distribution class

from django.db import migrations


def migrate_description_data_forward(apps, schema_editor):
    Distribution = apps.get_model("core", "Distribution")
    ContainerDistribution = apps.get_model("container", "ContainerDistribution")
    ContainerPullThroughDistribution = apps.get_model(
        "container", "ContainerPullThroughDistribution"
    )

    for Model in (ContainerDistribution, ContainerPullThroughDistribution):
        for dist in Model.objects.all():
            if dist.description:
                parent = Distribution.objects.get(pk=dist.pk)
                if not parent.description:
                    parent.description = dist.description
                    parent.save(update_fields=["description"])


class Migration(migrations.Migration):

    dependencies = [
        # Ensure parent field exists before copying data
        ("core", "0146_distribution_description"),
        ("container", "0047_containernamespace_pulp_labels"),
    ]

    operations = [
        # Copy description data from subclass tables to parent Distribution table
        migrations.RunPython(migrate_description_data_forward, migrations.RunPython.noop),
        # Remove duplicate fields from subclasses
        migrations.RemoveField(model_name="containerdistribution", name="description"),
        migrations.RemoveField(model_name="containerpullthroughdistribution", name="description"),
    ]
