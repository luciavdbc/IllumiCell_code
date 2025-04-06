import tkinter as tk
from tkinter import messagebox, filedialog
import serial
import time
import json
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

sensor_data_window = None
sensor_values = []
times = []
time_counter = 0
scheduled_tasks = []
scheduled_task_id = None
queue = []
arduino = None
start_time = None
elapsed_time = 0
experiment_running = False


# Function to display an initial instructions page for user to understand functionalities of the interface,
# including adding steps, saving experiments, and controlling the experiment (start/stop).
def show_instructions_overlay():
    overlay_frame = tk.Frame(root, bg="#1E90FF", width=1350, height=700)
    overlay_frame.place(relx=0.5, rely=0.59, anchor="center")

    root.after(100, lambda: overlay_frame.lift())

    instructions_label = tk.Label(overlay_frame, text="Welcome to IllumiCell!\n\n"
                                                     "Instructions:\n\n"
                                                     "1. Click 'Add Step' to create your experiment.\n"
                                                     "2. Use 'Save' and 'Open saved files' to save and load experiments.\n"
                                                     "3. Click 'Clear all' to reset the experiment queue.\n"
                                                     "4. Click 'Run' to start the experiment.\n"
                                                     "5. Click 'Stop' to halt a running experiment.\n"
                                                     "6. Click 'View sensor data' for real-time sensor recordings during the experiment.\n"

                                                     "\nClick 'OK' to continue.",
                             font=("Helvetica", 16), bg="#1E90FF", justify="center")
    instructions_label.pack(padx = 50, pady=37)

    ok_button = tk.Button(overlay_frame, text="OK", command=overlay_frame.destroy,
                          bg="blue", fg="white", font=("Helvetica", 14), width=4)
    ok_button.pack(pady=20)


# Function to initialize the connection to the Arduino board.
# This function attempts to open the serial connection on COM8 with a baud rate of 9600.
# If the connection is unsuccessful, it shows an error message to the user.
def initialize_arduino():
    global arduino
    try:
        arduino = serial.Serial('COM8', 9600)
        time.sleep(2)
    except serial.SerialException as e:
        messagebox.showerror('Error', f'Failed to connect to Arduino: {e}')


# Function to send a command to the connected Arduino board.
# This function checks if the Arduino connection is open, and if so, sends the given command.
# If the connection is not open or the command fails, an error message is shown.
def send_to_arduino(command):
    if arduino.isOpen():
        try:
            arduino.write(command.encode())
            print(f"Arduino is processing: {command.strip()}")
        except Exception as e:
            messagebox.showerror('Error', f'Failed to send command to Arduino: {e}')
    else:
        messagebox.showerror('Error', 'Arduino is not connected')


# Function to add a step to the experiment queue.
# This step represents a specific action or task within the experiment, such as turning on lights
# or controlling the duration of the experiment. The function takes various parameters depending
# on the type of step (e.g., light intensity, frequency, etc.) and appends it to the queue.
def add_step_to_queue(step_type, duration, rate=None, on_time=None, off_time=None, lux=None):
    step = [step_type, duration]
    if rate is not None:
        step.append(rate)
    if on_time is not None and off_time is not None:
        step.append(on_time)
        step.append(off_time)
    if lux is not None:
        step.append(lux)
    queue.append(step)
    update_queue_listbox()


# Function to update the contents of the queue listbox in the user interface.
# This function refreshes the display to show the current experiment steps in the queue.
# If no steps are added yet, a default message is shown. If steps are present, each one is
# listed with relevant details such as light intensity or frequency.
def update_queue_listbox():
    queue_listbox.delete(0, 'end')

    if not queue:
        queue_listbox.insert(tk.END, 'Add a step to the experiment queue or open a previously saved file.')
        queue_listbox.itemconfig(0, {'bg': 'lightgray'})
        delete_button.grid_forget()
    else:
        for idx, step in enumerate(queue):
            text = f"{idx + 1}: {step[0]} for {step[1]} seconds"

            if step[0] == 'Continuous light' and len(step) >= 3:
                text += f" at {step[2]} lux"

            elif step[0] == 'Pulsing light' and len(step) >= 4:
                text += f" - Frequency: {step[2]} Hz, Intensity: {step[3]} lux"

            elif step[0] == 'Advanced pulsing light' and len(step) >= 5:
                text += f" - On: {step[2]} ms, Off: {step[3]} ms, Intensity: {step[4]} lux"

            queue_listbox.insert(tk.END, text)
            queue_listbox.itemconfig(idx, {'bg': 'white'})


