import datetime
import ipywidgets as ipw
from collections import OrderedDict

from aiida.orm import CalcFunctionNode, CalcJobNode, Node, QueryBuilder, WorkChainNode, StructureData

class StructureBrowserWidget(ipw.VBox):
    
    def __init__(self):
        # Find all process labels
        qb = QueryBuilder()
        qb.append(WorkChainNode, project="label")
        qb.order_by({WorkChainNode:{'ctime':'desc'}})
        process_labels = {i[0] for i in qb.all() if i[0]}

        layout = ipw.Layout(width="900px")
        self.mode = ipw.RadioButtons(options=['all', 'uploaded', 'edited', 'calculated'],
                                     layout=ipw.Layout(width="25%"))
        
        
        # Date range
        self.dt_now = datetime.datetime.now()
        self.dt_end = self.dt_now - datetime.timedelta(days=10)
        self.date_start = ipw.Text(value='',
                                   description='From: ',
                                   style={'description_width': '120px'})

        self.date_end = ipw.Text(value='', description='To: ')
        self.date_text = ipw.HTML(value='<p>Select the date range:</p>')
        self.btn_date = ipw.Button(description='Search', layout={'margin': '1em 0 0 0'})
        self.age_selection = ipw.VBox([self.date_text, ipw.HBox([self.date_start, self.date_end]), self.btn_date],
                                      layout={'border': '1px solid #fafafa', 'padding': '1em'})

        # Labels
        self.drop_label = ipw.Dropdown(options=({'All'}.union(process_labels)),
                                       value='All',
                                       description='Process Label',
                                       style = {'description_width': '120px'},
                                       layout={'width': '50%'})

        self.btn_date.on_click(self.search)
        self.mode.observe(self.search, names='value')
        self.drop_label.observe(self.search, names='value')
        
        hr = ipw.HTML('<hr>')
        box = ipw.VBox([self.age_selection,
                        hr,
                        ipw.HBox([self.mode, self.drop_label])])
        
        self.results = ipw.Dropdown(layout=layout)
        self.search()
        super(StructureBrowser, self).__init__([box, hr, self.results])
    
    
    def preprocess(self):
        qb = QueryBuilder()
        qb.append(StructureData, filters={'extras': {'!has_key': 'formula'}})
        for n in qb.all(): # iterall() would interfere with set_extra()
            formula = n[0].get_formula()
            n[0].set_extra("formula", formula)

    
    def search(self, c=None):
        self.preprocess()
        
        qb = QueryBuilder()
        try: # If the date range is valid, use it for the search
            self.start_date = datetime.datetime.strptime(self.date_start.value, '%Y-%m-%d')
            self.end_date = datetime.datetime.strptime(self.date_end.value, '%Y-%m-%d') + datetime.timedelta(hours=24)
        except ValueError: # Otherwise revert to the standard (i.e. last 7 days)
            self.start_date = self.dt_end
            self.end_date = self.dt_now + datetime.timedelta(hours=24)

            self.date_start.value = self.start_date.strftime('%Y-%m-%d')
            self.date_end.value = self.end_date.strftime('%Y-%m-%d')

        filters = {}
        filters['ctime'] = {'and':[{'<=': self.end_date},{'>': self.start_date}]}        
        if self.drop_label.value != 'All':
            qb.append(WorkChainNode, filters={'label': self.drop_label.value})
#             print(qb.all())
#             qb.append(CalcJobNode, with_incoming=WorkChainNode)
            qb.append(StructureData, with_incoming=WorkChainNode, filters=filters)
        else:        
            if self.mode.value == "uploaded":
                qb2 = QueryBuilder()
                qb2.append(StructureData, project=["id"])
                qb2.append(Node, with_outgoing=StructureData)
                processed_nodes = [n[0] for n in qb2.all()]
                if processed_nodes:
                    filters['id'] = {"!in":processed_nodes}
                qb.append(StructureData, filters=filters)

            elif self.mode.value == "calculated":
                qb.append(CalcJobNode)
                qb.append(StructureData, with_incoming=CalcJobNode, filters=filters)

            elif self.mode.value == "edited":
                qb.append(CalcFunctionNode)
                qb.append(StructureData, with_incoming=CalcFunctionNode, filters=filters)

            else:
                self.mode.value == "all"
                qb.append(StructureData, filters=filters)

        qb.order_by({StructureData:{'ctime':'desc'}})
        matches = set([n[0] for n in qb.iterall()])
        matches = sorted(matches, reverse=True, key=lambda n: n.ctime)
        
        c = len(matches)
        options = OrderedDict()
        options["Select a Structure (%d found)"%c] = False

        for n in matches:
            label  = "PK: %d" % n.pk
            label += " | " + n.ctime.strftime("%Y-%m-%d %H:%M")
            label += " | " + n.get_extra("formula")
            label += " | " + n.description
            options[label] = n

        self.results.options = options
