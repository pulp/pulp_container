from django.core.exceptions import ObjectDoesNotExist

from pulpcore.plugin.models import CreatedResource

from pulp_container.app.models import ContainerDistribution
from pulp_container.app.serializers import ContainerDistributionSerializer


def create(*args, **kwargs):
    """
    Creates a :class:`~pulp_container.app.models.ContainerDistribution`.

    Raises:
        ValidationError: If the ContainerDistributionSerializer is not valid

    """
    data = kwargs.pop('data', None)
    serializer = ContainerDistributionSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    resource = CreatedResource(content_object=serializer.instance)
    resource.save()


def update(instance_id, *args, **kwargs):
    """
    Updates a :class:`~pulp_container.app.models.ContainerDistribution`.

    Args:
        instance_id (int): The id of the ContainerDistribution to be updated

    Raises:
        ValidationError: If the DistributionSerializer is not valid

    """
    data = kwargs.pop('data', None)
    partial = kwargs.pop('partial', False)
    instance = ContainerDistribution.objects.get(pk=instance_id)
    serializer = ContainerDistributionSerializer(instance, data=data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()


def delete(instance_id, *args, **kwargs):
    """
    Delete a :class:`~pulp_container.app.models.ContainerDistribution`.

    Args:
        instance_id (int): The id of the ContainerDistribution to be deleted

    Raises:
        ObjectDoesNotExist: If the ContainerDistribution was already deleted

    """
    try:
        instance = ContainerDistribution.objects.get(pk=instance_id)
    except ObjectDoesNotExist:
        # The object was already deleted, and we don't want an error thrown trying to delete again.
        return
    else:
        instance.delete()