# Function to highlight steps that are currently being processed in yellow, and steps that
# are complete in green.
def highlight_step(idx, color):
    queue_listbox.itemconfig(idx, {'bg': color})


# Function to reset the background colors of all steps in the queue listbox to their default color.
# This is used to clear any highlights after selecting or processing steps.
def reset_step_colors():
    for idx in range(len(queue)):
        queue_listbox.itemconfig(idx, {'bg': 'white'})


# Function to update the time label in the interface during the experiment.
# This continuously updates the elapsed time since the experiment started, and formats it into
# hours, minutes, and seconds. It runs every second while the experiment is active.
def update_time_label():
    if experiment_running:
        elapsed_time = time.time() - start_time
        hours, remainder = divmod(int(elapsed_time), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_label.config(text=f"Elapsed time: {hours:02}:{minutes:02}:{seconds:02}")
        global time_update_id
        time_update_id = root.after(1000, update_time_label)


# Function to hide the majority of buttons during the execution of an experiment.
# This helps to declutter the interface by only displaying the 'Stop' button.
def hide_buttons_except_stop():
    add_step_button.place_forget()
    open_button.place_forget()
    save_button.place_forget()
    reset_button.place_forget()
    delete_button.place_forget()


# Function to show the main control buttons after the experiment is complete.
def show_buttons_after_experiment():
    add_step_button.place(relx=0.42, rely=0.3, anchor="center")
    open_button.place(relx=0.58, rely=0.3, anchor="center")
    save_button.place(relx=0.35, rely=0.8, anchor="center")
    reset_button.place(relx=0.65, rely=0.8, anchor="center")
    delete_button.grid_forget()


# Function to start and run the experiment.
# This function processes each step in the experiment queue sequentially. It sends commands to the Arduino
# for each step and updates the user interface. It also handles the timing for each step, switching
# between different actions such as turning on lights or pulsing lights, and updates the elapsed time.
def run_experiment():
    global start_time, elapsed_time, experiment_running, scheduled_tasks

    scheduled_tasks = []

    if not queue:
        messagebox.showwarning('No steps', 'Please add steps to the experiment first.')
        return

    try:
        experiment_running = True

        start_time = time.time()
        elapsed_time = 0
        total_duration = sum(step[1] for step in queue)

        view_sensor_button.place(relx=0.5, rely=0.30, anchor="center")  # Show button
        info_icon.place(relx=0.558, rely=0.30, anchor="center")

        time_label.grid(row=6, column=0, columnspan=3, padx=570, pady=605)
        update_time_label()

        hide_buttons_except_stop()

        run_button.config(text="Stop", command=stop_experiment, bg="red")  # Change button to "Stop"

        def process_step(idx):
            if idx >= len(queue):
                send_to_arduino("OFF\n")
                messagebox.showinfo('Experiment Finished', 'Experiment completed successfully!')
                time_label.grid_forget()
                reset_step_colors()
                run_button.config(text="Run", command=run_experiment, bg="green")
                show_buttons_after_experiment()
                view_sensor_button.place_forget()
                info_icon.place_forget()
                global experiment_running
                experiment_running = False
                return

            step = queue[idx]
            highlight_step(idx, 'yellow')
            root.update()

            if step[0] == 'Continuous light':
                duration = step[1]
                lux = step[2]
                send_to_arduino(f"ON {duration} {lux}\n")

            elif step[0] == 'No light':
                duration = step[1]
                send_to_arduino(f"OFF {duration}\n")

            elif step[0] == 'Pulsing light':
                duration = step[1]
                frequency = step[2]
                lux = step[3]
                send_to_arduino(f"PULSING {duration} {frequency} {lux}\n")

            elif step[0] == 'Advanced pulsing light':
                duration = step[1]
                on_time = step[2]
                off_time = step[3]
                lux = step[4]
                send_to_arduino(f"ADV_PULSING {duration} {on_time} {off_time} {lux}\n")

            task_id = root.after(step[1] * 1000, highlight_step, idx, 'green')
            scheduled_tasks.append(task_id)

            task_id = root.after(step[1] * 1000, process_step, idx + 1)
            scheduled_tasks.append(task_id)

        process_step(0)

    except Exception as e:
        send_to_arduino("OFF\n")
        run_button.config(text="Run", command=run_experiment, bg="green")
        show_buttons_after_experiment()


# Function to stop the experiment by halting the commands being sent to the Arduino and updating the UI.
def stop_experiment():
    global experiment_running, scheduled_tasks
    if not experiment_running:
        return

    stop_confirm = messagebox.askyesno(
        "Stop Experiment",
        "Are you sure you want to stop the experiment?"
    )

    if stop_confirm:
        for task_id in scheduled_tasks:
            root.after_cancel(task_id)

        send_to_arduino("OFF\n")
        reset_step_colors()

        experiment_running = False
        run_button.config(text="Run", command=run_experiment, bg="green")
        show_buttons_after_experiment()

        time_label.grid_forget()
        view_sensor_button.place_forget()
        info_icon.place_forget()
        if sensor_data_window:
            close_sensor_data_window()

    else:
        return


# Function to save the current experiment as a JSON file in the user's personal desktop library location of choice.
def save_experiment():
    if not queue:
        messagebox.showwarning('Error', 'Please add steps to the experiment first.')
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        title="Save Experiment"
    )

    if file_path:
        try:
            with open(file_path, 'w') as file:
                json.dump(queue, file, indent=4)
            messagebox.showinfo('Success', f'Experiment saved successfully to {file_path}')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save experiment: {e}')


