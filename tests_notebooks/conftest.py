import os
from pathlib import Path
from urllib.parse import urljoin

import pytest
import requests
import selenium.webdriver.support.expected_conditions as ec
from requests.exceptions import ConnectionError
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait


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
def docker_compose_file(pytestconfig):
    return str(Path(pytestconfig.rootdir) / "tests_notebooks" / "docker-compose.yml")


@pytest.fixture(scope="session")
def docker_compose(docker_services):
    return docker_services._docker_compose


@pytest.fixture(scope="session")
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
def notebook_service(docker_ip, docker_services, aiidalab_exec):
    """Ensure that HTTP service is up and responsive."""
    # Directory ~/apps/aiidalab-widgets-base/ is mounted by docker,
    # make it writeable for jovyan user, needed for `pip install`
    aiidalab_exec("chmod -R a+rw /home/jovyan/apps/aiidalab-widgets-base", user="root")

    # Install AWB with extra dependencies for SmilesWidget
    # NOTE: I am not sure why the '-U' parameter is neccessary, but without it
    # the AWB package is not properly installed.
    aiidalab_exec("free -m && pip install -U --no-cache-dir .[smiles]")

    # `port_for` takes a container port and returns the corresponding host port
    port = docker_services.port_for("aiidalab", 8888)
    url = f"http://{docker_ip}:{port}"
    token = os.environ["JUPYTER_TOKEN"]
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1, check=lambda: is_responsive(url)
    )
    return url, token


@pytest.fixture(scope="function")
def selenium_driver(selenium, notebook_service):
    def _selenium_driver(nb_path):
        url, token = notebook_service
        url_with_token = urljoin(
            url, f"apps/apps/aiidalab-widgets-base/{nb_path}?token={token}"
        )
        selenium.get(f"{url_with_token}")
        # By default, let's allow selenium functions to retry for 10s
        # till a given element is loaded, see:
        # https://selenium-python.readthedocs.io/waits.html#implicit-waits
        selenium.implicitly_wait(10)
        window_width = 800
        window_height = 600
        selenium.set_window_size(window_width, window_height)

        selenium.find_element(By.ID, "ipython-main-app")
        selenium.find_element(By.ID, "notebook-container")
        WebDriverWait(selenium, 100).until(
            ec.invisibility_of_element((By.ID, "appmode-busy"))
        )

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
    return chrome_options
