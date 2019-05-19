# aiidalab-widgets-base 

Reusable widgets for applications in the AiiDA lab.

## Installation

Install the `aiidalab_widgets_base` python package via:
```
pip install aiidalab-widgets-base 
```

Install the corresponding `aiidalab-widgets-base` AiiDA lab application
via the app manager as usual.

## Usage

Using the widgets usually just involves importing and displaying them.
For demos, have a look at the jupyter notebooks (`.ipynb` extension) in
this folder.

### Structures

Uploading structures
```python
from aiidalab_widgets_base import StructureUploadWidget
from IPython.display import display

widget = StructureUploadWidget()
# Enforce node format to be CifData:
# widget = StructureUploadWidget(node_class='CifData')
display(widget)
```

![Demo](https://image.ibb.co/fjnHco/structure.gif "Using the StructureUploadWidget.")

### Codes

Selecting codes
```python
from aiidalab_widgets_base import CodeDropdown
from IPython.display import display

# Select from installed codes for 'zeopp.network' input plugin
dropdown = CodeDropdown(input_plugin='zeopp.network')
display(dropdown)

dropdown.selected_code  # returns selected code
```

![Demo](https://image.ibb.co/gSFFf8/codes.gif "Using the CodeDropDown.")

## License

MIT

## Contact

aiidalab@materialscloud.org

## Acknowledgements

This work is supported by the [MARVEL National Centre for Competency in Research](<http://nccr-marvel.ch>)
funded by the [Swiss National Science Foundation](<http://www.snf.ch/en>), as well as by the [MaX
European Centre of Excellence](<http://www.max-centre.eu/>) funded by the Horizon 2020 EINFRA-5 program,
Grant No. 676598.

![MARVEL](miscellaneous/logos/MARVEL.png)
![MaX](miscellaneous/logos/MaX.png)
