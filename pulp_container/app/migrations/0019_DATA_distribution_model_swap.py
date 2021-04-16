from django.db import migrations, models, transaction
import django.db.models.deletion


def migrate_data_from_old_model_to_new_model_up(apps, schema_editor):
    """ Move objects from ContainerDistribution to NewContainerDistribution."""
    ContainerDistribution = apps.get_model('container', 'ContainerDistribution')
    NewContainerDistribution = apps.get_model('container', 'NewContainerDistribution')
    for container_distribution in ContainerDistribution.objects.all():
        with transaction.atomic():
            NewContainerDistribution(
                pulp_id=container_distribution.pulp_id,
                pulp_created=container_distribution.pulp_created,
                pulp_last_updated=container_distribution.pulp_last_updated,
                pulp_type=container_distribution.pulp_type,
                name=container_distribution.name,
                base_path=container_distribution.base_path,
                content_guard=container_distribution.content_guard,
                remote=container_distribution.remote,
                repository=container_distribution.repository,
                repository_version=container_distribution.repository_version,
                private=container_distribution.private,
                namespace=container_distribution.namespace,
                description=container_distribution.description,
            ).save()
            container_distribution.delete()


def migrate_data_from_old_model_to_new_model_down(apps, schema_editor):
    """ Move objects from NewContainerDistribution to ContainerDistribution."""
    ContainerDistribution = apps.get_model('container', 'ContainerDistribution')
    NewContainerDistribution = apps.get_model('container', 'NewContainerDistribution')
    for container_distribution in NewContainerDistribution.objects.all():
        with transaction.atomic():
            ContainerDistribution(
                pulp_id=container_distribution.pulp_id,
                pulp_created=container_distribution.pulp_created,
                pulp_last_updated=container_distribution.pulp_last_updated,
                pulp_type=container_distribution.pulp_type,
                name=container_distribution.name,
                base_path=container_distribution.base_path,
                content_guard=container_distribution.content_guard,
                remote=container_distribution.remote,
                repository=container_distribution.repository,
                repository_version=container_distribution.repository_version,
                private=container_distribution.private,
                namespace=container_distribution.namespace,
                description=container_distribution.description,
            ).save()
            container_distribution.delete()


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('core', '0062_add_new_distribution_mastermodel'),
        ('container', '0018_containerdistribution_description'),
    ]

    operations = [
        migrations.CreateModel(
            name='NewContainerDistribution',
            fields=[
                ('distribution_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='container_containerdistribution', serialize=False, to='core.Distribution')),
                ('private', models.BooleanField(default=False, help_text='Restrict pull access to explicitly authorized users. Defaults to unrestricted pull access.')),
                ('namespace', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='container_distributions', to='container.ContainerNamespace')),
                ('description', models.TextField(null=True))
            ],
            options={
                'default_related_name': '%(app_label)s_%(model_name)s',
                'permissions': [('pull_containerdistribution', 'Can pull from a registry repo'), ('push_containerdistribution', 'Can push into the registry repo')]
            },
            bases=('core.distribution',),
        ),
        migrations.RunPython(
            code=migrate_data_from_old_model_to_new_model_up,
            reverse_code=migrate_data_from_old_model_to_new_model_down,
        ),
        migrations.DeleteModel(
            name='ContainerDistribution',
        ),
        migrations.RenameModel(
            old_name='NewContainerDistribution',
            new_name='ContainerDistribution',
        ),
    ]