# Function to open and load a saved experiment file, updating the queue list in the interface.
def open_experiment():
    file_path = filedialog.askopenfilename(
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        title="Open Experiment"
    )

    if file_path:
        try:
            with open(file_path, 'r') as file:
                loaded_queue = json.load(file)

            queue.extend(loaded_queue)
            update_queue_listbox()

            messagebox.showinfo('Success', 'Experiment loaded successfully')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to open experiment: {e}')


# Function to reset the experiment queue.
def reset_experiment():
    global queue
    queue = []
    update_queue_listbox()


# Function to delete a selected step from the experiment queue.
def delete_step():
    selected_index = queue_listbox.curselection()

    if selected_index:
        idx = selected_index[0]

        if idx == 0 and not queue:
            messagebox.showwarning("Cannot Delete", "The default text cannot be deleted.")
            return

        confirm = messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete this step?")
        if confirm:
            queue.pop(idx)
            update_queue_listbox()
            delete_button.grid_forget()
    else:
        messagebox.showwarning('No Selection', 'Please select a step to delete.')


# Function to handle a click on a step in the queue list.
# This function updates the UI to display the delete button when a step is selected, allowing the user to delete it.
def on_step_click(event):
    if experiment_running:
        return
    selected_index = queue_listbox.curselection()

    if selected_index:
        if selected_index[0] == 0 and not queue:
            delete_button.grid_forget()
        else:
            delete_button.grid(row=6, column=0, columnspan=3, pady=260, padx=875)
    else:
        delete_button.grid_forget()


# Function to hide the delete button when clicking outside the button.
# This function ensures that the delete button is hidden if the user clicks anywhere outside it.
def on_click_outside(event):
    if event.widget != delete_button:
        delete_button.grid_forget()


