file_loading_timer.start_timer(__file__)

import glob
import os

import numpy as np
from PIL import Image


def make_folder(file_path):
    file_base = os.path.dirname(file_path)
    if not os.path.exists(file_base):
        try:
            os.makedirs(file_base)
        except OSError:
            raise ValueError("Can't create the folder: {}".format(file_path))


def make_folder_name(folder_path, name_prefix="scan", zero_prefix=5):
    scan_name_prefix = name_prefix + "_"
    num_folder_exist = len(glob.glob(folder_path + "/" + scan_name_prefix + "*"))
    num_folder_new = num_folder_exist + 1
    name_tmp = "00000" + str(num_folder_new)
    scan_name = scan_name_prefix + name_tmp[-zero_prefix:]
    while os.path.isdir(folder_path + "/" + scan_name):
        num_folder_new = num_folder_new + 1
        name_tmp = "00000" + str(num_folder_new)
        scan_name = scan_name_prefix + name_tmp[-zero_prefix:]
    return scan_name


def make_file_name(file_path):
    file_base, file_ext = os.path.splitext(file_path)
    if os.path.isfile(file_path):
        nfile = 0
        check = True
        while check:
            name_add = "0000" + str(nfile)
            file_path = file_base + "_" + name_add[-4:] + file_ext
            if os.path.isfile(file_path):
                nfile = nfile + 1
            else:
                check = False
    return file_path


def save_image(file_path, mat, overwrite=True):
    if "\\" in file_path:
        raise ValueError("Please use the forward slash in the file path")
    file_ext = os.path.splitext(file_path)[-1]
    if not ((file_ext == ".tif") or (file_ext == ".tiff")):
        mat = np.uint8(255 * (mat - np.min(mat)) / (np.max(mat) - np.min(mat)))
    else:
        data_type = str(mat.dtype)
        if "complex" in data_type:
            raise ValueError(
                "Can't save to tiff with this format: " "{}".format(data_type)
            )
    image = Image.fromarray(mat)
    if not overwrite:
        file_path = make_file_name(file_path)
    make_folder(file_path)
    try:
        image.save(file_path)
    except IOError:
        raise ValueError("Couldn't write to file {}".format(file_path))
    return file_path

file_loading_timer.stop_timer(__file__)
