import subprocess
from distutils.core import setup, Command


class MakefileBuilder(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        subprocess.check_output(["make", "DETECTOR=EIGER"])
        print("C shared library built successfully.")


setup(
    name='detector_backend',
    version='0.0.1',
    description='Software for receiving, processing and writing PSI detectors.',
    author='PSI DAQ',
    author_email='daq@psi.ch',
    url='',
    cmdclass={"c_build": MakefileBuilder}
)
