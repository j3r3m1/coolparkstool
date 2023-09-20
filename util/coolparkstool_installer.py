import sys, subprocess, os
from pathlib import Path
import platform
from packaging import version


# locate QGIS-python interpreter
def locate_py():

    # get Python version
    str_ver_qgis = sys.version.split(" ")[0]

    try:
        # non-Linux
        path_py = os.environ["PYTHONHOME"]
    except Exception:
        # Linux
        path_py = sys.executable

    # convert to Path for eaiser processing
    path_py = Path(path_py)

    # pre-defined paths for python executable
    dict_pybin = {
        "Darwin": path_py / "bin" / "python3",
        "Windows": path_py
        / (
            "../../bin/pythonw.exe"
            if version.parse(str_ver_qgis) >= version.parse("3.9.1")
            else "pythonw.exe"
        ),
        "Linux": path_py,
    }

    # python executable
    path_pybin = dict_pybin[platform.system()]

    if path_pybin.exists():
        return path_pybin
    else:
        raise RuntimeError("CoolParksTool cannot locate the Python interpreter used by QGIS!")


# install CoolParksTool
def install_coolparkstool_python(ver=None):
    str_ver = f"=={ver}" if ver else ""
    # get Python version
    str_ver_qgis = sys.version.split(" ")[0]
    try:
        path_pybin = locate_py()
        # update pip to use new features
        list_cmd0 = f"{str(path_pybin)} -m pip install pip -U --user".split()
        str_info0 = subprocess.check_output(
            list_cmd0, stderr=subprocess.STDOUT, encoding="UTF8"
        )

        # add netCDF4 TODO: Should later be replaced with xarrays
        # list_cmd0 = f"{str(path_pybin)} -m pip install netCDF4 -U --user".split()
        # str_info0 = subprocess.check_output(
        #     list_cmd0, stderr=subprocess.STDOUT, encoding="UTF8"
        # )

        # install dependencies
        str_use_feature = (
            "--use-feature=2020-resolver"
            if version.parse(str_ver_qgis) <= version.parse("3.9.1")
            else ""
        )
        list_cmd = f"{str(path_pybin)} -m pip install coolparkstool-reqs{str_ver} -U --user {str_use_feature}".split()
        str_info = subprocess.check_output(
            list_cmd, stderr=subprocess.STDOUT, encoding="UTF8"
        )

        str_info = str_info.split("\n")[-2].strip()

        str_info = (
            str_info
            if "Successfully installed CoolParksTool dependent Python packages" in str_info
            else f"CoolParksTool dependent Python packages has already been installed!"
        )
        return str_info
    except Exception:
        raise RuntimeError(f"CoolParksTool couldn't install Python packages!") from Exception


# uninstall supy
def uninstall_coolparkstool_python():

    try:
        path_pybin = locate_py()
        list_cmd = f"{str(path_pybin)} -m pip uninstall coolparkstool-reqs -y".split()
        list_info = subprocess.check_output(list_cmd, encoding="UTF8").split("\n")

        str_info = list_info[-2].strip()
        return str_info
    except Exception:
        raise RuntimeError(f"CoolParksTool couldn't uninstall coolparkstool-reqs!") from Exception


# set up umep
def setup_coolparkstool_python(ver=None, debug=False):
    if debug:
        uninstall_coolparkstool_python()
        install_coolparkstool_python(ver)

    try:
        # check if supy and others have been installed
        import jaydebeapi

    except Exception:
        # install coolparkstool dependencies
        install_coolparkstool_python(ver)
