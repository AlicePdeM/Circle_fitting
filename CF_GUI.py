import circle_fitting as cf
import temp_sweep_script as tss

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.backend_bases import key_press_handler
from threading import Thread

from scipy.signal import find_peaks, peak_prominences

import numpy as np
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import filedialog

plt.rcParams["axes.grid"] = True
plt.rcParams["grid.linestyle"] = "--"
plt.rcParams["figure.figsize"] = (14, 7)
plt.rcParams["lines.linewidth"] = 3
plt.rcParams["font.size"] = 10

Selected_color = "#CCCCCC"
Unselected_color = "#FFFFFF"

# Color selected thanks to "I want Hue" https://medialab.github.io/iwanthue/
Left_color = "#01ca94"
Right_color = "#ce2b72"
Data_color = "#5ab039"
Fit_color = "#be5203"

n_peaks = 2

####### IMPORTANT #########


# this affects the reading of files, also see temp_sweep_script.py


root = tk.Tk()
root.wm_title("Circle fit GUI")
width = root.winfo_screenwidth()
height = root.winfo_screenheight()
# root.geometry("%dx%d" % (width, height))
root.geometry("500x500")

View_fig = Figure(figsize=(5, 4), dpi=100)
View_ax = View_fig.add_subplot()
View_canvas = FigureCanvasTkAgg(View_fig, master=root)  # A tk.DrawingArea.
View_canvas.draw()

# pack_toolbar=False will make it easier to use a layout manager later on.
toolbar = NavigationToolbar2Tk(View_canvas, root, pack_toolbar=False)
toolbar.update()


Surveillance_fig = Figure(figsize=(5, 4), dpi=100)
Surveillance_ax = []
Surveillance_ax.append(Surveillance_fig.add_axes([0, 0, 0.5, 1]))
Surveillance_ax.append(Surveillance_fig.add_axes([0.5, 0, 0.5, 1]))

Surveillance_canvas = FigureCanvasTkAgg(
    Surveillance_fig, master=root
)  # A tk.DrawingArea.
Surveillance_canvas.draw()


Result_fig = Figure(figsize=(5, 4), dpi=100)
Result_ax = Result_fig.add_subplot()
Result_canvas = FigureCanvasTkAgg(Result_fig, master=root)  # A tk.DrawingArea.
Result_canvas.draw()

progress = ttk.Progressbar(root, orient=tk.HORIZONTAL, length=200, mode="determinate")

################################ Variables ##################################
Data_struct = {}
Data_struct_viewed = {}
All_Data_variable = tk.Variable(root, value=list(Data_struct.keys()))
View_Data_variable = tk.Variable(root, value=list(Data_struct_viewed.keys()))

All_Data_LB = tk.Listbox(root, listvariable=All_Data_variable, selectmode=tk.MULTIPLE)
View_Data_LB = tk.Listbox(root, listvariable=View_Data_variable, selectmode=tk.MULTIPLE)

Estimated_tau = tk.DoubleVar(root, 0)

Span_selector = tk.IntVar(
    root, 0
)  # 0 if selected none, 1 for left span, 2 for right span
Left_span = tk.DoubleVar(root, 0)
Right_span = tk.DoubleVar(root, 0)
Line_left = View_ax.axvline(Left_span.get(), lw=1, ls="--", c=Left_color)
Line_right = View_ax.axvline(Right_span.get(), lw=1, ls="--", c=Right_color)


Analysis_selector = tk.IntVar(root, 0)


Double_Lor_bool = tk.BooleanVar(root, False)

peaks_result_show_bool = [tk.BooleanVar(root, False) for i in range(n_peaks)]
peaks_result_show_bool[0].set(True)


# Analysis variables to trace and eventually export
L_T = []
L_Q = ([], [])
L_Q_i = ([], [])
L_Q_c = ([], [])

Result_array = [np.array([]) for i in range(n_peaks)]

View_Q_Bool = tk.BooleanVar(root, True)
View_Q_i_Bool = tk.BooleanVar(root, False)
View_Q_c_Bool = tk.BooleanVar(root, False)

file_type = tk.StringVar(root, "Classic")

############################### Fonctions #####################################


