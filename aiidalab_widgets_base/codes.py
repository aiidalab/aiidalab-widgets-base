from __future__ import print_function

from __future__ import absolute_import
import ipywidgets as ipw

from subprocess import check_output
from IPython.display import clear_output

from aiida.orm import Code

VALID_AIIDA_CODE_SETUP_ARGUMETNS = {'label', 'selected_computer', 'plugin', 'description',
                                    'exec_path', 'prepend_text', 'append_text'}

def valid_arguments(arguments, valid_arguments):
    result = {}
    for key, value in arguments.items():
        if key in valid_arguments:
            if type(value) is tuple or type(value) is list:
                result[key] = '\n'.join(value)
            else:
                result[key] = value
    return result

def extract_aiidacodesetup_arguments(arguments):
    return valid_arguments(arguments, VALID_AIIDA_CODE_SETUP_ARGUMETNS)


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

        self.dropdown = ipw.Dropdown(description=text, disabled=True)
        self._btn_refresh = ipw.Button(description="Refresh", layout=ipw.Layout(width="70px"))
        self._btn_refresh.on_click(self.refresh)
        # TODO: use base_url here
        self._setup_another = ipw.HTML(value="""<a href=../aiidalab-widgets-base/setup_code.ipynb target="_blank">Setup new code</a>""")
        self.output = ipw.Output()

        children = [ipw.HBox([self.dropdown, self._btn_refresh, self._setup_another]),
                    self.output]

        super(CodeDropdown, self).__init__(children=children, **kwargs)

        self.refresh()

    def _get_codes(self, input_plugin):
        from aiida.orm.querybuilder import QueryBuilder
        from aiida.backends.utils import get_automatic_user
        from aiida.orm import Computer
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

    def refresh(self, b=None):
        with self.output:
            clear_output()
            self.codes = self._get_codes(self.input_plugin)
            options = list(self.codes.keys())

            self.dropdown.options = options

            if not options:
                print("No codes found for input plugin '{}'.".format(
                    self.input_plugin))
                self.dropdown.disabled = True
            else:
                self.dropdown.disabled = False

    @property
    def selected_code(self):
        try:
            return self.codes[self.dropdown.value]
        except KeyError:
            return None

class AiiDACodeSetup(ipw.VBox):
    """Class that allows to setup AiiDA code"""
    def __init__(self, **kwargs):
        from aiida.common.pluginloader import all_plugins
        from aiidalab_widgets_base.computers import ComputerDropdown

        style = {"description_width":"200px"}

        # list of widgets to be displayed

        self._inp_code_label = ipw.Text(description="AiiDA code label:",
                                       layout=ipw.Layout(width="500px"),
                                       style=style)

        self._computer = ComputerDropdown(layout={'margin': '0px 0px 0px 125px'})

        self._inp_code_description = ipw.Text(placeholder='No description (yet)',
                                              description="Code description:",
                                              layout=ipw.Layout(width="500px"),
                                              style=style)

        self._inp_code_plugin = ipw.Dropdown(options=sorted(all_plugins('calculations')),
                                             description="Code plugin:",
                                             layout=ipw.Layout(width="500px"),
                                             style=style)

        self._exec_path = ipw.Text(placeholder='/path/to/executable',
                                   description="Absolute path to executable:",
                                   layout=ipw.Layout(width="500px"),
                                   style=style)

        self._prepend_text = ipw.Textarea(placeholder='Text to prepend to each command execution',
                                          description='Prepend text:',
                                          layout=ipw.Layout(width="400px"))

        self._append_text = ipw.Textarea(placeholder='Text to append to each command execution',
                                         description='Append text:',
                                         layout=ipw.Layout(width="400px"))

        self._btn_setup_code = ipw.Button(description="Setup code")
        self._btn_setup_code.on_click(self._setup_code)
        self._setup_code_out = ipw.Output()
        children = [ipw.HBox([ipw.VBox([self._inp_code_label,
                                        self._computer,
                                        self._inp_code_plugin,
                                        self._inp_code_description,
                                        self._exec_path]), ipw.VBox([self._prepend_text,
                                                                     self._append_text])]),
                    self._btn_setup_code,
                    self._setup_code_out,
                   ]
        # Check if some settings were already provided
        self._predefine_settings(**kwargs)
        super(AiiDACodeSetup, self).__init__(children, **kwargs)

    def _predefine_settings(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError("'{}' object has no attribute '{}'".format(self, key))

    def _setup_code(self, b=None):
        with self._setup_code_out:
            clear_output()
            if self.label is None:
                print("You did not specify code label")
                return
            if not self.exec_path:
                print("You did not specify absolute path to the executable")
                return
            if self.exists():
                print ("Code {}@{} already exists".format(self.label, self.selected_computer.name))
                return
            code = Code(remote_computer_exec=(self.selected_computer, self.exec_path))
            code.label = self.label
            code.description = self.description
            code.set_input_plugin_name(self.plugin)
            code.set_prepend_text(self.prepend_text)
            code.set_append_text(self.append_text)
            code.store()
            code._reveal()
            full_string = "{}@{}".format(self.label, self.selected_computer.name)
            print(check_output(['verdi', 'code', 'show', full_string]))

    def exists(self):
        from aiida.common.exceptions import NotExistent, MultipleObjectsError
        try:
            Code.get_from_string("{}@{}".format(self.label, self.selected_computer.name))
            return True
        except MultipleObjectsError:
            return True
        except NotExistent:
            return False

    @property
    def label(self):
        if len(self._inp_code_label.value.strip()) == 0:
            return None
        else:
            return self._inp_code_label.value

    @label.setter
    def label(self, label):
        self._inp_code_label.value = label

    @property
    def description(self):
        return self._inp_code_description.value

    @description.setter
    def description(self, description):
        self._inp_code_description.value = description

    @property
    def plugin(self):
        return self._inp_code_plugin.value

    @plugin.setter
    def plugin(self, plugin):
        if plugin in self._inp_code_plugin.options:
            self._inp_code_plugin.value = plugin

    @property
    def exec_path(self):
        return self._exec_path.value

    @exec_path.setter
    def exec_path(self, exec_path):
        self._exec_path.value = exec_path

    @property
    def prepend_text(self):
        return self._prepend_text.value

    @prepend_text.setter
    def prepend_text(self, prepend_text):
        self._prepend_text.value = prepend_text

    @property
    def append_text(self):
        return self._append_text.value

    @append_text.setter
    def append_text(self, append_text):
        self._append_text.value = append_text

    @property
    def selected_computer(self):
        return self._computer.selected_computer

    @selected_computer.setter
    def selected_computer(self, selected_computer):
        self._computer.selected_computer = selected_computer
