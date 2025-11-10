import ipywidgets as ipw


class LoadingWidget(ipw.HBox):
    """Widget for displaying a loading spinner."""

    def __init__(self, message="Loading", **kwargs):
        self.message = ipw.Label(message)
        super().__init__(
            children=[
                ipw.Label(message),
                ipw.HTML(
                    value="<i class='fa fa-spinner fa-spin fa-2x fa-fw'/>",
                    layout=ipw.Layout(margin="12px 0 6px"),
                ),
            ],
            layout=ipw.Layout(
                justify_content="center",
                align_items="center",
                **kwargs.pop("layout", {}),
            ),
            **kwargs,
        )
        self.add_class("loading")
