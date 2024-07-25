# Customize Access Policies

The plugin is shipped with default access policies that can be modified to achieve different RBAC
behaviour. Administrators can update creation hooks accordingly:

```bash
pulp access-policy update --viewset-name "repositories/container/container" --creation-hooks '[{"function": "add_roles_for_object_creator", "parameters": {"roles": "container.containerrepository_syncer"}}]'
```

!!! note

    Access polices can be reset to their defaults using the `pulp access-policy reset` command.

!!! note

    Customizing the access policy will cause any future changes to the default policies, like
    statement changes and bug fixes, to be ignored unless reset to the default policy.

Visit [Role-based Access Control](site:pulp_container/docs/admin/learn/rbac) to learn more about
access policies.
