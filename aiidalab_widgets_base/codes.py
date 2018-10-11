from __future__ import print_function

import ipywidgets as ipw
from IPython.display import clear_output


class CodeDropdown(ipw.VBox):
    def __init__(self, input_plugin, text='Select code:', **kwargs):
        """ Dropdown for Codes for one input plugin.

        :param input_plugin: Input plugin of codes to show
        :type input_plugin: str
        :param text: Text to display before dropdown
        :type text: str
        """

        self.input_plugin = input_plugin
        self.codes = {}

        self.label = ipw.Label(value=text)
        self.dropdown = ipw.Dropdown(options=[], disabled=True)
        self.output = ipw.Output()

        children = [ipw.HBox([self.label, self.dropdown, self.output])]

        super(CodeDropdown, self).__init__(children=children, **kwargs)

        from aiida import load_dbenv, is_dbenv_loaded
        from aiida.backends import settings
        if not is_dbenv_loaded():
            load_dbenv(profile=settings.AIIDADB_PROFILE)
        self.refresh()

    def _get_codes(self, input_plugin):
        from aiida.orm.querybuilder import QueryBuilder
        from aiida.orm import Code, Computer
        from aiida.backends.utils import get_automatic_user

        current_user = get_automatic_user()

        qb = QueryBuilder()
        qb.append(
            Computer, filters={'enabled': True}, project=['*'], tag='computer')
        qb.append(
            Code,
            filters={
                'attributes.input_plugin': {
                    '==': input_plugin
                },
                'extras.hidden': {
                    "~==": True
                }
            },
            project=['*'],
            has_computer='computer')
        results = qb.all()

        # only codes on computers configured for the current user
        results = [r for r in results if r[0].is_user_configured(current_user)]

        codes = {"{}@{}".format(r[1].label, r[0].name): r[1] for r in results}
        return codes

    def refresh(self):
        with self.output:
            clear_output()
            self.codes = self._get_codes(self.input_plugin)
            options = self.codes.keys()

            self.dropdown.options = options

            if not options:
                print("No codes found for input plugin '{}'.".format(
                    self.input_plugin))
                self.dropdown.disabled = True
            else:
                self.dropdown.disabled = False

    @property
    def selected_code(self):
        return self.codes[self.dropdown.value]
