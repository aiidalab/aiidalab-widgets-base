[![Documentation Status](https://readthedocs.org/projects/aiidalab-widgets-base/badge/?version=latest)](https://aiidalab-widgets-base.readthedocs.io/en/latest/?badge=latest)
[![codecov](https://codecov.io/gh/aiidalab/aiidalab-widgets-base/branch/master/graph/badge.svg)](https://codecov.io/gh/aiidalab/aiidalab-widgets-base)

# AiiDAlab Widgets

[AiiDAlab](https://www.aiidalab.net/) applications typically involve some of following steps:

 * Prepare the input for a calculation (e.g. an atomic structure).
 * Select computational resources and submit a calculation to AiiDA.
 * Monitor a running calculation.
 * Find and analyze the results of a calculation.

The AiiDAlab widgets help with these common tasks.

## Documentation

Hosted on [aiidalab-widgets-base.readthedocs.io](https://aiidalab-widgets-base.readthedocs.io).

## For maintainers

To create a new release, clone the repository, install development dependencies with `pip install -e '.[dev]'`, and then execute `bumpver update [--major|--minor|--patch] [--tag-num --tag [alpha|beta|rc]]`.
This will:

  1. Create a tagged release with bumped version and push it to the repository.
  2. Trigger a GitHub actions workflow that creates a GitHub release and publishes it on PyPI.

Additional notes:

  - Use the `--dry` option to preview the release change.
  - The release tag (e.g. a/b/rc) is determined from the last release.
    Use the `--tag` option to switch the release tag.
  - This package follows [semantic versioning](https://semver.org/).

## License

MIT

## Citation

Users of AiiDAlab are kindly asked to cite the following publication in their own work:

A. V. Yakutovich et al., Comp. Mat. Sci. 188, 110165 (2021).
[DOI:10.1016/j.commatsci.2020.110165](https://doi.org/10.1016/j.commatsci.2020.110165)

## Contact

aiidalab@materialscloud.org

## Acknowledgements

This work is supported by the [MARVEL National Centre for Competency in Research](<https://nccr-marvel.ch>)
funded by the [Swiss National Science Foundation](<https://www.snf.ch/en>), as well as by the [MaX
European Centre of Excellence](<http://www.max-centre.eu/>) funded by the Horizon 2020 EINFRA-5 program,
Grant No. 676598.

![MARVEL](miscellaneous/logos/MARVEL.png)
![MaX](miscellaneous/logos/MaX.png)
