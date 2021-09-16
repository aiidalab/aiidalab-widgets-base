"""Start page appearance."""
import ipywidgets as ipw

TEMPLATE = """
<table>
<tr>
  <th style="text-align:center">Codes and computers.</th>
  <th style="width:70px" rowspan=2></th>
  <th style="text-align:center">Processes.</th>
  <th style="width:70px" rowspan=2></th>
  <th style="text-align:center">Electronic Lab Notebook.</th>
<tr>
  <td valign="top"><ul>
    <li><a href="{appbase}/notebooks/setup_computer.ipynb" target="_blank">Setup computer</a></li>
    <li><a href="{appbase}/notebooks/setup_code.ipynb" target="_blank">Setup code</a></li>
  </ul></td>
  <td valign="top"><ul>
    <li><a href="{appbase}/notebooks/process_list.ipynb" target="_blank">Process list</a></li>
    <li><a href="{appbase}/notebooks/process.ipynb" target="_blank">Follow a process</a></li>
  </ul></td>
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
