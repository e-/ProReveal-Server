import random
import time

from .job import *
from .predicate import Predicate
from accum import AggregateValue, AllAccumulator

accum = AllAccumulator()

def now():
    return int(time.time() * 1000)

class Query:
    id = 1
    
    def __init__(self, client_socket_id, client_id, shuffle):
        self.id = f'Query{Query.id}'
        self.client_socket_id = client_socket_id
        self.client_id = client_id
        self.shuffle = shuffle

        self.num_processed_rows = 0
        self.num_processed_blocks = 0     
        self.last_updated = now()
        
        self.result = {} # dict with keys

        Query.id += 1

    def to_json(self):
        return {'id': self.id, 'clientId': self.client_id}

    @staticmethod
    def from_json(json, dataset, client_socket_id, client_id):
        type_string = json['type']
        where_string = json['where']

        where = None
        
        if where_string is not None and len(where_string) > 0:
            where = Predicate.from_json(where_string)

        if type_string == Frequency1DQuery.name:
            grouping = json['grouping']['name']

            return Frequency1DQuery(dataset.get_field_by_name(grouping), where, dataset, client_socket_id, client_id)

        elif type_string == Frequency2DQuery.name:
            grouping1 = dataset.get_field_by_name(json['grouping1']['name'])
            grouping2 = dataset.get_field_by_name(json['grouping2']['name'])

            return Frequency2DQuery(grouping1, grouping2, where, dataset, client_socket_id, client_id)
        
        elif type_string == AggregateQuery.name:
            target = dataset.get_field_by_name(json['target']['name'])
            grouping = dataset.get_field_by_name(json['grouping']['name'])

            return AggregateQuery(target, grouping, where, dataset, client_socket_id, client_id)
        
        elif type_string == Histogram1DQuery.name:
            grouping = dataset.get_field_by_name(json['grouping']['name'])
            bin_spec = BinSpec.from_json(json['grouping'])

            return Histogram1DQuery(grouping, bin_spec, where, dataset, client_socket_id, client_id)
            
        elif type_string == Histogram2DQuery.name:
            grouping1 = dataset.get_field_by_name(json['grouping1']['name'])
            bin_spec1 = BinSpec.from_json(json['grouping1'])
            grouping2 = dataset.get_field_by_name(json['grouping2']['name'])
            bin_spec2 = BinSpec.from_json(json['grouping2'])

            return Histogram2DQuery(grouping1, bin_spec1, grouping2, bin_spec2,
            where, dataset, client_socket_id, client_id)

        elif type_string == SelectQuery.name:
            return SelectQuery(json['from'], json['to'], where, dataset, client_socket_id)

        raise f'Unknown query type: {json}'
    
    def to_json(self):
        return {
            'id': self.id,
            'numProcessedRows': self.num_processed_rows,
            'numProcessedBlocks': self.num_processed_blocks,
            'lastUpdated': self.last_updated,
            'result': self.get_result()
        }

class SelectQuery(Query):
    name = 'SelectQuery'
    priority = 0

    def __init__(self, where, dataset, client_socket_id, shuffle=False):
        super().__init__(client_socket_id, 0, shuffle)
        self.where = where
        self.dataset = dataset
    
    def get_jobs(self):
        jobs = []
        samples = self.dataset.samples[:]

        if self.shuffle:
            random.shuffle(samples)

        for i, sample in enumerate(samples):
            jobs.append(SelectJob(
                i,
                sample,
                #self.idx_from,
                #self.idx_to,
                sample, self.where, self, self.dataset
            ))

        return jobs

class AggregateQuery(Query):
    name = 'AggregateQuery'
    priority = 1

    def __init__(self, target, grouping, where, dataset, client_socket_id, client_id, shuffle=True):        
        super().__init__(client_socket_id, client_id, shuffle)

        self.target = target
        self.grouping = grouping
        self.where = where
        self.dataset = dataset

    def get_jobs(self):
        jobs = []
        samples = self.dataset.samples[:]

        if self.shuffle:
            random.shuffle(samples)

        for i, sample in enumerate(samples):
            jobs.append(AggregateJob(
                i, sample, self.target, self.grouping, self.where, 
                self, self.dataset
            ))

        return jobs

