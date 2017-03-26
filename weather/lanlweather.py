#!/usr/bin/env python

import sys

import datetime
import requests

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

def c_to_f(t):
    return t * (212.-32.) / 100. + 32.

class LANLWeather(object):
    '''Fetch and parse data from the LANL weather machine.
    '''

    def __init__(self, start, end, keys):
        self.keys = keys
        if not hasattr(start, 'year'):
            self.start = datetime.datetime(*start)
        else:
            self.start = start
        if not hasattr(end, 'year'):
            self.end = datetime.datetime(*endt)
        else:
            self.end = end

        self.data = {}

    request_keys = [ 'spd1', 'spd2', 'spd3', # Speeds at 12, 23 and 46 m height
                     'sdspd1', 'sdspd2', 'sdspd3', # sdev of wind speeds
                     'dir1', 'dir2', 'dir3', # wind directions 12, 23, 46 m
                     'sddir1', 'sddir2', 'sddir3', # sdev of wind directions
                     'w1', 'w2', 'w3',       # vertical wind speeds
                     'sdw1', 'sdw2', 'sdw3', # stdev of vertical wind sp
                     'fvel2',                # friction velocity
                     'temp0', 'temp1', 'temp2', 'temp3', # temps 1.2, 12, 23, 46
                     'press',                # pressure
                     'rh', 'ah',             # rel and abs humidity
                     'dewp', 'precip',       # dew point, precipitation
                     'swdn', 'swup',         # shortwave radiation down/up
                     'lwdn', 'lwup',         # longwave radiation down/up
                     'netrad',               # net radiation
                     'sheat', 'lheat',       # sensible/latent heatflux
                     'stemp1', 'stemp2', 'stemp3',# soil temp -.02, -.06, -.10 m
                     'smoist1', 'smoist2',   # soil moisture 0 to 0.8, 0 to -.15
                     'gheat'                 # ground heat flux
    ]

    # List of towers that offer 15-minute reports.
    # This hasn't been checked. Some tower names may be wrong.
    towers = [ 'mcdn',       # may be ta5
               'ta6', 'ta49', 'ta53', 'ta54',
               'ncom',       # North Community
             ]

    def make_lanl_request(self, tower, keys, starttime, endtime):
        '''Make a data request to the LANL weather machine.
           tower is a string, like 'ta54'
           keys is a list of keys we're interested in (see request_keys).
           start and end times can be either datetimes or [y, m, d, [h, m, s]]

           The weather machine will only return 3 months worth of 15-minute data
           at a time.
        '''
        request_data = { 'tower': tower,
                         'format': 'tab',
                         'type': '15',
                         'access': 'extend',
                         'SUBMIT_SIGNALS': 'Download Data',

                         'startyear': '%04d' % starttime.year,
                         'startmonth': '%02d' % starttime.month,
                         'startday': '%02d' % starttime.day,
                         'starthour': '00',
                         'startminute': '00',

                         'endyear': '%04d' % endtime.year,
                         'endmonth': '%02d' % endtime.month,
                         'endday': '%02d' % endtime.day,
                         'endhour': '00',
                         'endminute': '00'
        }

        request_data['checkbox'] = ','.join(keys)

        print "Making a request for tower", tower, "data"
        r = requests.post('http://environweb.lanl.gov/weathermachine/data_request_green_weather.asp', data = request_data)

        if not r.text:
            raise RuntimeException, "Empty response!"

        # While testing, save it locally so we don't have to keep hammering LANL.
        outfile = open("lanldata.csv", "w")
        outfile.write(r.text)
        outfile.close()
        print "Wrote to lanldata.csv"

        self.parse_lanl_data(r.text)

    def read_local_data_file(self):
        infile = open("lanldata.csv", "r")
        blob = infile.read()
        infile.close()
        print "Read from lanldata.csv"
        self.parse_lanl_data(blob)

    def parse_lanl_data(self, blob):
        lines = blob.split('\n')
        self.fields = lines[5].split('\t')
        self.units = lines[6].split('\t')

        # Find the indices in the data for each key we're interested in:
        self.indices = []
        for i, k in enumerate(self.keys):
            idx = self.fields.index(k)
            if idx <= 0:
                raise IndexError, k + " is not in dataset"
            self.indices.append(idx)

            # and initialize a vector of values for that key
            self.data[k] = []

        self.dates = []

        # We'll also need to know the indices for the time values.
        year = self.fields.index('year')
        month = self.fields.index('month')
        day = self.fields.index('day')
        hour = self.fields.index('hour')
        minute = self.fields.index('minute')

        for line in lines[7:]:
            line = line.strip()
            if not line:
                continue
            l = line.split('\t')
            self.dates.append(datetime.datetime(int(l[year]),
                                                int(l[month]), int(l[day]),
                                                int(l[hour]), int(l[minute]),
                                                0))
            for i, k in enumerate(self.keys):
                idx = self.indices[i]
                if not l[idx] or l[idx] == '*':
                    self.data[k].append(0.)
                elif k.startswith('temp'):
                    self.data[k].append(c_to_f(float(l[idx])))
                else:
                    self.data[k].append(float(l[idx]))

