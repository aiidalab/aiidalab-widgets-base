import ipywidgets as ipw
import json
import traitlets
from pathlib import Path
from aiida.orm import Node, QueryBuilder
from IPython.display import clear_output, display
from aiidalab_eln import get_eln_connector

ELN_CONFIG = Path.home() / ".aiidalab" / "aiidalab-eln-config.json"


def connect_to_eln(eln_name=None, **kwargs):
    try:
        with open(ELN_CONFIG, "r") as file:
            options = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None

    if not eln_name:
        eln_name = options.pop("default", None)

    if eln_name:
        if eln_name in options:
            options = options[eln_name]
        eln_type = options.pop("eln_type", None)
        if not eln_type:
            return None
        eln = get_eln_connector(eln_type)(eln_instance=eln_name, **options, **kwargs)
        eln.connect()
        return eln

    return None


class AppIcon:
    def __init__(self, icon, link, description):
        self.icon = icon
        self.link = link
        self.description = description

    def to_html_string(self):
        return f"""
            <table style="border-collapse:separate;border-spacing:15px;">
            <tr>
                <td style="width:200px"> <a href="{self.link}" target="_blank">  <img src="{self.icon}"> </a></td>
                <td style="width:800px"> <p style="font-size:16px;">{self.description} </p></td>
            </tr>
            </table>
            """


class DisplayAiidaObject(ipw.VBox):
    node = traitlets.Instance(Node, allow_none=True)

    def __init__(self, **kwargs):
        self._output = ipw.Output()
        super().__init__(
            children=[
                self._output,
            ],
            **kwargs,
        )

    @traitlets.observe("node")
    def _observe_node(self, change):
        from aiidalab_widgets_base import viewer

        if change["new"] != change["old"]:
            with self._output:
                clear_output()
                if change["new"]:
                    display(viewer(change["new"]))


class OpenInApp(ipw.VBox):

    node = traitlets.Instance(Node, allow_none=True)

    def __init__(self, **kwargs):
        self.tab = ipw.Tab()
        self.tab_selection = ipw.RadioButtons(
            options=[],
            description="",
            disabled=False,
            style={"description_width": "initial"},
            layout=ipw.Layout(width="auto"),
        )
        spacer = ipw.HTML("""<p style="margin-bottom:1cm;"></p>""")
        super().__init__(children=[self.tab_selection, spacer, self.tab], **kwargs)

    @traitlets.observe("node")
    def _observe_node(self, change):
        if change["new"]:
            self.tab.children = [
                self.get_geo_opt_tab(),
                self.get_geometry_analysis_tab(),
                self.get_isotherm_tab(),
            ]
            self.tab.set_title(0, "Geometry Optimization")
            self.tab.set_title(1, "Geometry analysis")
            self.tab.set_title(2, "Isotherm")

            self.tab_selection.options = [
                (
                    "Geometry Optimization - typically this is the first step needed to find optimal positions of atoms in the unit cell.",
                    0,
                ),
                (
                    "Geometry analysis - calculate parameters describing the geometry of a porous material.",
                    1,
                ),
                (
                    "Isotherm - compute adsorption isotherm of a small molecules in the selected material. ",
                    2,
                ),
            ]
            ipw.link((self.tab, "selected_index"), (self.tab_selection, "value"))
        else:
            self.tab.children = []

    def get_geo_opt_tab(self):
        geo_opt = ipw.HTML("")

        geo_opt.value += AppIcon(
            icon="https://gitlab.com/QEF/q-e/raw/develop/logo.jpg",
            link=f"https://aiidalab-demo.materialscloud.org/user-redirect/apps/apps/quantum-espresso/qe.ipynb?structure_uuid={self.node.uuid}",
            description="Optimize atomic positions and/or unit cell employing Quantum ESPRESSO. Quantum ESPRESSO is preferable for small structures with no cell dimensions larger than 15 Å. Additionally, you can choose to compute electronic properties of the material such as band structure and density of states.",
        ).to_html_string()

        geo_opt.value += AppIcon(
            icon="https://raw.githubusercontent.com/lsmo-epfl/aiidalab-epfl-lsmo/develop/miscellaneous/logos/LSMO.png",
            link=f"https://aiidalab-demo.materialscloud.org/user-redirect/apps/apps/aiidalab-lsmo/multistage_geo_opt_ddec.ipynb?structure_uuid={self.node.uuid}",
            description="Optimize atomic positions and unit cell with CP2K. CP2K is very efficient for large and/or porous structures. A structure is considered large when any cell dimension is larger than 15 Å. Additionally, you can choose to assign point charges to the atoms using DDEC.",
        ).to_html_string()

        return geo_opt

    def get_isotherm_tab(self):
        isotherm = ipw.HTML()
        isotherm.value += AppIcon(
            icon="https://raw.githubusercontent.com/lsmo-epfl/aiidalab-epfl-lsmo/develop/miscellaneous/logos/LSMO.png",
            link=f"https://aiidalab-demo.materialscloud.org/user-redirect/apps/apps/aiidalab-lsmo/compute_isotherm.ipynb?structure_uuid={self.node.uuid}",
            description="Compute adsorption isotherm of the selected material using the RASPA code. Typically, one needs to optimize geometry and compute the charges of material before isotherm. However, if this is already done, you can go for it.",
        ).to_html_string()

        return isotherm

    def get_geometry_analysis_tab(self):
        geo_analysis = ipw.HTML()
        geo_analysis.value += AppIcon(
            icon="https://raw.githubusercontent.com/lsmo-epfl/aiidalab-epfl-lsmo/develop/miscellaneous/logos/LSMO.png",
            link=f"https://aiidalab-demo.materialscloud.org/user-redirect/apps/apps/aiidalab-lsmo/pore_analysis.ipynb?structure_uuid={self.node.uuid}",
            description="Perform geometry analysis of a material employing Zeo++ code.",
        ).to_html_string()

        return geo_analysis


