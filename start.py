"""Start page appearance."""

import ipywidgets as ipw

TEMPLATE = """
<table>
<tr>
  <th style="text-align:center">Electronic Lab Notebook.</th>
<tr>
  <td valign="top"><ul>
    <li><a href="{appbase}/notebooks/eln_configure.ipynb" target="_blank">Configure ELN</a></li>
  </ul></td>
</tr>
</table>
"""


def get_start_widget(appbase, jupbase, notebase):
    html = TEMPLATE.format(appbase=appbase, jupbase=jupbase, notebase=notebase)
    return ipw.HTML(html)


# EOF
