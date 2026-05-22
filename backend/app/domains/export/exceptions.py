"""Export domain exceptions."""


class ExportForbiddenError(Exception):
    pass


class ExportNotFoundError(Exception):
    pass


class ExportInvalidSplitError(Exception):
    pass
