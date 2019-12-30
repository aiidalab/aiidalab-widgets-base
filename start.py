"""Start page appearance."""
from __future__ import absolute_import
import ipywidgets as ipw

TEMPLATE = """
<table>
<tr>
  <th style="text-align:center">AiiDA lab widgets</th>
  <th style="width:70px" rowspan=2></th>
  <th style="text-align:center"Useful apps</th>
<tr>
  <td valign="top"><ul>
    <li><a href="{appbase}/structures.ipynb" target="_blank">Dealing with one structure</a></li>
    <li><a href="{appbase}/structures_multi.ipynb" target="_blank">Dealing with multiple structures</a></li>
    <li><a href="{appbase}/codes.ipynb" target="_blank">Dealing with codes</a></li>
  </ul></td>
  <td valign="top"><ul>
    <li><a href="{appbase}/setup_computer.ipynb" target="_blank">Setup computer</a></li>
    <li><a href="{appbase}/setup_code.ipynb" target="_blank">Setup code</a></li>
    <li><a href="{appbase}/aiida_datatypes.ipynb" target="_blank">AiiDA datatypes viewers</a></li>
  </ul></td>
</tr>
</table>
"""


def get_start_widget(appbase, jupbase, notebase):
    html = TEMPLATE.format(appbase=appbase, jupbase=jupbase, notebase=notebase)
    return ipw.HTML(html)


#EOF
