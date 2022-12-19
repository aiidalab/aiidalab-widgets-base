import time

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


def test_notebook_service_available(notebook_service):
    url, token = notebook_service
    response = requests.get(f"{url}/?token={token}")
    assert response.status_code == 200


def test_process_list(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/process_list.ipynb")
    driver.find_element(By.XPATH, '//button[text()="Update now"]')

    # Save screenshot.
    driver.get_screenshot_as_file(f"{screenshot_dir}/process-list.png")


def test_aiida_datatypes_viewers(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/aiida_datatypes_viewers.ipynb")
    driver.set_window_size(1000, 2000)
    driver.find_element(By.CLASS_NAME, "widget-label")
    driver.find_element(By.XPATH, '//button[text()="Clear selection"]')
    time.sleep(5)

    # Save screenshot.
    driver.get_screenshot_as_file(f"{screenshot_dir}/datatypes-viewer.png")


def test_eln_configure(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/eln_configure.ipynb")
    driver.find_element(By.XPATH, '//button[text()="Set as default"]')

    # Save screenshot.
    driver.get_screenshot_as_file(f"{screenshot_dir}/eln-configure.png")


def test_process(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/process.ipynb")
    driver.find_element(By.XPATH, '//label[@title="Select calculation:"]')

    # Save screenshot.
    driver.get_screenshot_as_file(f"{screenshot_dir}/process.png")


def test_wizard_apps(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/wizard_apps.ipynb")
    driver.find_element(By.XPATH, '//label[@title="Delivery progress:"]')

    # Save screenshot.
    driver.get_screenshot_as_file(f"{screenshot_dir}/wizzard-apps.png")


def test_structures(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/structures.ipynb")
    driver.set_window_size(1000, 900)
    driver.find_element(By.XPATH, '//button[text()="Upload Structure (0)"]')
    time.sleep(5)

    # Save screenshot.
    driver.get_screenshot_as_file(f"{screenshot_dir}/structures.png")


def test_structures_generate_from_smiles(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/structures.ipynb")
    driver.set_window_size(1000, 900)
    # Switch to SMILES tab in StructureManagerWidget
    driver.find_element(By.XPATH, "//*[text()='SMILES']").click()

    # Generate methane molecule from SMILES
    driver.find_element(By.XPATH, "//input[@placeholder='C=C']").send_keys("C")
    driver.find_element(By.XPATH, '//button[text()="Generate molecule"]').click()
    time.sleep(5)

    # Select the first atom
    driver.find_element(By.XPATH, "//*[text()='Selection']").click()
    driver.find_element(
        By.XPATH, "//label[text()='Selected atoms:']/following-sibling::input"
    ).send_keys("1")
    driver.find_element(By.XPATH, '//button[text()="Apply selection"]').click()
    driver.find_element(By.XPATH, "//p[contains(text(),'Id: 1; Symbol: C;')]")

    # Save screenshot.
    driver.get_screenshot_as_file(
        f"{screenshot_dir}/structures_generate_from_smiles_2.png"
    )


def test_structure_from_examples_and_supercell_selection(
    selenium_driver, screenshot_dir
):

    driver = selenium_driver("notebooks/structures.ipynb")
    driver.set_window_size(1000, 900)
    # Switch to "From Examples tab in StructureManagerWidget
    driver.find_element(By.XPATH, "//*[text()='From Examples']").click()

    # Select SiO2 example
    driver.find_element(By.XPATH, '//option[@value="Silicon oxide"]').click()

    # Expand cell view in z direction
    driver.find_element(By.XPATH, "//*[text()='Appearance']").click()
    driver.find_element(By.XPATH, "(//input[@type='number'])[3]").send_keys(
        Keys.BACKSPACE
    )
    driver.find_element(By.XPATH, "(//input[@type='number'])[3]").send_keys("2")
    driver.find_element(By.XPATH, "(//input[@type='number'])[3]").send_keys(Keys.ENTER)

    # Select the 12th atom
    driver.find_element(By.XPATH, "//*[text()='Selection']").click()
    driver.find_element(
        By.XPATH, "//label[text()='Selected atoms:']/following-sibling::input"
    ).send_keys("12")
    driver.find_element(By.XPATH, '//button[text()="Apply selection"]').click()

    # Make sure the selection is what we expect
    driver.find_element(By.XPATH, "//p[contains(text(), 'Selected atoms: 12')]")
    driver.find_element(
        By.XPATH, "//p[contains(text(), 'Selected unit cell atoms: 6')]"
    )
    driver.find_element(By.XPATH, "//p[contains(text(),'Id: 12; Symbol: O;')]")

    # Save screenshot.
    driver.get_screenshot_as_file(
        f"{screenshot_dir}/structure_from_examples_and_supercell_selection.png"
    )


def test_eln_import(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/eln_import.ipynb")
    # TODO: This find_element is not specific enough it seems,
    # on the screenshot the page is still loading.
    driver.find_element(By.ID, "tooltip")
    time.sleep(5)

    # Save screenshot.
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
    driver.find_element(By.XPATH, '(//button[text()="Setup new code"])[1]').click()

    # Select daint.cscs.ch domain
    driver.find_element(By.XPATH, '(//option[text()="daint.cscs.ch"])[1]').click()

    # Select computer multicore
    driver.find_element(By.XPATH, '(//option[text()="multicore"])[1]').click()

    # select code pw-7.0-multicore
    driver.find_element(By.XPATH, '(//option[text()="pw-7.0-multicore"])[1]').click()

    # fill the SSH username
    driver.find_element(
        By.XPATH, "(//label[text()='SSH username:'])[1]/following-sibling::input"
    ).send_keys("dummyuser")

    # click the quick setup
    driver.find_element(By.XPATH, '(//button[text()="Quick Setup"])[1]').click()
    time.sleep(1.0)

    # check the new code pw-7.0@daint-mc is in code list
    output = aiidalab_exec("verdi code list").decode().strip()
    assert "pw-7.0@daint-mc" in output

    # Set the second code of the same computer
    # issue https://github.com/aiidalab/aiidalab-widgets-base/issues/416
    # click the "Setup new code" button
    driver.find_element(By.XPATH, '(//button[text()="Setup new code"])[2]').click()

    # Select daint.cscs.ch domain
    driver.find_element(By.XPATH, '(//option[text()="daint.cscs.ch"])[2]').click()

    # Select computer multicore
    driver.find_element(By.XPATH, '(//option[text()="multicore"])[2]').click()

    # select code pw-7.0-multicore
    driver.find_element(By.XPATH, '(//option[text()="dos-7.0-multicore"])[2]').click()

    # fill the SSH username
    # Get the element of index 3 which is the SSH username of second widget
    # the one of index 2 is the SSH username in detail setup of the first widget.
    driver.find_element(
        By.XPATH, "(//label[text()='SSH username:'])[3]/following-sibling::input"
    ).send_keys("dummyuser")

    # click the quick setup
    driver.find_element(By.XPATH, '(//button[text()="Quick Setup"])[2]').click()
    time.sleep(1.0)

    # check the new code pw-7.0@daint-mc is in code list
    output = aiidalab_exec("verdi code list").decode().strip()
    assert "dos-7.0@daint-mc" in output

    # Save screenshot.
    driver.get_screenshot_as_file(f"{screenshot_dir}/computational-resources.png")
