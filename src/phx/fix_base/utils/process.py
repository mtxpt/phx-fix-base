from subprocess import check_output, CalledProcessError
import sys


def process_is_running(proc_name):
    try:
        if sys.platform == 'linux':
            call = check_output("pgrep '{}'".format(proc_name), shell=True)
        else:
            call = check_output("pgrep -f '{}'".format(proc_name), shell=True)
        return True
    except CalledProcessError:
        return False


def kill_process(proc_name):
    try:
        call = check_output("pkill SIGKILL -f '{}'".format(proc_name), shell=True)
        return True
    except CalledProcessError:
        return False
