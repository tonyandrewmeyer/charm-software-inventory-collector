#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Functional tests for software-inventory-collector."""

import json
import logging
import time
import unittest
from typing import List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from zaza import model
from zaza.utilities.juju import get_application_ip

logger = logging.getLogger(__name__)


class SoftwareInventoryCollectorTests(unittest.TestCase):
    """Basic functional tests for software-inventory-collector charm."""

    NAME = "software-inventory-collector"

    def setUp(self) -> None:
        """Configure resource before tests."""
        self.session = requests.Session()
        self.session.mount(
            "http://", HTTPAdapter(max_retries=Retry(connect=3, backoff_factor=0.5))
        )
        self.endpoints = ["kernel", "dpkg", "snap"]

    def get_url(self) -> str:
        """Get the url to be tested."""
        port = model.get_application_config("software-inventory-exporter")["port"]["value"]
        ubuntu_ip = get_application_ip("ubuntu")
        return f"http://{ubuntu_ip}:{port}"

    def test_collector(self) -> None:
        """Test that the collector works as expected."""
        collector_unit = model.get_units("software-inventory-collector")[0].entity_id
        collector_config = model.get_application_config(self.NAME)
        collection_path = collector_config["collection_path"]["value"]
        extract_path = "/tmp/collector_result"
        # assert that there is no file on collection_path config
        files = self.get_files_from_path_on_unit(collector_unit, collection_path)
        logger.info("Checking that initially there aren't files extracted")
        assert len(files) == 0

        # run collect action
        logger.info("Running 'collect' action...")
        model.run_action(collector_unit, "collect")
        # wait some time to files be ready
        time.sleep(5)
        files = self.get_files_from_path_on_unit(collector_unit, collection_path)
        model_file = [file for file in files if "zaza" in file][0]
        logger.info("Checking that collector files were extracted")
        assert len(files) > 0
        # extract files
        model.run_on_unit(
            collector_unit,
            f"mkdir {extract_path} && tar -xf {collection_path}{model_file} -C {extract_path}",
        )

        uncompressed_files = self.get_files_from_path_on_unit(collector_unit, extract_path)
        assert len(uncompressed_files) > 0
        # check content of files
        url = self.get_url()

        for file in uncompressed_files:
            endpoint = file.split("_@_")[0]
            if endpoint in self.endpoints:
                logger.info(
                    "Checking if there is a file with the content of endpoint: %s", endpoint
                )
                response = self.session.get(f"{url}/{endpoint}")
                content = model.file_contents(collector_unit, f"{extract_path}/{file}")
                self.assertEqual(response.json(), json.loads(content))

    def get_files_from_path_on_unit(self, unit: str, path: str) -> List:
        """Return a list of filenames in the provided path."""
        response = model.run_on_unit(unit, f"ls {path}")["Stdout"].split("\n")
        return [file for file in response if file != ""]
