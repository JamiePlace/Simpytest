import simpy
import random
import itertools
from functools import partial, wraps
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

class fsru:
    def __init__(self, lngc, env):
        self.lngc = lngc
        self.sendout = 1097
        self.min = 3300
        self.optim = 174e3 - 170e3 + (self.sendout * (170e3/lngc.sendout))
        self.arrival_time = [5, 5]
        self.called = False

        self.connection = simpy.Resource(env, capacity=1)
        self.gas_tank = simpy.Container(env, init=174e3, capacity=174e3)

        self.level = []

        # initial optimal filling time
        # predict when we will get to the optimal level
        self._optim_time = self.find_optimal_time()
        # initial time when the lngc can visit
        self.lngc_call = lngc.find_closest(self._optim_time)

        self.mon_proc = env.process(self.monitor_tank(env))

    def monitor_tank(self, env):
        while True:

            # if we are at a time when the LNGC
            # should be at the FSRU
            # we initiate the filling
            if env.now == self.lngc_call:
                if not self.called:
                    self.called = True
                    env.process(lngc.tanker(env, self))
            
            self.level.append((env.now, self.gas_tank.level))
            yield env.timeout(1)

    def find_optimal_time(self):
        t = (self.gas_tank.level - self.optim) / self.sendout
        t = t + env.now
        t = round(t, 0)
        return t

    def sendout_process(self, env):
        for i in itertools.count():
            amnt_send = min([1097, self.gas_tank.level - self.min])

            print(f'sending. tank level @ {env.now}: {self.gas_tank.level} to {self.gas_tank.level - amnt_send}')
            if amnt_send > 0:
                self.gas_tank.get(amnt_send)

            self.level.append((env.now, self.gas_tank.level))
            yield env.timeout(1)

class lngc:
    def __init__(self, env):
        self.arrival_time_upper = 33
        self.leg1 = pd.read_csv("leg1.csv", parse_dates=['timestamp'])
        self.leg2 = pd.read_csv("leg2.csv", parse_dates=['timestamp'])
        self.leg3 = pd.read_csv("leg3.csv", parse_dates=['timestamp'])
        self.sendout = 1e4
        self.LNG = simpy.Container(env, init=170e3, capacity=170e3)
        self.env = env
        self.data = []

    def find_closest(self, time):
        # find the accessible times for leg 2
        _l2 = np.where(self.leg2.accessible == True)[0].tolist()
        # create a distance metric based on distance from current time
        # to accessible times
        _l2_diff = [t - time for t in _l2]

        # remove times over the upper limit
        # negative time because it is in the past
        bad_times = np.where(np.array(_l2_diff) < -self.arrival_time_upper)[0]

        # drop these indices from both lists
        for item in sorted(bad_times, reverse=True):
            del _l2[item]
            del _l2_diff[item]

        # times closer to zero are better than further
        # closer negative times are better than closer possitive times
        
        _l2_diff = [1/t if t < 0 else t for t in _l2_diff]
        
        # the best time is the minimum of the above list
        try:
            best_time = np.where(np.array(_l2_diff) == min(_l2_diff))[0][0]
            print('-------- LNGC ---------')
            print(f'arriving @ {_l2[best_time]}')
            print(f'ideal time: {time}')
            print('----------------------')

            return(_l2[best_time])
        except:
            # if no times return a time that doesn't exist
            print('-------- LNGC ---------')
            print('no more arrivals')
            print('----------------------')
            return len(self.leg1) + 1

    def tanker(self, env, fsru):
        with fsru.connection.request() as req:
            yield req
            self.data.append(self.LNG.level)

            while self.LNG.level > 0:
                # can't overfill the fsru
                desired_sendout = min(self.sendout, self.LNG.level)
                amnt = min(fsru.gas_tank.capacity - fsru.gas_tank.level, desired_sendout)

                print(f'emptying lngc @ {env.now}, from {self.LNG.level} to {self.LNG.level - amnt}')
                print(f'filling @ {env.now}. from {fsru.gas_tank.level} to {fsru.gas_tank.level + amnt}')
                yield self.LNG.get(amnt)
                yield fsru.gas_tank.put(amnt)
                fsru.level.append((env.now, fsru.gas_tank.level))
                self.data.append(self.LNG.level)
                yield env.timeout(1)

            
            fsru._optim_time = fsru.find_optimal_time()
            self.LNG.put(self.LNG.capacity)

            print('------- LNGC LEAVING ---------')
            fsru.called = False
            # update values for the fsru controller
            # update the new optimal filling time
            # update the time the lngc can make it
            fsru.lngc_call = lngc.find_closest(fsru._optim_time)
            print(f'Tanker leaving @ {env.now}, tank level: {fsru.gas_tank.level}')

if '__main__' in __name__:
    env = simpy.Environment()

    lngc = lngc(env)
    fsru = fsru(lngc, env)

    runtime = len(lngc.leg1)

    env.process(fsru.sendout_process(env))
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

    print('-----------------------')
    print(f'percentage opperable: {sum(full_df.lvl > fsru.min)/len(full_df)}')
    print('-----------------------')


    fig, (ax1, ax2) = plt.subplots(1, 2)

    ax1.plot(full_df.index, full_df.lvl)
    ax1.axhline(y=fsru.optim, color='r', linestyle='-')

    ax2.plot(lngc.data)
    plt.show()