# Opens a new window to add a step to the experiment.
# Allows the user to select a type of step (Continuous light, Pulsing light, No light)
# and enter relevant parameters for that step (e.g., duration, pulse rate, light intensity).
def open_add_step_window():
    add_step_window = tk.Toplevel(root)
    add_step_window.title("Add Step to Experiment")
    add_step_window.geometry("500x470")
    add_step_window.configure(bg="light blue")

    hours_var = tk.IntVar(value=0)
    minutes_var = tk.IntVar(value=0)
    seconds_var = tk.IntVar(value=0)

    on_time_var = tk.IntVar()
    off_time_var = tk.IntVar()
    pulse_rate_var = tk.IntVar()

    def show_step_selection():
        for widget in add_step_window.winfo_children():
            widget.destroy()

        add_step_window.title("Add Step to Experiment")

        tk.Label(add_step_window, text="Which type of step would you like to add?",
                 font=("Helvetica", 16), bg="light blue", fg="black").pack(pady=40)

        tk.Button(add_step_window, text="Continuous light", command=lambda: select_step("Continuous light"),
                  bg="blue", fg="white", font=("Helvetica", 14), width=20).pack(pady=20)
        tk.Button(add_step_window, text="Pulsing light", command=lambda: select_step("Pulsing light"),
                  bg="blue", fg="white", font=("Helvetica", 14), width=20).pack(pady=20)
        tk.Button(add_step_window, text="No light", command=lambda: select_step("No light"),
                  bg="blue", fg="white", font=("Helvetica", 14), width=20).pack(pady=20)

    def get_total_duration(h_var=None, m_var=None, s_var=None):
        h = h_var.get() if h_var else hours_var.get()
        m = m_var.get() if m_var else minutes_var.get()
        s = s_var.get() if s_var else seconds_var.get()
        return (h * 3600) + (m * 60) + s

    def validate_and_add_step(callback,
                              h_var=None, m_var=None, s_var=None,
                              pulse_rate_var=None,
                              on_time_var=None,
                              off_time_var=None):
        if get_total_duration(h_var, m_var, s_var) == 0:
            messagebox.showwarning("Invalid input", "Duration cannot be 0. Please enter a valid time.")
            add_step_window.lift()
            add_step_window.focus_force()
            return

        if pulse_rate_var is not None and pulse_rate_var.get() == 0:
            messagebox.showwarning("Invalid input", "Pulse rate cannot be 0. Please enter a valid pulse rate.")
            add_step_window.lift()
            add_step_window.focus_force()
            return

        if on_time_var is not None and on_time_var.get() == 0:
            messagebox.showwarning("Invalid input", "Time on (ms) cannot be 0. Please enter a valid value.")
            add_step_window.lift()
            add_step_window.focus_force()
            return

        if off_time_var is not None and off_time_var.get() == 0:
            messagebox.showwarning("Invalid input", "Time off (ms) cannot be 0. Please enter a valid value.")
            add_step_window.lift()
            add_step_window.focus_force()
            return

        callback()
        add_step_window.destroy()

    def select_step(step_type):
        for widget in add_step_window.winfo_children():
            widget.destroy()

        add_step_window.title(step_type)

        tk.Label(add_step_window, text=f"{step_type} duration:",
                 font=("Helvetica", 16), bg="light blue", fg="black").pack(pady=10)

        def validate_input(value):
            return value.isdigit() or value == ""

        validate_cmd = add_step_window.register(validate_input)

        duration_frame = tk.Frame(add_step_window, bg="light blue")
        duration_frame.pack(pady=5)

        tk.Entry(duration_frame, textvariable=hours_var, width=5, validate="key",
                 validatecommand=(validate_cmd, "%P")).grid(row=0, column=0, padx=5)
        tk.Label(duration_frame, text="h", font=("Helvetica", 14), bg="light blue").grid(row=0, column=1, padx=5)

        tk.Entry(duration_frame, textvariable=minutes_var, width=5, validate="key",
                 validatecommand=(validate_cmd, "%P")).grid(row=0, column=2, padx=5)
        tk.Label(duration_frame, text="m", font=("Helvetica", 14), bg="light blue").grid(row=0, column=3, padx=5)

        tk.Entry(duration_frame, textvariable=seconds_var, width=5, validate="key",
                 validatecommand=(validate_cmd, "%P")).grid(row=0, column=4, padx=5)
        tk.Label(duration_frame, text="s", font=("Helvetica", 14), bg="light blue").grid(row=0, column=5, padx=5)

        if step_type == "Pulsing light":
            tk.Label(add_step_window, text="Pulse rate (Hz):", font=("Helvetica", 14), bg="light blue",
                     fg="black").pack(pady=5)
            tk.Entry(add_step_window, textvariable=pulse_rate_var, width=10, validate="key",
                     validatecommand=(validate_cmd, "%P")).pack(pady=5)

            tk.Label(add_step_window, text="Light intensity (lux):", font=("Helvetica", 14), bg="light blue",
                     fg="black").pack(pady=10)

            intensity_slider = tk.Scale(add_step_window, from_=0, to=100, orient="horizontal", length=300,
                                        tickinterval=20,
                                        sliderlength=20, font=("Helvetica", 12), bg="light blue", fg="black")
            intensity_slider.set(50)
            intensity_slider.pack(pady=10)

            def open_advanced_settings():
                for widget in add_step_window.winfo_children():
                    widget.destroy()

                add_step_window.title("Advanced Settings")

                tk.Label(add_step_window, text="Advanced pulsing light duration:", font=("Helvetica", 14),
                         bg="light blue").pack(pady=10)
                advanced_hours_var = tk.IntVar(value=hours_var.get())
                advanced_minutes_var = tk.IntVar(value=minutes_var.get())
                advanced_seconds_var = tk.IntVar(value=seconds_var.get())

                advanced_duration_frame = tk.Frame(add_step_window, bg="light blue")
                advanced_duration_frame.pack(pady=5)

                tk.Entry(advanced_duration_frame, textvariable=advanced_hours_var, width=5).grid(row=0, column=0,
                                                                                                 padx=5)
                tk.Label(advanced_duration_frame, text="h", font=("Helvetica", 14), bg="light blue").grid(row=0,
                                                                                                          column=1,
                                                                                                          padx=5)

                tk.Entry(advanced_duration_frame, textvariable=advanced_minutes_var, width=5).grid(row=0, column=2,
                                                                                                   padx=5)
                tk.Label(advanced_duration_frame, text="m", font=("Helvetica", 14), bg="light blue").grid(row=0,
                                                                                                          column=3,
                                                                                                          padx=5)

                tk.Entry(advanced_duration_frame, textvariable=advanced_seconds_var, width=5).grid(row=0, column=4,
                                                                                                   padx=5)
                tk.Label(advanced_duration_frame, text="s", font=("Helvetica", 14), bg="light blue").grid(row=0,
                                                                                                          column=5,
                                                                                                          padx=5)

                tk.Label(add_step_window, text="Time a single pulse is on (ms):", font=("Helvetica", 14),
                         bg="light blue").pack(pady=10)
                advanced_on_time_var = tk.IntVar(value=on_time_var.get())
                tk.Entry(add_step_window, textvariable=advanced_on_time_var, width=10).pack(pady=5)

                tk.Label(add_step_window, text="Time between pulses (ms):", font=("Helvetica", 14),
                         bg="light blue").pack(pady=10)
                advanced_off_time_var = tk.IntVar(value=off_time_var.get())
                tk.Entry(add_step_window, textvariable=advanced_off_time_var, width=10).pack(pady=5)

                tk.Label(add_step_window, text="Light intensity (lux):", font=("Helvetica", 14), bg="light blue",
                         fg="black").pack(pady=10)
                intensity_slider = tk.Scale(add_step_window, from_=0, to=100, orient="horizontal", length=300,
                                            tickinterval=20, sliderlength=20, font=("Helvetica", 12), bg="light blue",
                                            fg="black")
                intensity_slider.set(50)
                intensity_slider.pack(pady=10)

                def add_advanced_pulsing_step():
                    add_step_to_queue("Advanced pulsing light",
                                      get_total_duration(advanced_hours_var, advanced_minutes_var,
                                                         advanced_seconds_var),
                                      on_time=advanced_on_time_var.get(),
                                      off_time=advanced_off_time_var.get(),
                                      lux=intensity_slider.get())

                btn_frame = tk.Frame(add_step_window, bg="light blue")
                btn_frame.pack(pady=20)

                tk.Button(btn_frame, text="Add Step to Queue",
                          command=lambda: validate_and_add_step(add_advanced_pulsing_step,
                                                                h_var=advanced_hours_var,
                                                                m_var=advanced_minutes_var,
                                                                s_var=advanced_seconds_var,
                                                                on_time_var=advanced_on_time_var,
                                                                off_time_var=advanced_off_time_var),
                          bg="blue", fg="white", font=("Helvetica", 14), width=16).grid(row=0, column=1, padx=10)

                tk.Button(btn_frame, text="Back", command=lambda: select_step("Pulsing light"), bg="red", fg="white",
                          font=("Helvetica", 14), width=6).grid(row=0, column=0, padx=10)

            tk.Button(add_step_window, text="Advanced Settings", command=open_advanced_settings, bg="blue", fg="white",
                      font=("Helvetica", 14), width=16).pack(pady=10)

            def add_pulsing_step():
                light_intensity = intensity_slider.get()
                add_step_to_queue(step_type, get_total_duration(), pulse_rate_var.get(), lux=light_intensity)

            btn_frame = tk.Frame(add_step_window, bg="light blue")
            btn_frame.pack(pady=20)

            tk.Button(btn_frame, text="Add Step to Queue",
                      command=lambda: validate_and_add_step(add_pulsing_step,
                                                            pulse_rate_var=pulse_rate_var),
                      bg="blue", fg="white", font=("Helvetica", 14), width=16).grid(row=0, column=1, padx=10)

            tk.Button(btn_frame, text="Back", command=show_step_selection, bg="red", fg="white",
                      font=("Helvetica", 14), width=6).grid(row=0, column=0, padx=10)

        elif step_type == "Continuous light":
            tk.Label(add_step_window, text="Light intensity (lux):", font=("Helvetica", 14), bg="light blue",
                     fg="black").pack(pady=10)
            intensity_slider = tk.Scale(add_step_window, from_=0, to=100, orient="horizontal", length=300,
                                        tickinterval=20, sliderlength=20, font=("Helvetica", 12), bg="light blue",
                                        fg="black")
            intensity_slider.set(50)
            intensity_slider.pack(pady=10)

            def add_continuous_light_step():
                light_intensity = intensity_slider.get()
                add_step_to_queue(step_type, get_total_duration(), lux=light_intensity)

            btn_frame = tk.Frame(add_step_window, bg="light blue")
            btn_frame.pack(pady=20)

            tk.Button(btn_frame, text="Add Step to Queue",
                      command=lambda: validate_and_add_step(add_continuous_light_step),
                      bg="blue", fg="white", font=("Helvetica", 14), width=16).grid(row=0, column=1, padx=10)

            tk.Button(btn_frame, text="Back", command=show_step_selection, bg="red", fg="white",
                      font=("Helvetica", 14), width=6).grid(row=0, column=0, padx=10)

        else:
            def add_no_light_step():
                add_step_to_queue(step_type, get_total_duration())

            btn_frame = tk.Frame(add_step_window, bg="light blue")
            btn_frame.pack(pady=20)

            tk.Button(btn_frame, text="Add Step to Queue",
                      command=lambda: validate_and_add_step(add_no_light_step),
                      bg="blue", fg="white", font=("Helvetica", 14), width=16).grid(row=0, column=1, padx=10)

            tk.Button(btn_frame, text="Back", command=show_step_selection, bg="red", fg="white",
                      font=("Helvetica", 14), width=6).grid(row=0, column=0, padx=10)

    show_step_selection()


