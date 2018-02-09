# Data acquisition backend for Jungfrau detectors

# Development

## Running the tests

Before each major commit, please run the unittest suite. In order to do so, you do need the ``detector_replay`` package, that can be retrieved here: https://git.psi.ch/HPDI/detector_replay

Then:
```
cd tests
python -m unittest test_reconstruction
```

This should that 1-2 minutes on a laptop.
