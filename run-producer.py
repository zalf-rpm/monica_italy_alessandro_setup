#!/usr/bin/python
# -*- coding: UTF-8

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/. */

# Authors:
# Michael Berg-Mohnicke <michael.berg@zalf.de>
#
# Maintainers:
# Currently maintained by the authors.
#
# This file has been created at the Institute of
# Landscape Systems Analysis at the ZALF.
# Copyright (C: Leibniz Centre for Agricultural Landscape Research (ZALF)

import csv
import json
import os
import sys
import zmq

import monica_io3
import shared


def run_producer(server=None, port=None):

    context = zmq.Context()
    socket = context.socket(zmq.PUSH)  # pylint: disable=no-member

    config = {
        "server-port": port if port else "6666",
        "server": server if server else "localhost",
        "sim.json": os.path.join(os.path.dirname(__file__), "sim.json"),
        "crop.json": os.path.join(os.path.dirname(__file__), "crop.json"),
        "site.json": os.path.join(os.path.dirname(__file__), "site.json"),
        "monica_path_to_climate_dir": "/home/berg/GitHub/monica_italy_alessandro_setup/data",
        "path_to_data_dir": "./data/",
    }
    shared.update_config(config, sys.argv, print_config=True, allow_new_keys=False)

    socket.connect("tcp://" + config["server"] + ":" + config["server-port"])

    with open(config["sim.json"]) as _:
        sim_json = json.load(_)

    with open(config["site.json"]) as _:
        site_json = json.load(_)

    with open(config["crop.json"]) as _:
        crop_json = json.load(_)

    env_template = monica_io3.create_env_json_from_json_config({
        "crop": crop_json,
        "site": site_json,
        "sim": sim_json,
        "climate": ""  # climate_csv
    })

    data = {}
    csv_path = f"{config['path_to_data_dir']}/soil.csv"
    print(f"{os.path.basename(__file__)} CSV path:", csv_path)
    with open(csv_path) as file:
        dialect = csv.Sniffer().sniff(file.read(), delimiters=';,\t')
        file.seek(0)
        reader = csv.reader(file, dialect)
        next(reader)
        header = next(reader)
        for line in reader:
            row = {}
            id = None
            for i, value in enumerate(line):
                if value.strip() in ["", "#N/A"]:
                    row = None
                    break
                if header[i] == "POINTID":
                    id = int(value)
                else:
                    key = f"{header[i]}{'_0-30cm' if 4 <= i <= 9 else ('_30-200cm' if 10 <= i <= 15 else '')}"
                    row[key] = value
            #print(id, end=" ")
            if row:
                if float(row["BD_0-30cm"]) == 0 or float(row["Sand_0-30cm"]) == 0.0:
                    continue
                if id not in [1064, 16923, 25580]:
                    continue
                data[id] = row
        print()

    no_of_sites = 0
    for id, site in data.items():
        climate_id = int(id)

        env_template["csvViaHeaderOptions"] = sim_json["climate.csv-options"]
        env_template["pathToClimateCSV"] = \
            f"{config['monica_path_to_climate_dir']}/climate/IT_{climate_id}.csv"

        # build soil profile
        soil_profile = [
            {
                "Thickness": [0.3, "m"],
                "SoilOrganicCarbon": [float(site[f"Organic_ca_0-30cm"]), "%"],
                "SoilBulkDensity": [float(site[f"BD_0-30cm"]), "kg m-3"],
                "Sand": [float(site[f"Sand_0-30cm"]), "fraction"],
                "Clay": [float(site[f"Clay_0-30cm"]), "fraction"],
                "pH": [float(site[f"pH_0-30cm"]), ""],
            },
            {
                "Thickness": [1.7, "m"],
                "SoilOrganicCarbon": [float(site[f"Organic_ca_30-200cm"]), "%"],
                "SoilBulkDensity": [float(site[f"BD_30-200cm"]), "kg m-3"],
                "Sand": [float(site[f"Sand_30-200cm"]), "fraction"],
                "Clay": [float(site[f"Clay_30-200cm"]), "fraction"],
                "pH": [float(site[f"pH_30-200cm"]), ""],
            }
        ]

        # build environment
        if len(soil_profile) == 0:
            continue
        env_template["params"]["siteParameters"]["SoilProfileParameters"] = soil_profile

        env_template["params"]["siteParameters"]["Latitude"] = float(site["POINT_Y"])
        env_template["params"]["siteParameters"]["Slope"] = float(site["Slope"])

        env_template["customId"] = {
            "id": id,
            "nodata": False,
        }
        socket.send_json(env_template)
        no_of_sites += 1
        print(f"{os.path.basename(__file__)} sent job {id}")

    # send done message
    env_template["customId"] = {
        "no_of_sites": no_of_sites,
        "nodata": True,
    }
    socket.send_json(env_template)
    print(f"{os.path.basename(__file__)} done")


if __name__ == "__main__":
    run_producer()