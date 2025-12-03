

class AutoInt:
    pass


class AutoUUID:
    pass


class PrimaryKey:

    def __init__(self, *args):
        self.columns = list(args)