class LANLWeatherPlots(LANLWeather):
    '''Plot (as well as fetch and parse) data from the LANL weather machine.
    '''

    def __init__(self, start, end, keys):
        super(LANLWeatherPlots, self).__init__(start, end, keys)
        self.fig = plt.figure(figsize=(15, 5))

    def show(self):
        # Reducing hspace here doesn't seem to make any difference.
        self.fig.subplots_adjust(hspace=0.5)

        # This gets rid of a lot of the extra whitespace.
        # pad controls padding at the top, bottom and sides;
        # w_pad does nothing I can see -- I think it's space between
        # plots horizontally if there are more than two columns;
        # h_pad seems to control the space between the plots vertically.
        # There doesn't seem to be a way to allow enough space at the top
        # for the top legend without also adding a bunch of unneeded
        # whitespace at the sides and bottom.
        plt.tight_layout(pad=2.0, w_pad=10.0, h_pad=3.0)

        plt.show()

    def plot_winds(self, ws, wd, plot_range=None):
        """
        Required input:
            ws: Key used for Wind speeds (knots)
            wd: Key used for Wind direction (degrees)
        Optional Input:
            plot_range: Data range for making figure (list of (min,max,step))
        """
        # PLOT WIND SPEED AND WIND DIRECTION
        self.ax1 = self.fig.add_subplot(2, 1, 1)   # nrows, ncols, plotnum
        ln1 = self.ax1.plot(self.dates, self.data[ws], label='Wind Speed')
        plt.fill_between(self.dates, self.data[ws], 0)
        self.ax1.set_xlim(self.start, self.end)
        if not plot_range:
            plot_range = [0, 20, 1]
        plt.ylabel('Wind Speed (knots)', multialignment='center')
        self.ax1.set_ylim(plot_range[0], plot_range[1], plot_range[2])
        plt.grid(b=True, which='major', axis='y', color='k',
                 linestyle='--', linewidth=0.5)

        plt.setp(self.ax1.get_xticklabels(), visible=True)
        axtwin = self.ax1.twinx()
        ln3 = axtwin.plot(self.dates,
                          self.data[wd],
                          '.k',
                          linewidth=0.5,
                          label='Wind Direction')
        plt.ylabel('Wind\nDirection\n(degrees)', multialignment='center')
        plt.ylim(0, 360)
        plt.yticks(np.arange(45, 405, 90), ['NE', 'SE', 'SW', 'NW'])
        # lns = ln1 + ln2 + ln3
        lns = ln1 + ln3
        labs = [l.get_label() for l in lns]
        # plt.gca().xaxis.set_major_formatter(mpl.dates.DateFormatter('%d/%H UTC'))
        axtwin.legend(lns, labs, loc='upper center',
                      bbox_to_anchor=(0.5, 1.2), ncol=3, prop={'size': 12})

        # Don't show all the extra whitespace matplotlib wants to add
        # to the edges of the graph.
        # This doesn't work.
        self.ax1.set_xlim(self.start, self.end)

    def plot_temp(self, temp, plot_range=None):
        if not plot_range:
            plot_range = [0, max(self.data[temp]), 4]
        self.ax3 = self.fig.add_subplot(2, 1, 2, sharex=self.ax1)
        self.ax3.plot(self.dates,
                      self.data[temp],
                      'g-',
                      label='Ground temperature')
        self.ax3.legend(loc='upper center', bbox_to_anchor=(0.5, 1.22),
                        prop={'size': 12})
        plt.setp(self.ax3.get_xticklabels(), visible=True)
        plt.grid(b=True, which='major', axis='y', color='k',
                 linestyle='--', linewidth=0.5)
        self.ax3.set_ylim(plot_range[0], plot_range[1], plot_range[2])
        plt.fill_between(self.dates, self.data[temp], plt.ylim()[0], color='g')
        plt.ylabel('Temperature', multialignment='center')
        # plt.gca().xaxis.set_major_formatter(mpl.dates.DateFormatter('%d/%H UTC'))
        axtwin = self.ax3.twinx()
        axtwin.set_ylim(plot_range[0], plot_range[1], plot_range[2])

def main():
    lwp = LANLWeatherPlots([2017, 3, 1], datetime.datetime.now(),
                           ["spd1", "dir1", "temp0"],)
    live = True
    if live:
        lwp.make_lanl_request('ta54')
    else:
        lwp.read_local_data_file()

    lwp.plot_winds('spd1', 'dir1')
    lwp.plot_temp('temp0')

    lwp.show()

if __name__ == '__main__':
    main()