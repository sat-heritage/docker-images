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
            if bloc:
                bloc = []
        else:
            if not bloc:
                blocs.append(bloc)
            bloc.append(line)

entries = {
    "Name": "name",
    "Authors": "authors",
    "Version": "version",
    "Solver command line": "args",
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
    cmdline = d["args"].replace("HOME", ".").replace("BENCHNAME", "FILECNF").split()
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
    else:
        myid = make_id(name)
        assert myid not in solvers, myid
        solvers[myid] = entries[0]

print(json.dumps(solvers, indent=4))
