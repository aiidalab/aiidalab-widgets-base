import time

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


def test_notebook_service_available(notebook_service):
    url, token = notebook_service
    response = requests.get(f"{url}/?token={token}")
    assert response.status_code == 200


def test_process_list(selenium_driver, final_screenshot):
    driver = selenium_driver("notebooks/process_list.ipynb")
    driver.find_element(By.XPATH, '//button[text()="Update now"]')


def test_aiida_datatypes_viewers(selenium_driver, final_screenshot):
    driver = selenium_driver("notebooks/viewers.ipynb")
    driver.set_window_size(1000, 2000)
    driver.find_element(By.CLASS_NAME, "widget-label")
    driver.find_element(By.XPATH, '//button[text()="Clear selection"]')
    time.sleep(5)


def test_process(selenium_driver, final_screenshot):
    driver = selenium_driver("notebooks/process.ipynb")
    driver.find_element(By.XPATH, '//label[@title="Select calculation:"]')


def test_wizard_apps(selenium_driver, final_screenshot):
    driver = selenium_driver("notebooks/wizard_apps.ipynb")
    driver.find_element(By.XPATH, '//label[@title="Delivery progress:"]')


def test_structures(selenium_driver, final_screenshot):
    driver = selenium_driver("notebooks/structures.ipynb")
    driver.set_window_size(1000, 900)
    driver.find_element(By.XPATH, '//button[text()="Upload Structure (0)"]')


def test_structures_generate_from_smiles(selenium_driver, final_screenshot):
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
        By.XPATH, "//label[text()='Select atoms:']/following-sibling::input"
    ).send_keys("1")
    driver.find_element(By.XPATH, '//button[text()="Apply selection"]').click()
    driver.find_element(By.XPATH, "//p[contains(text(),'Id: 1; Symbol: C;')]")


def test_structure_from_examples_and_supercell_selection(
    selenium_driver, final_screenshot
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
        By.XPATH, "//label[text()='Select atoms:']/following-sibling::input"
    ).send_keys("12")
    time.sleep(
        1
    )  # This is needed, otherwise selenium often presses "Apply selection" button too fast.
    driver.find_element(By.XPATH, '//button[text()="Apply selection"]').click()

    # Make sure the selection is what we expect
    driver.find_element(By.XPATH, "//p[contains(text(), 'Selected atoms: 12')]")
    driver.find_element(
        By.XPATH, "//p[contains(text(), 'Selected unit cell atoms: 6')]"
    )
    driver.find_element(By.XPATH, "//p[contains(text(),'Id: 12; Symbol: O;')]")


def test_computational_resources_code_setup(
    selenium_driver, aiidalab_exec, final_screenshot
):
    """Test the quicksetup of the code"""
    # check the code CP2K is not in code list
    output = aiidalab_exec("verdi code list").decode().strip()
    assert "cp2k" not in output

    driver = selenium_driver("notebooks/computational_resources.ipynb")
    driver.set_window_size(800, 1600)

    # click the "Setup new code" button
    driver.find_element(By.XPATH, '(//button[text()="Setup new code"])[1]').click()

    # Select daint.cscs.ch domain
    driver.find_element(By.XPATH, '(//option[text()="daint.cscs.ch"])[1]').click()

    # Select computer mc
    driver.find_element(By.XPATH, '(//option[text()="mc"])[1]').click()

    # select code
    driver.find_element(By.XPATH, '(//option[text()="cp2k-9.1"])[1]').click()

    # fill the SSH username
    driver.find_element(
        By.XPATH, "(//label[text()='SSH username:'])[1]/following-sibling::input"
    ).send_keys("dummyuser")

    driver.find_element(
        By.XPATH, "(//label[text()='Slurm account:'])[1]/following-sibling::input"
    ).send_keys("dummyuser")

    # click the quick setup (contain text "Quick setup")
    driver.find_element(
        By.XPATH, '(//button[contains(text(),"Quick setup")])[1]'
    ).click()
    time.sleep(1.0)

    # check the new code cp2k-9.1@daint-mc is in code list
    output = aiidalab_exec("verdi code list").decode().strip()
    assert "cp2k-9.1@daint-mc" in output
