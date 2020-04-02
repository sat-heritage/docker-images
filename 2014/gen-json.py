# FIXME: this is an ongoing effort to generate the skeletons for the 2013 contest
# This is not finished yet.
from lxml import html
import requests
import json


def buildargs(command):
    replace = [("<instance>","FILECNF"), ("<seed>","RANDOMSEED"),("<tempdir>","/tmp")]
    toret = []
    args = command.split()[1:]
    for a in args:
        for r in replace:
            a = a.replace(r[0],r[1])
        toret.append(a)
    return toret

solvers = set()
solvernames = set()
dom = html.parse("http://satcompetition.org/edacc/sc14/experiments/").getroot()
links = [l for l in [(el.get("href"),el.text) for el in dom.cssselect('a')] if l[0].startswith('/edacc/sc14/experiment/')]
jsonoutput = {}
jsonsetup = {}

for (experiment,track) in links:
    print(track)
    if track == "Sequential, Application SAT+UNSAT track":
        print("I am skipping the track", track, "(in this version, see code)")
        continue #FIXME: for other tracks, we must check if this is a similar solver by
    # Downloading the tar file, getting the code.zip and checking if this is the same
    experimentlink = "http://satcompetition.org" + experiment
    dom =  html.parse(experimentlink).getroot()
    newsolvers = [l for l in [el.get('href') for el in dom.cssselect('a')] if
            l.startswith(experiment+'solver-configurations')]
    for solver in newsolvers:
        print(solver, "in track", track)
        dom = html.parse("http://satcompetition.org"+solver).getroot()
        solverconfigurations = [l for l in [el.get('href') for el in dom.cssselect('a')] if
                l.startswith(experiment+'solver-configurations/')]
        for sc in solverconfigurations:
            dom = html.parse("http://satcompetition.org"+sc).getroot()
            launchcommand = [l[16:] for l in [el.text for el in dom.cssselect('strong')] if l.startswith('Launch Command:')][0]

            name = None
            authors = None
            searchname = dom.cssselect('td')
            for i in range(len(searchname)):
                if searchname[i].text == "Name:":
                    name = searchname[i+1].text
                if searchname[i].text == "Authors:":
                    authors = searchname[i+1].text
                    break

            solverdetails = [l for l in [el.get('href') for el in dom.cssselect('a')] if l.startswith('/edacc/sc14/solver-download/')]
            if len(solverdetails)==0: # Disqualified solver
              print("Solver", name, "does not have a download folder")
              continue
            s = solverdetails[0]
            if name not in solvernames:
                solvernames.add(name)
                print("Solver", name, "found")
            solvers.add((name, s, launchcommand))
            normalizedname = name.lower().replace(" ","_")
            if normalizedname in jsonoutput:
                # We have the same solver used in different tracks
                # This must be fixed by hand
                i = 1
                while normalizedname+"_"+str(i) in jsonoutput:
                    i += 1
                normalizedname = normalizedname+"_"+str(i)
            
            jsonoutput[normalizedname] = {"call":launchcommand.split()[0], "name":name, "gz":True, "args":
                    buildargs(launchcommand), "comments":"Launchcommand was: " + launchcommand +"\nTrack was "+track, "authors": authors}
            jsonsetup[normalizedname] = {"download_url":"http://satcompetition.org"+solverdetails[0]}

with open("auto-setup-2.json","wt") as f:
  json.dump(jsonsetup, f, sort_keys=True, indent=4)
print("File auto-setup.json created")

with open("auto-solvers-2.json","wt") as f:
  json.dump(jsonoutput, f, sort_keys=True, indent=4)
print("File auto-solvers.json created")
print("Warning, there is probably multiple entries for the same solver (when used in different tracks). Check the parameters to see if there is any difference. This scripts only builds starter json files.")
