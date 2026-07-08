Added a `migrate` endpoint on push repositories that converts a legacy `ContainerPushRepository` into a `ContainerRepository`. Optional `copy_versions` preserves repository version history; by default only the latest version content is copied.

