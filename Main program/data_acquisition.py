import time
import threading
import numpy as np
from scipy import signal
import queue

import pyqtgraph as pg
from PyQt5 import QtCore

import filter

from acconeer_utils.clients.reg.client import RegClient
from acconeer_utils.clients.json.client import JSONClient
from acconeer_utils.clients import configs
from acconeer_utils import example_utils
from acconeer_utils.pg_process import PGProcess, PGProccessDiedException


class DataAcquisition(threading.Thread):
    def __init__(self, list_of_variables_for_threads):
        super(DataAcquisition, self).__init__()  # Inherit threading vitals
        self.go = list_of_variables_for_threads["go"]
        self.list_of_variables_for_threads = list_of_variables_for_threads
        # Setup for collecting data from acconeer's radar files.
        self.args = example_utils.ExampleArgumentParser().parse_args()
        example_utils.config_logging(self.args)
        if self.args.socket_addr:
            self.client = JSONClient(self.args.socket_addr)
            print("RADAR Port = " + self.args.socket_addr)
        else:
            port = self.args.serial_port or example_utils.autodetect_serial_port()
            self.client = RegClient(port)
        self.client.squeeze = False
        self.config = configs.IQServiceConfig()
        self.config.sensor = self.args.sensors

        # Settings for radar setup
        self.config.range_interval = [0.4, 1.5]  # Measurement interval
        # Frequency for collecting data. To low means that fast movements can't be tracked.
        self.config.sweep_rate = 80
        # The hardware of UART/SPI limits the sweep rate.
        self.config.gain = 0.7  # Gain between 0 and 1. Larger gain increase the SNR, but come at a cost
        # with more instability. Optimally is around 0.7
        self.info = self.client.setup_session(self.config)  # Setup acconeer radar session
        self.data_length = self.info["data_length"]  # Length of data per sampel

        # Inputs for tracking
        self.first_data = True  # first time data is processed
        self.f = self.config.sweep_rate  # frequency
        self.dt = 1 / self.f
        self.low_pass_const = self.low_pass_filter_constants_function(
            0.25, self.dt)  # Constant for a small low-pass filter to
        # smooth the changes. tau changes the filter weight, lower tau means shorter delay. Usually tau = 0.25 is good.
        self.number_of_averages = 2  # number of averages for tracked peak
        self.plot_time_length = 10  # length of plotted data
        # number of time samples when plotting
        self.number_of_time_samples = int(self.plot_time_length / self.dt)
        # distance over time
        self.tracked_distance_over_time = np.zeros(
            self.number_of_time_samples)  # array for distance over time plot
        self.local_peaks_index = []  # index of local peaks
        self.track_peak_index = []  # index of last tracked peaks
        self.track_peaks_average_index = None  # average of last tracked peaks
        self.threshold = None  # threshold for removing small local peaks
        self.tracked_distance = None
        self.tracked_amplitude = None
        self.tracked_phase = None
        self.tracked_data = None  # the final tracked data that is returned
        self.low_pass_amplitude = None
        self.low_pass_track_peak = None
        self.track_peak_relative_position = None

        # Graphs
        self.pg_updater = PGUpdater(self.config)
        self.pg_process = PGProcess(self.pg_updater)
        self.pg_process.start()
        # acconeer graph
        self.low_pass_vel = 0
        self.hist_vel = np.zeros(self.number_of_time_samples)
        self.hist_pos = np.zeros(self.number_of_time_samples)
        self.last_data = None  # saved old data

        # filter
        self.highpass_HR = filter.Filter('highpass_HR')
        self.lowpass_HR = filter.Filter('lowpass_HR')
        self.highpass_RR = filter.Filter('highpass_RR')
        self.lowhpass_RR = filter.Filter('lowpass_RR')

        self.HR_filtered_queue = list_of_variables_for_threads["HR_filtered_queue"]
        self.RR_filtered_queue = list_of_variables_for_threads["RR_filtered_queue"]

    def run(self):
        self.client.start_streaming()  # Starts Acconeers streaming server
        while self.list_of_variables_for_threads["go"]:
            # This data is an 1D array in terminal print, not in Python script however....
            data = self.get_data()
            tracked_data = self.tracking(data)  # processing data and tracking peaks
            if tracked_data is not None:
                # filter the data
                highpass_filtered_data_HR = self.highpass_HR.filter(tracked_data["tracked phase"])
                bandpass_filtered_data_HR = self.lowpass_HR.filter(highpass_filtered_data_HR)
                highpass_filtered_data_RR = self.highpass_RR.filter(tracked_data["tracked phase"])
                bandpass_filtered_data_RR = self.lowpass_RR.filter(highpass_filtered_data_RR)

                # put filtered data in output queue to send to SignalProcessing
                self.HR_filtered_queue.put(bandpass_filtered_data_HR)
                self.RR_filtered_queue.put(bandpass_filtered_data_RR)
                try:
                    self.pg_process.put_data(tracked_data)  # plot data
                except PGProccessDiedException:
                    break
        print("out of while go in radar")
        self.client.disconnect()

    def get_data(self):
        info, data = self.client.get_next()
        return data

    def tracking(self, data):
        data = np.array(data).flatten()
        data_length = len(data)
        amplitude = np.abs(data)
        power = amplitude * amplitude

        # Find and track peaks
        if np.sum(power) > 1e-6:
            max_peak_index = np.argmax(power)
            if self.first_data:  # first time
                self.track_peak_index.append(max_peak_index)  # global max peak
                self.track_peaks_average_index = max_peak_index
            else:
                self.local_peaks_index, _ = signal.find_peaks(power)  # find local max in data
                index = 0
                index_list = []
                for peak in self.local_peaks_index:
                    if np.abs(amplitude[peak]) < self.threshold:
                        index_list.append(index)
                        index += 1
                # deletes all indexes with amplitude < threshold
                np.delete(self.local_peaks_index, index_list)
                if len(self.local_peaks_index) == 0:  # if no large peaks were found, use the latest value instead
                    print("No local peak found")
                    self.track_peak_index.append(self.track_peak_index[-1])
                else:
                    # Difference between found local peaks and last tracked peak
                    peak_difference_index = np.subtract(
                        self.local_peaks_index, self.track_peaks_average_index)
                    # The tracked peak is expected to be the closest local peak found
                    self.track_peak_index.append(
                        self.local_peaks_index[np.argmin(np.abs(peak_difference_index))])
                if len(self.track_peak_index) > self.number_of_averages:
                    self.track_peak_index.pop(0)  # remove oldest value
                if amplitude[self.track_peak_index[-1]] < 0.5 * amplitude[
                        max_peak_index]:  # if there is a much larger peak
                    self.track_peak_index.clear()  # reset the array
                    self.track_peak_index.append(max_peak_index)  # new peak is global max
                self.track_peaks_average_index = int(  # Average and smooth the movements of the tracked peak
                    np.round(self.low_pass_const * (np.average(self.track_peak_index))
                             + (1 - self.low_pass_const) * self.track_peaks_average_index))
            # threshold for next peak
            self.threshold = np.abs(amplitude[self.track_peaks_average_index]) * 0.8
            # so it won't follow a much smaller peak
            self.track_peak_relative_position = self.track_peaks_average_index / \
                len(data)  # Position of the peak
            # relative the range of the data
            # Converts relative distance to absolute distance
            self.tracked_distance = (1 - self.track_peaks_average_index / len(data)) * self.config.range_interval[
                0] + self.track_peaks_average_index / len(data) * self.config.range_interval[1]
            # Tracked amplitude is absolute value of data for the tracked index
            self.tracked_amplitude = np.abs(data[self.track_peaks_average_index])
            # Tracked phase is the angle between I and Q in data for tracked index
            self.tracked_phase = np.angle(data[self.track_peaks_average_index])
        else:
            #track_peak_relative_position = 0
            self.tracked_distance = 0

        # Plots
        if self.first_data:
            self.tracked_data = None
            self.low_pass_amplitude = amplitude
        else:
            # Amplitude of data for plotting
            self.low_pass_amplitude = self.low_pass_const * amplitude + \
                (1 - self.low_pass_const) * self.low_pass_amplitude
            self.tracked_distance_over_time = np.roll(
                self.tracked_distance_over_time, -1)  # Distance over time
            # - np.mean(self.tracked_distance_over_time)
            self.tracked_distance_over_time[-1] = self.tracked_distance

            com_idx = int(self.track_peak_relative_position * data_length)
            delta_angle = np.angle(data[com_idx] * np.conj(self.last_data[com_idx]))
            vel = self.f * 2.5 * delta_angle / (2 * np.pi)
            self.low_pass_vel = self.low_pass_const * vel + \
                (1 - self.low_pass_const) * self.low_pass_vel
            dp = self.low_pass_vel / self.f
            self.hist_pos = np.roll(self.hist_pos, -1)
            self.hist_pos[-1] = self.hist_pos[-2] + dp
            plot_hist_pos = self.hist_pos - self.hist_pos.mean()

            # Tracked data to return and plot
            self.tracked_data = {"tracked distance": self.tracked_distance,
                                 "tracked amplitude": self.tracked_amplitude, "tracked phase": self.tracked_phase,
                                 "abs": self.low_pass_amplitude, "tracked distance over time": plot_hist_pos,
                                 "tracked distance over time 2": self.tracked_distance_over_time}
        self.last_data = data
        self.first_data = False
        return self.tracked_data

    # Creates low-pass filter constants for a very small low-pass filter
    def low_pass_filter_constants_function(self, tau, dt):
        return 1 - np.exp(-dt / tau)


