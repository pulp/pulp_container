# Migrate from Permissions to Roles

As of release 2.11.0, the plugin started to support roles instead of separate groups and
permissions. Default permission classes provided by Pulp are **automatically** migrated when
upgrading from older releases. But, custom permissions created before release 2.11.0 require
additional **post-upgrade steps** to preserve the initial behaviour.

Usually, administrators define permissions for two types of operations:

1. **pull** - Pulling content from all or a number of specific repositories
2. **push** - Pushing content to all or concrete repositories

During the upgrade, the custom permissions need to be manually revised and assigned. To do so, one
can proceed as follows:

1. Make all repositories private:

```bash
for name in $(pulp container distribution list | jq -re '.[].name')
do
    pulp container distribution update --name $name --private
done
```

2. Start assigning Pulp-provided/adjusted roles to a particular user. For instance, use the role
   `container.containerdistribution_consumer` to enable user `alice` to consume content from
   distributions `dist1`, `dist2`, `dist3`:

```bash
for distribution in "dist1" "dist2" "dist3"
do
    DISTRIBUTION_HREF=$(pulp container distribution show --name $distribution | jq -r ".pulp_href")
    pulp user role-assignment add --username "alice" --role "container.containerdistribution_consumer" --object $DISTRIBUTION_HREF
done
```

Similarly, execute an adjusted script for other repository objects that were asserted under
the permissions' scope.

!!! note

    As of release 2.13.0, administrators should use the `pulpcore-manager dump-permissions`
    command to list deprecated permissions not yet translated into roles.
