import os
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
def docker_compose(docker_services):
    return docker_services._docker_compose


@pytest.fixture
def aiidalab_exec(docker_compose):
    def execute(command, user=None, **kwargs):
        workdir = "/home/jovyan/apps/aiidalab-widgets-base"
        if user:
            command = f"exec --workdir {workdir} -T --user={user} aiidalab {command}"
        else:
            command = f"exec --workdir {workdir} -T aiidalab {command}"
        return docker_compose.execute(command, **kwargs)

    return execute


@pytest.fixture(scope="session", autouse=True)
def notebook_service(docker_ip, docker_services):
    """Ensure that HTTP service is up and responsive."""
    # `port_for` takes a container port and returns the corresponding host port
    port = docker_services.port_for("aiidalab", 8888)
    url = f"http://{docker_ip}:{port}"
    token = os.environ["JUPYTER_TOKEN"]
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1, check=lambda: is_responsive(url)
    )
    return url, token


@pytest.fixture(scope="session", autouse=True)
def install_package(aiidalab_exec):
    # assurance for host user UID other that 1000
    aiidalab_exec(
        "chown -R jovyan:users /home/jovyan/apps/aiidalab-widgets-base", user="root"
    )
    # install the package
    aiidalab_exec("pip install -U .")


@pytest.fixture(scope="function")
def selenium_driver(selenium, notebook_service):
    def _selenium_driver(nb_path):
        url, token = notebook_service
        url_with_token = urljoin(
            url, f"apps/apps/aiidalab-widgets-base/{nb_path}?token={token}"
        )
        selenium.get(f"{url_with_token}")
        selenium.implicitly_wait(10)  # must wait until the app loaded

        selenium.find_element(By.ID, "ipython-main-app")
        selenium.find_element(By.ID, "notebook-container")

        return selenium

    return _selenium_driver


@pytest.fixture
def firefox_options(firefox_options):
    firefox_options.add_argument("--headless")
    return firefox_options


@pytest.fixture
def chrome_options(chrome_options):
    chrome_options.add_argument("--headless")
    return chrome_options
