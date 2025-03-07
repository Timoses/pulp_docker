from pulpcore.plugin.models import Repository, RepositoryVersion

from pulp_docker.app.models import Blob, Manifest, MEDIA_TYPE, Tag


def recursive_add_content(repository_pk, content_units):
    """
    Create a new repository version by recursively adding content.

    For each unit that is specified, we also need to add related content. For example, if a
    manifest-list is specified, we need to add all referenced manifests, and all blobs referenced
    by those manifests.

    Args:
        repository_pk (int): The primary key for a Repository for which a new Repository Version
            should be created.
        content_units (list): List of PKs for :class:`~pulpcore.app.models.Content` that
            should be added to the previous Repository Version for this Repository.
    """
    repository = Repository.objects.get(pk=repository_pk)

    tags_to_add = Tag.objects.filter(
        pk__in=content_units,
    )

    manifest_lists_to_add = Manifest.objects.filter(
        pk__in=content_units,
        media_type=MEDIA_TYPE.MANIFEST_LIST
    ) | Manifest.objects.filter(
        pk__in=tags_to_add.values_list('tagged_manifest', flat=True),
        media_type=MEDIA_TYPE.MANIFEST_LIST,
    )

    manifests_to_add = Manifest.objects.filter(
        pk__in=content_units,
        media_type__in=[MEDIA_TYPE.MANIFEST_V1, MEDIA_TYPE.MANIFEST_V1_SIGNED,
                        MEDIA_TYPE.MANIFEST_V2]
    ) | Manifest.objects.filter(
        pk__in=manifest_lists_to_add.values_list('listed_manifests', flat=True)
    ) | Manifest.objects.filter(
        pk__in=tags_to_add.values_list('tagged_manifest', flat=True),
        media_type__in=[MEDIA_TYPE.MANIFEST_V1, MEDIA_TYPE.MANIFEST_V1_SIGNED,
                        MEDIA_TYPE.MANIFEST_V2]
    )

    blobs_to_add = Blob.objects.filter(
        pk__in=content_units,
        media_type__in=[MEDIA_TYPE.CONFIG_BLOB, MEDIA_TYPE.REGULAR_BLOB, MEDIA_TYPE.FOREIGN_BLOB]
    ) | Blob.objects.filter(
        pk__in=manifests_to_add.values_list('blobs', flat=True)
    ) | Blob.objects.filter(
        pk__in=manifests_to_add.values_list('config_blob', flat=True)
    )

    latest_version = RepositoryVersion.latest(repository)
    if latest_version:
        tags_in_repo = latest_version.content.filter(
            pulp_type="docker.tag"
        )
        tags_to_replace = Tag.objects.filter(
            pk__in=tags_in_repo,
            name__in=tags_to_add.values_list("name", flat=True)
        )
    else:
        tags_to_replace = []

    with RepositoryVersion.create(repository) as new_version:
        new_version.remove_content(tags_to_replace)
        new_version.add_content(tags_to_add)
        new_version.add_content(manifest_lists_to_add)
        new_version.add_content(manifests_to_add)
        new_version.add_content(blobs_to_add)
