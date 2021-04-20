#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2020-2021 Barcelona Supercomputing Center (BSC), Spain
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import zipfile

from collections import defaultdict
from rocrate import rocrate_api
from ruamel import yaml
from utils import logger


class Workflow:
    """
    Workflow class
    """
    DEFAULT_KEYS = ['cwl_metadata']  # TODO

    def __init__(self, abs_path):
        """
        Init function

        :param abs_path: Absolute path
        :type abs_path: str
        """
        self.abs_path = abs_path
        self.type = "cwl"
        self.execution_provenance = "execution_create.zip"

    def createYAMLFile(self, input_files, arguments, filename):
        """
        Method to create YAML file that describes the execution inputs of the workflow
        needed for their execution.

        :param input_files: Dictionary of input files locations.
        :type input_files: dict
        :param arguments: Dictionary of input arguments.
        :type arguments: dict
        :param filename: YAML filename
        :type filename: str
        """
        try:
            wf_exec_inputs = defaultdict(list)

            for k_in, v_in in input_files.items():
                file_type = "File"
                file_keys = ["class", "location"]

                if not os.path.isabs(v_in):  # if input file path is not an absolute path
                    v_in = os.path.join(self.abs_path, v_in)

                if isinstance(v_in, str):
                    wf_exec_inputs.update({k_in: {file_keys[0]: file_type, file_keys[1]: v_in}})

                elif isinstance(v_in, list):
                    for file_path in v_in:
                        wf_exec_inputs[k_in].append({file_keys[0]: file_type, file_keys[1]: file_path})

            for k_arg, v_arg in arguments.items():
                if k_arg != "cwl_wf_url":
                    # if isinstance(v_arg, list): TODO
                    #     new_value = [item.replace("\t", "\\t") for item in v_arg]
                    #     # mapping special char inside argument list
                    #
                    wf_exec_inputs[k_arg] = v_arg

            if len(wf_exec_inputs) != 0:
                with open(filename, 'w+', encoding="utf-8") as yaml_file:
                    yaml.dump(dict(wf_exec_inputs), yaml_file, allow_unicode=True, default_flow_style=False)
            else:
                errstr = "Dictionary of execution inputs is empty"
                logger.error(errstr)
                raise Exception(errstr)

        except IOError as error:
            errstr = "Cannot create YAML file {}, {}. See logs.".format(filename, error)
            logger.error(errstr)
            raise Exception(errstr)

    def createOutputsFiles(self, output_files, output_metadata, outputs_execution, execution_path):
        """
        Create and validate output files generated for workflow execution

        :param output_files: Dictionary of the output files locations.
        :type output_files: dict
        :param output_metadata: # TODO
        :type output_metadata: list
        :param outputs_execution: TODO
        :type outputs_execution: dict
        :param execution_path: Working directory
        :type execution_path: str
        """
        try:
            for metadata in output_metadata:
                out_id = metadata["name"]
                out_keys = ["class", "path"]
                outputs = list()  # list of tuples (path, type of output)
                if out_id in outputs_execution.keys():
                    if not metadata["allow_multiple"]:  # allow multiple false
                        file_path = outputs_execution[next(iter(outputs_execution))][0][out_keys[1]]
                        file_type = outputs_execution[next(iter(outputs_execution))][0][out_keys[0]].lower()
                        outputs.append((file_path, file_type))

                    else:  # allow multiple true
                        for key_exec in outputs_execution[out_id]:
                            file_path = key_exec[out_keys[1]]
                            file_type = key_exec[out_keys[0]].lower()
                            outputs.append((file_path, file_type))

                else:  # execution provenance data
                    if out_id in self.DEFAULT_KEYS:
                        file_path = execution_path + "/" + self.execution_provenance
                        outputs.append((file_path, "file"))

                output_files[out_id] = outputs

        except:
            errstr = "CWL output files not created. See logs."
            logger.fatal(errstr)
            raise Exception(errstr)

    @staticmethod
    def compress_provenance(filename, provenance_path):
        """
        Create ZIP file of provenance data folder

        :param filename: filename
        :type filename: str
        :param provenance_path: path that contains provenance data
        :type provenance_path: str
        """
        try:
            with zipfile.ZipFile(filename, "w", zipfile.ZIP_DEFLATED) as zpf:
                abs_src = os.path.abspath(provenance_path)  # absolute path from provenance path
                for folder_name, sub_folders, files in os.walk(provenance_path):
                    # rule = re.search(r"\b(data/)\b", folder_name)
                    # if rule is None:  # if not contains data folder
                    for file in files:
                        abs_name = os.path.abspath(os.path.join(folder_name, file))
                        arc_name = abs_name[len(abs_src) + 1:]
                        zpf.write(abs_name, arc_name)
            zpf.close()

            if not os.path.isfile(filename):  # if zip file is not created the execution stops
                sys.exit("{} not created; See logs".format(filename))

            logger.debug("Provenance data {} created".format(filename))

        except Exception as error:
            errstr = "Unable to create provenance data {}. ERROR: {}".format(filename, error)
            logger.fatal(errstr)
            raise Exception(errstr)

    def create_rocrate(self, cwl_wf_url, input_files, rocrate_path):
        """"
        Create workflow RO-crate

        :param cwl_wf_url: URL for the location of the workflow
        :param input_files: List containing tool input files
        :param rocrate_path: path that will contain the RO-Crate
        :type cwl_wf_url: str
        :type input_files: dict
        :type rocrate_path: str
        """
        try:

            include_files = list()

            # Create list of input files location
            for in_rec in input_files.keys():
                input_file = input_files[in_rec]
                if isinstance(input_file, dict):  # input is a File
                    include_files.append(str(input_file['location']))  # add to include_files

            logger.debug("Include files:\n{}".format(include_files))

            # Create RO-Crate
            ro_crate = rocrate_api.make_workflow_rocrate(workflow_path=cwl_wf_url, wf_type=self.wf_type,
                                                         include_files=include_files)
            # Write RO-Crate JSON-LD format
            ro_crate.write_crate_entities(rocrate_path)

        except Exception as error:
            errstr = "Unable to create RO-Crate. ERROR: {}".format(error)
            logger.fatal(errstr)
            raise Exception(errstr)