# Generated by Django 3.2.11 on 2022-02-03 11:15

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('container', '0027_data_translate_perms_to_roles'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='containerdistribution',
            options={'default_related_name': '%(app_label)s_%(model_name)s', 'permissions': [('pull_containerdistribution', 'Can pull from a registry repo'), ('push_containerdistribution', 'Can push into the registry repo'), ('manage_roles_containerdistribution', 'Can manage role assignments on container distribution')]},
        ),
        migrations.AlterModelOptions(
            name='containernamespace',
            options={'permissions': [('namespace_add_containerdistribution', 'Add any distribution to a namespace'), ('namespace_delete_containerdistribution', 'Delete any distribution from a namespace'), ('namespace_view_containerdistribution', 'View any distribution in a namespace'), ('namespace_pull_containerdistribution', 'Pull from any distribution in a namespace'), ('namespace_push_containerdistribution', 'Push to any distribution in a namespace'), ('namespace_change_containerdistribution', 'Change any distribution in a namespace'), ('namespace_view_containerpushrepository', 'View any push repository in a namespace'), ('namespace_modify_content_containerpushrepository', 'Modify content in any push repository in a namespace'), ('namespace_change_containerpushrepository', 'Update any existing push repository in a namespace'), ('manage_roles_containernamespace', 'Can manage role assignments on container namespace')]},
        ),
        migrations.AlterModelOptions(
            name='containerpushrepository',
            options={'default_related_name': '%(app_label)s_%(model_name)s', 'permissions': [('modify_content_containerpushrepository', 'Can modify content in a push repository'), ('manage_roles_containerpushrepository', 'Can manage role assignments on container pushrepository')]},
        ),
        migrations.AlterModelOptions(
            name='containerremote',
            options={'default_related_name': '%(app_label)s_%(model_name)s', 'permissions': [('manage_roles_containerremote', 'Can manage role assignments on container remote')]},
        ),
        migrations.AlterModelOptions(
            name='containerrepository',
            options={'default_related_name': '%(app_label)s_%(model_name)s', 'permissions': [('sync_containerrepository', 'Can start a sync task'), ('modify_content_containerrepository', 'Can modify content in a repository'), ('build_image_containerrepository', 'Can use the image builder in a repository'), ('delete_containerrepository_versions', 'Can delete repository versions'), ('manage_roles_containerrepository', 'Can manage role assignments on container repository')]},
        ),
    ]
