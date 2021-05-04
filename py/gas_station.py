import simpy
import random
import itertools
from functools import partial, wraps
import pandas as pd
import matplotlib.pyplot as plt

class fsru:
    def __init__(self, env, accessible):
        self.sendout = 1097
        self.min = 3300
        self.optim = 14e3
        self.arrival_time = [5, 5]
        self.called = False

        self.accessible = accessible # the list of times the LNGC can get to the FSRU

        self.connection = simpy.Resource(env, capacity=1)
        self.gas_tank = simpy.Container(env, init=174e3, capacity=174e3)

        self.level = []

        self.mon_proc = env.process(self.monitor_tank(env))

    def monitor_tank(self, env):
        while True:
            if self.gas_tank.level <= self.optim:
                if not self.called:
                    if self.accessible[env.now]:
                        self.called = True
                        yield env.timeout(random.randint(*self.arrival_time))
                        env.process(tanker(env, self))
            
            self.level.append((env.now, self.gas_tank.level))
            yield env.timeout(1)


def tanker(env, fsru):
    with fsru.connection.request() as req:
        yield req
        amount = 80e3
        time = 15
        apt = amount/time
        for i in range(time):
            print(f'filling @ {env.now}. from {fsru.gas_tank.level} to {fsru.gas_tank.level + apt}')
            yield fsru.gas_tank.put(apt)
            fsru.level.append((env.now, fsru.gas_tank.level))
            yield env.timeout(1)
        fsru.called = False
        print(f'Tanker leaving @ {env.now}, tank level: {fsru.gas_tank.level}')


def sendout(env, fsru):
    for i in itertools.count():
        amnt_send = min([1097, fsru.gas_tank.level - fsru.min])

        print(f'sending. tank level @ {env.now}: {fsru.gas_tank.level} to {fsru.gas_tank.level - amnt_send}')
        if amnt_send > 0:
            fsru.gas_tank.get(amnt_send)

        fsru.level.append((env.now, fsru.gas_tank.level))
        yield env.timeout(1)

if '__main__' in __name__:
    env = simpy.Environment()
    runtime = 50000
    accessible = [bool(random.getrandbits(1)) for val in range(runtime)]

    fsru = fsru(env, accessible)

    env.process(sendout(env, fsru))
    env.run(runtime)

    f_lvl = [val[1] for val in fsru.level]
    idx = [val[0] for val in fsru.level]

    df = pd.DataFrame(
        {
            'row' : idx,
            'lvl' : f_lvl
        }
    )

    full_df = pd.DataFrame(
        {
            'row' : [i for i in range(max(df.row.values))]
        }
    )

    df = df.groupby('row', as_index=False).min()

    full_df = full_df.set_index('row').join(df.set_index('row'))
    full_df = full_df.ffill()

    plt.plot(full_df.index, full_df.lvl)
    plt.show()