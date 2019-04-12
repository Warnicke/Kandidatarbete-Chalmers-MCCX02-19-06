from typing import Any, Union

import time
import threading
import numpy as np
import queue

#import Radar
import bluetooth_server        # import bluetooth class
import data_acquisition      # Import class which collects and filters relevant data.
import signal_processing
# import bluetooth_app

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
                                     "RR_filtered_queue": RR_filtered_queue, "RR_final_queue": RR_final_queue,
                                     "RTB_final_queue": RTB_final_queue, "go": go, "run_measurement": run_measurement,
                                     "sample_freq": sample_freq}
    # heart_rate_queue = queue.Queue()
    # resp_rate_queue = queue.Queue()

    # radar = Radar.Radar(radar_queue, go)
    # radar.start()
    dataAcquisition = data_acquisition.DataAcquisition(list_of_variables_for_threads)
    dataAcquisition.start()
    signal_processings = signal_processing.SignalProcessing(list_of_variables_for_threads)

    bluetooth_servers = bluetooth_server.BluetoothServer(list_of_variables_for_threads)
    #bluetooth_servers = bluetooth_app.bluetooth_app(go)
    bluetooth_servers.app_data()
    bluetooth_servers.connect_device_thread.join()

    print('Bluetooth server is closed')
    # time.sleep(300)
    #list_of_variables_for_threads["go"] = go.pop(0)
    # radar.join()
    # signal_processings.heart_rate_thread.join()
    signal_processings.schmittTrigger_thread.join()
    #print("signal_processing is closed")
    time.sleep(1 / 20)  # Making sure signal processing have data in queue before radar quits.
    dataAcquisition.join()
    print("radar is closed")

    #print("connect_device is closed")

    print('Shut down succeed')
    #subprocess.call(["sudo", "shutdown", "-r", "now"])


if __name__ == "__main__":
    main()