import random

from .job import Frequency1DJob

class Query:
    id = 1

    def __init__(self, shuffle):
        self.id = f'Query{Query.id}'
        self.shuffle = shuffle
        Query.id += 1

    @staticmethod
    def from_json(json, dataset):
        type_string = json['type']

        if type_string == Frequency1DQuery.name:
            grouping = json['grouping']['name']

            return Frequency1DQuery(dataset.get_field_by_name(grouping), None, dataset)
        
        return 
    
    def to_json(self):
        return {'id': self.id}

class Frequency1DQuery(Query):
    name = "Frequency1DQuery"

    def __init__(self, grouping, where, dataset, shuffle=True):
        
        super().__init__(shuffle)

        self.grouping = grouping
        self.where = where
        self.dataset = dataset

    def get_jobs(self):
        jobs = []
        
        for sample in self.dataset.samples:
            jobs.append(Frequency1DJob(
                sample, self.grouping, self.where, self, self.dataset
            ))

        if self.shuffle:
            random.shuffle(jobs)

        return jobs

        