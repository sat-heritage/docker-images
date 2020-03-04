import json

jsonoutput = {}

solvers_2016_main = (
    "BeansAndEggs",
    "CHBR_glucose",
    "CHBR_glucose_tuned",
    "COMiniSatPSChandrasekharDRUP",
    "GHackCOMSPS_DRUP",
    "Glucose_nbSat",
    "Lingelingbbcmain",
    "MapleCMS",
    "MapleCOMSPS_CHB_DRUP",
    "MapleCOMSPS_DRUP",
    "MapleCOMSPS_LRB_DRUP",
    "MapleGlucose",
    "Riss6",
    "Scavel_SAT",
    "Splatz06vmain",
    "YalSAT03r",
    "abcdSAT_drup",
    "cmsat5_autotune2",
    "cmsat5_main2",
    "glucose",
    "glucosePLE",
    "glucose_hack_kiel_newScript",
    "glue_alt",
    "glueminisat-2.2.10-81-main",
    "gulch",
    "tb_glucose",
    "tc_glucose"
)

solvers_2017_main = (
    "COMiniSatPS_Pulsar_drup", "Candy", "CandyRSILi", "CandyRSILv", "CandySL21", "GHackCOMSPS_drup",
    "MapleCOMSPS_CHB_VSIDS_drup", "MapleCOMSPS_LRB_VSIDS_2_drup", "MapleCOMSPS_LRB_VSIDS_drup"
                                                                  "MapleLRB_LCM.", "MapleLRB_LCMoccRestart",
    "Maple_LCM", "Maple_LCM_Dist",
    "Riss7", "abcdsat_r17", "bs_glucose", "cadical-sc17-proof", "cadical-sc17-agile-proof",
    "glu_vc", "glucose-3.0+width", "glucose-4.1", "lingeling-bbe", "satUZK-seq", "tch_glucose1",
    "tch_glucose2", "tch_glucose3")

solvers_2018 = (
    "COMiniSatPS_Pulsar_drup", "CaDiCaL", "Candy", "GHackCOMSPS_drup", "Glucose_Hack_Kiel_fastBVE", "Lingeling",
    "MapleCOMSPS_CHB_VSIDS_drup",
    "MapleCOMSPS_LRB_VSIDS_2_drup", "MapleCOMSPS_LRB_VSIDS_drup", "MapleLCMDistChronoBT", "Maple_CM",
    "Maple_CM_Dist", "Maple_CM_ordUIP+", "Maple_CM_ordUIP", "Maple_LCM+BCrestart", "Maple_LCM+BCrestart_M1",
    "Maple_LCM_M1", "Maple_LCM_Scavel", "Maple_LCM_Scavel_200", "Minisat-v2.2.0-106-ge2dd095",
    "Riss7.1", "Sparrow2Riss-2018", "YalSAT", "abcdsat_r18", "cms55-main-all4fixed", "expGlucose",
    "expMC_LRB_VSIDS_Switch", "expMC_LRB_VSIDS_Switch_2500", "expMC_VSIDS_LRB_Switch_2500",
    "gluHack", "glu_mix", "glucose-3.0D-patched", "glucose-3.0_PADC_3", "glucose-3.0_PADC_10",
    "glucose3.0", "glucose4.2.1", "inIDGlucose", "smallsat", "varisat")

solvers_2019 = (
    "CCAnrSim", "COMiniSatPS_Pulsar_drup", "CaDiCaL", "Candy", "MLDChronoBT_GCBump", "MapleCOMSPS_CHB_VSIDS_drup",
    "MapleCOMSPS_LRB_VSIDS_2_drup", "MapleCOMSPS_LRB_VSIDS_drup", "MapleLCMChronoBT_DEL",
    "MapleLCMChronoBT_Scavel_EWMA",
    "MapleLCMChronoBT_ldcr", "MapleLCMDISTChronoBT_Scavel_EWMA_08ALL", "MapleLCMDiscChronoBT-DL-v3",
    "MapleLCMDistChronoBT-DL-v1", "MapleLCMDistChronoBT-DL-v2.1", "MapleLCMDistChronoBT-DL-v2.2",
    "MapleLCMDistChronoBTVariableReindexing", "MapleLCMdistCBTcoreFirst", "Maple_LCM_OnlineDel_19a",
    "Maple_CM_OnlineDel_19b", "Maple_LCM_BTL", "Maple_LCM_Scavel_155", "MergeSAT", "Minisat-v2.2.0-106-ge2dd095",
    "PADC_MapleLCMDistChronoBT", "PADC_Maple_LCM_Dist", "PSIDS_MapleLCMDistChronoBT", "Relaxed_LCMDistChronoBT",
    "Relaxed_LCMDistChronoBT_Scavel", "Relaxed_LCMDistChronoBT_p9", "Relaxed_LCM_Dist", "Riss7.1", "SLIME",
    "SparrowToMergeSAT", "Topk3.2_Glucose3.0", "Topk3_Glucose3.0", "Topk6.2_Glucose3.0", "Topk6_Glucose3.0",
    "ZIB_Glucose",
    "cmsatv56-walksat-chronobt", "cmsatv56-walksat", "cmsatv56-yalsat-chronobt", "cmsatv56-yalsat", "expMaple_CM",
    "expMaple_CM_GCBump", "expMaple_CM_GCBumpOnlyLRB", "glucose-4.2.1", "glucose3.0", "glucose_421_del", "glucose_BTL",
    "optsat", "smallsat")

for s in solvers_2016_main:
    print(s)
    normalizedname = s.lower().replace(" ", "_")
    jsonoutput[normalizedname] = {"name": s, "call": "./" + normalizedname, "gz": True, "args": ["FILECNF"],
                                  "argsproof": ["FILECNF", "FILEPROOF"]}

with open("auto-setup.json", "wt") as f:
    json.dump(jsonoutput, f)
