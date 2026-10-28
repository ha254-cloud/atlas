class ProgressTracker:
    def __init__(self):
        self.total = 0
        self.success = 0
        self.failed = 0
        self.duplicates = 0

    def success_row(self):
        self.success += 1
        self.total += 1

    def failed_row(self):
        self.failed += 1
        self.total += 1

    def duplicate_row(self):
        self.duplicates += 1
        self.total += 1

    @property
    def processed(self):
        return self.success + self.failed + self.duplicates
