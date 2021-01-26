from pulp_smash import cli, config, exceptions


class BaseRegistryTest:
    """
    Base class that container pull/push registy operations.
    """

    @classmethod
    def setUpClass(cls):
        """Prepare registry api."""
        cfg = config.get_config()
        cls.registry = cli.RegistryClient(cfg)

    @classmethod
    def _pull(cls, image_path, user=None):
        """
        Pull using specified user.

        Ensure we login with a user if specified and logout after the pull.

        If user is not specified, ensure that no other user is logged in and pull is performed
        anonymously.
        """
        if user:
            cls.registry.login("-u", user["username"], "-p", user["password"], cls.registry_name)
        else:
            # Ensure logout
            try:
                cls.registry.logout(cls.registry_name)
            except exceptions.CalledProcessError:
                pass

        cls.registry.pull(image_path)

        if user:
            cls.registry.logout(cls.registry_name)

    @classmethod
    def _push(cls, image_path, local_url, user):
        """
        Tag and push an image to Pulp registry using specified user.

        Ensure we login with a specified user and logout after the push.
        A local tag is removed for cleanup purposes.
        """
        # Tag it to registry under test
        cls.registry.tag(image_path, local_url)
        # Log in
        cls.registry.login("-u", user["username"], "-p", user["password"], cls.registry_name)
        try:
            cls.registry.push(local_url)
        finally:
            # Untag local copy
            cls.registry.rmi(local_url)

            cls.registry.logout(cls.registry_name)