def setting_f_span(event):
    # print("hey", tempi.get())

    width = View_canvas.get_tk_widget().winfo_width()
    axes_bounds = View_ax.viewLim
    relx = event.x / width
    # print(View_ax.transData.inverted().transform((event.x, event.y)))
    # if axes_bounds.containsx(relx):
    x_val, _ = View_ax.transData.inverted().transform(
        (event.x, event.y)
    )  # Warning, doesn't work for y but doesn't matter

    Span_select_val = Span_selector.get()
    if Span_select_val == 1:
        Left_span.set(x_val)
        if Right_span.get() != 0:
            Span_selector.set(0)
        else:
            Span_selector.set(2)
    elif Span_select_val == 2:
        Right_span.set(x_val)
        Span_selector.set(0)
    Update_View_Span_lines()
    Update_span_btn()


# print("clicked at", event.x, event.y)


def Right_span_btn_action():

    # View_canvas.get_tk_widget().bind("<Button-1>", setting_f_span)
    if Span_selector.get() != 2:
        Span_selector.set(2)
    else:
        Span_selector.set(0)
    Update_span_btn()


def Left_span_btn_action():
    # View_canvas.get_tk_widget().bind("<Button-1>", setting_f_span)
    if Span_selector.get() != 1:
        Span_selector.set(1)
    else:
        Span_selector.set(0)
    Update_span_btn()


def Move_selection_to_View(event):
    selected = All_Data_LB.curselection()
    for identifier in [All_Data_LB.get(i) for i in selected]:
        tss.add_to_DS(identifier, Data_struct[identifier], Data_struct_viewed)

    Update_Listboxes()
    Update_View_Canvs()


def Remove_from_View(event):
    selected = View_Data_LB.curselection()
    for identifier in [View_Data_LB.get(i) for i in selected]:
        tss.remove_from_DS(identifier, Data_struct_viewed)
    Update_Listboxes()
    Update_View_Canvs()


def Start_analysis():
    t = Thread(target=analysis_threaded)
    t.start()


def analysis_threaded():
    global Result_array
    progress["value"] = 0
    List_of_temp = []
    if Analysis_selector.get() == 0:  # All
        List_of_temp = list(Data_struct.keys())

    elif Analysis_selector.get() == 1:  # Only View
        List_of_temp = list(Data_struct_viewed.keys())

    elif Analysis_selector.get() == 2:
        T_max = max(Data_struct_viewed)
        T_min = min(Data_struct_viewed)
        for t in list(Data_struct):
            if (t >= T_min) and (t <= T_max):
                List_of_temp.append(t)

    for i, T in enumerate(List_of_temp):
        # print(T)
        f = np.array([])
        x = np.array([])
        y = np.array([])
        S = np.array([])
        for identifier, info in Data_struct[T].items():
            data = np.loadtxt(
                info[0], skiprows=1, delimiter=tss.Dico_regex[file_type.get()][2]
            )
            # print(np.shape(data))
            f = np.append(f, data[:, 0])
            x = np.append(x, data[:, 1])
            y = np.append(y, data[:, 2])
            S = np.append(S, data[:, 3])

        selection_mask = (f > Left_span.get()) & (f < Right_span.get())

        masks = [selection_mask]

        if Double_Lor_bool.get():
            f_temp = f[selection_mask]
            S_temp = S[selection_mask]

            peak_indices, _ = find_peaks(-S_temp)

            peak_prominence = peak_prominences(-S_temp, peak_indices)[0]
            ind = np.argsort(-peak_prominence)
            p1 = f_temp[peak_indices[ind[0]]]
            p2 = f_temp[peak_indices[ind[1]]]

            if p1 > p2:
                t = p2
                p2 = p1
                p1 = p2

            tresh1 = p1 + (p2 - p1) / 3
            tresh2 = p2 - (p2 - p1) / 3

            print(f"detected peaks : {p1}, {p2}")

            masks = [selection_mask & (f < tresh1), selection_mask & (f > tresh2)]

        for j in range(n_peaks):

            if j == 0 or (j > 0 and Double_Lor_bool.get()):

                res, Surp1, Surp2 = cf.lor_circle_fit(
                    f[masks[j]],
                    x[masks[j]],
                    y[masks[j]],
                    pre_calc_tau=Estimated_tau.get(),
                )
                Update_Surveillancep1(*Surp1)
                Update_Surveillancep2(*Surp2)
                progress["value"] = int(
                    100 * (i * n_peaks + j + 1) / (len(List_of_temp) * n_peaks)
                )
                # print(res, type(res))

                cleaned_res = np.insert(res.flatten("F"), 0, T)
                Estimated_tau.set(cleaned_res[5])
                print(Estimated_tau.get())
                if not Result_array[j].size:
                    Result_array[j] = np.copy(cleaned_res)
                else:
                    Result_array[j] = np.vstack((Result_array[j], cleaned_res))

        Update_Result_Canvs()


