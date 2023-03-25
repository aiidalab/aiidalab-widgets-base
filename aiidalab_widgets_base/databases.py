"""Widgets that allow to query online databases."""
import ase
import ipywidgets as ipw
import requests
import traitlets as tl
from aiida.tools.dbimporters.plugins.cod import CodDbImporter
from optimade_client import default_parameters, query_filter, query_provider


class CodQueryWidget(ipw.VBox):
    """Query structures in Crystallography Open Database (COD)
    Useful class members:
    :ivar structure(Atoms): trait that contains the selected structure, None if structure is not selected."""

    structure = tl.Instance(ase.Atoms, allow_none=True)

    def __init__(self, title="", **kwargs):
        description = ipw.HTML(
            """<h3>Get crystal structures from
    <a href="http://www.crystallography.net">Crystallography Open Database</a></h3>
    <b>Queries by formula</b>
    <br>
    For the queries by formula please adhere to the Hill notation.
    The chemical symbol of an element should be followed by its number in the structure,
    except when there is only one atom.
    When the structure does NOT contain carbon atoms, all the elements are listed alphabetically.
    Example: <i>O2 Si</i>.
    <br>
    In case the structure DOES contain carbon atoms its number following the 'C' symbol is indicated first.
    If hydrogen is also present in the structure then 'H' symbol and its number is indicated second.
    The remaining elements are listed in the alphabetical order. Example: <i>C H4 N2 O</i>.
    <br>
    <b>Queries by the structure id number</b>
    <br>
    For the queries by structure id, plese provide the database id number. Example: <i>1008786</i>
    """
        )
        self.title = title
        layout = ipw.Layout(width="400px")
        style = {"description_width": "initial"}
        self.inp_elements = ipw.Text(
            description="",
            value="",
            placeholder="e.g.: Ni Ti or id number",
            layout=layout,
            style=style,
        )
        self.btn_query = ipw.Button(description="Query")
        self.query_message = ipw.HTML("Waiting for input...")
        self.drop_structure = ipw.Dropdown(
            description="",
            options=[("select structure", {"status": False})],
            style=style,
            layout=layout,
        )
        self.link = ipw.HTML("Link to the web-page will appear here")
        self.btn_query.on_click(self._on_click_query)
        self.drop_structure.observe(self._on_select_structure, names=["value"])

        children = [
            description,
            ipw.HBox([self.btn_query, self.inp_elements]),
            self.query_message,
            ipw.HBox([self.drop_structure, self.link]),
        ]
        super().__init__(children=children, **kwargs)

    @staticmethod
    def _query(idn=None, formula=None):
        """Make the actual query."""
        importer = CodDbImporter()
        if idn is not None:
            return importer.query(id=idn)
        if formula is not None:
            return importer.query(formula=formula)
        return None

    def _on_click_query(self, _=None):
        """Call query when the corresponding button is pressed."""
        structures = [("select structure", {"status": False})]
        idn = None
        formula = None
        self.query_message.value = "Quering the database ... "
        try:
            idn = int(self.inp_elements.value)
        except ValueError:
            formula = str(self.inp_elements.value)

        for entry in self._query(idn=idn, formula=formula):
            try:
                entry_cif = entry.get_cif_node()
                formula = entry_cif.get_ase().get_chemical_formula()
            except Exception:
                continue
            entry_add = (
                f"{formula} (id: {entry.source['id']})",
                {
                    "status": True,
                    "cif": entry_cif,
                    "url": entry.source["uri"],
                    "id": entry.source["id"],
                },
            )
            structures.append(entry_add)

        self.query_message.value += f"{len(structures) - 1} structures found"
        self.drop_structure.options = structures

    def _on_select_structure(self, change):
        """When a structure was selected."""
        selected = change["new"]
        if selected["status"] is False:
            self.structure = None
            return
        self.structure = selected["cif"].get_ase()
        struct_url = selected["url"].split(".cif")[0] + ".html"
        self.link.value = (
            f"""<a href="{struct_url}" target="_blank">COD entry {selected["id"]}</a>"""
        )

    @tl.default("structure")
    def _default_structure(self):
        return None


