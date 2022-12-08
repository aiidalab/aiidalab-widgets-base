from urllib.parse import urljoin

import requests
from selenium.webdriver.common.by import By


def test_notebook_service_available(notebook_service):
    url, token, _ = notebook_service
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


def test_computational_resources(notebook_service, selenium):
    """Test the quicksetup of the code"""
    url, token, docker_compose = notebook_service

    # check the code pw-7.0 is not in code list
    install_command = "verdi code list"
    command = f"exec --workdir /home/jovyan/apps/aiidalab-widgets-base --user jovyan -T aiidalab {install_command}"
    output = docker_compose.execute(command).decode().strip()
    assert "pw-7.0" not in output

    url_with_token = urljoin(
        url,
        f"apps/apps/aiidalab-widgets-base/notebooks/computational_resources.ipynb?token={token}",
    )
    selenium.get(f"{url_with_token}")
    selenium.implicitly_wait(10.0)  # must wait until the app loaded
    driver = selenium

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
    selenium.implicitly_wait(1.0)

    # check the code pw-7.0 is not in code list
    install_command = "verdi code list"
    command = f"exec --workdir /home/jovyan/apps/aiidalab-widgets-base --user jovyan -T aiidalab {install_command}"
    output = docker_compose.execute(command).decode().strip()
    assert "pw-7.0@daint-mc" in output
