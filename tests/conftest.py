import io
import json
import time
import uuid
from collections.abc import Mapping

import pytest
from aiida import engine, orm, plugins

# Load aiida-core's sqlite-based pytest fixtures
pytest_plugins = ["aiida.tools.pytest_fixtures"]


@pytest.fixture(scope="session")
def aiida_profile(aiida_config, aiida_profile_factory, config_sqlite_dos):
    """Create and load a profile with ``core.sqlite_dos`` as a storage backend and RabbitMQ as the broker.

    This overrides the ``aiida_profile`` fixture provided by ``aiida-core`` which runs with ``core.sqlite_dos`` and
    without broker. However, tests in this package make use of the daemon which requires a broker.
    """
    broker = "core.rabbitmq"
    storage = "core.sqlite_dos"
    config = config_sqlite_dos()

    with aiida_profile_factory(
        aiida_config,
        storage_backend=storage,
        storage_config=config,
        broker_backend=broker,
    ) as profile:
        yield profile


@pytest.fixture
def generate_calc_job_node(aiida_localhost):
    """Fixture to generate a mock `CalcJobNode` for testing parsers."""

    def flatten_inputs(inputs, prefix=""):
        """Flatten inputs recursively like :meth:`aiida.engine.processes.process::Process._flatten_inputs`."""
        flat_inputs = []
        for key, value in inputs.items():
            if isinstance(value, Mapping):
                flat_inputs.extend(flatten_inputs(value, prefix=prefix + key + "__"))
            else:
                flat_inputs.append((prefix + key, value))
        return flat_inputs

    def _generate_calc_job_node(
        entry_point_name="base",
        computer=None,
        inputs=None,
        attributes=None,
    ):
        """Fixture to generate a mock `CalcJobNode` for testing parsers.

        :param entry_point_name: entry point name of the calculation class
        :param computer: a `Computer` instance
        :param inputs: any optional nodes to add as input links to the corrent CalcJobNode
        :param attributes: any optional attributes to set on the node
        :return: `CalcJobNode` instance
        """
        from aiida import orm
        from aiida.common import LinkType
        from aiida.plugins.entry_point import format_entry_point_string
        from plumpy import ProcessState

        if computer is None:
            computer = aiida_localhost

        entry_point = format_entry_point_string("aiida.calculations", entry_point_name)

        node = orm.CalcJobNode(computer=computer, process_type=entry_point)
        node.base.attributes.set("input_filename", "aiida.in")
        node.base.attributes.set("output_filename", "aiida.out")
        node.base.attributes.set("error_filename", "aiida.err")
        node.set_option("resources", {"num_machines": 1, "num_mpiprocs_per_machine": 1})
        node.set_option("max_wallclock_seconds", 1800)

        if attributes:
            node.base.attributes.set_many(attributes)

        if inputs:
            options = inputs.pop("metadata", {}).get("options", {})

            for name, option in options.items():
                node.set_option(name, option)

            for link_label, input_node in flatten_inputs(inputs):
                input_node.store()
                node.base.links.add_incoming(
                    input_node, link_type=LinkType.INPUT_CALC, link_label=link_label
                )

        node.store()

        # Set process state and exit status
        node.set_process_state(ProcessState.FINISHED)
        node.set_exit_status(0)

        return node

    return _generate_calc_job_node


@pytest.fixture
def multiply_add_completed_workchain(aiida_local_code_bash):
    """Return a `MultiplyAddWorkChain` instance with a `finished` process state and exit status of 0."""
    from aiida.workflows.arithmetic.multiply_add import MultiplyAddWorkChain

    inputs = {
        "x": orm.Int(1),
        "y": orm.Int(2),
        "z": orm.Int(3),
        "code": aiida_local_code_bash,
    }
    _, process = engine.run_get_node(MultiplyAddWorkChain, **inputs)
    return process


