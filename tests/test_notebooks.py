import time

import requests
from selenium.webdriver.common.by import By


def test_notebook_service_available(notebook_service):
    url, token = notebook_service
    response = requests.get(f"{url}/?token={token}")
    assert response.status_code == 200


def test_process_list(selenium_driver):
    driver = selenium_driver("notebooks/process_list.ipynb")
    driver.find_element(By.XPATH, '//button[text()="Update now"]')


def test_aiida_datatypes_viewers(selenium_driver):
    driver = selenium_driver("notebooks/aiida_datatypes_viewers.ipynb")
    driver.find_element(By.CLASS_NAME, "widget-label")


def test_eln_configure(selenium_driver):
    driver = selenium_driver("notebooks/eln_configure.ipynb")
    driver.find_element(By.XPATH, '//button[text()="Set as default"]')


def test_process(selenium_driver):
    driver = selenium_driver("notebooks/process.ipynb")
    driver.find_element(By.XPATH, '//label[@title="Select calculation:"]')


def test_wizard_apps(selenium_driver):
    driver = selenium_driver("notebooks/wizard_apps.ipynb")
    driver.find_element(By.XPATH, '//label[@title="Delivery progress:"]')


def test_structures(selenium_driver):
    driver = selenium_driver("notebooks/structures.ipynb")
    driver.find_element(By.XPATH, '//button[text()="Upload Structure (0)"]')


def test_eln_import(selenium_driver):
    driver = selenium_driver("notebooks/eln_import.ipynb")
    driver.find_element(By.ID, "tooltip")


def test_computational_resources_code_setup(selenium_driver, aiidalab_exec):
    """Test the quicksetup of the code"""
    # check the code pw-7.0 is not in code list
    output = aiidalab_exec("verdi code list").decode().strip()
    assert "pw-7.0" not in output

    driver = selenium_driver("notebooks/computational_resources.ipynb")

    # click the "Setup new code" button
    driver.find_element(By.XPATH, '//button[text()="Setup new code"]').click()

    # Select daint.cscs.ch domain
    driver.find_element(By.XPATH, '//option[text()="daint.cscs.ch"]').click()

    # Select computer multicore
    driver.find_element(By.XPATH, '//option[text()="multicore"]').click()

    # select code pw-7.0-multicore
    driver.find_element(By.XPATH, '//option[text()="pw-7.0-multicore"]').click()

    # fill the SSH username
    driver.find_element(
        By.XPATH, "//label[text()='SSH username:']/following-sibling::input"
    ).send_keys("dummyuser")

    # click the quick setup
    driver.find_element(By.XPATH, '//button[text()="Quick Setup"]').click()
    time.sleep(1.0)

    # check the new code pw-7.0@daint-mc is in code list
    output = aiidalab_exec("verdi code list").decode().strip()
    assert "pw-7.0@daint-mc" in output
