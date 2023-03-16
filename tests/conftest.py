import io
import os
import shutil
from collections.abc import Mapping

import numpy as np
import pytest
from aiida import plugins

pytest_plugins = ["aiida.manage.tests.pytest_fixtures"]


@pytest.fixture
def fixture_localhost(aiida_localhost):
    """Return a localhost `Computer`."""
    localhost = aiida_localhost
    localhost.set_default_mpiprocs_per_machine(1)
    return localhost


@pytest.fixture
def generate_calc_job_node(fixture_localhost):
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
        test_name=None,
        inputs=None,
        attributes=None,
        retrieve_temporary=None,
    ):
        """Fixture to generate a mock `CalcJobNode` for testing parsers.
        :param entry_point_name: entry point name of the calculation class
        :param computer: a `Computer` instance
        :param test_name: relative path of directory with test output files in the `fixtures/{entry_point_name}` folder.
        :param inputs: any optional nodes to add as input links to the corrent CalcJobNode
        :param attributes: any optional attributes to set on the node
        :param retrieve_temporary: optional tuple of an absolute filepath of a temporary directory and a list of
            filenames that should be written to this directory, which will serve as the `retrieved_temporary_folder`.
            For now this only works with top-level files and does not support files nested in directories.
        :return: `CalcJobNode` instance with an attached `FolderData` as the `retrieved` node.
        """
        from aiida import orm
        from aiida.common import LinkType
        from aiida.plugins.entry_point import format_entry_point_string
        from plumpy import ProcessState

        if computer is None:
            computer = fixture_localhost

        filepath_folder = None

        if test_name is not None:
            basepath = os.path.dirname(os.path.abspath(__file__))
            filename = os.path.join(
                entry_point_name[len("quantumespresso.") :], test_name
            )
            filepath_folder = os.path.join(basepath, "parsers", "fixtures", filename)
            filepath_input = os.path.join(filepath_folder, "aiida.in")

        entry_point = format_entry_point_string("aiida.calculations", entry_point_name)

        node = orm.CalcJobNode(computer=computer, process_type=entry_point)
        node.base.attributes.set("input_filename", "aiida.in")
        node.base.attributes.set("output_filename", "aiida.out")
        node.base.attributes.set("error_filename", "aiida.err")
        node.set_option("resources", {"num_machines": 1, "num_mpiprocs_per_machine": 1})
        node.set_option("max_wallclock_seconds", 1800)

        if attributes:
            node.base.attributes.set_many(attributes)

        if filepath_folder:
            from aiida_quantumespresso.tools.pwinputparser import PwInputFile
            from qe_tools.exceptions import ParsingError

            try:
                with open(filepath_input, encoding="utf-8") as input_file:
                    parsed_input = PwInputFile(input_file.read())
            except (ParsingError, FileNotFoundError):
                pass
            else:
                inputs["structure"] = parsed_input.get_structuredata()
                inputs["parameters"] = orm.Dict(parsed_input.namelists)

        if inputs:
            metadata = inputs.pop("metadata", {})
            options = metadata.get("options", {})

            for name, option in options.items():
                node.set_option(name, option)

            for link_label, input_node in flatten_inputs(inputs):
                input_node.store()
                node.base.links.add_incoming(
                    input_node, link_type=LinkType.INPUT_CALC, link_label=link_label
                )

        node.store()

        if retrieve_temporary:
            dirpath, filenames = retrieve_temporary
            for filename in filenames:
                try:
                    shutil.copy(
                        os.path.join(filepath_folder, filename),
                        os.path.join(dirpath, filename),
                    )
                except FileNotFoundError:
                    pass  # To test the absence of files in the retrieve_temporary folder

        if filepath_folder:
            retrieved = orm.FolderData()
            retrieved.base.repository.put_object_from_tree(filepath_folder)

            # Remove files that are supposed to be only present in the retrieved temporary folder
            if retrieve_temporary:
                for filename in filenames:
                    try:
                        retrieved.base.repository.delete_object(filename)
                    except OSError:
                        pass  # To test the absence of files in the retrieve_temporary folder

            retrieved.base.links.add_incoming(
                node, link_type=LinkType.CREATE, link_label="retrieved"
            )
            retrieved.store()

            remote_folder = orm.RemoteData(computer=computer, remote_path="/tmp")
            remote_folder.base.links.add_incoming(
                node, link_type=LinkType.CREATE, link_label="remote_folder"
            )

            remote_folder.store()

        # Set process state and exit status
        node.set_process_state(ProcessState.FINISHED)
        node.set_exit_status(0)

        return node

    return _generate_calc_job_node


