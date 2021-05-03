import simpy
import random
import itertools
from functools import partial, wraps
import pandas as pd
import matplotlib.pyplot as plt

class fsru:
    def __init__(self, env):
        self.sendout = 1097
        self.min = 3300
        self.optim = 14e3
        self.arrival_time = [5, 33]
        self.called = False

        self.connection = simpy.Resource(env, capacity=1)
        self.gas_tank = simpy.Container(env, init=174e3, capacity=174e3)
        self.mon_proc = env.process(self.monitor_tank(env))

    def monitor_tank(self, env):
        while True:
            if self.gas_tank.level <= self.optim:
                if not self.called:
                    self.called = True
                    env.process(tanker(env, self))
            print(f'sending. tank level @ {env.now}: {self.gas_tank.level}')

            yield env.timeout(1)


def tanker(env, fsru):
    with fsru.connection.request() as req:
        yield req
        yield env.timeout(random.randint(*fsru.arrival_time))
        print(f'Tanker arriving at {env.now}')
        amount = 80e3
        time = 15-1
        apt = amount/time
        print(f'---- TANKER ------')
        print(f'Current Level: {fsru.gas_tank.level}')
        print(f'End Level: {fsru.gas_tank.level + amount}')
        print(f'------------------')
        for i in range(time):
            yield fsru.gas_tank.put(apt)
            yield env.timeout(1)
            print(f'filling @ {env.now}. tank level: {fsru.gas_tank.level}')
        fsru.called = False
        print(f'Tanker leaving @ {env.now}, tank level: {fsru.gas_tank.level}')


def sendout(env, fsru):
    for i in itertools.count():
        amnt_send = min([1097, fsru.gas_tank.level - fsru.min])
        if amnt_send > 0:
            fsru.gas_tank.get(amnt_send)
        yield env.timeout(1)

def patch_resource(resource, pre=None, post=None):
     """Patch *resource* so that it calls the callable *pre* before each
     put/get/request/release operation and the callable *post* after each
     operation.  The only argument to these functions is the resource
     instance.

     """
     def get_wrapper(func):
         # Generate a wrapper for put/get/request/release
         @wraps(func)
         def wrapper(*args, **kwargs):
             # This is the actual wrapper
             # Call "pre" callback
             if pre:
                 pre(resource)

             # Perform actual operation
             ret = func(*args, **kwargs)

             # Call "post" callback
             if post:
                 post(resource)

             return ret
         return wrapper

     # Replace the original operations with our wrapper
     for name in ['put', 'get', 'request', 'release']:
         if hasattr(resource, name):
             setattr(resource, name, get_wrapper(getattr(resource, name)))

def monitor(data, resource):
     """This is our monitoring callback."""
     item = (
         resource._env.now,  # The current simulation time
         resource.level,  # The level of the container
     )
     data.append(item)

if '__main__' in __name__:
    env = simpy.Environment()
    fsru = fsru(env)

    data = []
    monitor = partial(monitor, data)
    patch_resource(fsru.gas_tank, post=monitor)  # Patches (only) this resource instance
    env.process(sendout(env, fsru))
    env.run(200)

    f_lvl = [val[1] for val in data]
    idx = [val[0] for val in data]

    df = pd.DataFrame(
        {
            'row' : idx,
            'lvl' : f_lvl
        }
    )
    df.to_csv("data.csv")
    plt.plot(df.row, df.lvl)
    plt.show()