import tempfile
import subprocess
import sys, os
import gzip
from mOTUlizer.config import *
from Bio import SeqIO
from os.path import join as pjoin
import shutil

methods =  ['silixCOGs', 'mmseqsCluster']

def compute_COGs(faas, name, precluster = False, threads = 4, method =  "mmseqsCluster"):
    name = name + method + "_"

    temp_folder = tempfile.mkdtemp(prefix = name)
    all_faas_file = pjoin(temp_folder, "concat.faa")
    gene_clusters2rep = None
    prot_ids = set()
    prot2faa ={}
    for k,v in faas.items():
        if not v.endswith(".gz"):
            with open(v) as handle:
                ids = [l[:-1].split()[0][1:] for l in handle if l[0] == ">"]
        else :
            with gzip.open(v) as handle:
                ids = [l.decode()[:-1].split()[0][1:] for l in handle if l.decode()[0] == ">"]
        for i in ids:
            if i in prot2faa:
                prot2faa[i] += [k]
            else :
                prot2faa[i] = [k]

    print("concatenating all faas", file = sys.stdout)

    if all([faa.endswith(".gz") for faa in faas.values()]):
        cat = "zcat "
    elif all([not faa.endswith(".gz") for faa in faas.values()]) :
        cat = "cat "
    else :
        sys.exit("Please make my life easy, either all faas gziped or none gzipped ...")

    # Attempt to reduce command length
    # Extract the largest matching prefix
    common_prefix = os.path.dirname(os.path.commonprefix([*faas.values()]))
    # Ensure the common_prefix ends with a slash to make it a valid directory path
    if not common_prefix.endswith('/'):
        common_prefix += '/'
    # Create an environment variable containing the common prefix
    os.environ['BASE_PATH'] = common_prefix
    # Store the current working directory
    original_directory = os.getcwd()
    # Change the working directory to BASE_PATH
    os.chdir(common_prefix)
    # Create a list to hold the modified values for the command
    shortened_faas = [value.replace(common_prefix, '') for value in faas.values()]

    ##TODO: Does this create any overhead for the bash script?  Maybe change
    ##      So that you only do that if the command length is above the treshold of 250k
    
    # Build Cat command and bash script
    cmd = "find " + " ".join(shortened_faas) + " -type f -print0 | xargs -0 " + cat + " > " + all_faas_file
    print(f"length of cmd is: {len(cmd)}")
    cat_script = pjoin(temp_folder, "concat.sh")
    with open(cat_script, 'w') as file: file.write(cmd)
    print(f"Path to concat script: {cat_script}")
    print(f"Path to concat faa file: {all_faas_file}")
    
    #Execute and run bash script with cat
    cmd = "bash " + cat_script
    try:
        # Execute the command and capture output and error messages
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
    except subprocess.CalledProcessError as e:
        # Command execution failed
        print("Command execution failed with return code:", e.returncode)
        print("Error message:", e.output)
    else:
        # Command executed successfully
        print("Command executed successfully.")
    finally:
        # Change the working directory back to the original directory
        os.chdir(original_directory)

    if precluster:
        cdhit_file = tempfile.NamedTemporaryFile().name

        if not shutil.which('cd-hit'):
            print("You need cd-hit to run the preclustering, either install it or run mOTUpan without preclustering", file = sys.stderr)
            sys.exit(-1)

        exec = "cd-hit -i {input} -o {output} -c 0.95 -M 0 -T {threads} -d 0 -s 0.95 >> {log} 2>&1".format(input = all_faas_file, output = cdhit_file, threads = threads, log = "/dev/null")
        print("Running cd-hit preclustering", file = sys.stdout)
        os.system(exec)

        print("parsing cd-hit", file = sys.stdout)

        with open(cdhit_file + ".clstr") as handle:
            clusters = "\n".join(handle.readlines()).split("Cluster ")

        os.remove(cdhit_file + ".clstr")
        os.remove(cdhit_file)

        clusters = [c.split("\n\n") for c in clusters[1:] if "*" in c]
        clusters = [[cc.split(">")[1].split("... ") for cc in c if ">" in cc and cc != ">"] for c in clusters ]
        clusters = {[cc[0] for cc in c if cc[1] == "*" or cc[1] == "*\n"][0] : [cc[0] for cc in c] for c in clusters}

        print("For", len(prot2faa), "CDSes we got ", len(clusters), "preclusters", file = sys.stdout)
        seqs = [s for s in SeqIO.parse(all_faas_file, "fasta") if s.id in clusters]
        SeqIO.write(seqs, all_faas_file, "fasta")

    if method == "silixCOGs" :
        if not shutil.which("diamond") or not shutil.which("silix"):
            print("You need diamond and silix to run the silix gene-clustering, either install it or run mOTUpan with an other gene-clustering or your own traits", file = sys.stderr)
            sys.exit(-1)

        print("all v all diamond for silix", file = sys.stdout)

        os.system("diamond makedb --db {faas} --in {faas} > /dev/null 2> /dev/null".format(faas = all_faas_file))
        os.system("diamond blastp --more-sensitive -p {threads} -f 6 -q {faas} --db {faas} -o {out} 2> /dev/null > /dev/null".format(faas = all_faas_file, out = temp_out, threads = threads))

        print("running silix", file = sys.stdout)
        os.system("silix {faas} {out} > {clust_temp} #2> /dev/null".format(faas = all_faas_file, out = temp_out, clust_temp = temp_clust))

        print("parsing silix", file = sys.stdout)
        with open(temp_clust) as handle:
            if precluster:
                recs = {g : l[:-1].split()[0]  for l in handle for g in clusters[l[:-1].split()[1]]}
            else :
                recs = {l[:-1].split()[1] : l[:-1].split()[0]  for l in handle}


        #pretty formating names
        fill = max([len(v) for v in recs.values()])
        recs = {k : name + "_" + v.zfill(fill) for k, v in recs.items()}

        genome2gene_clusters = {k : set() for k in faas.keys()}
        for k,v in recs.items():
            for vv in prot2faa[k]:
                genome2gene_clusters[vv].update([v])

    elif method == "mmseqsCluster" :
        "coverage = 80% with cov-mode = 0, minimal amino acid sequence identity = 0% and cluster-mode = 0"
        covmode = 0
        cov = 0.80
        seqid = 0.0
        if not shutil.which("mmseqs"):
            print("You need mmseqs2 to run the silix gene-clustering, either install it or run mOTUpan with an other gene-clustering or your own traits", file = sys.stderr)
            sys.exit(-1)

        mmseqs_dat = pjoin(temp_folder, "mmseqs_")
        print("Running mmseqs:\nmmseqs easy-cluster --threads {threads} --min-seq-id {seqid} --cov-mode {covmode} -c {cov} {faas} {out} {tmp} 2> /dev/null > /dev/null".format(covmode = covmode, cov = cov, seqid=seqid, faas = all_faas_file, out = mmseqs_dat, tmp = temp_folder, threads = threads), file = sys.stdout)
        os.system("mmseqs easy-cluster --threads {threads} --min-seq-id {seqid} --cov-mode {covmode} -c {cov} {faas} {out} {tmp} 2> /dev/null > /dev/null".format(covmode = covmode, cov = cov, seqid=seqid, faas = all_faas_file, out = mmseqs_dat, tmp = temp_folder, threads = threads))

        with open(mmseqs_dat + "_cluster.tsv") as handle:
            if precluster:
                recs = {g : l[:-1].split()[0]  for l in handle for g in clusters[l[:-1].split()[1]]}
            else :
                recs = {l[:-1].split()[1] : l[:-1].split()[0]  for l in handle}

        #pretty formating names
        fill = len(str(len(set(recs.values()))))

        rep2clust = {k : name + str(i).zfill(fill) for i,k in enumerate(set(recs.values()))}
        gene_clusters2rep = {v: k for k,v in rep2clust.items()}

        print("For", len(recs), "CDSes we got ", len(gene_clusters2rep), " gene-clusters", file = sys.stdout)

        recs = {k : rep2clust[v] for k, v in recs.items()}
        genome2gene_clusters = {k : set() for k in faas.keys()}
        for k,v in recs.items():
            for vv in prot2faa[k]:
                genome2gene_clusters[vv].update([v])

    else :
        print("The '{}' clustering method is not implemented yet".format(name) , file = sys.stderr)
        print("only allowed are :", methods, file = sys.stderr)
        sys.exit(-1)


    shutil.rmtree(temp_folder)

    for k,v in genome2gene_clusters.items():
        genome2gene_clusters[k] = set(v)



    return { 'genome2gene_clusterss' : genome2gene_clusters, 'aa2gene_clusters' : recs, 'gene_clusters2rep' : gene_clusters2rep}
