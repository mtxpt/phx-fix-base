# Phoenix Prime FIX Client Application 

This repository provides the foundations for FIX based trading applications based on the widely used 
[QuickFix](https://quickfixengine.org) open source library and its application framework.


## Installation 

It is highly recommended to create a new Python environment. The script
`scripts/setup_all.sh` automates the creation of a conda based environment 
with all dependencies installed. Optionally provide the argument `clean` to 
remove existing environment and rebuild all. 

```
scripts/setup_all.sh [clean]
```

Note that `setup_all.sh` also builds a custom QuickFix version for `arm64` architecture. 

Alternatively a Python environment can be created and the `requirements.txt` can 
be installed directly as follows 

``` 
pip3 install -r requirements.txt
```

Note that `requirements.txt` does not install QuickFix for macOS with arm64 architecture
as the current QuickFix version 1.15.1 has some issues and requires a patch. 


## Custom Build QuickFix for arm64 on macOS 

Building QuickFix for Apple arm64 requires a patch. The following script
automates the patch and builds QuickFix for `arm64` from source:

```
scripts/build_quickfix_arm64.sh
```

If you use `setup_all.sh` you don't have to execute this build step as it is handled 
by `setup_all.sh` as well. 


## Installing QuicFix on Windows

The Python QuickFIX bindings also fail to install on Windows. Fortunately, for Windows there are 
[prebuilt wheel packages](https://www.lfd.uci.edu/~gohlke/pythonlibs/#quickfix). 

To setup the Python environment using Conda follow these steps:

  - Install Conda or Miniconda
  - Create a new environment with `conda create --name phx python=3.9`
  - Activate the environment
  - Install all dependencies first `pip install -r requirements.txt` 
  - Download the QuickFix wheel `quickfix‑1.15.1‑cp39‑cp39‑win_amd64.whl`
  - Install the wheel `pip install quickfix‑1.15.1‑cp39‑cp39‑win_amd64.whl`
  - List packages and check if `quickfix 1.15.1` shows up `conda list`

Note that during the execution of `pip install -r requirements.txt` you should first see

```
Ignoring quickfix: markers 'platform_machine != "arm64" and sys_platform != "win32"' don't match your environment
```


## Configure PyCharm

To conveniently work with PyCharm it must be configured to use the proper interpreter.
Set the Python interpreter managed by the Conda package manager in `./opt/conda/`

Lower right corner in PyCharm choose "Python Interpreter". Then

  - `Add New Interpreter` -> `Add Local Interpreter`
  - Choose `Conda Environment` with conda executable `<path to>/opt/conda/condabin/conda` 
  - Click the button `Load Environments`, make sure the radio button `Use existing environment` is selected
  - Choose `dev` and give it optionally another name by editing the interpreter configuration

PyCharm can also be configured for Remote Development. This allows to run the project on the server,
while using PyCharm client.











