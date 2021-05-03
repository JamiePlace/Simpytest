"""
Fuel Station Refueling example per SimPy documentation:
https://simpy.readthedocs.io/en/latest/examples/gas_station_refuel.html
This example covers various differences in changing the refilling
threshold percentage as well as differences in customer behavior.
1. Customers arrive at a fuel station with n number of stations at
exponentially distributed interarrival times
2. Customers have one of three tank sizes: small, medium, large
and refill their tanks based on how much fuel they need at a triangular
distribution with most people filling 90-100% of their tank up.
3. The tanker truck is called when the station pump drops below a
certain threshold defined
4. The tanker truck takes a constant time to arrive and constant time
to refill the main pump
Covers:
- Resources: Resource
- Resources: Container
- Waiting for other processes
Scenario:
  A fuel station has a limited number of fuel pumps that share a common
  fuel reservoir. Cars randomly arrive at the fuel station, request one
  of the fuel pumps and start refueling from that reservoir.
  A fuel station control process observes the fuel station's fuel level
  and calls a tank truck for refueling if the station's level drops
  below a threshold.
"""
import itertools

import matplotlib.pyplot as plt
import numpy as np
import simpy


RANDOM_SEED = 42
THRESHOLD = 30             # Threshold for calling the tank truck (in %)
FUEL_TANK_SIZES = [45, 60, 150]   # liters, small/medium/large
REFUELING_SPEED = 50       # liters / minute
TANK_TRUCK_TIME = 30       # Minutes it takes the tank truck to arrive
TANK_REFILL_TIME = 20      # Minutes for refilling the pump
T_INTER = 1                # Create a car every [min, max] minutes
SIM_TIME = 1440            # Simulation time in minutes (24 hours)


class MonitoredResource(simpy.Resource):
    """MonitoredResource: custom class for monitoring
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = []

    def request(self, *args, **kwargs):
        self.data.append((self._env.now, len(self.queue)))
        return super().request(*args, **kwargs)

    def release(self, *args, **kwargs):
        self.data.append((self._env.now, len(self.queue)))
        return super().release(*args, **kwargs)


class FuelStation:
    """Create a fuel station with pumps and an underground tank"""

    def __init__(self, env, n_pumps, size):
        self.fuel_dispensers = MonitoredResource(env, capacity=n_pumps)
        self.fuel_tank = simpy.Container(env, init=size, capacity=size)
        self.mon_proc = env.process(self.monitor_tank(env))

    def monitor_tank(self, env):
        """Monitor fuel tank and refill if needed"""
        while True:
            if self.fuel_tank.level / self.fuel_tank.capacity < THRESHOLD:
                print('Calling tanker truck at %d' % env.now)
                yield env.process(tanker(env, self))

            yield env.timeout(10)  # Check every 10 minutes


def tanker(env, fuel_station):
    """Call tanker truck"""
    yield env.timeout(TANK_TRUCK_TIME)
    print('Tank truck arriving at time %d' % env.now)
    amount = fuel_station.fuel_tank.capacity - fuel_station.fuel_tank.level
    amnt = amount / TANK_REFILL_TIME
    print('Tank truck refuelling %.1f liters.' % amount)
    # this doesn't work
    # probably need to model the tanker as another object with the fuel in the
    # tank being monitored in a container and every itteration once it starts filling
    # we monitor the level
    for i in range(TANK_REFILL_TIME):
        yield env.timeout(1)
        print('Tank truck refueled %d at time %d' % (amnt, env.now))
        yield fuel_station.fuel_tank.put(amnt)


def car(name, env, fuel_station):
    """Car process interaction, refill car from tank"""
    fuel_tank_level = np.random.triangular(0.75, .90, 1.0)
    print('%s arriving at fuel station at %.1f' % (name, env.now))
    with fuel_station.fuel_dispensers.request() as req:
        start = env.now
        # Request one of the fuel pumps
        yield req

        # Get the required amount of fuel
        fuel_tank_size = np.random.choice(FUEL_TANK_SIZES)
        liters_required = fuel_tank_size * fuel_tank_level
        yield fuel_station.fuel_tank.get(liters_required)

        # The "actual" refueling process takes some time
        yield env.timeout(liters_required / REFUELING_SPEED)

        print(
            '%s finished refueling in %.1f minutes at %d. Filled %d liters. %d liters ramining' % 
            (name, env.now - start, env.now, liters_required, fuel_station.fuel_tank.level)
        )


def car_generator(env, fuel_station):
    """Generate new cars that arrive at the fuel station."""
    for i in itertools.count():
        yield env.timeout(np.random.exponential(T_INTER))
        env.process(car('Car %d' % i, env, fuel_station))


if __name__ == "__main__":
    np.random.seed(RANDOM_SEED)
    n_pumps = [2, 4]
    sizes = [5000, 10000]
    fig, ax = plt.subplots(len(n_pumps), 2, sharex='col', sharey='row')
    for i, capacity in enumerate(n_pumps):
        for j, size in enumerate(sizes):
            env = simpy.Environment()

            fuel_station = FuelStation(env, capacity, size)
            env.process(car_generator(env, fuel_station))
            env.run(until=SIM_TIME)

            X = [d[0] for d in fuel_station.fuel_dispensers.data]
            y = [d[1] for d in fuel_station.fuel_dispensers.data]

            ax[i, j].bar(X, y)
            ax[i, j].set_title('n=%d, c=%d' %
                               (capacity, size))
            ax[i, j].set_xlabel('Sim time')
            ax[i, j].set_ylabel('Queue size')

    plt.show()