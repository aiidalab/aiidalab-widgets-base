import time

import requests
from selenium.webdriver.common.by import By


def test_notebook_service_available(notebook_service):
    url, token = notebook_service
    response = requests.get(f"{url}/?token={token}")
    assert response.status_code == 200


def test_process_list(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/process_list.ipynb")
    driver.find_element(By.XPATH, '//button[text()="Update now"]')
    driver.get_screenshot_as_file(f"{screenshot_dir}/process-list.png")


def test_aiida_datatypes_viewers(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/aiida_datatypes_viewers.ipynb")
    driver.set_window_size(1000, 2000)
    driver.find_element(By.CLASS_NAME, "widget-label")
    driver.find_element(By.XPATH, '//button[text()="Clear selection"]')
    time.sleep(5)
    driver.get_screenshot_as_file(f"{screenshot_dir}/datatypes-viewer.png")


def test_eln_configure(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/eln_configure.ipynb")
    driver.find_element(By.XPATH, '//button[text()="Set as default"]')
    driver.get_screenshot_as_file(f"{screenshot_dir}/eln-configure.png")


def test_process(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/process.ipynb")
    driver.find_element(By.XPATH, '//label[@title="Select calculation:"]')
    driver.get_screenshot_as_file(f"{screenshot_dir}/process.png")


def test_wizard_apps(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/wizard_apps.ipynb")
    driver.find_element(By.XPATH, '//label[@title="Delivery progress:"]')
    driver.get_screenshot_as_file(f"{screenshot_dir}/wizzard-apps.png")


def test_structures(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/structures.ipynb")
    driver.set_window_size(1000, 900)
    driver.find_element(By.XPATH, '//button[text()="Upload Structure (0)"]')
    time.sleep(5)
    driver.get_screenshot_as_file(f"{screenshot_dir}/structures.png")


def test_structures_generate_from_smiles(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/structures.ipynb")
    driver.set_window_size(1000, 900)
    # Switch to SMILES tab in StructureManagerWidget
    driver.find_element(By.XPATH, "//*[text()='SMILES']").click()

    # Generate methane molecule from SMILES
    smiles_textarea = driver.find_element(By.XPATH, "//input[@placeholder='C=C']")
    smiles_textarea.send_keys("C")
    generate_mol_button = driver.find_element(
        By.XPATH, "//button[contains(.,'Generate molecule')]"
    )
    generate_mol_button.click()
    time.sleep(5)

    # Select the first atom
    driver.find_element(By.XPATH, "//*[text()='Selection']").click()
    driver.find_element(
        By.XPATH, "//label[text()='Selected atoms:']/following-sibling::input"
    ).send_keys("1")
    driver.get_screenshot_as_file(
        f"{screenshot_dir}/structures_generate_from_smiles_2.png"
    )
    driver.find_element(By.XPATH, "//div[starts-with(text(),'Id: 1; Symbol:C;')]")


def test_eln_import(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/eln_import.ipynb")
    # TODO: This find_element is not specific enough it seems,
    # on the screenshot the page is still loading.
    driver.find_element(By.ID, "tooltip")
    time.sleep(5)
    driver.get_screenshot_as_file(f"{screenshot_dir}/eln-import.png")


def test_computational_resources_code_setup(
    selenium_driver, aiidalab_exec, screenshot_dir
):
    """Test the quicksetup of the code"""
    # check the code pw-7.0 is not in code list
    output = aiidalab_exec("verdi code list").decode().strip()
    assert "pw-7.0" not in output

    driver = selenium_driver("notebooks/computational_resources.ipynb")
    driver.set_window_size(800, 800)

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

    # take screenshots
    driver.get_screenshot_as_file(f"{screenshot_dir}/computational-resources.png")
