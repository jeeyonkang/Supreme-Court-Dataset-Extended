class Utterance:

    def __init__(self):
        self.id = ""
        self.text = ""
        self.speaker = ""
        self.conversation_id = ""
        self.case_id = ""
        self.speaker_type = ""
        self.side = ""
        self.start_times = []
        self.stop_times = []
        self.timestamp = ""
        self.reply_to = ""
    
    def get_utterance_id(self):
        return self.id
    
    def get_text(self):
        return self.text
    
    def get_speaker(self):
        return self.speaker

    def get_conversation_id(self):
        return self.conversation_id

    def get_case_id(self):
        return self.case_id
    
    def get_speaker_type(self):
        return self.speaker_type

    def make_dict(self):
        utterance_dict = self.__dict__
        return utterance_dict