def get_tau():
    T = min(Data_struct_viewed)
    f = np.array([])
    x = np.array([])
    y = np.array([])
    for identifier, info in Data_struct[T].items():
        data = np.loadtxt(
            info[0], skiprows=1, delimiter=tss.Dico_regex[file_type.get()][2]
        )
        # print(np.shape(data))
        f = np.append(f, data[:, 0])
        x = np.append(x, data[:, 1])
        y = np.append(y, data[:, 2])
    selection_mask = (f > Left_span.get()) & (f < Right_span.get())
    Estimated_tau.set(cf.rough_estimate_tau(f, x, y))
    print(Estimated_tau.get())


def Clear_analysis():
    global Result_array
    Result_array = [np.array([]) for i in range(n_peaks)]
    progress["value"] = 0

    Update_Result_Canvs()


All_Data_LB.bind("<Return>", Move_selection_to_View)
View_Data_LB.bind("<BackSpace>", Remove_from_View)

Left_span_btn = tk.Button(
    root,
    text="Left bound",
    command=Left_span_btn_action,
    background=Unselected_color,
    foreground=Left_color,
)
Right_span_btn = tk.Button(
    root,
    text="Right bound",
    command=Right_span_btn_action,
    background=Unselected_color,
    foreground=Right_color,
)

Estimate_tau_btn = tk.Button(root, text="Get tau", command=get_tau)
Forget_tau_btn = tk.Button(
    root, text="Forget tau", command=lambda: Estimated_tau.set(0)
)

Analysis_Start_btn = tk.Button(root, text="Start", command=Start_analysis)

Analysis_Clear_btn = tk.Button(root, text="Clear", command=Clear_analysis)


def import_file():
    file_path = filedialog.askopenfilename(
        title="Select a Data file",
        filetypes=[("Data file", "*.dat"), ("All files", "*.*")],
    )
    if file_path:
        # Process the selected file (you can replace this with your own logic)

        tss.add_single_file_to_DS(
            file_path, Data_struct, reg=tss.Dico_regex[file_type.get()][0]
        )
        Update_Listboxes()
        # Update_View_Canvs()


def import_folder():
    folder_path = filedialog.askdirectory(
        title="Select a data folder",
    )
    if folder_path:
        # print(folder_path)
        tss.load_folder_on_DS(
            folder_path.replace("/", "\\"), Data_struct, file_type.get()
        )
        Update_Listboxes()
        # Update_View_Canvs()


def save_result(event=None):

    if not Double_Lor_bool.get():
        file_path = filedialog.asksaveasfilename(
            title="Select a save file", filetypes=[("CSV", "*.csv"), ("Any", "*.*")]
        )
        if file_path:
            np.savetxt(
                file_path,
                Result_array[0],
                delimiter=",",
                header="0:T,1:a,2:u_a,3:alpha,4:u_alpha,5:tau,6:u_tau,7:q,8:u_q,9:q_c,10:u_q_c,11:phi,12:u_phi,13:f,14:u_f,15:q_i,16:u_q_i",
            )
    else:
        for i in range(n_peaks):
            file_path = filedialog.asksaveasfilename(
                title="Select a save file", filetypes=[("CSV", "*.csv"), ("Any", "*.*")]
            )
        if file_path:
            np.savetxt(
                file_path,
                Result_array[i],
                delimiter=",",
                header="0:T,1:a,2:u_a,3:alpha,4:u_alpha,5:tau,6:u_tau,7:q,8:u_q,9:q_c,10:u_q_c,11:phi,12:u_phi,13:f,14:u_f,15:q_i,16:u_q_i",
            )


