import json
from pathlib import Path

import ipywidgets as ipw
import requests_cache
import traitlets as tl
from aiida import orm
from IPython.display import clear_output, display

ELN_CONFIG = Path.home() / ".aiidalab" / "aiidalab-eln-config.json"
ELN_CONFIG.parent.mkdir(
    parents=True, exist_ok=True
)  # making sure that the folder exists.


def connect_to_eln(eln_instance=None, **kwargs):
    try:
        from aiidalab_eln import get_eln_connector
    except ImportError:
        return (
            None,
            "AiiDAlab-ELN connector not installed. Install with `pip install aiidalab-eln`",
        )
    # assuming that the connection can only be established to the ELNs
    # with the stored configuration.
    try:
        with open(ELN_CONFIG) as file:
            config = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return (
            None,
            f"Can't open {ELN_CONFIG!r} (ELN configuration file). Instance: {eln_instance}",
        )

    # If no ELN instance was specified, trying the default one.
    if not eln_instance:
        eln_instance = config.pop("default", None)

    if eln_instance:  # The ELN instance could be identified.
        if eln_instance in config:
            eln_config = config[eln_instance]
            eln_type = eln_config.pop("eln_type", None)
        else:  # The selected instance is not present in the config.
            return None, f"Didn't find configuration for the {eln_instance!r} instance."

        # If the ELN type cannot be identified - aborting.
        if not eln_type:
            return None, f"Can't identify the type of {eln_instance} ELN."

        # Everything is alright, can populate the ELN connector
        # with the required info.
        try:
            eln = get_eln_connector(eln_type)(
                eln_instance=eln_instance, **eln_config, **kwargs
            )
        except NotImplementedError as err:
            return None, str(err)
        eln.connect()
        return eln, None

    return (
        None,
        "No ELN instance was provided, the default ELN instance is not configured either. Set a default ELN or select an ELN instance.",
    )


class ElnImportWidget(ipw.VBox):
    node = tl.Instance(orm.Node, allow_none=True)

    def __init__(self, path_to_root="../", **kwargs):
        # Used to output additional settings.
        self._output = ipw.Output()

        # Communicate to the user if something isn't right.
        error_message = ipw.HTML()
        super().__init__(children=[error_message], **kwargs)

        eln, msg = connect_to_eln(**kwargs)

        if eln is None:
            url = f"{path_to_root}aiidalab-widgets-base/notebooks/eln_configure.ipynb"
            error_message.value = f"""Warning! The access to ELN is not configured. Please follow <a href={url!r} target="_blank">the link</a> to configure it.</br> More details: {msg!r}"""
            return

        tl.dlink((eln, "node"), (self, "node"))
        with requests_cache.disabled():
            # Since the cache is enabled in AiiDAlab, we disable it here to get correct results.
            eln.import_data()


