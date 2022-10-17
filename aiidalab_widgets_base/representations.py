import traitlets
import ipywidgets as ipw
from IPython.display import clear_output
import aiidalab_widgets_base as awb

STYLE = {'description_width': '100px'}
BOX_LAYOUT = ipw.Layout(display='flex-wrap', flex_flow='row wrap', justify_content='space-between')

class Representation(ipw.HBox):
    master_class = None
    def __init__(self, indices="1..2", name="no-name"):
        self.label = ipw.HTML("<b>Rep</b>")
        self.selection = ipw.Text(description="atoms:",value="",style={"description_width": "initial"} )
        self.style = ipw.Dropdown(options=["molecule","surface"],value="molecule",description="mode",disabled=False)
        #self.show =  ipw.Checkbox(description="show",value=True,disabled=False,indent=False)
        #self.name = ipw.Text(description="Name", value=name, style=STYLE)

        #ipw.dlink((self.name, "value"), (self.label, "value"), transform=lambda x: f"<b>Fragment: {x}</b>")

        #self.output = ipw.Output()

        # Delete button.
        self.delete_button = ipw.Button(description="Delete", button_style="danger")
        self.delete_button.on_click(self.delete_myself)


        super().__init__(
            children=[
                self.label,
                ipw.HTML("<hr>"),
                self.selection,
                self.style,
                #self.show,
                self.delete_button,
            ]
            )

    #@traitlets.observe("uks")
    #def _observe_uks(self, change):
    #    with self.output:
    #        clear_output()
    #        if change['new']:
    #            display(ipw.VBox([self.multiplicity]))
    
    def delete_myself(self, _):
        self.master_class.delete_representation(self)


class RepresentationList(ipw.VBox):
    representations = traitlets.List()
    #selection_string = traitlets.Unicode()

    def __init__(self):
        # Fragment selection.
        self.new_representation_name = ipw.Text(value='', description='Rep name', style={"description_width": "initial"})
        self.add_new_rep_button = ipw.Button(description="Add rep", button_style="info")
        self.add_new_rep_button.on_click(self.add_representation)

        # Outputs.
        #self.fragment_add_message = awb.utils.StatusHTML()
        self.representation_output = ipw.Box(layout=BOX_LAYOUT)
        super().__init__(children=[ipw.HBox([self.new_representation_name, self.add_new_rep_button])])#, self.fragment_add_message, self.fragment_output])


        self.representation_output.children = self.representations

    def add_representation(self, _):
        """Add a representation to the list of representations."""

        self.representations = self.representations + [Representation()]
        self.new_representation_name.value = ''
    
    def delete_representation(self, representation):
        try:
            index = self.representations.index(representation)
        except ValueError:
            self.representation_add_message.message = f"""<span style="color:red">Error:</span> Fragment {representation} not found."""
            return

        self.representation_add_message.message = f"""<span style="color:blue">Info:</span> Removing {representation.name.value} ({representation.indices.value}) from the fragment list."""
        self.representations = self.representations[:index] + self.representations[index+1:]
        del representation
    
    @traitlets.observe("representations")
    def _observe_representations(self, change):
        """Update the list of representations."""
        if change['new']:
            self.representation_output.children = change["new"]
            self.representations[-1].master_class = self
        else:
            self.representation_output.children = []
    
