import numpy as np
import glob
import re

temp_regex = r"((?<=[/(\\)][0-9]{4}_)[a-zA-Z0-9]*).+((?<=setTemp=)[0-9.]*).+((?<=actTemp=)[0-9.]*)"
old_regex = r"((?<=[\/(\\)])[a-zA-Z0-9]*(?=_)).+((?<=_)[0-9.,]*(?=K))"

Dico_regex = {"Old": (old_regex, 2, " "), "Classic": (temp_regex, 3, "	")}


def load_folder_on_DS(folder, Data_struct, regex_kind="Classic"):

    all_files = glob.glob(folder + "\\*")
    # print(all_files)
    # test = re.search(temp_regex, all_files[0])
    # print(test.groups())

    reg = Dico_regex[regex_kind]

    file_info = list(
        map(lambda f: [f] + list(re.search(reg[0], f).groups()), all_files)
    )
    # print(file_info)
    n_info = reg[1]

    for info in file_info:
        temp = float(info[2].replace(",", "."))
        if not (temp in Data_struct):
            if n_info == 2:
                Data_struct[temp] = {info[1]: (info[0], 0)}
            else:
                Data_struct[temp] = {info[1]: (info[0], float(info[3]))}
        else:
            if n_info == 2:
                Data_struct[temp][info[1]] = (info[0], 0)
            else:
                Data_struct[temp][info[1]] = (info[0], float(info[3]))

    return Data_struct


def add_single_file_to_DS(filepath, DS={}, reg=temp_regex):

    # print(filepath)
    # print(re.search(temp_regex, filepath))
    info = [filepath] + list(re.search(reg, filepath).groups())
    temp = float(info[2].replace(",", "."))
    n_info = len(info) - 1
    if not (temp in DS):
        if n_info == 2:
            DS[temp] = {info[1]: (info[0], 0)}
        else:
            DS[temp] = {info[1]: (info[0], float(info[3]))}
    else:
        if n_info == 2:
            DS[temp][info[1]] = (info[0], 0)
        else:
            DS[temp][info[1]] = (info[0], float(info[3]))
    return DS


def remove_from_DS(identifier, DS):

    # print(filepath)
    # print(re.search(temp_regex, filepath))

    DS.pop(identifier)


def add_to_DS(identifier, data, DS):
    if not (identifier in DS):
        DS[identifier] = data
    else:
        DS[identifier].update(data)


def show_temp(Temp, ax, DS, label="", c=None, ix=0, iy=3, delimiter="	"):
    # Data selection
    closest_Temp = min(DS.keys(), key=lambda x: abs(x - Temp))
    Datas = DS[closest_Temp]

    # Actual info + automatic label creation
    mean_temp = np.mean(list(map(lambda identifier: Datas[identifier][1], Datas)))
    # print(f"Mean actual temp : {mean_temp:.2f}")
    label = label + f"T = {mean_temp:.2f}K"

    # Loop for plotting with the same color and adding one unified legend.
    first_for_label = True
    Lines = []
    for identifier, info in Datas.items():
        data = np.loadtxt(info[0], skiprows=1, delimiter=delimiter)

        if first_for_label:
            first_for_label = False
            if c == None:
                f = ax.plot(data[:, ix], data[:, iy], lw=1, label=label)
                c = f[0].get_color()
                Lines.append(f)
            else:
                Lines.append(ax.plot(data[:, ix], data[:, iy], lw=1, c=c, label=label))
        else:
            f = ax.plot(data[:, ix], data[:, iy], lw=1, c=c)
            Lines.append(f)

    ax.legend()
    return Lines
