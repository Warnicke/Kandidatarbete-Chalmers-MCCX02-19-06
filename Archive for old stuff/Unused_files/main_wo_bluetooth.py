import time
import threading
import numpy as np
import queue

import Radar

# Queues:
radar_queue = queue.Queue()
interrupt_queue = queue.Queue()
# heart_rate_queue = queue.Queue()
# resp_rate_queue = queue.Queue()


radar = Radar.Radar(radar_queue, interrupt_queue)
radar.start()

time.sleep(10)
interrupt_queue.put(1)
radar.join
