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
    driver.find_element(By.CLASS_NAME, "widget-label")
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
    driver.find_element(By.XPATH, '//button[text()="Upload Structure (0)"]')
    driver.get_screenshot_as_file(f"{screenshot_dir}/structures.png")


def test_eln_import(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/eln_import.ipynb")
    # TODO: This find_element is not specific enough it seems,
    # on the screenshot the page is still loading.
    driver.find_element(By.ID, "tooltip")
    driver.get_screenshot_as_file(f"{screenshot_dir}/eln-import.png")


def test_computational_resources(selenium_driver, screenshot_dir):
    driver = selenium_driver("notebooks/computational_resources.ipynb")
    driver.find_element(By.XPATH, '//button[text()="Setup new code"]')
    driver.get_screenshot_as_file(f"{screenshot_dir}/computational-resources.png")
