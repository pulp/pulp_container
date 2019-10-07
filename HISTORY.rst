4.0.0b4
^^^^^^^

- Enable sync from registries that use basic auth or have private repos
- Enable on_demand or streamed sync
- Enable whitelist tags specification when syncing
- Compatibility with pulpcore-plugin-0.1.0rc2

`Comprehensive list of changes and bugfixes for beta 4 <https://github.com/pulp/pulp_container/compare/4.0.0b3...4.0.0b4>`_.

4.0.0b3
^^^^^^^

- Enable sync from gcr and quay registries
- Enable support to handle pagination for tags/list endpoint during sync
- Enable support to manage a docker image that has manifest schema v2s1
- Enable docker distribution to serve directly latest repository version

`Comprehensive list of changes and bugfixes for beta 3 <https://github.com/pulp/pulp_container/compare/4.0.0b2...4.0.0b3>`_.

4.0.0b2
^^^^^^^

- Compatibility with pulpcore-plugin-0.1.0rc1
- Performance improvements and bug fixes
- Add support for syncing repo with foreign layers
- Change sync pipeline to use Futures to handle nested content
- Make Docker distributions asyncronous
- Add support to create publication directly

4.0.0b1
^^^^^^^

- Add support for basic sync of a docker repo form a V2Registry
- Add support for docker/podman pull from a docker distbution served by Pulp