class ElnExportWidget(ipw.VBox):
    node = tl.Instance(orm.Node, allow_none=True)

    def __init__(self, path_to_root="../", **kwargs):
        self.path_to_root = path_to_root

        # Send to ELN button.
        send_button = ipw.Button(description="Send to ELN")
        send_button.on_click(self.send_to_eln)

        # Use non-default destination.
        self.modify_settings = ipw.Checkbox(
            description="Update destination.", indent=False
        )
        self.modify_settings.observe(self.handle_output, "value")

        # Used to output additional settings.
        self._output = ipw.Output()

        # Communicate to the user if something isn't right.
        self.message = ipw.HTML()

        children = [
            ipw.HBox([send_button, self.modify_settings]),
            self._output,
            self.message,
        ]
        self.eln, msg = connect_to_eln()
        if self.eln:
            tl.dlink((self, "node"), (self.eln, "node"))
        else:
            self.modify_settings.disabled = True
            send_button.disabled = True
            self.message.value = f"""Warning! The access to ELN is not configured. Please follow <a href="{self.path_to_root}/aiidalab-widgets-base/notebooks/eln_configure.ipynb" target="_blank">the link</a> to configure it.</br> </br> More details: {msg}"""

        super().__init__(children=children, **kwargs)

    @tl.observe("node")
    def _observe_node(self, _=None):
        if self.node is None or self.eln is None:
            return

        info = self.node.base.extras.get("eln", {})
        if not info:
            try:
                q = orm.QueryBuilder().append(
                    orm.Node,
                    filters={"extras": {"has_key": "eln"}},
                    tag="source_node",
                    project="extras.eln",
                )
                q.append(
                    orm.Node,
                    filters={"uuid": self.node.uuid},
                    with_ancestors="source_node",
                )
                info = q.all(flat=True)[0]
            except IndexError:
                info = {}

        self.eln.set_sample_config(**info)

    def send_to_eln(self, _=None):
        if self.eln and self.eln.is_connected:
            self.message.value = f"\u29d7 Sending data to {self.eln.eln_instance}..."
            with requests_cache.disabled():
                # Since the cache is enabled in AiiDAlab, we disable it here to get correct results.
                self.eln.export_data()
            self.message.value = (
                f"\u2705 The data were successfully sent to {self.eln.eln_instance}."
            )
        else:
            self.message.value = f"""\u274c Something isn't right! We were not able to send the data to the "<strong>{self.eln.eln_instance}</strong>" ELN instance. Please follow <a href="{self.path_to_root}/aiidalab-widgets-base/notebooks/eln_configure.ipynb" target="_blank">the link</a> to update the ELN's configuration."""

    def handle_output(self, _=None):
        with self._output:
            clear_output()
            if self.modify_settings.value:
                display(
                    ipw.HTML(
                        f"""Currently used ELN is: "<strong>{self.eln.eln_instance}</strong>". To change it, please follow <a href="{self.path_to_root}/aiidalab-widgets-base/notebooks/eln_configure.ipynb" target="_blank">the link</a>."""
                    )
                )
                display(self.eln.sample_config_editor())


class ElnConfigureWidget(ipw.VBox):
    def __init__(self, **kwargs):
        self._output = ipw.Output()
        self.eln = None

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

        self.my_output = ipw.HTML()

        self.display_eln_config()

        super().__init__(
            children=[
                self.eln_instance,
                self.eln_types,
                self._output,
                ipw.HBox([default_button, save_config, erase_config, check_connection]),
                self.my_output,
            ],
            **kwargs,
        )

    def write_to_config(self, config):
        with open(ELN_CONFIG, "w") as file:
            json.dump(config, file, indent=4)

    def get_config(self):
        try:
            with open(ELN_CONFIG) as file:
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

        self.eln_instance.options = [("Setup new ELN", {}), *list(config.items())]
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
        if self.eln:
            err_message = self.eln.connect()
            if self.eln.is_connected:
                self.my_output.value = "\u2705 Connected."
                return
        self.my_output.value = f"\u274c Not connected. {err_message}"

    def display_eln_config(self, value=None):
        """Display ELN configuration specific to the selected type of ELN."""
        try:
            from aiidalab_eln import get_eln_connector
        except ImportError:
            with self._output:
                clear_output()
                msg = "AiiDAlab-ELN connector not installed. Install with `pip install aiidalab-eln`"
                display(ipw.HTML(f"&#10060; {msg}"))
            return

        try:
            eln_class = get_eln_connector(self.eln_types.value)
        except NotImplementedError as err:
            with self._output:
                clear_output()
                display(ipw.HTML("&#10060;" + str(err)))
                return

        self.eln = eln_class(
            eln_instance=self.eln_instance.label if self.eln_instance.value else "",
            **self.eln_instance.value,
        )

        if self.eln_instance.value:
            self.eln_types.value = self.eln.eln_type
            self.eln_types.disabled = True
        else:
            self.eln_types.disabled = False

        with self._output:
            clear_output()
            display(self.eln)

    def save_eln_configuration(self, _=None):
        config = self.eln.get_config()
        eln_instance = config.pop("eln_instance")
        if eln_instance:
            self.update_eln_configuration(eln_instance, config)
            self.update_list_of_elns()