######################################## Update fonctions ####################################


def Update_span_btn():
    # print(Span_selector.get())
    Left_span_btn.config(background=Unselected_color)
    Right_span_btn.config(background=Unselected_color)
    if Span_selector.get() == 1:
        Left_span_btn.config(background=Selected_color)
        # View_canvas.get_tk_widget().bind("<Button-1>", setting_f_span)
    elif Span_selector.get() == 2:
        Right_span_btn.config(background=Selected_color)
        # View_canvas.get_tk_widget().bind("<Button-1>", setting_f_span)
    if Span_selector.get() == 0:
        pass
        # View_canvas.get_tk_widget().unbind("<Button-1>")


def Update_View_Span_lines():
    # print(Left_span.get(), Right_span.get())
    Line_left.set_xdata([Left_span.get(), Left_span.get()])
    Line_right.set_xdata([Right_span.get(), Right_span.get()])
    View_canvas.draw()


Lines = []


def Update_View_Canvs():
    # View_ax.cla()
    global Lines

    for obj in Lines:
        for objobj in obj:
            # print(objobj)
            objobj.remove()  # Line2D matplotlib object

    Lines.clear()

    for temp in list(View_Data_variable.get()):
        Lines += tss.show_temp(
            temp,
            View_ax,
            Data_struct_viewed,
            delimiter=tss.Dico_regex[file_type.get()][2],
        )

    Update_View_Span_lines()


def Update_Listboxes():

    All_Data_variable.set(list(Data_struct.keys()))
    View_Data_variable.set(list(Data_struct_viewed.keys()))


def show1D_errorbars(ax, data, iy, label, ix=0):
    ax.errorbar(
        data[ix],
        data[iy],
        yerr=data[iy + 1],
        ls="",
        label=label,
        elinewidth=1,
        capsize=2,
    )


def show2D_errorbars(ax, data, iy, label, ix=0):
    ax.errorbar(
        data[:, ix],
        data[:, iy],
        yerr=data[:, iy + 1],
        ls="",
        label=label,
        elinewidth=1,
        capsize=2,
    )


def Update_Result_Canvs():
    Result_ax.cla()
    for i, peaks_bool in enumerate(peaks_result_show_bool):
        if peaks_bool.get():
            if View_Q_Bool.get():
                if Result_array[i].ndim == 1:
                    show1D_errorbars(
                        Result_ax, Result_array[i], 7, f"Global Quality ({i})"
                    )
                else:
                    show2D_errorbars(
                        Result_ax, Result_array[i], 7, f"Global Quality ({i})"
                    )

            if View_Q_c_Bool.get():
                if Result_array[i].ndim == 1:
                    show1D_errorbars(
                        Result_ax, Result_array[i], 9, f"Coupling Factor ({i})"
                    )
                else:
                    show2D_errorbars(
                        Result_ax, Result_array[i], 9, f"Coupling Factor ({i})"
                    )

            if View_Q_i_Bool.get():
                if Result_array[i].ndim == 1:
                    show1D_errorbars(
                        Result_ax, Result_array[i], 15, f"Internal Quality ({i})"
                    )
                else:
                    show2D_errorbars(
                        Result_ax, Result_array[i], 15, f"Internal Quality ({i})"
                    )
    Result_ax.legend()

    Result_canvas.draw()


def Update_Surveillancep1(x, y, x_c, y_c, r_c):
    Surveillance_ax[0].cla()
    Surveillance_ax[0].set_axis_off()
    Surveillance_ax[0].plot(
        x_c + r_c * np.cos(np.linspace(0, 2 * np.pi)),
        y_c + r_c * np.sin(np.linspace(0, 2 * np.pi)),
        lw=2,
        ls="--",
        c=Fit_color,
    )
    Surveillance_ax[0].scatter(x, y, c=Data_color, s=1, marker="x")
    Surveillance_canvas.draw()


def Update_Surveillancep2(x, y, y_fit):
    Surveillance_ax[1].cla()
    Surveillance_ax[1].set_axis_off()
    Surveillance_ax[1].plot(
        x,
        y_fit,
        lw=2,
        ls="--",
        c=Fit_color,
    )
    Surveillance_ax[1].scatter(x, y, c=Data_color, s=1, marker="x")
    Surveillance_canvas.draw()