@pytest.fixture
def multiply_add_process_builder_ready(aiida_local_code_bash):
    """Return a `MultiplyAddWorkChain` builder with all inputs set."""
    from aiida.workflows.arithmetic.multiply_add import MultiplyAddWorkChain

    builder = MultiplyAddWorkChain.get_builder()
    builder.x = orm.Int(1)
    builder.y = orm.Int(2)
    builder.z = orm.Int(3)
    builder.code = aiida_local_code_bash
    return builder


@pytest.fixture
def structure_data_object():
    """Return a `StructureData` object."""
    StructureData = plugins.DataFactory("core.structure")  # noqa: N806
    structure = StructureData(
        cell=[
            [3.84737, 0.0, 0.0],
            [1.923685, 3.331920, 0.0],
            [1.923685, 1.110640, 3.141364],
        ]
    )
    structure.append_atom(position=(0.0, 0.0, 0.0), symbols="Si")
    structure.append_atom(position=(1.923685, 1.110640, 0.785341), symbols="Si")
    structure.base.extras.set_many(
        {"eln": {"file_name": "file.xyz", "sample_uuid": "12345abcde"}}
    )
    return structure


@pytest.fixture
def folder_data_object():
    """Return a `FolderData` object."""
    FolderData = plugins.DataFactory("core.folder")  # noqa: N806
    folder_data = FolderData()
    with io.StringIO("content of test1.txt") as fobj:
        folder_data.put_object_from_filelike(fobj, path="test1.txt")
    with io.StringIO("content of test2.txt") as fobj:
        folder_data.put_object_from_filelike(fobj, path="test2.txt")
    with io.StringIO("content of test_long.txt" * 1000) as fobj:
        folder_data.put_object_from_filelike(fobj, path="test_long.txt")
    # NOTE: The byte-sequence is chosen so that it is not valid UTF-8
    with io.BytesIO(b"\xf8\x01") as fobj:
        folder_data.put_object_from_filelike(fobj, path="test.bin")

    return folder_data


@pytest.fixture
def aiida_local_code_bash(aiida_code_installed):
    """Return `InstalledCode` configured for bash executable."""
    return aiida_code_installed(
        filepath_executable="/bin/bash", default_calc_job_plugin="bash"
    )


@pytest.fixture
def await_for_process_completeness():
    """Await for a process to complete and return the process node."""

    def _await_for_process_completeness(process):
        """Await for a process to complete and return the process node."""
        while not process.is_sealed:
            time.sleep(0.1)
        return process

    return _await_for_process_completeness


@pytest.fixture
def mock_eln_config():
    """Backup the ELN_CONFIG file and restore it after the test."""

    class _MockElnConfig:
        """Mock the ELN_CONFIG file."""

        def mock(self, original_config):
            """Backup the eln config file if it exists."""
            self.original_config = original_config
            self.backup_config_name = None
            if self.original_config.exists():
                self.backup_config_name = self.original_config.with_suffix(
                    f".bak.{uuid.uuid4()}"
                )
                self.original_config.rename(self.backup_config_name)

        def restore(self):
            """Restore the eln config file if it existed and delete the test one."""
            if self.original_config.exists():
                self.original_config.unlink()

            if self.backup_config_name and self.backup_config_name.exists():
                self.backup_config_name.rename(self.original_config)

        def populate_mock_config_with_cheminfo(self):
            """Populate the mock config file with cheminfo credentials."""

            dictionary = {
                "https://mydb.cheminfo.org/": {
                    "eln_type": "cheminfo",
                    "token": "1234567890abcdef",
                },
                "default": "https://mydb.cheminfo.org/",
            }
            self.write(dictionary)

        def write(self, config_dictionary):
            """Write a config dictionary to the config file."""
            with open(self.original_config, "w") as f:
                json.dump(config_dictionary, f)

        def get(self):
            """Return the path to the config file."""
            with open(self.original_config) as f:
                return json.load(f)

    return _MockElnConfig()


@pytest.fixture
def pw_code(aiida_code_installed):
    """Return a `Code` configured for the pw.x executable."""

    return aiida_code_installed(
        label="pw",
        filepath_executable="/bin/bash",
        default_calc_job_plugin="quantumespresso.pw",
    )
