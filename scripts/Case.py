class Case:

    def __init__(self):
        self.id = ""
        self.year = 0
        self.title = ""
        self.petitioner = ""
        self.respondent = ""
        self.docket_no = ""
        self.scdb_docket_id = ""
        self.citation = ""
        self.url = ""
        self.court = ""
        self.decided_date = ""
        self.win_side = 0.0
        self.win_side_detail = 0.0
        self.transcripts = []
        self.advocates = {}
        self.votes = {}
        self.votes_detail = {}
        self.votes_side = {}
        self.adv_sides_inferred = False

        self.convos = []
    
    def get_case_id(self):
        return self.id
    
    def get_docket_no(self):
        return self.docket_no

    def __eq__(self, other):
        if isinstance(other, Case):
            return self.id == other.id
        return False

    def __hash__(self):
        return hash(self.id)

    def make_dict(self):
        case_dict = self.__dict__
        case_dict.pop('convos')
        return case_dict
