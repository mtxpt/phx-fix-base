import os


def make_dirs(path_to_make):
    if os.path.exists(path_to_make):
        if not os.path.isdir(path_to_make):
            raise OSError(f"cannot create a file when that file already exists: {path_to_make}")
    else:
        os.makedirs(path_to_make)


def make_dirs_for_file(filename):
    path_to_make = os.path.dirname(str(filename))
    if os.path.exists(path_to_make):
        if not os.path.isdir(path_to_make):
            raise OSError(f"cannot create a file when that file already exists: {path_to_make}")
    else:
        os.makedirs(path_to_make)
    return filename