def dict_to_list(dic):
    res = []
    for key, value in dic.items():
        if isinstance(key, str):
            key = ((key, ), )
        
        res.append(key + value.to_tuple())
    
    return res

class Frequency1DQuery(Query):
    name = 'Frequency1DQuery'
    priority = 1

    def __init__(self, grouping, where, dataset, client_socket_id, client_id, shuffle=True):        
        super().__init__(client_socket_id, client_id, shuffle)

        self.grouping = grouping
        self.where = where
        self.dataset = dataset

    def get_jobs(self):
        jobs = []
        samples = self.dataset.samples[:]

        if self.shuffle:
            random.shuffle(samples)

        for i, sample in enumerate(samples):
            jobs.append(Frequency1DJob(
                i, sample, self.grouping, self.where, self, self.dataset
            ))

        return jobs

    def accumulate(self, res):
        for name, count in res:
            if name not in self.result:
                self.result[name] = AggregateValue(0, 0, count, 0, 0, 0)
            else:
                partial = AggregateValue(0, 0, count, 0, 0, 0)

                self.result[name] = accum.accumulate(self.result[name], partial)
                
    def get_result(self):
        return dict_to_list(self.result)

class Frequency2DQuery(Query):
    name = 'Frequency2DQuery'
    priority = 1

    def __init__(self, grouping1, grouping2, where, dataset, client_socket_id, client_id, shuffle=True):
        super().__init__(client_socket_id, client_id, shuffle)

        self.grouping1 = grouping1
        self.grouping2 = grouping2
        self.where = where
        self.dataset = dataset

    def get_jobs(self):
        jobs = []
        samples = self.dataset.samples[:]

        if self.shuffle:
            random.shuffle(samples)

        for i, sample in enumerate(samples):
            jobs.append(Frequency2DJob(
                i, sample, self.grouping1, self.grouping2, self.where, self, self.dataset
            ))

        return jobs

class BinSpec:
    def __init__(self, start, end, step, num_bins):
        self.start = start
        self.end = end
        self.step = step
        self.num_bins = num_bins

    @staticmethod
    def from_json(bin_spec_json):
        start = bin_spec_json['start']
        end = bin_spec_json['end']
        step = bin_spec_json['step']
        num_bins = bin_spec_json['numBins']

        return BinSpec(start, end, step, num_bins)

class Histogram1DQuery(Query):
    name = 'Histogram1DQuery'
    priority = 1

    def __init__(self, grouping, bin_spec, where, dataset, client_socket_id, client_id, shuffle=True):
        super().__init__(client_socket_id, client_id, shuffle)

        self.grouping = grouping
        self.bin_spec = bin_spec
        self.where = where
        self.dataset = dataset
        
    def get_jobs(self):
        jobs = []
        samples = self.dataset.samples[:]

        if self.shuffle:
            random.shuffle(samples)

        for i, sample in enumerate(samples):
            jobs.append(Histogram1DJob(
                i, sample, self.grouping, self.bin_spec, self.where, self,
                self.dataset
            ))

        return jobs


class Histogram2DQuery(Query):
    name = 'Histogram2DQuery'
    priority = 1

    def __init__(self, grouping1, bin_spec1, grouping2, bin_spec2, where, dataset, client_socket_id, client_id, shuffle=True):
        super().__init__(client_socket_id, client_id, shuffle)

        self.grouping1 = grouping1
        self.bin_spec1 = bin_spec1
        self.grouping2 = grouping2
        self.bin_spec2 = bin_spec2
        self.where = where
        self.dataset = dataset
        
    def get_jobs(self):
        jobs = []
        samples = self.dataset.samples[:]

        if self.shuffle:
            random.shuffle(samples)

        for i, sample in enumerate(samples):
            jobs.append(Histogram2DJob(
                i, sample, self.grouping1, self.bin_spec1, 
                self.grouping2, self.bin_spec2, self.where, self,
                self.dataset
            ))

        return jobs