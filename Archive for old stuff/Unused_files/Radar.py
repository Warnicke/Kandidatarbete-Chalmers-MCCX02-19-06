import time
import threading
import numpy as np
from scipy import signal
import queue
import copy       # import for static variable run in class

from acconeer_utils.clients.reg.client import RegClient
from acconeer_utils.clients.json.client import JSONClient
from acconeer_utils.clients import configs
from acconeer_utils import example_utils
from acconeer_utils.mpl_process import PlotProcess, PlotProccessDiedException, FigureUpdater


class Radar(threading.Thread):
    def __init__(self, HR_filter_queue, go):  # Lägg till RR_filter_queue som inputargument
        self.go = go
        # Setup for collecting data from radar
        self.args = example_utils.ExampleArgumentParser().parse_args()
        example_utils.config_logging(self.args)
        if self.args.socket_addr:
            self.client = JSONClient(self.args.socket_addr)
            # Test för att se vilken port som används av radarn
            print("RADAR Port = " + self.args.socket_addr)
        else:
            port = self.args.serial_port or example_utils.autodetect_serial_port()
            self.client = RegClient(port)

        self.client.squeeze = False
        self.config = configs.IQServiceConfig()
        self.config.sensor = self.args.sensors

        self.config.range_interval = [0.2, 0.6]  # Measurement interval
        self.config.sweep_rate = 20  # Frequency for collecting data
        self.config.gain = 1  # Gain between 0 and 1.
        self.time = 1  # Duration for a set amount of sequences
        self.seq = self.config.sweep_rate * self.time  # Amount of sequences during a set time and sweep freq

        self.info = self.client.setup_session(self.config)  # Setup acconeer radar session
        self.num_points = self.info["data_length"]  # Amount of data points per sampel
        self.data_getting = 0  # Inedex for printing still getting data once a second

        self.HR_filter_queue = HR_filter_queue
        # self.a = a
        # self.RR_filter_queue = RR_filter_queue
        # Initiation for tracking method
        self.N_avg = 10         # How manny peaks averaged over when calculating peaks_filtered
        self.I_peaks = np.zeros(self.N_avg)
        self.locs = np.zeros(self.N_avg)
        self.I_peaks_filtered = np.zeros(self.N_avg)
        self.tracked_distance = np.zeros(self.N_avg)
        self.tracked_amplitude = np.zeros(self.N_avg)
        self.tracked_phase = np.zeros(self.N_avg)
        self.threshold = 0  # variable for finding peaks above threshold
        self.data_idx = 0  # Index in vector for tracking. Puts new tracked peak into tracking vector
        # converts index to real length
        self.real_dist = np.linspace(
            self.config.range_interval[0], self.config.range_interval[1], num=self.num_points)
        self.counter = 0  # Used only for if statement only for first iteration and not when data_idx goes back to zero

        super(Radar, self).__init__()  # Inherit threading vitals

    # Loop which collects data from the radar, tracks the maximum peak and filters it for further signal processing. The final filtered data is put into a queue.
    def run(self):

        self.client.start_streaming()  # Starts Acconeers streaming server
        # static variable impported from bluetooth_app class (In final version)
        while self.go:
            # for i in range(self.seq*2):
            data = self.get_data()
            tracked_data = self.tracking(data)
            print("Tracked distance: ", tracked_data)
            # self.filter_HeartRate()
            # self.filter_RespRate()
            self.data_getting += 1
            if self.data_getting % self.config.sweep_rate == 0:
                print("Still getting data")
                self.HR_filter_queue.put(2)
            # Resets matrix index to zero for printing getting data.
            if self.data_getting >= self.config.sweep_rate:
                self.data_getting = 0
        print("End of getting data from radar")

        self.client.disconnect()

    # Method to collect data from the streaming server
    def get_data(self):
        # self.data should be accessable from all other methods
        info, data = self.client.get_next()
        #print("How long the data is ", data)
        return np.array(data)

    # Filter for heart rate using the last X sampels according to data_idx. Saves data to queue
    # def filter_HeartRate(self):
    #     # HR_peak_vector = copy.copy(self.peak_vector)
    #     # for i in range(5):
    #     #     HR_peak_vector[0][i] = 0
    #     # # self.HR_filter_queue.put(HR_peak_vector)
    #     pass

    # Filter for Respitory rate. Saves data to queue

    # def filter_RespRate(self):
    #     # RR_peak_vector = copy.copy(self.peak_vector)
    #     # for i in range(5):
    #     #     RR_peak_vector[0][i] = 0
    #     # self.RR_filter_queue.put(RR_peak_vector)
    #     pass

    # Tracks the maximum peak from collected data which is filtered for further signal processing
    def tracking(self, data):
        data = np.transpose(data)
        # self.data = data      # Removed because using local data variable. Easier to understand how data travells in class
        # print("Length of data input ", str(len(data)))
        if self.data_idx == 0 and self.counter == 0:      # things that only happens first time
            I = np.argmax(np.abs(data))
            self.I_peaks[:] = I
            self.I_peaks_filtered[0] = self.I_peaks[0]
            self.tracked_distance[0] = self.real_dist[int(self.I_peaks_filtered[0])]
            self.tracked_amplitude[0] = np.abs(data[int(self.I_peaks_filtered[0])])
            self.tracked_phase[0] = np.angle(data[int(self.I_peaks_filtered[0])])

        # After first seq continous tracking
        else:
            self.locs, _ = signal.find_peaks(np.abs(data))        # find local maximas in data
            # removes local maxima if under threshhold
            self.locs = [x for x in self.locs if(np.abs(data[x]) > self.threshold)]
            difference = np.subtract(self.locs, self.I_peaks_filtered[self.data_idx])
            print("locks: ", self.locs)
            print("Last I_peaks_filtered: ", self.I_peaks_filtered[self.data_idx])
            print("difference: ", difference)
            abs = np.abs(difference)
            argmin = np.argmin(abs)
            Index_in_locks = argmin     # index of closest peak in locs

            # Index_in_locks = np.argmin(np.abs(self.locks - self.I_peaks_filtered[self.data_idx - 1]))       # difference between current peak index and last peak index

            if len(self.locs) == 0:        # if no peak is found
                self.I_peaks[self.data_idx] = self.I_peaks[self.data_idx - 1]
                print("Last peak value. Not updated.")
            else:
                I = self.locs[int(Index_in_locks)]
                self.I_peaks[self.data_idx] = I

            print("I_peaks: ", self.I_peaks)

            # if self.counter == 0:  # Questions about this part.
            #     self.i_avg_start = 0        # this will be 0 as long as counter == 0
            #     if self.data_idx == self.N_avg - 1:  # change dist to nmbr of sequences later
            #         self.counter = 1
            # else:
            # self.i_avg_start = self.data_idx - (self.N_avg - 1)

            self.I_peaks_filtered[self.data_idx] = np.round(np.mean(self.I_peaks))      # mean value of N_avg latest peaks

            # determines threshold
            self.threshold = np.abs(data[int(self.I_peaks_filtered[self.data_idx])])*0.5

            self.tracked_distance[self.data_idx] = self.real_dist[int(self.I_peaks_filtered[self.data_idx])]
            self.tracked_amplitude[self.data_idx] = np.abs(data[int(self.I_peaks_filtered[self.data_idx])])
            self.tracked_phase[self.data_idx] = np.angle(data[int(self.I_peaks_filtered[self.data_idx])])

        # print("I_peaks_filtered: ", self.I_peaks_filtered)

        self.data_idx += 1
        if self.data_idx == self.N_avg:
            self.data_idx = 0
        return self.tracked_distance[self.data_idx - 1]
