class ImportProgress:
    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.failed = 0

    def success(self):
        self.completed += 1

    def error(self):
        self.failed += 1

    @property
    def percentage(self):
        if self.total == 0:
            return 0

        return round(
            (self.completed / self.total) * 100,
            2,
        )
