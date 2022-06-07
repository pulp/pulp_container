Export and Import a Repository
==============================

When maintaining an **air-gapped** environment, one can benefit from using the import/export
machinery. A common workflow usually resembles the following steps:

#. **An administrator exports Pulp's content on a system with the internet connectivity.** The
   system runs a Pulp instance that syncs content from remote repositories.
#. **The exported content (tarball) is moved to another (air-gapped) system.** The transfer can
   be made through the intranet or via an external hard drive.
#. **The administrator imports the exported content by initiating an import task.** The
   procedure takes care of importing the content to another Pulp instance running in the air-gapped
   environment.

Exporting a Repository
----------------------

To export a repository, run the following set of commands:

.. literalinclude:: ../_scripts/export_repository.sh
   :language: bash

If the exported content is no longer needed to be managed on the system, delete it:

.. literalinclude:: ../_scripts/cleanup_export.sh
   :language: bash

Importing the Repository
------------------------

Import the exported content by running the next commands and monitor the task:

.. literalinclude:: ../_scripts/import_repository.sh
   :language: bash

.. note::
    Pass ``create_repositories=True`` to the ``http POST ${BASE_ADDR}${IMPORTER_HREF}imports/``
    request to tell Pulp to create missing repositories during the import procedure on the fly.
    Otherwise, the repositories need to be created ahead of the import.

.. warning::
    Repositories of the push type are automatically converted to sync repositories at import time.