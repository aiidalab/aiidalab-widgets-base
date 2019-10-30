"""Setup metadata for an AiiDA process."""
from __future__ import print_function
from __future__ import absolute_import

import ipywidgets as ipw
STYLE = {'description_width': '120px'}
LAYOUT = {'width': '70%'}


class MetadataWidget(ipw.VBox):
    """Setup metadata for an AiiDA process."""

    def __init__(self):
        """ Metadata widget to generate metadata"""

        self.walltime_d = ipw.IntText(value=0,
                                      description='d:',
                                      style={'description_width': 'initial'},
                                      layout={'width': '30%'})
        self.walltime_h = ipw.IntText(value=24,
                                      description='h:',
                                      style={'description_width': 'initial'},
                                      layout={'width': '30%'})
        self.walltime_m = ipw.IntText(value=0,
                                      description='m:',
                                      style={'description_width': 'initial'},
                                      layout={'width': '30%'})

        self.process_description = ipw.Text(description='Process description: ',
                                            placeholder='Type the name here.',
                                            style=STYLE,
                                            layout=LAYOUT)

        self.num_machines = ipw.IntText(value=1, description='# Nodes', style=STYLE, layout=LAYOUT)

        self.num_mpiprocs_per_machine = ipw.IntText(value=12, description='# Tasks', style=STYLE, layout=LAYOUT)

        self.num_cores_per_mpiproc = ipw.IntText(value=1, description='# Threads', style=STYLE, layout=LAYOUT)

        children = [
            self.process_description, self.num_machines, self.num_mpiprocs_per_machine, self.num_cores_per_mpiproc,
            ipw.HBox([ipw.HTML("walltime:"), self.walltime_d, self.walltime_h, self.walltime_m])
        ]

        super(MetadataWidget, self).__init__(children=children)
        ### ---------------------------------------------------------

    @property
    def dict(self):
        return {
            "description": self.process_description.value,
            "options": {
                "resources": {
                    "num_machines": self.num_machines.value,
                    "num_mpiprocs_per_machine": self.num_mpiprocs_per_machine.value,
                    "num_cores_per_mpiproc": self.num_cores_per_mpiproc.value,
                },
                "max_wallclock_seconds":
                    int(self.walltime_d.value * 3600 * 24 + self.walltime_h.value * 3600 + self.walltime_m.value * 60),
                'withmpi':
                    True,
            }
        }
