# Phoenix Prime FIX Foundation Package 

This repository provides the foundations for FIX based trading applications based on the widely used 
[QuickFIX](https://QuickFIXengine.org) open source library and its application framework. 

A simplistic FIX client implementing a fully fledged trading strategy building on this foundation package 
can be found in this [repository](https://github.com/mtxpt/phx-fix-examples).

Detailed documentation on the Phoenix Prime Service API and the Phoenix Prime FIX endpoints can be found in the 
official Phoenix Prime [documentation](https://www.matrixport.com/docs/en-us/phoenix.html). 


## Requirements  

The project requires
  - Python >= 3.11
  - QuickFIX >= 1.15.1
  - Dependencies as listed in `requirements.txt`


## Developer Installation 

It is highly recommended to create a new Python environment. On Linux or macOS the script
`scripts/setup_all.sh` automates the creation of a [conda](https://docs.conda.io/en/latest/) 
based environment with all dependencies installed. Optionally provide the argument `clean` 
to remove existing environment and rebuild all. 

```
scripts/setup_all.sh [clean]
```

Note that `setup_all.sh` also builds a custom QuickFIX version for `arm64` architecture. 

Alternatively a Python environment can be created and the `requirements.txt` can 
be installed directly as follows 

``` 
pip3 install -r requirements.txt
```

Note that `requirements.txt` does not install QuickFIX for macOS with arm64 architecture
as the current QuickFIX version 1.15.1 has some issues and requires a patch. 


## QuickFIX 

This project depends on [QuickFIX](http://www.QuickFIXengine.org/). Check their [license agreement](http://www.QuickFIXengine.org/LICENSE) for licensing information.

### Custom Build QuickFIX for arm64 on macOS 

Building QuickFIX for Apple arm64 requires a patch. The following script
automates the patch and builds QuickFIX for `arm64` from source:

```
scripts/build_QuickFIX_arm64.sh
```

If you use `setup_all.sh` you don't have to execute this build step as it is handled by `setup_all.sh` as well.

### Installing QuickFIX on Windows

The Python QuickFIX bindings also fail to install on Windows. Fortunately, for Windows there are 
[prebuilt wheel packages](https://www.lfd.uci.edu/~gohlke/pythonlibs/#QuickFIX). 

To set up the Python environment using Conda follow these steps:
  - Install Conda or Miniconda
  - Create a new environment with `conda create --name phx python=3.11`
  - Activate the environment
  - Install all dependencies first `pip install -r requirements.txt` 
  - Download the QuickFIX wheel `QuickFIX‑1.15.1‑cp39‑cp39‑win_amd64.whl`
  - Install the wheel `pip install QuickFIX‑1.15.1‑cp39‑cp39‑win_amd64.whl`
  - List packages and check if `QuickFIX 1.15.1` shows up `conda list`

Note that during the execution of `pip install -r requirements.txt` you should first see

```
Ignoring QuickFIX: markers 'platform_machine != "arm64" and sys_platform != "win32"' don't match your environment
```


## Configure PyCharm

To conveniently work with PyCharm it must be configured to use the proper interpreter.
Set the Python interpreter managed by the Conda package manager in `./opt/conda/`

Lower right corner in PyCharm or in `Settings` choose `Python Interpreter`. Then

  - `Add New Interpreter` -> `Add Local Interpreter`
  - Choose `Conda Environment` with conda executable `<path to>/opt/conda/condabin/conda` 
  - Click the button `Load Environments`, make sure the radio button `Use existing environment` is selected
  - Choose `dev` and give it optionally another name by editing the interpreter configuration

Next navigate to `Settings` -> `Project` -> `Project Structure` and configure the directory `src` as 
source folder and the `tests` directory as test folder. 


## User 

The package can be added to the `requirements.txt` through a 

```
# Phoenix Prime FIX foundation package
phx-fix-base @ git+https://github.com/mtxpt/phx-fix-base.git@main
```


Alternatively, follow these steps

 - Download `phx-fix-base` project with
  ```bash
  git clone git@github.com:mtxpt/phx-fix-base.git
  ```
 - Install `phx-fix-base` library in your environment of choice 
  ```bash
  pip install git+file:///<path to installed phx-fix-base project>
  ```
  for example 
  ```bash 
  pip install git+file:///Users/user/phoenix/phx-fix-base
  ```
 - Import `phx-fix-base` modules into your code and use them. 
   For example see`<phx-fix-base>/tests/test_base_strategy`


## Developer Notes

We appreciate feedback and contributions. If you have feature requests, questions, 
or want to contribute code or config files, don't hesitate to use the 
[GitHub issue tracker](https://github.com/mtxpt/phx-fix-base/issues).


## License

The __Phoenix Prime FIX Foundation Package__ is released under the 
[BSD 3-Clause License](LICENSE).









