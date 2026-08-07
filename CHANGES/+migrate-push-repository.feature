Added a `migrate` endpoint on push repositories that converts a legacy `ContainerPushRepository`
into a `ContainerRepository` in place. The repository primary key and version history are
preserved; only the repository type changes.
