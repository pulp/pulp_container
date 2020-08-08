def delete_from_storage(sender, instance, *args, **kwargs):
    """Delete the stored file from the current storage if it exists."""
    file_storage = instance.file.storage
    file_name = instance.file.name
    if file_storage.exists(file_name):
        file_storage.delete(file_name)
