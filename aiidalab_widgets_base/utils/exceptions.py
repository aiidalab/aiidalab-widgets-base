class AtLeastTwoStepsError(ValueError):
    """Raised when the number of steps is less than two."""

    def __init__(self, steps):
        super().__init__(
            f"The number of steps of a WizardAppWidget must be at least two, but {len(steps)} were provided."
        )


class ListOrTuppleError(TypeError):
    """Raised when the provided value is not a list or a tupple."""

    def __init__(self, value):
        super().__init__(
            f"The provided value '{value}' is not a list or a tupple, but a {type(value)}."
        )
