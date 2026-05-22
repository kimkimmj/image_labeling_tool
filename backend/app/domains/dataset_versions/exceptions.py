"""Dataset version domain exceptions."""


class DatasetVersionNotFoundError(Exception):
    pass


class DatasetVersionDuplicateNameError(Exception):
    pass


class DatasetVersionForbiddenError(Exception):
    pass
