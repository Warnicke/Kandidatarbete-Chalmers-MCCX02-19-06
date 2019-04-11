from typing import Any, Union

import time
import threading
import numpy as np
import queue

#import Radar
import bluetooth_server        # import bluetooth class
import data_acquisition      # Import class which collects and filters relevant data.
#import signal_processing

# Bluetooth imports
import bluetooth
import math
import random
import subprocess       # for Raspberry Pi shutdown


def main():
    # subprocess.call(
    #    "./Documents/evk_service_linux_armv71_xc112/utils/acc_streaming_server_rpi_xc112_r2b_xr112_r2b_a111_r2c")

    radar_queue = queue.Queue()  # Not used right now?
    HR_filtered_queue = queue.Queue()
    HR_final_queue = queue.Queue()
    RR_filtered_queue = queue.Queue()
    RR_final_queue = queue.Queue()
    RTB_final_queue = queue.Queue()  # Real time breating final queue
    go = ["True"]
    run_measurement = []
    sample_freq = 0
    list_of_variables_for_threads = {"HR_filtered_queue": HR_filtered_queue, "HR_final_queue": HR_final_queue,
                                     "RR_filtered_queue": RR_filtered_queue, "RR_final_queue": RR_final_queue, "RTB_final_queue": RTB_final_queue, "go": go, "run measurement": run_measurement, "sample_freq": sample_freq}
    # heart_rate_queue = queue.Queue()
    # resp_rate_queue = queue.Queue()

    # radar = Radar.Radar(radar_queue, go)
    # radar.start()
    dataAcquisition = data_acquisition.DataAcquisition(list_of_variables_for_threads)
    dataAcquisition.start()
    # signal_processing = signal_processing.SignalProcessing(
    #    list_of_variables_for_threads)
    # signal_processing.thread_start()

    # bluetooth_server = bluetooth_server.BluetoothServer(list_of_variables_for_threads)
    # bluetooth_server.app_data()
    # print('End of bluetooth_app')
    time.sleep(300)
    # interrupt_queue.put(1)
    list_of_variables_for_threads["go"] = go.pop(0)
    # radar.join()
    # signal_processing.heart_rate_thread.join()
    # signal_processing.schmittTrigger_thread.join()
    time.sleep(1 / 20)  # Making sure signal processing have data in queue before radar quits.
    dataAcquisition.join()
    print("radar is closed")
    # bluetooth_server.connect_device_thread.join()
    print("connect_device is closed")

    print('Shut down succeed')
    #subprocess.call(["sudo", "shutdown", "-r", "now"])


if __name__ == "__main__":
    main()
