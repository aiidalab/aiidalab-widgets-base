# CHANGELOG

## v2.5.1 - 2026-06-03

### Bug fixes 🐛
* fix bug if No symmetry from spglib by @cpignedoli in https://github.com/aiidalab/aiidalab-widgets-base/pull/713
* Fix AiidaNodeViewer not resetting when assigned None by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/754
* Fix OptimadeQueryWidget crash by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/759
* [Clear stale bond shapes from structure viewer (](https://github.com/aiidalab/aiidalab-widgets-base/commit/cad2c6c2c949c5a9879299ff6febd61b4665aee2)https://github.com/aiidalab/aiidalab-widgets-base/pull/746[)](https://github.com/aiidalab/aiidalab-widgets-base/commit/cad2c6c2c949c5a9879299ff6febd61b4665aee2)

### Other changes
* Fix CI: Pin RabbitMQ version and update requests-cache by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/743
* Pin numpy to 1.x due to bokeh incompatibility by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/740
* Temporarily skip test_cod_query_widget if it fails by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/723
* [Bump minimum ansi2html version to fix failing tests](https://github.com/aiidalab/aiidalab-widgets-base/commit/621add79c56df9774ab8e2743445341067c6a639)

**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.5.0...v2.5.1

## v2.5.0 - 2025-12-19


### Breaking Changes 🛠
* Remove private key upload functionality by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/690

We've removed the functionality to upload private SSH keys due to (obvious) security concerns.
Users who know what they're doing can still upload arbitrary files via File Manager accessible from the Home app.

### New Features 🎉
* Update StructureViewer units by @mikibonacci in https://github.com/aiidalab/aiidalab-widgets-base/pull/694

### Bug fixes 🐛
* Fix password input by @superstar54 in https://github.com/aiidalab/aiidalab-widgets-base/pull/692
* Fix typo in bug report by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/702
* Fix `ipyoptimade` version by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/703

### Documentation 📝
* Document the SSH setup widget by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/695

### Other Changes
* Pin ipython version to <9.0 by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/700
* Test aiida 2.7 by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/698
* CI: Use uv to test with lowest supported dependency versions by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/714


**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.4.0...v2.5.0

## v2.4.0 - 2025-02-26
* Implement `LoadingWidget` by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/685
* Implement caching in `AiidaNodeViewWidget` by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/686


## v2.3.2 - 2025-02-12


* Wrap structure importers in accordion panel by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/683

**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.3.1...v2.3.2

## v2.3.1 - 2025-02-11


* Fix issue with `StructureManager` when no editor is provided by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/681


**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.3.0...v2.3.1

## v2.3.0 - 2025-02-10


### Breaking Changes 🛠
* Make ELN widgets optional by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/609

### New Features 🎉
* Adding support for `orm.Containerized` codes by @mikibonacci in https://github.com/aiidalab/aiidalab-widgets-base/pull/617
* Add `static` folder for static files and pre-loaded stylesheets (using new utility) by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/624
* Allow user to hide the header of the Wizard App by @superstar54 in https://github.com/aiidalab/aiidalab-widgets-base/pull/638
* Make the setup new codes widget part of the code selection widget optional by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/646
* Add volume information in the cell tab by @superstar54 in https://github.com/aiidalab/aiidalab-widgets-base/pull/653
* Tag structure manager and viewer with CSS classes for easy styling by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/662
* Fix typo in structure editor by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/665
* Clarify structure operations by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/666
* Accept an optional logging `Output` widget for logging monitor exceptions by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/669

### Bug fixes 🐛
* Avoid black sphere in structure viewer by @superstar54 in https://github.com/aiidalab/aiidalab-widgets-base/pull/637
* Guard against null process states by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/658
* Fix resource setup widget bugs by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/661
* Use tmpdir for povray rendering by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/675
* Replace check of empty string in unfilled template widgets to `None` by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/650

### Documentation 📝
* Speedup readthedocs build with uv by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/604
* Hide private methods in API documentation by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/607

### Other Changes
* Test with aiida-core=2.5 by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/599
* CI fix: Test on push to master branch, not main! by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/611
* CI: Don't track coverage of tests/ by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/614
* Support and test with py3.11 by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/619
* Make auto-generated release notes nicer by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/618
* deps: Vendor more_itertools.consecutive_groups by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/613
* Various dependency fixes by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/621
* Fix warnings in pytest by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/628
* Downgrade minimum traitlets version to 5.4 by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/629
* Fix notebook tests by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/630
* Test with aiida 2.6.2 by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/616
* Silence warning by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/647
* Fix capitalization in basic editor by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/654
* Update structure manager editor title casing by @edan-bainglass in https://github.com/aiidalab/aiidalab-widgets-base/pull/655
* Update uv in RTD config by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/660
* CI: Pin Ubuntu version to fix Firefox installation by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/673
* Remove sklearn dependency. by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/671
* Unpin ASE, fix test by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/627
* Add ipython as a direct dependency by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/678

## New Contributors
* @mikibonacci made their first contribution in https://github.com/aiidalab/aiidalab-widgets-base/pull/617
* @edan-bainglass made their first contribution in https://github.com/aiidalab/aiidalab-widgets-base/pull/624

**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.2.2...v2.3.0

## v2.2.3 - 2025-02-06This patch release brings in Support for Python 3.11 to 2.2.x release branch.


* Backport to 2.2.x: Support and test with py3.11 (#619) by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/642


**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.2.2...v2.2.3

## v2.2.2 - 2024-05-15
* Fix handling of default computer in `ComputationalResourcesDatabaseWidget` by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/601


**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.2.1...v2.2.2

## v2.2.1 - 2024-05-04

This is a purely bugfix release.

* remove underscore in function call by @AndresOrtegaGuerrero in https://github.com/aiidalab/aiidalab-widgets-base/pull/597
* Run test publish workflow on push to release/ branches by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/594


**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.2.0...v2.2.1

## v2.2.0 - 2024-04-30

### New features
* Build NodeTree on demand by @superstar54 in https://github.com/aiidalab/aiidalab-widgets-base/pull/583
* Allow registering different viewers for different WorkChains. by @superstar54 in https://github.com/aiidalab/aiidalab-widgets-base/pull/541

### Breaking changes
* Move optimade dependency as extra dependency by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/554
* Drop support for py38 by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/557

### Bug fixes
* Fix download of binary files in FolderDataViewer by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/579
* mimic the behavior of nglview and update the cell and positions by @superstar54 in https://github.com/aiidalab/aiidalab-widgets-base/pull/576

### Devops
* Update dev dependencies by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/556
* Remove deprecated load_documentation_profile for doc build by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/555
* Add test to latest and oldest supported aiida-core by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/558
* Replace optimade-client with ipyoptimade by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/553
* Add Dependabot config for updating GHAs by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/560
* Bump the gha-dependencies group with 6 updates by @dependabot in https://github.com/aiidalab/aiidalab-widgets-base/pull/561
* Remove obsolete files by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/562
* Use Ruff by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/566
* CI: Add CODECOV_TOKEN secret by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/569
* New release workflow by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/570
* Only trigger publish on release.published event by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/572
* CI: Use uv installer instead of pip (take 2) by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/578
* Bump uv + minor CI cleanups by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/573
* [pre-commit.ci] pre-commit autoupdate by @pre-commit-ci in https://github.com/aiidalab/aiidalab-widgets-base/pull/580
* Add pandas as direct dependency by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/589

## New Contributors
* @dependabot made their first contribution in https://github.com/aiidalab/aiidalab-widgets-base/pull/561

**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.1.0...v2.2.0

## v2.1.0 - 2024-01-22

### New features and improvements :hammer:
* Implement viewer representations by @cpignedoli in https://github.com/aiidalab/aiidalab-widgets-base/pull/373
* Enhance cell editor by @superstar54 in https://github.com/aiidalab/aiidalab-widgets-base/pull/372
* Draw bonds computed by ASE by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/535
* allow structures with different periodicity, add periodicity by @AndresOrtegaGuerrero in https://github.com/aiidalab/aiidalab-widgets-base/pull/488
* StructureViewer: Print 3 decimal places for distance and angles by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/495
* Structure download section: add `extxyz` and `xsf` formats by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/501
* SmilesWidget: Canonicalize SMILES code by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/507
* Improve generation of tough SMILES by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/517
* Template resources setting by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/511
* App loading speed improvements:
    * Lazy import optimade_client by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/496
    * Bump traitlets to v5.9 by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/526

### Bug fixes :bug:
* Computer setup: Fix core.local transport by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/502
* `CompResourcesWidget`: do not raise when computer test fails by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/506
* Fix .ssh/config file not being closed by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/513
* Fix threading issue when accessing user instance in _get_codes of ComputationalResourceWidgets by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/543

### Documentation :memo:
* DOC: re-strucuture the doc folder by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/514
* Extend documentation for the viewers module. by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/515

### Devops

* [pre-commit.ci] pre-commit autoupdate by @pre-commit-ci in https://github.com/aiidalab/aiidalab-widgets-base/pull/494
* Bump scikit-learn by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/498
* Make notebook tests less flaky by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/497
* Add the concurrency setup to CI workflow by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/503
* Remove leftover load profile by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/481
* StructureViewer Download tab: pass file format explicitly by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/504
* Get rid of deprecation warnings in computational_resources.py by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/508
* Fix Warning coming from ProcessFollowerWidget by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/512
* Remove openbabel dependency by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/518
* Use mock home and monkeypatch ssh parser for ssh config testing by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/523
* [pre-commit.ci] pre-commit autoupdate by @pre-commit-ci in https://github.com/aiidalab/aiidalab-widgets-base/pull/520
* Remove warnings in unit tests by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/509
* Fix/xx/increase timeout of di test by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/529
* Fix failed tests of resource setup after the resource database updated by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/538
* Add timeout to cod query test to avoid test hang by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/536
* Use GHCR image to avoid dockerhub pull rate limit by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/539
* Allow set key_filename/key_policy in computer configure by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/537
* Fix failed resources widget  by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/544
* [pre-commit.ci] pre-commit autoupdate by @pre-commit-ci in https://github.com/aiidalab/aiidalab-widgets-base/pull/546


**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.0.1...v2.1.0

## v2.0.2 - 2023-09-07
* StructureViewer: Print 3 decimal places for distance and angles by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/495
* Allow structures with different periodicity, add periodicity by @AndresOrtegaGuerrero in https://github.com/aiidalab/aiidalab-widgets-base/pull/488
* Bump scikit-learn by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/498
* Make notebook tests less flaky by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/497
* Lazy import optimade_client by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/496


**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.0.1...v2.0.2

## v2.0.1 - 2023-06-27
* ProcessCallStackWidget: Fix calc_info signature for aiida-core 2.4 by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/491
* updating spglib to 2.0.2 by @AndresOrtegaGuerrero in https://github.com/aiidalab/aiidalab-widgets-base/pull/487
* SmilesWidget: Fix generation of 1- and 2-atom molecules by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/489


**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v2.0.0...v2.0.1

## v2.0.0 - 2023-04-27
* Migrate widgets to 2.x by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/344
* 10 mins are too short for notebook CI tests by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/380
* UUID as traitlets for threading related widgets by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/375
* Clean AiiDAV3 deprecation warnings by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/388
* Two more deprecated APIs with AIIDA_WARN_v3=1 for QeApp by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/390
* Clean up dependencies requirements by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/395
* Install Firefox/geckodriver in GH workflow for the test by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/397
* Using new code create API by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/394
* Update `flake8` config for `flake8>=6` by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/399
* Chore: maintain pre-commit checks by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/400
* Require aiida-core>=2.1 by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/403
* Code quick setup can have the computer label in its dropdown as a placeholder before the computer is set by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/408
* CI improvement and clean up by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/410
* Take screenshots in notebook tests and upload them as artifacts by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/411
* Fix/406/default calc job plugin by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/409
* Work on pre-commit hooks, and small readme update by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/401
* Manifest the issue of setting multiple codes by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/415
* Delayed import of scikit-learn and pandas + other dependency tweaks by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/412
* CI: Configure pre-commit schedule to run quarterly by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/424
* Add screenshot teardown fixture - approach 1 by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/421
* Use `displayed_structure` to create selection info by @superstar54 in https://github.com/aiidalab/aiidalab-widgets-base/pull/371
* Bump isort to fix pre-commit CI build by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/428
* Fix/configure tabs by @AndresOrtegaGuerrero in https://github.com/aiidalab/aiidalab-widgets-base/pull/429
* ProcessMonitorWidget: Print traceback for callback exceptions by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/427
* Resolve new flake8-bugbear error B028 by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/442
* Support the inputs namespace for process inputs check widget by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/435
* Measure the test coverage by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/441
* fix bug report to use the new return type of find_installed_packages by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/446
* Add tests for `computational_resources` module by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/448
* Add tests to the `structure` module, a small modification to the module itself by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/453
* Add tests to the `viewers` module and slightly improve its styling by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/450
* Test and update process module by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/455
* Test and update databases module by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/458
* Update the `pymysql` version restriction to `~=0.9` by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/465
* pin the widgetsnbextension version `< 3.6.3` by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/467
* Test and update the `elns` module by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/464
* Test nodes module by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/468
* Test for export button widget by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/469
* Test and update the `wizard` module by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/466
* Update README.md on how to bumpver on tag num by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/470
* Use aiida_structuredata as the transition state of a query by @unkcpz in https://github.com/aiidalab/aiidalab-widgets-base/pull/472
* Add test for the `ProcessMonitor` widget by @yakutovicha in https://github.com/aiidalab/aiidalab-widgets-base/pull/478
* ProcessMonitor: Increase default timeout by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/480
* Remove spinning Thread from WizzardAppWidgetStep by @danielhollas in https://github.com/aiidalab/aiidalab-widgets-base/pull/479

## New Contributors
* @AndresOrtegaGuerrero made their first contribution in https://github.com/aiidalab/aiidalab-widgets-base/pull/429

**Full Changelog**: https://github.com/aiidalab/aiidalab-widgets-base/compare/v1.4.2...v2.0.0
