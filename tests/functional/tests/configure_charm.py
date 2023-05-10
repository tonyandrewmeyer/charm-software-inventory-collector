#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.
"""Pre-test configuration of a export/collector testing model."""

import logging
import os
from base64 import b64encode

import yaml
from zaza import model

logger = logging.getLogger(__name__)

JUJU_CRED_DIR = ".local/share/juju/"


def wait_for_model_settle() -> None:
    """Wait for specific unit states that indicate settled model."""
    expected_app_states = {
        "ubuntu": {
            "workload-status-message-prefix": "",
        },
        "software-inventory-exporter": {
            "workload-status-message-prefix": "Unit is ready.",
        },
        "software-inventory-collector": {
            "workload-status-message-prefix": "Unit ready.",
        },
    }
    model.wait_for_application_states(states=expected_app_states)


def get_juju_data():
    """Get juju account data and credentials."""
    juju_controller_file = os.path.join(os.path.expanduser("~"), JUJU_CRED_DIR, "controllers.yaml")
    juju_account_file = os.path.join(os.path.expanduser("~"), JUJU_CRED_DIR, "accounts.yaml")
    assert os.path.isfile(juju_controller_file)
    assert os.path.isfile(juju_account_file)

    with open(juju_controller_file) as controller_file:
        try:
            controller_data = yaml.safe_load(controller_file)
            current_controller = controller_data["current-controller"]
            cacert = controller_data["controllers"][current_controller]["ca-cert"]
            endpoint = controller_data["controllers"][current_controller]["api-endpoints"][0]
            assert current_controller is not None
            assert cacert is not None
            assert endpoint is not None
        except yaml.YAMLError as err:
            logging.error(err)

    with open(juju_account_file) as account_file:
        try:
            account_data = yaml.safe_load(account_file)
            user = account_data["controllers"][current_controller]["user"]
            password = account_data["controllers"][current_controller]["password"]
        except yaml.YAMLError as err:
            logging.error(err)

    return user, password, cacert, endpoint


def setup_juju_credentials() -> None:
    """Configure software-inventory-collector with required juju credentials."""
    # Get juju controller credentials
    user, password, cacert, endpoint = get_juju_data()

    # configure software-inventory-collector
    model.set_application_config(
        "software-inventory-collector",
        {
            "customer": "my_customer",
            "site": "my_site",
            "juju_endpoint": endpoint,
            "juju_ca_cert": b64encode(cacert.encode()).decode(encoding="ascii"),
            "juju_username": user,
            "juju_password": password,
        },
    )

    wait_for_model_settle()