# This function receives real-time sensor data from the Arduino and plots
# a graph with the data while updating every 500ms until the experiment finishes.
def open_sensor_data_window():
    global sensor_data_window, sensor_values, time_counter, times, line, canvas, ax

    if sensor_data_window is not None and tk.Toplevel.winfo_exists(sensor_data_window):
        return

    sensor_data_window = tk.Toplevel(root)
    sensor_data_window.title("Sensor Data")
    sensor_data_window.geometry("600x400")

    sensor_values.clear()
    times.clear()
    time_counter = 0

    fig = Figure(figsize=(6, 4))
    ax = fig.add_subplot(111)
    ax.set_title("Real-time Sensor Data")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("LED Intensity (lux)")

    line, = ax.plot([], [], "b-")

    canvas = FigureCanvasTkAgg(fig, master=sensor_data_window)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_graph():
        global time_counter

        if experiment_running and arduino is not None:
            if arduino.in_waiting > 0:
                try:
                    sensor_value = arduino.readline().decode('utf-8').strip()
                    print(f"Received: {sensor_value}")

                    if sensor_value.replace(".", "", 1).isdigit():
                        sensor_value = float(sensor_value)
                        sensor_values.append(sensor_value)
                        times.append(time_counter)
                        time_counter += 1

                        line.set_xdata(times)
                        line.set_ydata(sensor_values)
                        ax.relim()
                        ax.autoscale_view()
                        canvas.draw()

                except Exception as e:
                    print(f"Error reading serial: {e}")

            sensor_data_window.after(500, update_graph)
        else:
            sensor_data_window.destroy()

    update_graph()
    sensor_data_window.protocol("WM_DELETE_WINDOW", lambda: close_sensor_data_window())