View_Q_CB = tk.Checkbutton(
    root, text="Q", variable=View_Q_Bool, command=Update_Result_Canvs
)
View_Q_i_CB = tk.Checkbutton(
    root, text="Q_i", variable=View_Q_i_Bool, command=Update_Result_Canvs
)
View_Q_c_CB = tk.Checkbutton(
    root, text="Q_c", variable=View_Q_c_Bool, command=Update_Result_Canvs
)

################################## Menu Bar ##########################################


menubar = tk.Menu(root)

data_managment = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Data", menu=data_managment)
data_managment.add_command(label="Load single file", command=import_file)
data_managment.add_command(label="Load Folder", command=import_folder)
data_managment.add_separator()
data_managment.add_command(label="Save Results as ", command=save_result)

data_parameters = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Data Parameters", menu=data_parameters)
for regex_possibilities in tss.Dico_regex.keys():
    data_parameters.add_radiobutton(
        label=regex_possibilities, value=regex_possibilities, variable=file_type
    )

analysis_parameters = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Analysis +", menu=analysis_parameters)
analysis_parameters.add_checkbutton(
    label="Multiple Peaks Analysis", variable=Double_Lor_bool
)
analysis_parameters.add_separator()
for i, peaks_bool in enumerate(peaks_result_show_bool):
    analysis_parameters.add_checkbutton(
        label=f"show result for peak n°{i}",
        variable=peaks_bool,
        command=Update_Result_Canvs,
    )


root.config(menu=menubar)
################################## Placing things and labels #################################
View_canvas.get_tk_widget().bind("<Control-Button-1>", setting_f_span)
root.bind("<Control-s>", save_result)

Label_dict = {
    "Frequency span:": (0.1, 0.68),
    "Circle fitting analysis:": (0.75, 0.05),
    "All loaded temperature (in K)": (0.3, 0.65),
    "Viewed temperature (in K)": (0.45, 0.65),
}

Buttons_dict = {
    Left_span_btn: (0.05, 0.8, 0.2, 0.07),
    Right_span_btn: (0.05, 0.9, 0.2, 0.07),
    Analysis_Start_btn: (0.70, 0.15, 0.1, 0.07),
    Analysis_Clear_btn: (0.85, 0.15, 0.1, 0.07),
    Estimate_tau_btn: (0.70, 0.08, 0.1, 0.05),
    Forget_tau_btn: (0.85, 0.08, 0.1, 0.05),
}


View_canvas.get_tk_widget().place(relx=0.05, rely=0.1, relheight=0.5, relwidth=0.5)
toolbar.place(relx=0.05, rely=0.6)
Surveillance_canvas.get_tk_widget().place(
    relx=0.6, rely=0.3, relheight=0.25, relwidth=0.35
)
Result_canvas.get_tk_widget().place(relx=0.64, rely=0.55, relheight=0.4, relwidth=0.31)

All_Data_LB.place(relx=0.3, rely=0.70, relwidth=0.1, relheight=0.25)
View_Data_LB.place(relx=0.45, rely=0.70, relwidth=0.1, relheight=0.25)


for key, val in Label_dict.items():
    temp = tk.Label(root, text=key)
    temp.place(relx=val[0], rely=val[1])

for key, val in Buttons_dict.items():
    key.place(relx=val[0], rely=val[1], relwidth=val[2], relheight=val[3])

tk.Radiobutton(root, text="All loaded data", value=0, variable=Analysis_selector).place(
    relx=0.6, rely=0.15, relheight=0.04
)

tk.Radiobutton(
    root, text="Viewed data only", value=1, variable=Analysis_selector
).place(relx=0.6, rely=0.2, relheight=0.04)

tk.Radiobutton(
    root, text="Viewed data as T-bound", value=2, variable=Analysis_selector
).place(relx=0.6, rely=0.25, relheight=0.04)


View_Q_CB.place(relx=0.6, rely=0.65)
View_Q_i_CB.place(relx=0.6, rely=0.7)
View_Q_c_CB.place(relx=0.6, rely=0.75)


progress.place(relx=0.75, rely=0.25)

tk.mainloop()
