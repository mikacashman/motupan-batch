#!/usr/bin/env python

import os
import shutil
import sys
from os.path import join as pjoin
import argparse
import json
from random import uniform


#print("This is temporary, fix the hard-path once all is clean", file=sys.stderr)
sys.path.append("/home/moritz/repos/moritz/0039_mOTUlizer/")

from mOTUlizer.classes import *
from mOTUlizer.utils import *

from mOTUlizer.classes.mOTU import mOTU

#from mOTUlizer.config import *

description_text = """
From a buch of amino-acid sequences or COG-sets, computes concensus AA/COG sets.

Returns all to stdout by default.
"""

def main(args):
    if args.cog_file:
        try :
            if args.cog_file.endswith(".json"):
                with open(args.cog_file) as handle:
                    cog_dict = json.load(handle)
            else :
                with open(args.cog_file) as handle:
                    cog_dict = {l.split("\t")[0] : l[:-1].split("\t")[1:] for l in handle}
            cog_dict = {k : set(v) for k,v in cog_dict.items()}
        except :
            print("Either the cog_file does not exists or it is not formated well")

        if all([len(v) == 0 for v in cog_dict]):
            print("None of your bins have any cogs in them, that's weird, you probably have wrong delimiter in you file, use tab.\nIf you do not have COGs you can also just run it without the --cog_file option and mOTUlizer will automatically compute some! (slower)")
    else :
        cog_dict = {}

    #parse and check your amino-acid files
    faas = {os.path.splitext(os.path.basename(f))[0] : f for f in args.faas} if args.faas else {}
    assert all([os.path.exists(f) for f in faas.values()]), "one or some of your faas don't exists"


    genomes = set(faas.keys()).union(set(cog_dict.keys()))

    if cog_dict and len(faas) > 0:
        if len(genomes) != len(faas) or len(faas) != len(cog_dict):
            print("your faas and cog_drct are not the same length,\nit might not matter just wanted to let you know.", file = sys.stderr)

    out_json = args.output
    checkm = {}
    if args.checkm :
        with open(args.checkm) as handle:
            #this is a bad fix, fix it for checkm output and json
            col_idx = [i for i, ll in enumerate(handle.readline().split(",")) if "complet" in ll][0]
            for l in handle:
                if l.split(",")[0] in genomes:
                    checkm[l.split(",")[0]] = float(l.split(",")[col_idx])
    if args.seed :
        for f in genomes:
            checkm[f] = args.seed
    if args.random_seed :
        for f in genomes:
            checkm[f] = uniform(50,80)
    if args.length_seed :
        checkm = "length_seed"


    name = args.name if args.name else random_name()

    if faas is None and cogs is None:
        sys.exit("at least one of --faas and --cog_file is required")

    motu = mOTU( name , faas , cog_dict, checkm_dict = checkm)

    if args.output:
        out_handle = open(out_file, "w")
    else :
        out_file = sys.stdout
    if not args.genome2cog_only:
        json.dump(motu.get_stats(), out_file)
    else :
        json.dump({k : list(v) for k,v in motu.cog_dict.items()}, out_file)
    if args.output:
        out_handle.close()

    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog = "mOTUlizer", description=description_text, epilog = "Let's do this")
    parser.add_argument('--output', '-o', nargs = '?', help = "send output to this file")
    parser.add_argument('--force', '-f', action='store_true', help = "force execution answering default answers")
    parser.add_argument('--checkm', '-k',nargs = '?', help = "checkm file if you want to see completnesses with it")
    parser.add_argument('--seed', '-s', type = float , nargs = '?', help = "seed completeness, advice a number around 90 (95 default)")
    parser.add_argument('--length_seed', '--ls', action='store_true', help = "seed completeness by length fraction")
    parser.add_argument('--random_seed', '--rs', action='store_true', help = "random seed completeness between 5 and 95%")
    parser.add_argument('--genome2cog_only', action='store_true', help = "returns genome2cog only")
    parser.add_argument('--faas','-F', nargs = '*', help = "list of amino-acids faas of MAGs or whatnot")
    parser.add_argument('--cog_file', '--cogs', '-c', nargs = '?', help = "file with COG-sets (see doc)")
    parser.add_argument('--name', '-n', nargs = '?', help = "if you want to name this bag of bins")

    args = parser.parse_args()

#    print(args, file=sys.stderr)

    main(args)


#for tt in `sed 's/\t/:/' scratch/test_data/mOTUs.txt` ;
#do
#    echo $tt | cut -f1 -d":"
#    fs=`echo $tt | cut -f2 -d":"| sed 's#;#.faa scratch/test_data/proteoms/#g'`;
#    mOTUlizer/bin/__main__.py -n `echo $tt | cut -f1 -d":"` --faas scratch/test_data/proteoms/${fs}.faa >> test;
#done
