Started signing manifests asynchronously. This feature improves the performance of signing tasks.
Additionally, setting ``MAX_PARALLEL_SIGNING_TASKS`` was introduced to cap the number of threads
used for parallel signing (defaults to ``10``).
