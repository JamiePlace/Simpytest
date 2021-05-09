import simpy
import pandas as pd

class MonitoredContainer(simpy.Container):
    def __init__(self, *args, **kwargs):
        super().__init__(kwargs['env'], kwargs['capacity'], kwargs['init'])
        if 'min_level' in kwargs:
            self.min = kwargs['min_level']
        else:
            self.min = 0

        self.data = {
            'time' : [kwargs['env'].now],
            'level' : [kwargs['init']]
        }

    def get(self, amount):
        self.data['time'].append(self._env.now)
        self.data['level'].append(self.level - amount)
        return super().get(amount)

    def put(self, amount):
        self.data['time'].append(self._env.now)
        self.data['level'].append(self.level + amount)
        return super().put(amount)


def test_process(env, res):
    while True:
        yield env.timeout(1)
        yield res.get(amount = 5)

env = simpy.Environment()
tank = MonitoredContainer(env = env, capacity = 100, init = 100)

p1 = env.process(test_process(env, tank))
env.run(until = 15)

print(pd.DataFrame(tank.data))