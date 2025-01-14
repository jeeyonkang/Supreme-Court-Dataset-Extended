class Conversation:

    def __init__(self):
        self.id = ""
        self.case_id = ""
        self.advocates = {}
        self.votes_side = {}
        self.win_side = 0.0

        self.utterances = []
    
    def get_conversation_id(self):
        return self.id
    
    def get_case_id(self):
        return self.case_id

    def get_votes_side(self):
        return self.votes_side

    def make_dict(self):
        convo_dict = self.__dict__
        return convo_dict