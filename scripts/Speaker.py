class Speaker:

    def __init__(self, id, name, type):
        self.id = id
        self.name = name
        self.type = type

    def __eq__(self, other):
        if not isinstance(other, Speaker):
            return False
        return self.name == other.name and self.type == other.type

    def __hash__(self):
        return hash((self.name, self.type))

    def make_dict(self):
        speaker_dict = self.__dict__
        return speaker_dict