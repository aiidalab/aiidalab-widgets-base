"""Manage structures stored in the AiiDA database."""
from __future__ import absolute_import
import datetime
from collections import OrderedDict

import ipywidgets as ipw

from aiida.orm import CalcFunctionNode, CalcJobNode, Node, QueryBuilder, WorkChainNode, StructureData


class StructureBrowserWidget(ipw.VBox):
    """Class to query for structures stored in the AiiDA database."""

    def __init__(self):
        # Find all process labels
        qbuilder = QueryBuilder()
        qbuilder.append(WorkChainNode, project="label")
        qbuilder.order_by({WorkChainNode: {'ctime': 'desc'}})
        process_labels = {i[0] for i in qbuilder.all() if i[0]}

        layout = ipw.Layout(width="900px")
        self.mode = ipw.RadioButtons(options=['all', 'uploaded', 'edited', 'calculated'],
                                     layout=ipw.Layout(width="25%"))

        # Date range
        self.dt_now = datetime.datetime.now()
        self.dt_end = self.dt_now - datetime.timedelta(days=10)
        self.date_start = ipw.Text(value='', description='From: ', style={'description_width': '120px'})

        self.date_end = ipw.Text(value='', description='To: ')
        self.date_text = ipw.HTML(value='<p>Select the date range:</p>')
        self.btn_date = ipw.Button(description='Search', layout={'margin': '1em 0 0 0'})
        self.age_selection = ipw.VBox(
            [self.date_text, ipw.HBox([self.date_start, self.date_end]), self.btn_date],
            layout={
                'border': '1px solid #fafafa',
                'padding': '1em'
            })

        # Labels
        self.drop_label = ipw.Dropdown(options=({'All'}.union(process_labels)),
                                       value='All',
                                       description='Process Label',
                                       style={'description_width': '120px'},
                                       layout={'width': '50%'})

        self.btn_date.on_click(self.search)
        self.mode.observe(self.search, names='value')
        self.drop_label.observe(self.search, names='value')

        h_line = ipw.HTML('<hr>')
        box = ipw.VBox([self.age_selection, h_line, ipw.HBox([self.mode, self.drop_label])])

        self.results = ipw.Dropdown(layout=layout)
        self.search()
        super(StructureBrowserWidget, self).__init__([box, h_line, self.results])

    @staticmethod
    def preprocess():
        """Search structures in AiiDA database."""
        queryb = QueryBuilder()
        queryb.append(StructureData, filters={'extras': {'!has_key': 'formula'}})
        for itm in queryb.all():  # iterall() would interfere with set_extra()
            formula = itm[0].get_formula()
            itm[0].set_extra("formula", formula)

    def search(self, change=None):  # pylint: disable=unused-argument
        """Launch the search of structures in AiiDA database."""
        self.preprocess()

        qbuild = QueryBuilder()
        try:  # If the date range is valid, use it for the search
            self.start_date = datetime.datetime.strptime(self.date_start.value, '%Y-%m-%d')
            self.end_date = datetime.datetime.strptime(self.date_end.value, '%Y-%m-%d') + datetime.timedelta(hours=24)
        except ValueError:  # Otherwise revert to the standard (i.e. last 7 days)
            self.start_date = self.dt_end
            self.end_date = self.dt_now + datetime.timedelta(hours=24)

            self.date_start.value = self.start_date.strftime('%Y-%m-%d')
            self.date_end.value = self.end_date.strftime('%Y-%m-%d')

        filters = {}
        filters['ctime'] = {'and': [{'<=': self.end_date}, {'>': self.start_date}]}
        if self.drop_label.value != 'All':
            qbuild.append(WorkChainNode, filters={'label': self.drop_label.value})
            #             print(qbuild.all())
            #             qbuild.append(CalcJobNode, with_incoming=WorkChainNode)
            qbuild.append(StructureData, with_incoming=WorkChainNode, filters=filters)
        else:
            if self.mode.value == "uploaded":
                qbuild2 = QueryBuilder()
                qbuild2.append(StructureData, project=["id"])
                qbuild2.append(Node, with_outgoing=StructureData)
                processed_nodes = [n[0] for n in qbuild2.all()]
                if processed_nodes:
                    filters['id'] = {"!in": processed_nodes}
                qbuild.append(StructureData, filters=filters)

            elif self.mode.value == "calculated":
                qbuild.append(CalcJobNode)
                qbuild.append(StructureData, with_incoming=CalcJobNode, filters=filters)

            elif self.mode.value == "edited":
                qbuild.append(CalcFunctionNode)
                qbuild.append(StructureData, with_incoming=CalcFunctionNode, filters=filters)

            elif self.mode.value == "all":
                qbuild.append(StructureData, filters=filters)

        qbuild.order_by({StructureData: {'ctime': 'desc'}})
        matches = {n[0] for n in qbuild.iterall()}
        matches = sorted(matches, reverse=True, key=lambda n: n.ctime)

        options = OrderedDict()
        options["Select a Structure ({} found)".format(len(matches))] = False

        for mch in matches:
            label = "PK: %d" % mch.pk
            label += " | " + mch.ctime.strftime("%Y-%m-%d %H:%M")
            label += " | " + mch.get_extra("formula")
            label += " | " + mch.description
            options[label] = mch

        self.results.options = options
