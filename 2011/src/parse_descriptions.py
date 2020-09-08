import re
import itertools
import json
import operator

blocs = []
bloc = []
with open("descriptions") as fp:
    for line in fp.readlines():
        line = line.strip()
        if not line:
            continue
        if line == "[Show/Hide files]":
            blocs.append(bloc)
            bloc = []
        else:
            bloc.append(line)

entries = {
    "Name": "name",
    "Authors": "authors",
    "Version": "version",
    "Solver command line": "args",
    "Is able to solve" : "tracks"
}
re_entries = re.compile("^(%s) (.*)$" % "|".join(entries))

def parse_bloc(bloc):
    d = {}
    for line in bloc:
        m = re_entries.match(line)
        if m:
            entry = m.group(1)
            value = m.group(2)
            d[entries[entry]] = value
    cmdline = d["args"]\
            .replace("HOME", ".")\
            .replace("BENCHNAME", "FILECNF")\
            .replace("TMPDIR", "/tmp")\
            .split()
    d["tracks"] = d["tracks"].lower().split()
    d["call"] = cmdline.pop(0)
    d["args"] = cmdline
    d["gz"] = False
    d["status"] = "unknown"

    return d

all_solvers = [parse_bloc(bloc) for bloc in blocs]

def make_id(name):
    return name.lower()\
            .replace(" ", "_")\
            .replace("+","-plus")

solvers = {}
solvers2 = {}
for name, entries in itertools.groupby(all_solvers,
        key=operator.itemgetter("name")):
    entries = list(entries)
    if len(entries) > 1:
        for entry in entries:
            version = entry["version"]
            myname = f"{name}-{version}"
            myid = make_id(myname)
            assert myid not in solvers, myid
            solvers[myid] = entry
            solvers2[myid] = {}
    else:
        myid = make_id(name)
        assert myid not in solvers, myid
        solvers[myid] = entries[0]
        solvers2[myid] = {}


print(json.dumps(solvers, indent=4))
#print(json.dumps(solvers2, indent=4))

