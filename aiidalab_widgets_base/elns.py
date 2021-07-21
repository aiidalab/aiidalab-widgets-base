import json
from pathlib import Path

import ipywidgets as ipw
import traitlets
from aiida.orm import Node, QueryBuilder
from aiidalab_eln import get_eln_connector
from IPython.display import clear_output, display

ELN_CONFIG = Path.home() / ".aiidalab" / "aiidalab-eln-config.json"


def connect_to_eln(eln_instance=None, **kwargs):
    try:
        with open(ELN_CONFIG, "r") as file:
            config = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None

    if not eln_instance:
        eln_instance = config.pop("default", None)

    if eln_instance:
        if eln_instance in config:
            eln_config = config[eln_instance]
            eln_type = eln_config.pop("eln_type", None)
        else:
            eln_type = None
        if not eln_type:
            return None
        eln = get_eln_connector(eln_type)(
            eln_instance=eln_instance, **eln_config, **kwargs
        )
        eln.connect()
        return eln

    return None


class ElnImportWidget(ipw.VBox):
    node = traitlets.Instance(Node, allow_none=True)

    def __init__(self, path_to_root="../", **kwargs):
        # Used to output additional settings.
        self._output = ipw.Output()

        # Communicate to the user if something isn't right.
        error_message = ipw.HTML()
        super().__init__(children=[error_message], **kwargs)

        eln = connect_to_eln(**kwargs)

        if eln is None:
            url = f"{path_to_root}aiidalab-widgets-base/eln_configure.ipynb"
            error_message.value = f"""Warning! The access to ELN {kwargs['eln_instance']} is not configured. Please follow <a href="{url}" target="_blank">the link</a> to configure it."""
            return

        traitlets.dlink((eln, "node"), (self, "node"))
        eln.import_data()


class ElnExportWidget(ipw.VBox):
    node = traitlets.Instance(Node, allow_none=True)

    def __init__(self, path_to_root="../", **kwargs):

        self.path_to_root = path_to_root

        # Send to ELN button.
        self.send = ipw.Button(description="Send to ELN")
        self.send.on_click(self.send_to_eln)

        # Use non-default destination.
        self.modify_settings = ipw.Checkbox(
            description="Update destination.", indent=False
        )
        self.modify_settings.observe(self.handle_output, "value")

        # Used to output additional settings.
        self._output = ipw.Output()

        # Communicate to the user if something isn't right.
        self.error_message = ipw.HTML()

        children = [
            ipw.HBox([self.send, self.modify_settings]),
            self.error_message,
            self._output,
        ]
        self.eln = connect_to_eln()
        traitlets.dlink((self, "node"), (self.eln, "node"))

        super().__init__(children=children, **kwargs)

    @traitlets.observe("node")
    def _observe_node(self, _=None):
        if self.node is None:
            return

        if "eln" in self.node.extras:
            info = self.node.extras["eln"]
        else:
            try:
                q = QueryBuilder().append(
                    Node,
                    filters={"extras": {"has_key": "eln"}},
                    tag="source_node",
                    project="extras.eln",
                )
                q.append(
                    Node, filters={"uuid": self.node.uuid}, with_ancestors="source_node"
                )
                info = q.all(flat=True)[0]
            except IndexError:
                info = {}

        self.eln.set_sample_config(**info)

    def send_to_eln(self, _=None):
        if self.eln.is_connected:
            self.error_message.value = ""
            self.eln.export_data()
        else:
            self.error_message.value = f"""Warning! The access to ELN is not configured. Please follow <a href="{self.path_to_root}/aiidalab-widgets-base/eln_configure.ipynb" target="_blank">the link</a> to configure it."""

    def handle_output(self, _=None):
        with self._output:
            clear_output()
            if self.modify_settings.value:
                display(self.eln.sample_config_editor())


class ElnConfigureWidget(ipw.VBox):
    def __init__(self, **kwargs):
        self._output = ipw.Output()

        self.eln_instance = ipw.Dropdown(
            description="ELN:",
            options=("Set up new ELN", {}),
            style={"description_width": "initial"},
        )
        self.update_list_of_elns()
        self.eln_instance.observe(self.display_eln_config, names=["value", "options"])

        self.eln_types = ipw.Dropdown(
            description="ELN type:",
            options=["cheminfo", "openbis"],
            value="cheminfo",
            style={"description_width": "initial"},
        )
        self.eln_types.observe(self.display_eln_config, names=["value", "options"])

        # Buttons.

        # Make current ELN the default.
        default_button = ipw.Button(description="Set as default", button_style="info")
        default_button.on_click(self.set_current_eln_as_default)

        # Save current ELN configuration.
        save_config = ipw.Button(
            description="Save configuration", button_style="success"
        )
        save_config.on_click(self.save_eln_configuration)

        # Erase current ELN from the configuration.
        erase_config = ipw.Button(
            description="Erase configuration", button_style="danger"
        )
        erase_config.on_click(self.erase_current_eln_from_configuration)

        # Check if connection to the current ELN can be established.
        check_connection = ipw.Button(
            description="Check connection", button_style="warning"
        )
        check_connection.on_click(self.check_connection)

        self.display_eln_config()

        super().__init__(
            children=[
                self.eln_instance,
                self.eln_types,
                self._output,
                ipw.HBox([default_button, save_config, erase_config, check_connection]),
            ],
            **kwargs,
        )

    def write_to_config(self, config):
        with open(ELN_CONFIG, "w") as file:
            json.dump(config, file, indent=4)

    def get_config(self):
        try:
            with open(ELN_CONFIG, "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return {}

    def update_list_of_elns(self):
        config = self.get_config()
        default_eln = config.pop("default", None)
        if (
            default_eln not in config
        ):  # Erase the default ELN if it is not present in the config
            self.write_to_config(config)
            default_eln = None

        self.eln_instance.options = [("Setup new ELN", {})] + [
            (k, v) for k, v in config.items()
        ]
        if default_eln:
            self.eln_instance.label = default_eln

    def set_current_eln_as_default(self, _=None):
        self.update_eln_configuration("default", self.eln_instance.label)

    def update_eln_configuration(self, eln_instance, eln_config):
        config = self.get_config()
        config[eln_instance] = eln_config
        self.write_to_config(config)

    def erase_current_eln_from_configuration(self, _=None):
        config = self.get_config()
        config.pop(self.eln_instance.label, None)
        self.write_to_config(config)
        self.update_list_of_elns()

    def check_connection(self, _=None):
        print("Not implemented :(")

    def display_eln_config(self, value=None):
        """Display ELN configuration specific to the selected type of ELN."""
        connector_class = get_eln_connector(self.eln_types.value)
        self.connector = connector_class(
            eln_instance=self.eln_instance.label if self.eln_instance.value else "",
            **self.eln_instance.value,
        )

        if self.eln_instance.value:
            self.eln_types.value = self.connector.eln_type
            self.eln_types.disabled = True
        else:
            self.eln_types.disabled = False

        with self._output:
            clear_output()
            display(self.connector)

    def save_eln_configuration(self, _=None):
        config = self.connector.get_config()
        eln_instance = config.pop("eln_instance")
        if eln_instance:
            self.update_eln_configuration(eln_instance, config)
            self.update_list_of_elns()