# This function closes the sensor data window and stops data collection.
# It is triggered when the window's close button is clicked.
def close_sensor_data_window():
    global sensor_data_window
    sensor_data_window.destroy()
    sensor_data_window = None


# This section sets up the main IllumiCell GUI window, configuring its title, size, and background.
root = tk.Tk()
root.title("IllumiCell")
root.geometry("1350x700")
root.configure(bg="light blue")

show_instructions_overlay()


title_label = tk.Label(root, text="IllumiCell", font=("Helvetica", 30, "bold"), bg="light blue")
title_label.place(relx=0.5, rely=0.09, anchor="center")  # Centered horizontally

description_label = tk.Label(root,
                             text="Device that administers light to study the effects of in vitro activation of skin cell opsins",
                             font=("Helvetica", 16), bg="light blue", wraplength=650)
description_label.place(relx=0.5, rely=0.20, anchor="center")  # Centered text

initialize_arduino()

add_step_button = tk.Button(root, text="Add step", command=open_add_step_window, bg="blue", fg="white",
                            font=("Helvetica", 14), width=8)
add_step_button.place(relx=0.42, rely=0.3, anchor="center")

open_button = tk.Button(root, text="Open saved files", command=open_experiment, bg="blue", fg="white",
                        font=("Helvetica", 14), width=14)
