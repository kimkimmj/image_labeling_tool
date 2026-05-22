"""Dataset split domain exceptions."""


class DatasetSplitNotFoundError(Exception):
    pass


class DatasetSplitForbiddenError(Exception):
    pass


class DatasetSplitInvalidRatiosError(Exception):
    pass


class DatasetSplitVersionNotFoundError(Exception):
    pass
