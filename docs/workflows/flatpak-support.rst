.. _flatpak-workflow:

Hosting Flatpak Content in OCI Format
=====================================

Pulp can host Flatpak application and runtime images that are distributed in OCI format.  To make
such content discoverable, it can provide ``/index/dynamic`` and ``/index/static`` endpoints as
specified by `the Flatpak registry index protocol
<https://github.com/flatpak/flatpak-oci-specs/blob/main/registry-index.md>`_.  This is not enabled
by default.  To enable it, define ``FLATPAK_INDEX = True`` in the settings file.

Clients like the ``flatpak`` command-line tool or the GNOME Software application will typically
query the ``/index/static`` endpoint, which is intended to be called repeatedly with identical query
parameters, and whose responses are meant to be cached.  The ``/index/dynamic`` endpoint serves
exactly the same content, but is intended for one-off requests that should not be cached.  These
endpoints can be accessed without authentication.  They only provide information about public
repositories.

The two endpoints support a number of query parameters (``architecture``, ``tag``, ``label``, etc.),
see the protocol specification for details.  Two notes:

* Every request must include a ``label:org.flatpak.ref:exists=1`` query parameter.  This acts as a
  marker to only report Flatpak content, and to exclude other container content that may also be
  provided by the Pulp instance.

* This implementation does not support annotations.  Including any ``annotation`` query parameters
  will result in a 400 failure response.  Use ``label`` query parameters instead.  (Existing clients
  like the ``flatpak`` command-line tool never issue requests including any ``annotation`` query
  parameters.)

Install a Flatpak image from Pulp
---------------------------------

This section assumes that you have created at least one public distribution in your Pulp instance
that serves a repository containing Flatpak content.  To do this, see the general :doc:`host`
documentation.

You can for example use the ``flatpak`` `command-line tool
<https://docs.flatpak.org/en/latest/using-flatpak.html#the-flatpak-command>`_ to set up a Flatpak
remote (named ``pulp`` here) that references your Pulp instance:

.. code:: shell

  flatpak remote-add pulp oci+"$BASE_ADDR"

Then, use

.. code:: shell

  flatpak remote-ls pulp

to retrieve a list of all Flatpak applications and runtimes that your Pulp instance serves.  (This
queries the ``/index/static`` endpoint, as explained above.)  Finally, if your Pulp instance serves
e.g. the ``org.gnome.gedit`` application, use

.. code:: shell

  flatpak install pulp org.gnome.gedit

to install it and run it with

.. code:: shell

  flatpak run org.gnome.gedit