class ElnImportWidget(ipw.VBox):
    node = traitlets.Instance(Node, allow_none=True)

    def __init__(self, **kwargs):
        # Used to output additional settings.
        self._output = ipw.Output()

        # Communicate to the user if something isn't right.
        error_message = ipw.HTML()
        super().__init__(children=[error_message], **kwargs)

        eln = connect_to_eln(**kwargs)

        if eln is None:
            error_message.value = f"""Warning! The access to ELN {kwargs['eln_name']} is not configured. Please follow <a href="https://aiidalab-demo.materialscloud.org/user/aliaksandr.yakutovich@epfl.ch/apps/apps/aiidalab-widgets-base/eln_configure.ipynb" target="_blank">the link</a> to configure it."""
            return

        traitlets.dlink((eln, "node"), (self, "node"))
        eln.import_data_object()


class ElnExportWidget(ipw.VBox):
    node = traitlets.Instance(Node, allow_none=True)

    def __init__(self, **kwargs):

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
            self.eln.export_data_object(data_object=self.node)
        else:
            self.error_message.value = """Warning! The access to ELN is not configured. Please follow <a href="https://aiidalab-demo.materialscloud.org/user/aliaksandr.yakutovich@epfl.ch/apps/apps/aiidalab-widgets-base/eln_configure.ipynb" target="_blank">the link</a> to configure it."""

    def handle_output(self, _=None):
        with self._output:
            clear_output()
            if self.modify_settings.value:
                display(self.eln.sample_config_editor())


class ElnConfigureWidget(ipw.VBox):
    selected = traitlets.Dict()

    def __init__(self, **kwargs):
        self._output = ipw.Output()

        self.eln_instance = ipw.Dropdown(
            description="ELN:",
            options=("Setup new ELN", {}),
            style={"description_width": "initial"},
        )
        self.update_list_of_elns()

        self.eln_types = ipw.Dropdown(
            description="ELN type:",
            options=["cheminfo", "openbis"],
            value="cheminfo",
            style={"description_width": "initial"},
        )

        self.eln_instance.observe(self.display_eln_config, names=["value", "options"])
        self.eln_types.observe(self.display_eln_config, names=["value", "options"])

        default_button = ipw.Button(description="Set as default", button_style="info")
        default_button.on_click(self.set_current_eln_as_default)

        save_config = ipw.Button(
            description="Save configuration", button_style="success"
        )
        save_config.on_click(self.save_eln_configuration)

        erase_config = ipw.Button(
            description="Erase configuration", button_style="danger"
        )
        erase_config.on_click(self.erase_eln_configuration)

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

    def update_list_of_elns(self):
        config = self.get_configured_elns()
        default_eln = config.pop("default", None)
        self.eln_instance.options = [("Setup new ELN", {})] + [
            (k, v) for k, v in config.items()
        ]
        if default_eln:
            self.eln_instance.label = default_eln

    def get_configured_elns(self):
        try:
            with open(ELN_CONFIG, "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            return {}

    def set_current_eln_as_default(self, _=None):
        self.update_eln_configuration("default", self.eln_instance.label)

    def update_eln_configuration(self, eln, config):
        elns = self.get_configured_elns()
        elns[eln] = config
        with open(ELN_CONFIG, "w") as file:
            json.dump(elns, file, indent=4)

    def erase_eln_configuration(self, _=None):
        elns = self.get_configured_elns()
        elns.pop(self.eln_instance.label, None)
        if "default" in elns and elns["default"] not in elns:
            elns.pop("default")

        with open(ELN_CONFIG, "w") as file:
            json.dump(elns, file, indent=4)
        self.update_list_of_elns()

    def check_connection(self, _=None):
        print("Not implemented :(")

    def display_eln_config(self, value=None):
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
        eln = config.pop("eln_instance")
        if eln:
            self.update_eln_configuration(eln, config)
            self.update_list_of_elns()
