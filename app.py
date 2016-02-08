import requests, json, math
from urllib import urlencode
import datetime
from flask import Flask, render_template
import pyeto

app = Flask(__name__)

#assign current day and past 7 days to a variable
now = datetime.datetime.now()
week_ago = now - datetime.timedelta(days=6)

### function for requesting 7 days weather data from CIMIS API
def get_data_from_CIMIS():
    url = 'http://et.water.ca.gov/api/data'
    headers = {'content-type': 'application/JSON; charset=utf8'} 
    params = (('appKey', 'f9215da5-a2d7-4eff-bbe5-9b09d967088b'),
    ('targets', '95316'), 
    ('startDate', week_ago.strftime('%Y-%m-%d')),
    ('endDate', now.strftime('%Y-%m-%d')),
    ('dataItems', 'day-eto,day-precip,day-vap-pres-avg,day-air-tmp-avg,day-rel-hum-avg,day-dew-pnt,day-wind-spd-avg,day-wind-ene,day-soil-tmp-avg')
    )

    response = requests.get(url, params=params, headers=headers)
    data = json.loads(response.text)   
    return data["Data"]["Providers"][0]["Records"]


### method for requesting weather data from WU
def get_data_from_WU():

    ###array to store the reports
    wu_weather_reports = []

    ##  today and last 6 days definition
    day1 = now - datetime.timedelta(days=6)
    day2 = now - datetime.timedelta(days=5)
    day3 = now - datetime.timedelta(days=4)
    day4 = now - datetime.timedelta(days=3)
    day5 = now - datetime.timedelta(days=2)
    day6 = now - datetime.timedelta(days=1)
    day7 = now

    #### convert dates to WU required format
    days = {
    'day1': day1.strftime('%Y%m%d'),
    'day2': day2.strftime('%Y%m%d'),
    'day3': day3.strftime('%Y%m%d'),
    'day4': day4.strftime('%Y%m%d'),
    'day5': day5.strftime('%Y%m%d'),
    'day6': day6.strftime('%Y%m%d'),
    'day7': day7.strftime('%Y%m%d')

    }

    ### make API wather hisotry call for each day
    for day in days:
        url = 'http://api.wunderground.com/api/7c2ab99a0ccee978/history_{0}/q/95316.json'.format(days[day])
        headers = {'content-type': 'application/JSON; charset=utf8'} 
        response = requests.get(url, headers=headers)

        data = json.loads(response.text)

        #ETo calculation for the day using FAO-56 Penman-Monteith method
        lat = pyeto.deg2rad(37.585652)
        altitude = 38

        julian_day = datetime.datetime.strptime(days.get(day), '%Y%m%d').timetuple().tm_yday
        sol_dec = pyeto.sol_dec(julian_day)
        sha = pyeto.sunset_hour_angle(lat, sol_dec)
        ird = pyeto.inv_rel_dist_earth_sun(julian_day)

        ### net radiation calculator
        net_rad = pyeto.et_rad(lat, sol_dec, sha, ird) 

        temp_c = float(data["history"]["observations"][1]["tempm"])
        temp_k = float(data["history"]["observations"][1]["tempi"])
        humidity = float(data["history"]["observations"][1]["hum"])
        dew_point = float(data["history"]["observations"][1]["dewptm"])
        ws = float(data["history"]["observations"][1]["wspdm"])

        #actual and saturated vapour pressure in kPH
        svp = pyeto.svp_from_t(temp_c)
        avp = pyeto.avp_from_tdew(dew_point)
        delta_svp = pyeto.delta_svp(temp_c)

        atm_pressure = pyeto.atm_pressure(altitude)
        psy = pyeto.psy_const(atm_pressure)

        #### the ETo plugin retun results in mm, it was converted to inched
        ETo_in_mm = pyeto.fao56_penman_monteith(net_rad, temp_k, ws, svp, avp, delta_svp, psy, shf=0.0)
        ETo = ETo_in_mm * 0.039370

        ## insert eto value to day weather report
        data["history"]["observations"][1].update({"ETo": "{0:.2f}".format(ETo)})

        ###add report to report collector array
        wu_weather_reports.append(data["history"]["observations"][1])

    #return all reports
    return wu_weather_reports

@app.route('/')
def get_weather_data():
    weather_reports = {}

    ##make api calls on app requests.
    weather_reports.update({'CIMIS': get_data_from_CIMIS()})
    weather_reports.update({'WU': get_data_from_WU()})
    return render_template('index.html', weather_reports=weather_reports)



if __name__ == '__main__':
    app.run(debug=True)