import argparse
import glob
import os
import json
import random
import pandas as pd
import csv

from tqdm import tqdm

parser = argparse.ArgumentParser(description='Split the given dataset into mini-batches')
parser.add_argument('input_path', metavar='<input path to dataset>', type=str, help='Files to split')
parser.add_argument('output_path', metavar='<output path>', type=str, help='Path to save the output')

parser.add_argument('--num-rows', metavar='N', type=int, help='Number of rows in each mini-batch')
parser.add_argument('--num-batches', metavar='N', type=int, help='Number of mini-batches')
parser.add_argument('--preseve-header', dest='skip_header', action='store_const', const=False, default=True, help='preserve the first line of a CSV')
parser.add_argument('--fields', metavar='A,B,C,D', type=str, default='', help='Fields to use')

args = parser.parse_args()

def create_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def write(oid, buffer):
    output_path = os.path.join(args.output_path, f'{oid}.csv')
    with open(output_path, 'w', encoding='utf8', newline='') as fout:
        writer = csv.writer(fout)
        for line in buffer:
            writer.writerow(line)            
            
    return output_path

def append(oid, buffer):
    output_path = os.path.join(args.output_path, f'{oid}.csv')
    with open(output_path, 'a', encoding='utf8') as fout:
        for line in buffer:
            print(line, file=fout, end='')
            
    return output_path

def output_meta(index, path, num_rows):
    return {
        'index': index,
        'path': path,
        'num_rows': num_rows
    }

def shuffle(oid):
    path = os.path.join(args.output_path, f'{oid}.csv')
    with open(path, 'r', encoding='utf8') as fin:
        lines = fin.readlines()
    
    random.shuffle(lines)

    write(oid, lines)

    return path, len(lines)

def write_metadata(metadata):
    with open(os.path.join(args.output_path, 'metadata.json'), 'w', encoding='utf8') as outf:
        json.dump(metadata, outf, indent=2)           

def main():
    oid = 0
    header = None
    metadata = {
        'input_files': [],
        'output_files': [],
        'header': None
    }
    # E:\gaia\cdn.gea.esac.esa.int\Gaia\gdr2\gaia_source\csv\GaiaSource-1824978848714654592-1824998712986627584.csv
    # python tools/split.py --num-rows 300000 --fields source_id,ra,ra_error,dec,dec_error,parallax,parallax_error,phot_g_mean_mag,bp_rp,bp_g,radial_velocity,radial_velocity_error,phot_variable_flag,teff_val,a_g_val E:\gaia\cdn.gea.esac.esa.int\Gaia\gdr2\gaia_source\csv\*.csv e:\gaia_batches
    
    create_directory(args.output_path)

    if args.num_rows:
        buffer = []
        for input_index, input_path in enumerate(tqdm(glob.glob(args.input_path))):
            metadata['input_files'].append(input_path)

            csv = pd.read_csv(input_path)

            csv = csv.fillna('')
            if args.fields:
                header = args.fields.split(',')
                csv = csv[header]
            else:
                header = csv.columns

            buffer.extend(csv.values.tolist())
            
            while len(buffer) >= args.num_rows:    
                output_path = write(oid, buffer[:args.num_rows])
                metadata['output_files'].append(output_meta(oid, output_path, args.num_rows))
                oid += 1

                buffer = buffer[args.num_rows:]

        if len(buffer) > 0:
            output_path = write(oid, buffer)
            metadata['output_files'].append(output_meta(oid, output_path, len(buffer)))
            oid += 1

        if header is not None:
            metadata['header'] = [{"name": name.lstrip('\"').rstrip('\"')} for name in header]
            
        write_metadata(metadata)

    elif args.num_batches:       
        # empty and create all mini-batches
        for oid in range(args.num_batches):
            write(oid, [])

        header = None
        # read an input block and split into n mini-batches
        for input_index, input_path in enumerate(tqdm(glob.glob(args.input_path))):
            metadata['input_files'].append(input_path)
            
            with open(input_path) as fin:
                count = 0
                lines = fin.readlines()
                if args.skip_header:
                    header = lines[0]
                    lines = lines[1:]

                buffers = [[] for x in range(args.num_batches)]

                for line in lines:
                    index = random.randint(0, args.num_batches - 1) 
                    buffers[index].append(line)
                    
            for oid in tqdm(range(args.num_batches)):
                append(oid, buffers[oid])

        if header is not None:
            metadata['header'] = [{"name": name.lstrip('\"').rstrip('\"')} for name in header.strip().split(',') if len(name) > 0]
        
        # shuffle all mini-batches and build metadata

        print('Shuffling')
        for oid in tqdm(range(args.num_batches)):
            output_path, num_rows = shuffle(oid)
            metadata['output_files'].append(output_meta(oid, output_path, num_rows))

        write_metadata(metadata)    

        
if __name__ == '__main__':
    if args.num_rows is None and args.num_batches is None:
        raise Exception('Either --num-rows or --num-batches must be given.')

    main()