class PGUpdater:
    def __init__(self, config):
        self.config = config
        self.interval = config.range_interval

    def setup(self, win):
        win.resize(1600, 1000)
        win.setWindowTitle("Track distance example")

        # Plot amplitude from data and the tracked distance
        self.distance_plot = win.addPlot(row=0, col=0, colspan=2)
        self.distance_plot.showGrid(x=True, y=True)
        self.distance_plot.setLabel("left", "Amplitude")
        self.distance_plot.setLabel("bottom", "Depth (m)")
        self.distance_curve = self.distance_plot.plot(pen=example_utils.pg_pen_cycler(0))
        pen = example_utils.pg_pen_cycler(1)
        pen.setStyle(QtCore.Qt.DashLine)
        self.distance_inf_line = pg.InfiniteLine(pen=pen)
        self.distance_plot.addItem(self.distance_inf_line)

        # Dynamic plot to show breath over time
        self.distance_over_time_plot = win.addPlot(row=1, col=0)
        self.distance_over_time_plot.showGrid(x=True, y=True)
        self.distance_over_time_plot.setLabel("left", "Distance")
        self.distance_over_time_plot.setLabel("bottom", "Time (s)")
        self.distance_over_time_curve = self.distance_over_time_plot.plot(
            pen=example_utils.pg_pen_cycler(0))
        self.distance_over_time_plot.setYRange(-8, 8)

        # Plot for tracked distance over time
        self.distance_over_time_plot2 = win.addPlot(row=1, col=1)
        self.distance_over_time_plot2.showGrid(x=True, y=True)
        self.distance_over_time_plot2.setLabel("left", "Distance")
        self.distance_over_time_plot2.setLabel("bottom", "Time (s)")
        self.distance_over_time_curve2 = self.distance_over_time_plot2.plot(
            pen=example_utils.pg_pen_cycler(0))
        self.distance_over_time_plot2.setYRange(0.4, 1.5)

        self.smooth_max = example_utils.SmoothMax(self.config.sweep_rate)
        self.first = True

    def update(self, data):
        if self.first:
            self.xs = np.linspace(*self.interval, len(data["abs"]))
            self.ts = np.linspace(-5, 0, len(data["tracked distance over time"]))
            self.first = False

        self.distance_curve.setData(self.xs, np.array(data["abs"]).flatten())
        self.distance_plot.setYRange(0, self.smooth_max.update(np.amax(data["abs"])))
        self.distance_inf_line.setValue(data["tracked distance"])
        self.distance_over_time_curve.setData(self.ts, data["tracked distance over time"])
        self.distance_over_time_curve2.setData(self.ts, data["tracked distance over time 2"])
