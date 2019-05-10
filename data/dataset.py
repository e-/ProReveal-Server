import os
import json
import re

from pyspark.sql.types import StructType, StructField
from .field import FieldTrait

class Sample:
    def __init__(self, index, path, num_rows):
        self.index = index
        self.path = path
        self.num_rows = num_rows

class Dataset:    
    def __init__(self, spark, path):
        self.spark = spark
        self.path = path
        self.fields = []        
        self.is_hdfs = path.startswith('hdfs')

        if self.is_hdfs:
            p = '(?:hdfs.*://)?(?P<host>[^:/ ]+).?(?P<port>[0-9]*).*'
            m = re.search(p, self.path)

            self.hdfs_host = m.group('host')
            self.hdfs_port = int(m.group('port'))
    
    def load(self):
        if not self.is_hdfs:
            metadata = json.load(open(os.path.join(self.path, 'metadata.json')))
        else:
            metadata_rdd = self.spark.read.text(self.path + '/metadata.json')
            metadata_json = ''.join([row.value.strip() for row in metadata_rdd.collect()])
            metadata = json.loads(metadata_json)

        self.metadata = metadata

        self.fields = []
        for field in self.metadata['header']:
            self.fields.append(FieldTrait.from_json(field))
        
        self.samples = [Sample(i, sample['path'], sample['num_rows']) for i, sample in enumerate(self.metadata['output_files'])]

        num_rows = 0
        for sample in self.samples:
            num_rows += sample.num_rows

        self.num_rows = num_rows        

    def get_field_by_name(self, name):
        for field in self.fields:
            if field.name == name:
                return field
        
        return None
    
    def get_spark_schema(self):
        schema = [StructField(field.name, field.get_pyspark_sql_type()())
            for field in self.fields]
        
        return StructType(schema)
    
    def get_json_schema(self):
        return [field.to_json() for field in self.fields]

    def get_sample_df(self, sid):
        df = self.spark.read.format('csv').option('header', 'false')\
            .schema(self.get_spark_schema())\
            .load(os.path.join(self.path, self.metadata['output_files'][sid]['path']))

        return df
    