class OptimadeQueryWidget(ipw.VBox):
    """AiiDAlab-specific OPTIMADE Query widget

    Useful as a widget to integrate with the
    :class:`aiidalab_widgets_base.structures.StructureManagerWidget`,
    embedded into applications.

    NOTE: `embedded` for `OptimadeQueryFilterWidget` was introduced in `optimade-client`
    version 2020.11.5.

    :param embedded: Whether or not to show extra database and provider information.
        When set to `True`, the extra information will be hidden, this is useful
        in situations where the widget is used in a Tab or similar, e.g., for the
        class :class:`aiidalab_widgets_base.structures.StructureManagerWidget`.
    :type embedded: bool
    :param title: Title used for Tab header if employed in
        :class:`aiidalab_widgets_base.structures.StructureManagerWidget`.
    :type title: str
    """

    structure = tl.Instance(ase.Atoms, allow_none=True)

    _disable_providers = default_parameters.DISABLE_PROVIDERS
    _skip_databases = default_parameters.SKIP_DATABASE
    _skip_providers = default_parameters.SKIP_PROVIDERS
    _provider_database_groupings = default_parameters.PROVIDER_DATABASE_GROUPINGS

    def __init__(
        self,
        embedded: bool = True,
        title: str = None,
        **kwargs,
    ) -> None:
        providers_header = ipw.HTML("<h4>Select a provider</h4>")
        providers = query_provider.OptimadeQueryProviderWidget(
            embedded=embedded,
            width_ratio=kwargs.pop("width_ratio", None),
            width_space=kwargs.pop("width_space", None),
            database_limit=kwargs.pop("database_limit", None),
            disable_providers=kwargs.pop("disable_providers", self._disable_providers),
            skip_databases=kwargs.pop("skip_databases", self._skip_databases),
            skip_providers=kwargs.pop("skip_providers", self._skip_providers),
            provider_database_groupings=kwargs.pop(
                "provider_database_groupings", self._provider_database_groupings
            ),
        )
        filters = query_filter.OptimadeQueryFilterWidget(
            embedded=embedded,
            button_style=kwargs.pop("button_style", None),
            result_limit=kwargs.pop("results_limit", None),
            subparts_order=kwargs.pop("subparts_order", None),
        )

        ipw.dlink((providers, "database"), (filters, "database"))

        filters.observe(self._update_structure, names="structure")

        self.title = title or "OPTIMADE"
        layout = kwargs.pop("layout", {"width": "auto", "height": "auto"})

        super().__init__(
            children=(providers_header, providers, filters),
            layout=layout,
            **kwargs,
        )

    def _update_structure(self, change: dict) -> None:
        """New structure chosen"""
        self.structure = (
            change["new"].as_aiida_structuredata.get_ase() if change["new"] else None
        )


