Added a `migrate` endpoint on push repositories
  (`POST .../repositories/container/container-push/{pk}/migrate/`) that converts a legacy
  `ContainerPushRepository` into a `ContainerRepository`. Optional `copy_versions` preserves
  repository version history; by default only the latest version content is copied.
  Distributions keep the same registry path after migration.
