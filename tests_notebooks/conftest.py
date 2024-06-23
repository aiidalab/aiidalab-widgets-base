import os
import time
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

    # The aiida-core version is pinned in the requirements.txt file only after
    # we release the docker stack with aiida-core v2.4.0 in:
    # https://github.com/aiidalab/aiidalab-docker-stack/commit/dfa65151017362fefeb56d97fed3c1b8f25537c5
    # There is a possibility that aiida-core version will be overwritten by the installation of AWB.
    # TODO: We can remove this before/after version check after the lowest supported aiida-core version is 2.4.0.

    # Get the aiida-core version before installing AWB
    output = aiidalab_exec("verdi --version").decode("utf-8").strip()
    before_version = output.split(" ")[-1]

    # Install AWB with extra dependencies for SmilesWidget
    aiidalab_exec("pip install --no-cache-dir .[smiles,optimade]")

    # Get the aiida-core version before installing AWB
    output = aiidalab_exec("verdi --version").decode("utf-8").strip()
    after_version = output.split(" ")[-1]

    assert (
        before_version == after_version
    ), f"aiida-core version was changed from {before_version} to {after_version}."

    # `port_for` takes a container port and returns the corresponding host port
    port = docker_services.port_for("aiidalab", 8888)
    url = f"http://{docker_ip}:{port}"
    token = os.environ["JUPYTER_TOKEN"]
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.5, check=lambda: is_responsive(url)
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
        selenium.implicitly_wait(30)
        window_width = 800
        window_height = 600
        selenium.set_window_size(window_width, window_height)

        selenium.find_element(By.ID, "ipython-main-app")
        selenium.find_element(By.ID, "notebook-container")
        WebDriverWait(selenium, timeout=240, poll_frequency=0.5).until(
            ec.invisibility_of_element((By.ID, "appmode-busy"))
        )
        time.sleep(3)

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
