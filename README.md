# mc-aiida-widgets

Reusable AiiDA widgets for applications in the AiiDA Lab.

## Usage

Using the widgets usually just involves importing and displaying them.
For demos, have a look at the jupyter notebooks (`.ipynb` extension) in
this folder.

### Structures

Uploading structures
```python
from aiida_widgets import StructureUploadWidget
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
from aiida_widgets import CodeDropdown
from IPython.display import display

# Select from installed codes for 'zeopp.network' input plugin
dropdown = CodeDropdown(input_plugin='zeopp.network')
display(dropdown)

dropdown.selected_code  # returns selected code
```

## License

MIT

## Contact

aiidalab@materialscloud.org
