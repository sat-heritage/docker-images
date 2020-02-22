#!/bin/bash

for s in 2clseq berkmin blindsat dlmsat1 dlmsat2 dlmsat3 ga limmat lsat marchI "marchI-hc" marchII "marchII-hc" marchIIse "marchIIse-hc" marchIse modoc oksolver partsat rb2cl sato saturn simo unitwalk usat05 usat10 zchaff; do
echo "\"$s\":{"
echo "   \"name\": \"$s\","
echo "   \"call\": \"./$s\","
echo "   \"gz\": false,"
echo "   \"args\": ["
echo "     \"FILECNF\""
echo "    ]"
echo "},"  
done
exit
    "2clseq": {
        "name": "2clseq",
        "call": "./2clseq",
        "gz": false,
        "args": [
          "FILECNF"
        ]
    }  
