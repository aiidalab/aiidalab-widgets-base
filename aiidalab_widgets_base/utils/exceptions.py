class ListOrTuppleError(TypeError):
    """Raised when the provided value is not a list or a tupple."""

    def __init__(self, value):
        super().__init__(
            f"The provided value {value!r} is not a list or a tupple, but a {type(value)}."
        )
