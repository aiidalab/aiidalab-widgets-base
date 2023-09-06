"""Widgets that allow to query online databases."""
import ase
import ipywidgets as ipw
import requests
import traitlets as tl


class CodQueryWidget(ipw.VBox):
    """Query structures in Crystallography Open Database (COD)
    Useful class members:
    :ivar structure(Atoms): trait that contains the selected structure, None if structure is not selected.
    """

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
        from aiida.tools.dbimporters.plugins.cod import CodDbImporter

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

    def __init__(
        self,
        embedded: bool = True,
        title: str = None,
        **kwargs,
    ) -> None:
        from optimade_client import default_parameters, query_filter, query_provider

        providers_header = ipw.HTML("<h4>Select a provider</h4>")
        providers = query_provider.OptimadeQueryProviderWidget(
            embedded=embedded,
            width_ratio=kwargs.pop("width_ratio", None),
            width_space=kwargs.pop("width_space", None),
            database_limit=kwargs.pop("database_limit", None),
            disable_providers=kwargs.pop(
                "disable_providers", default_parameters.DISABLE_PROVIDERS
            ),
            skip_databases=kwargs.pop(
                "skip_databases", default_parameters.SKIP_DATABASE
            ),
            skip_providers=kwargs.pop(
                "skip_providers", default_parameters.SKIP_DATABASE
            ),
            provider_database_groupings=kwargs.pop(
                "provider_database_groupings",
                default_parameters.PROVIDER_DATABASE_GROUPINGS,
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
            disabled=False,
        )
        self.inp_computer.observe(self._computer_changed, names=["value", "options"])

        # Select code.
        self.inp_code = ipw.Dropdown(
            options=[],
            description="Code:",
            disabled=False,
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


class NewComputationalResourcesDatabaseWidget(ipw.VBox):
    """Extract the setup of a known computer from the AiiDA code registry."""

    _default_database_source = (
        "https://aiidateam.github.io/aiida-resource-registry/database.json"
    )

    database_source = tl.Unicode(allow_none=True)

    ssh_config = tl.Dict()
    computer_setup = tl.Dict()
    code_setup = tl.Dict()

    def __init__(self, default_calc_job_plugin=None, database_source=None, **kwargs):
        if database_source is None:
            database_source = self._default_database_source

        self.default_calc_job_plugin = default_calc_job_plugin

        # Select domain.
        self.domain_selector = ipw.Dropdown(
            options=(),
            description="Domain",
            disabled=False,
        )
        self.domain_selector.observe(self._domain_changed, names=["value", "options"])

        # Select computer.
        self.computer_selector = ipw.Dropdown(
            options=(),
            description="Computer:",
            disabled=False,
        )
        self.computer_selector.observe(
            self._computer_changed, names=["value", "options"]
        )

        # Select code.
        self.code_selector = ipw.Dropdown(
            options=(),
            description="Code:",
            disabled=False,
        )
        self.code_selector.observe(self._code_changed, names=["value", "options"])

        reset_button = ipw.Button(description="Reset")
        reset_button.on_click(self.reset)

        super().__init__(
            children=[
                self.domain_selector,
                self.computer_selector,
                self.code_selector,
                reset_button,
            ],
            **kwargs,
        )
        self.database_source = database_source
        self.reset()

    def reset(self, _=None):
        """Reset widget and traits"""
        with self.hold_trait_notifications():
            self.domain_selector.value = None
            self.computer_selector.value = None
            self.code_selector.value = None

    @tl.observe("database_source")
    def _database_source_changed(self, _=None):
        self.database = self._database_generator(
            self.database_source, self.default_calc_job_plugin
        )

        # Update domain selector.
        self.domain_selector.options = self.database.keys()
        self.reset()

    @staticmethod
    def _calc_job_plugin_match(plugin, default_plugin):
        """Check if plugin entry point read from database (may have jinja2 template included)
        matches default plugin
        """
        # Replace jinja2 template with regex
        import re

        plugin = re.sub(r"\{\{.*\}\}", r".*", plugin)
        return re.match(plugin, default_plugin) is not None

    def _database_generator(self, database_source, default_calc_job_plugin):
        """From database source JSON and default calc job plugin, generate resource database"""
        try:
            database = requests.get(database_source).json()
        except Exception:
            database = {}

        if default_calc_job_plugin is None:
            return database

        # filter database by default calc job plugin
        for domain, domain_value in database.copy().items():
            for computer, computer_value in domain_value.copy().items():
                if computer == "default":
                    # skip default computer
                    continue

                for code, code_value in list(computer_value["codes"].items()):
                    # if code_value["default_calc_job_plugin"] != default_calc_job_plugin:
                    if not self._calc_job_plugin_match(
                        code_value["default_calc_job_plugin"], default_calc_job_plugin
                    ):
                        # remove code
                        del computer_value["codes"][code]

                if len(computer_value["codes"]) == 0:
                    # remove computer since no codes defined in this computer source
                    del domain_value[computer]
                    if domain_value.get("default") == computer:
                        # also remove default computer from domain
                        del domain_value["default"]

            if len(domain_value) == 0:
                # remove domain since no computers with required codes defined in this domain source
                del database[domain]
                continue

            if domain_value["default"] not in domain_value:
                # make sure default computer is still points to existing computer
                domain_value["default"] = sorted(domain_value.keys() - {"default"})[0]

        return database

    def _domain_changed(self, change=None):
        """callback when new domain selected"""
        with self.hold_trait_notifications():  # To prevent multiple calls to callbacks
            if change["new"] is None:
                self.computer_selector.options = ()
                self.computer_selector.value = None
                self.code_selector.options = ()
                self.code_selector.value = None
                return
            else:
                selected_domain = self.domain_selector.value

            with self.hold_trait_notifications():
                try:
                    self.computer_selector.options = tuple(
                        key
                        for key in self.database[selected_domain].keys()
                        if key != "default"
                    )
                    self.computer_selector.value = self.database[selected_domain][
                        "default"
                    ]
                except KeyError:
                    raise

    def _computer_changed(self, change=None):
        """callback when new computer selected"""
        with self.hold_trait_notifications():
            if change["new"] is None:
                self.code_selector.options = ()
                self.code_selector.value = None
                self.computer_setup = {}
                self.ssh_config = {}
                return
            else:
                self.code_selector.value = None
                selected_computer = self.computer_selector.value

            selected_domain = self.domain_selector.value

            computer_dict = self.database.get(selected_domain, {}).get(
                selected_computer, {}
            )

            try:
                self.code_selector.options = list(computer_dict.get("codes", {}).keys())
                self.code_selector.value = None
            except KeyError:
                raise

            computer_setup = computer_dict.get("computer", {}).get("computer-setup", {})
            computer_configure = computer_dict.get("computer", {}).get(
                "computer-configure", {}
            )

            # To avoid {'setup': {}, 'configure': {}} when no computer setup is defined
            if computer_setup == {} and computer_configure == {}:
                self.computer_setup = {}
                self.ssh_config = {}
                return

            ssh_config = {"hostname": computer_setup.get("hostname")}
            if "proxy_command" in computer_configure:
                ssh_config["proxy_command"] = computer_configure["proxy_command"]
            if "proxy_jump" in computer_configure:
                ssh_config["proxy_jump"] = computer_configure["proxy_jump"]

            self.ssh_config = ssh_config  # To notify the trait change

            self.computer_setup = {
                "setup": computer_setup,
                "configure": computer_configure,
            }

    def _code_changed(self, change=None):
        """Update code settings."""
        if change["new"] is None:
            self.code_setup = {}
            return
        else:
            selected_code = self.code_selector.value

        selected_domain = self.domain_selector.value
        selected_computer = self.computer_selector.value

        try:
            self.code_setup = (
                self.database.get(selected_domain, {})
                .get(selected_computer, {})
                .get("codes", {})
                .get(selected_code, {})
            )
        except KeyError:
            raise
