# Domain support

Enabling domain support in pulp_container works a bit differently than other plugins due to the 
nature of the Registry API. Each domain is scoped as a unique registry by the domain name. This 
means that all images will include the domain name as a prefix to its repository path.

## Examples

### Sync and Pull

Here's an example of syncing and hosting an image (`pulp/pulp`) in the domain `foo`.

```bash
pulp --domain foo container repository create --name pulp
pulp --domain foo container remote create --name quay-pulp --url https://quay.io --upstream-name pulp/pulp
pulp --domain foo container repository sync --name pulp --remote quay-pulp
pulp --domain foo distribution create --name pulp --repository pulp --base-path pulp/pulp

# 'foo' is added to the repository path
docker pull localhost:24817/foo/pulp/pulp:latest
```

### Push

Here's an example of pushing an image (`pulp/pulp`) to the domain `foo`.

```bash
docker tag pulp/pulp localhost:24817/foo/pulp/pulp:latest
# This will create a 'pulp/pulp' repository in the domain 'foo'
docker push localhost:24817/foo/pulp/pulp:latest
```

### RBAC

With domain support enabled, roles can now be assigned at the domain level.

```bash
pulp --domain foo container distribution create --name "bar" --base-path "bar" --private
pulp user create --username "alice"
# This will allow alice to pull all images from the 'foo' domain
pulp user role-assignment add --username "alice" --role "container.containerdistribution_consumer" --domain "foo"

docker login localhost:24817 -u alice
docker pull localhost:24817/foo/bar:latest
```

!!! note

    Objects are still prohibited from being used across domains even if you have permissions for both.

!!! note

    The Flatpak endpoints will only work within the default domain, even with domains enabled.

