import time
import queue
import faster_fifo
from random import random
from threading import Thread


# generate work
def producer(queue, n):
    for i in range(n):
        value = random()
        queue.put(value)
    queue.put(None)


def consumer(queue, verbose):
    while True:
        item = queue.get()  # blocking wait
        if item is None:
            break
        if verbose:
            print(f'>got {item}')


if __name__ == '__main__':

    def queue_time(n, fast):
        q = faster_fifo.Queue() if fast else queue.Queue()
        p_thread = Thread(target=producer, args=(q, n))
        c_thread = Thread(target=consumer, args=(q, False))

        st = time.time()
        p_thread.start()
        c_thread.start()
        p_thread.join()
        c_thread.join()
        et = time.time()

        elapsed_time = et - st
        print(f"Execution time for fast={fast}: {elapsed_time}sec")
        return elapsed_time

    n = 10000
    queue_time(n, True)
    queue_time(n, False)

    def timeit(m, fast):
        av = 0
        for i in range(m):
            av += queue_time(n, True)
        print(f"Average execution time for fast={fast}: {av/m}sec")

    timeit(10, True)
    timeit(10, False)
