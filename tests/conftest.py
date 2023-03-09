import os
import subprocess
from pathlib import Path
from urllib.parse import urljoin

import pytest
import requests
from requests.exceptions import ConnectionError
from selenium.webdriver.common.by import By


def is_responsive(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return True
    except ConnectionError:
        return False


@pytest.fixture(scope="session")
def screenshot_dir():
    sdir = Path.joinpath(Path.cwd(), "screenshots")
    try:
        os.mkdir(sdir)
    except FileExistsError:
        pass
    return sdir


@pytest.fixture(scope="session")
def aiidalab_exec():
    """Exeute aiidalab command in a subprocess."""

    def _aiidalab_exec(command, **kwargs):
        if isinstance(command, str):
            command = command.split()
        return subprocess.run(command, capture_output=True, **kwargs).stdout

    return _aiidalab_exec


@pytest.fixture(scope="session", autouse=True)
def notebook_service():
    url = "http://localhost:8888"
    token = os.environ["JUPYTER_TOKEN"]
    return url, token


@pytest.fixture(scope="function")
def selenium_driver(selenium, notebook_service):
    # Directory ~/apps/aiidalab-widgets-base/ is mounted by docker,
    # make it writeable for jovyan user, needed for `pip install`
    def _selenium_driver(nb_path):

        url, token = notebook_service

        full_url = urljoin(
            url, f"apps/apps/aiidalab-widgets-base/{nb_path}?token={token}"
        )
        selenium.get(full_url)
        # By default, let's allow selenium functions to retry for 10s
        # till a given element is loaded, see:
        # https://selenium-python.readthedocs.io/waits.html#implicit-waits
        selenium.implicitly_wait(10)
        window_width = 800
        window_height = 600
        selenium.set_window_size(window_width, window_height)

        selenium.find_element(By.ID, "ipython-main-app")
        selenium.find_element(By.ID, "notebook-container")

        return selenium

    return _selenium_driver


@pytest.fixture
def final_screenshot(request, screenshot_dir, selenium):
    """Take screenshot at the end of the test.
    Screenshot name is generated from the test function name
    by stripping the 'test_' prefix
    """
    screenshot_name = f"{request.function.__name__[5:]}.png"
    screenshot_path = Path.joinpath(screenshot_dir, screenshot_name)
    yield
    selenium.get_screenshot_as_file(screenshot_path)


@pytest.fixture
def firefox_options(firefox_options):
    firefox_options.add_argument("--headless")
    return firefox_options


@pytest.fixture
def chrome_options(chrome_options):
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    return chrome_options
