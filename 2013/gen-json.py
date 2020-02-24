#from HTMLParser import HTMLParser
from lxml import html
import requests
import json

solvers = set()
solvernames = set()
dom = html.parse("http://satcompetition.org/edacc/SATCompetition2013/experiments/").getroot()
links = [l for l in [el.get("href") for el in dom.cssselect('a')] if l.startswith('/edacc/SATCompetition2013/experiment/')]
jsonoutput = {}
jsonsetup = {}

for experiment in links:
    experimentlink = "http://satcompetition.org" + experiment
    dom =  html.parse(experimentlink).getroot()
    newsolvers = [l for l in [el.get('href') for el in dom.cssselect('a')] if
            l.startswith(experiment+'solver-configurations')]
    for solver in newsolvers:
        print(solver)
        dom = html.parse("http://satcompetition.org"+solver).getroot()
        solverconfigurations = [l for l in [el.get('href') for el in dom.cssselect('a')] if
                l.startswith(experiment+'solver-configurations/')]
        for sc in solverconfigurations:
            dom = html.parse("http://satcompetition.org"+sc).getroot()
            launchcommand = [l[16:] for l in [el.text for el in dom.cssselect('strong')] if l.startswith('Launch Command:')][0]

            name = None
            searchname = dom.cssselect('td')
            for i in range(len(searchname)):
                if searchname[i].text == "Name:":
                    name = searchname[i+1].text
                    break

            solverdetails = [l for l in [el.get('href') for el in dom.cssselect('a')] if l.startswith('/edacc/SATCompetition2013/solver-download/')]
            assert len(solverdetails)==1
            s = solverdetails[0]
            if name not in solvernames:
                solvernames.add(name)
                print("Solver", name, "found")
            solvers.add((name, s, launchcommand))
            normalizedname = name.lower().replace(" ","_")
            jsonoutput[normalizedname] = {"call":launchcommand.split()[0], "name":name, "gz":True, "args":
                    ["FILECNF"]}
            jsonsetup[normalizedname] = {"download_url":"http://satcompetition.org"+solverdetails[0]}

with open("auto-setup.json","wt") as f:
  
  json.dump(jsonsetup, f)
print("File auto-setup.json created")