open_button.place(relx=0.58, rely=0.3, anchor="center")

queue_label = tk.Label(root, text="Experiment queue:", font=("Helvetica", 16), bg="light blue")
queue_label.place(relx=0.5, rely=0.39, anchor="center")

queue_listbox = tk.Listbox(root, font=("Helvetica", 12), height=10, width=71, selectmode=tk.SINGLE)
queue_listbox.place(relx=0.5, rely=0.59, anchor="center")  # Adjusts dynamically

queue_listbox.bind("<ButtonRelease-1>", on_step_click)
root.bind("<Button-1>", on_click_outside)

time_label = tk.Label(root, text="Elapsed Time: 0 seconds", font=("Helvetica", 14), bg="light blue")

run_button = tk.Button(root, text="Run", command=run_experiment, bg="green", fg="white",
                       font=("Helvetica", 14), width=5)
run_button.place(relx=0.5, rely=0.8, anchor="center")  # Centered

save_button = tk.Button(root, text="Save", command=save_experiment, bg="blue", fg="white",
                        font=("Helvetica", 14), width=6)
save_button.place(relx=0.35, rely=0.8, anchor="center")

reset_button = tk.Button(root, text="Clear all", command=reset_experiment, bg="red", fg="white",
                         font=("Helvetica", 14), width=8)
reset_button.place(relx=0.65, rely=0.8, anchor="center")

delete_button = tk.Button(root, text="Delete step", command=delete_step, bg="red", fg="white", font=("Helvetica", 14), width=10)

view_sensor_button = tk.Button(root, text="View sensor data      ", command=open_sensor_data_window, bg="blue", fg="white", font=("Helvetica", 14), width=18)


image = tk.PhotoImage(
        file="C:\\Users\\lucia\\OneDrive - Imperial College London\\##Year 3 AFTER interruption\\Group project\\#GUI\\info_icon.png")
image_resize = image.subsample(17, 17)
info_icon = tk.Button(root, image=image_resize, command=open_sensor_data_window, bg="blue", bd=0)


# Displays a tooltip near the mouse pointer when triggered, showing a description of what the 'View sensor data' button does.
def show_tooltip(event):
    tooltip = tk.Toplevel(root)
    tooltip.wm_overrideredirect(True)

    tooltip.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")

    tooltip.configure(bg="white")

    label = tk.Label(
        tooltip,
        text="Click to view LED intensity values (lux) recorded in real-time by the light sensor inside IllumiCell.",
        bg="white",
        fg="black",
        font=("Helvetica", 11),
        wraplength=250,
        justify="left",
        padx=10,
        pady=5
    )

    label.pack()
    event.widget.tooltip = tooltip


# Hides the tooltip when the user moves the mouse away.
def hide_tooltip(event):
    if hasattr(event.widget, 'tooltip'):
        event.widget.tooltip.destroy()
        event.widget.tooltip = None

info_icon.bind("<Enter>", show_tooltip)
info_icon.bind("<Leave>", hide_tooltip)

update_queue_listbox()

root.mainloop()
