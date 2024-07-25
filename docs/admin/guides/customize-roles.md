# Customize Roles

In Pulp, administrators are allowed to create or update roles. To create a role with permissions
required only for syncing content, one can do the following:

```bash
pulp role create --name "container.containerrepository_syncer" \
    --permission "container.view_containerrepository" \
    --permission "container.view_containerremote" \
    --permission "container.change_containerrepository" \
    --permission "container.modify_content_containerrepository" \
    --permission "container.sync_containerrepository"

pulp user role-assignment add --username "alice" --role "container.containerrepository_syncer" --object ""
```

Visit [Role-based Access Control](site:pulp_container/docs/admin/learn/rbac) to learn more about roles.