@pytest.fixture
def structure_data_object():
    """Return a `StructureData` object."""
    StructureData = plugins.DataFactory("core.structure")  # noqa: N806
    structure = StructureData(cell=[[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]])
    structure.append_atom(position=(0.0, 0.0, 0.0), symbols="Si")
    structure.append_atom(position=(1.0, 1.0, 1.0), symbols="Si")
    return structure


@pytest.fixture
def bands_data_object():
    BandsData = plugins.DataFactory("core.array.bands")  # noqa: N806
    bs = BandsData()
    kpoints = np.array(
        [
            [0.0, 0.0, 0.0],  # array shape is 12 * 3
            [0.1, 0.0, 0.1],
            [0.2, 0.0, 0.2],
            [0.3, 0.0, 0.3],
            [0.4, 0.0, 0.4],
            [0.5, 0.0, 0.5],
            [0.5, 0.0, 0.5],
            [0.525, 0.05, 0.525],
            [0.55, 0.1, 0.55],
            [0.575, 0.15, 0.575],
            [0.6, 0.2, 0.6],
            [0.625, 0.25, 0.625],
        ]
    )

    bands = np.array(
        [
            [
                -5.64024889,
                6.66929678,
                6.66929678,
                6.66929678,
                8.91047649,
            ],  # array shape is 12 * 5, where 12 is the size of the kpoints mesh
            [
                -5.46976726,
                5.76113772,
                5.97844699,
                5.97844699,
                8.48186734,
            ],  # and 5 is the number of states
            [-4.93870761, 4.06179965, 4.97235487, 4.97235488, 7.68276008],
            [-4.05318686, 2.21579935, 4.18048674, 4.18048675, 7.04145185],
            [-2.83974972, 0.37738276, 3.69024464, 3.69024465, 6.75053465],
            [-1.34041116, -1.34041115, 3.52500177, 3.52500178, 6.92381041],
            [-1.34041116, -1.34041115, 3.52500177, 3.52500178, 6.92381041],
            [-1.34599146, -1.31663872, 3.34867603, 3.54390139, 6.93928289],
            [-1.36769345, -1.24523403, 2.94149041, 3.6004033, 6.98809593],
            [-1.42050683, -1.12604118, 2.48497007, 3.69389815, 7.07537154],
            [-1.52788845, -0.95900776, 2.09104321, 3.82330632, 7.20537566],
            [-1.71354964, -0.74425095, 1.82242466, 3.98697455, 7.37979746],
        ]
    )
    bs.set_kpoints(kpoints)
    bs.set_bands(bands)
    labels = [(0, "GAMMA"), (5, "X"), (6, "Z"), (11, "U")]
    bs.labels = labels
    return bs


@pytest.fixture
def folder_data_object():
    """Return a `FolderData` object."""
    FolderData = plugins.DataFactory("core.folder")  # noqa: N806
    folder_data = FolderData()
    with io.StringIO("content of test1 filelike") as fobj:
        folder_data.put_object_from_filelike(fobj, path="test1.txt")
    with io.StringIO("content of test2 filelike") as fobj:
        folder_data.put_object_from_filelike(fobj, path="test2.txt")
    with io.StringIO("content of test_long file" * 1000) as fobj:
        folder_data.put_object_from_filelike(fobj, path="test_long.txt")

    return folder_data
