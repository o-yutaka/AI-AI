class UnknownRunError(KeyError):
    pass


class InvalidRunStateError(ValueError):
    pass


class IdempotencyConflictError(ValueError):
    pass
