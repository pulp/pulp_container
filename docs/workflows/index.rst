.. _workflows-index:

Workflows
=========

If you have not yet installed the ``pulp_container`` plugin on your Pulp installation, please follow our
:doc:`../installation`. These documents will assume you have the environment installed and
ready to go.

Recommended Tools
-----------------

**httpie**:
The REST API examples here use `httpie <https://httpie.org/doc>`_ to perform the requests.
The ``httpie`` commands below assume that the user executing the commands has a ``.netrc`` file
in the home directory. The ``.netrc`` should have the following configuration:

.. code-block:: bash

    machine localhost
    login admin
    password admin

One should observe that ``httpie`` uses the configuration retrieved from ``.netrc`` by default.
Due to this, a custom Authorization header is always overwritten by the Basic Authorization with
the provided login and password. In order to send HTTP requests which contain JWT Authorization
headers, ensure yourself that the plugin `JWTAuth plugin <https://github.com/teracyhq/httpie-jwt-auth>`_
was already installed.

If you configured the ``admin`` user with a different password, adjust the configuration
accordingly. If you prefer to specify the username and password with each request, please see
``httpie`` documentation on how to do that.

**jq**:
This documentation makes use of the `jq library <https://stedolan.github.io/jq/>`_
to parse the json received from requests, in order to get the unique urls generated
when objects are created. To follow this documentation as-is please install the jq
library with:

``$ sudo dnf install jq``

**environtoment variables**
To make these workflows copy/pastable, we make use of environment variables. The first variable to
set is the hostname and port::

   $ export BASE_ADDR=http://<hostname>:24817


Container Workflows
-------------------

.. toctree::
   :maxdepth: 2

   sync
   host
   manage-content
   authentication