class ComputationalResourcesDatabaseWidget(ipw.VBox):
    """Extract the setup of a known computer from the AiiDA code registry."""

    default_calc_job_plugin = tl.Unicode(allow_none=True)
    ssh_config = tl.Dict()
    computer_setup = tl.Dict()
    code_setup = tl.Dict()
    database = tl.Dict()

    def __init__(self, **kwargs):
        # Select domain.
        self.inp_domain = ipw.Dropdown(
            options=[],
            description="Domain",
            disabled=False,
        )
        self.inp_domain.observe(self._domain_changed, names=["value", "options"])

        # Select computer.
        self.inp_computer = ipw.Dropdown(
            options=[],
            description="Computer:",
            disable=False,
        )
        self.inp_computer.observe(self._computer_changed, names=["value", "options"])

        # Select code.
        self.inp_code = ipw.Dropdown(
            options=[],
            description="Code:",
            disable=False,
        )
        self.inp_code.observe(self._code_changed, names=["value", "options"])

        btn_reset = ipw.Button(description="Reset")
        btn_reset.on_click(self._reset)

        super().__init__(
            children=[
                self.inp_domain,
                self.inp_computer,
                self.inp_code,
                btn_reset,
            ],
            **kwargs,
        )
        self.update()
        self._reset()

    def _reset(self, _=None):
        self.inp_domain.value = None

    def clean_up_database(self, database, plugin):
        for domain in list(database.keys()):
            for computer in list(database[domain].keys() - {"default"}):
                for code in list(
                    database[domain][computer].keys()
                    - {"computer-configure", "computer-setup"}
                ):
                    if (
                        plugin
                        != database[domain][computer][code]["default_calc_job_plugin"]
                    ):
                        del database[domain][computer][code]
                # If no codes remained that correspond to the chosen plugin, remove the computer.
                if (
                    len(
                        database[domain][computer].keys()
                        - {"computer-configure", "computer-setup"}
                    )
                    == 0
                ):
                    del database[domain][computer]
            # If no computers remained - remove the domain.
            if len(database[domain].keys() - {"default"}) == 0:
                del database[domain]
            # Making sure the 'default' key still points to an existing computer.
            elif database[domain]["default"] not in database[domain]:
                database[domain]["default"] = sorted(
                    database[domain].keys() - {"default"}
                )[0]
        return database

    def update(self, _=None):
        database = requests.get(
            "https://aiidateam.github.io/aiida-code-registry/database_v2_1.json"
        ).json()
        self.database = (
            self.clean_up_database(database, self.default_calc_job_plugin)
            if self.default_calc_job_plugin
            else database
        )

    @tl.observe("database")
    def _observer_database_change(self, _=None):
        self.inp_domain.options = self.database.keys()
        self._reset()

    def _domain_changed(self, _=None):
        with self.hold_trait_notifications():
            self.inp_computer.value = None
            try:
                self.inp_computer.options = [
                    key
                    for key in self.database[self.inp_domain.value].keys()
                    if key != "default"
                ]
                self.inp_computer.value = self.database[self.inp_domain.value][
                    "default"
                ]
            except KeyError:
                self.inp_computer.options = []
                return

    def _computer_changed(self, _=None):
        """Read settings from the YAML files and populate self.database with them."""

        with self.hold_trait_notifications():
            if self.inp_computer.value is None:
                self.inp_code.options = []
                self.inp_code.value = None
                self.ssh_config = {}
                self.computer_setup = {}
                return

            self.inp_code.options = [
                key
                for key in self.database[self.inp_domain.value][
                    self.inp_computer.value
                ].keys()
                if key not in ("computer-setup", "computer-configure")
            ]

            setup = self.database[self.inp_domain.value][self.inp_computer.value][
                "computer-setup"
            ]
            config = self.database[self.inp_domain.value][self.inp_computer.value][
                "computer-configure"
            ]
            ssh_config = {"hostname": setup["hostname"]}
            if "proxy_command" in config:
                ssh_config["proxy_command"] = config["proxy_command"]
            if "proxy_jump" in config:
                ssh_config["proxy_jump"] = config["proxy_jump"]

            self.ssh_config = ssh_config  # To notify the trait change

            self.computer_setup = {
                "setup": setup,
                "configure": config,
            }

            self._code_changed()

    def _code_changed(self, _=None):
        """Update code settings."""
        with self.hold_trait_notifications():
            if self.inp_code.value is None:
                self.code_setup = {}
                return
            code_setup = self.database[self.inp_domain.value][self.inp_computer.value][
                self.inp_code.value
            ]

            if (
                "label"
                in self.database[self.inp_domain.value][self.inp_computer.value][
                    "computer-setup"
                ]
            ):
                code_setup["computer"] = self.database[self.inp_domain.value][
                    self.inp_computer.value
                ]["computer-setup"]["label"]

            self.code_setup = code_setup

    @tl.default("default_calc_job_plugin")
    def _default_calc_job_plugin(self):
        return None
