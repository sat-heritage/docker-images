import json

jsonoutput = {}


solvers = (
"CCAnrSim", "COMiniSatPS_Pulsar_drup", "CaDiCaL", "Candy", "MLDChronoBT_GCBump", "MapleCOMSPS_CHB_VSIDS_drup",
"MapleCOMSPS_LRB_VSIDS_2_drup", "MapleCOMSPS_LRB_VSIDS_drup", "MapleLCMChronoBT_DEL", "MapleLCMChronoBT_Scavel_EWMA",
"MapleLCMChronoBT_ldcr", "MapleLCMDISTChronoBT_Scavel_EWMA_08ALL", "MapleLCMDiscChronoBT-DL-v3",
"MapleLCMDistChronoBT-DL-v1", "MapleLCMDistChronoBT-DL-v2.1", "MapleLCMDistChronoBT-DL-v2.2",
"MapleLCMDistChronoBTVariableReindexing", "MapleLCMdistCBTcoreFirst", "Maple_LCM_OnlineDel_19a",
"Maple_CM_OnlineDel_19b", "Maple_LCM_BTL", "Maple_LCM_Scavel_155", "MergeSAT", "Minisat-v2.2.0-106-ge2dd095",
"PADC_MapleLCMDistChronoBT", "PADC_Maple_LCM_Dist", "PSIDS_MapleLCMDistChronoBT", "Relaxed_LCMDistChronoBT",
"Relaxed_LCMDistChronoBT_Scavel", "Relaxed_LCMDistChronoBT_p9", "Relaxed_LCM_Dist", "Riss7.1", "SLIME",
"SparrowToMergeSAT", "Topk3.2_Glucose3.0", "Topk3_Glucose3.0", "Topk6.2_Glucose3.0", "Topk6_Glucose3.0", "ZIB_Glucose",
"cmsatv56-walksat-chronobt", "cmsatv56-walksat", "cmsatv56-yalsat-chronobt", "cmsatv56-yalsat", "expMaple_CM",
"expMaple_CM_GCBump", "expMaple_CM_GCBumpOnlyLRB", "glucose-4.2.1", "glucose3.0", "glucose_421_del", "glucose_BTL",
"optsat", "smallsat")

for s in solvers :
    print(s)
    normalizedname = s.lower().replace(" ", "_")
    jsonoutput[normalizedname] = { "name": s, "call": "./"+normalizedname, "gz": True, "args": ["FILECNF"],"argsproof": ["FILECNF", "FILEPROOF"]}

with open("auto-setup.json","wt") as f:
    json.dump(jsonoutput, f)