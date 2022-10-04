
from google.appengine.ext import ndb
import datetime
import json
from datetime import timedelta

import webapp2

# The name of the kinds in DataStore
# In the live system they will be StationSettings and Station4
# But there may be kinds used during testing
StationHourValueKind = "StationHourValue4"
StationSettingsKind = "StationSettings3"
StationKind = "Station3"
StationScalingKind = "Station_Scaling"
StationScalingVersionKind = "CurrentStationScalingVersion"


class StationScalingVersionModel(ndb.Model):
    @classmethod
    def _get_kind(cls):
        # Usually the class name would match the datastore kinds
        # This is so we can change the kind name at the top of the code
        return StationScalingVersionKind
    CurrentVersion = ndb.IntegerProperty()


class StationScalingModel(ndb.Model):
    @classmethod
    def _get_kind(cls):
        # Usually the class name would match the datastore kinds
        # This is so we can change the kind name at the top of the code
        return StationScalingKind
    TBTimestamp = ndb.DateTimeProperty()
    Offset = ndb.FloatProperty()
    Slope = ndb.FloatProperty()
    Suppress = ndb.BooleanProperty()
    Pollutant = ndb.StringProperty()
    Version = ndb.IntegerProperty()


# A subset of the StationHourValue kind in datastore,
#  just the 1 hour averages and end time
class StationHourValueModel(ndb.Model):
    @classmethod
    def _get_kind(cls):
        # Usually the class name would match the datastore kinds
        # This is so we can change the kind name at the top of the code
        return StationHourValueKind
    EndTime = ndb.DateTimeProperty()
    NO_1hour = ndb.FloatProperty()
    NO2_1hour = ndb.FloatProperty()
    PM1_1hour = ndb.FloatProperty()
    PM2_5_1hour = ndb.FloatProperty()
    PM4_1hour = ndb.FloatProperty()
    PM10_1hour = ndb.FloatProperty()
    PC_1hour = ndb.FloatProperty()
    CO2_1hour = ndb.FloatProperty()
    TSP_1hour = ndb.FloatProperty()
    O3_1hour = ndb.FloatProperty()


# The StationSettings kind in the datastore, when the settings apply from and
#  the slope and offsets for each pollutant
# Note: We currently do not apply slope and offset to the PM values
class StationSettingsModel(ndb.Model):
    @classmethod
    def _get_kind(cls):
        # Usually the class name would match the datastore kinds
        # This is so we can change the kind name at the top of the code
        return StationSettingsKind
    TBTimestamp = ndb.DateTimeProperty()
    NO_Offset = ndb.FloatProperty()
    NO_Slope = ndb.FloatProperty()
    NO_Suppress = ndb.BooleanProperty()
    NO_Hide = ndb.BooleanProperty()
    NO2_Offset = ndb.FloatProperty()
    NO2_Slope = ndb.FloatProperty()
    NO2_Suppress = ndb.BooleanProperty()
    NO2_Hide = ndb.BooleanProperty()
    CO2_Offset = ndb.FloatProperty()
    CO2_Slope = ndb.FloatProperty()
    CO2_Suppress = ndb.BooleanProperty()
    CO2_Hide = ndb.BooleanProperty()
    O3_Offset = ndb.FloatProperty()
    O3_Slope = ndb.FloatProperty()
    O3_Suppress = ndb.BooleanProperty()
    O3_Hide = ndb.BooleanProperty()
    PM10_Offset = ndb.FloatProperty()
    PM10_Slope = ndb.FloatProperty()
    PM10_Suppress = ndb.BooleanProperty()
    PM10_Hide = ndb.BooleanProperty()
    PM1_Offset = ndb.FloatProperty()
    PM1_Slope = ndb.FloatProperty()
    PM1_Suppress = ndb.BooleanProperty()
    PM1_Hide = ndb.BooleanProperty()
    PM2_5_Offset = ndb.FloatProperty()
    PM2_5_Slope = ndb.FloatProperty()
    PM2_5_Suppress = ndb.BooleanProperty()
    PM2_5_Hide = ndb.BooleanProperty()
    PM4_Offset = ndb.FloatProperty()
    PM4_Slope = ndb.FloatProperty()
    PM4_Suppress = ndb.BooleanProperty()
    PM4_Hide = ndb.BooleanProperty()
    TSP_Offset = ndb.FloatProperty()
    TSP_Slope = ndb.FloatProperty()
    TSP_Suppress = ndb.BooleanProperty()
    TSP_Hide = ndb.BooleanProperty()
    PC_Offset = ndb.FloatProperty()
    PC_Slope = ndb.FloatProperty()
    PC_Suppress = ndb.BooleanProperty()
    PC_Hide = ndb.BooleanProperty()


# The output data for the graph control
class GraphData(list):
    def __init__(self, stationName):
        self.stationName = stationName
        self.GraphValues = []

    def add_point(self, pt):
        self.GraphValues.append((pt))


# A point on the graph, level is the pollutant level (Y-axis)
#  and the datetime (X-axis)
class GraphPoint:
    def __init__(self, level, timeString):
        self.Level = level
        self.DateTime = timeString


# Dictionary containing the HiHi, LoLo and conversion factors for the pollutants
# If the conversionFactor is missing, it will use the default 1
pollutantInfo = {"NO2": {'lowerBound': 0, 'upperBound': 961, 'conversionFactor': 1.9125},
                 "O3": {'lowerBound': -20, 'upperBound': 300, 'conversionFactor': 1.9957},
                 "CO2": {'lowerBound': 200, 'upperBound': 2000},
                 "NOX": {'lowerBound': -39, 'upperBound': 2884, 'conversionFactor': 1.9125},
                 "PM10": {'lowerBound': -10, 'upperBound': 1000},
                 "PC": {'lowerBound': -5, 'upperBound': 300},
                 "PM2_5": {'lowerBound': -10, 'upperBound': 500}}


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.headers['Access-Control-Allow-Origin'] = '*'

        # URL parameters
        stationID = self.request.get('station')
        # From/To are UTC datetimes
        datetimeFrom = self.request.get('from')
        datetimeTo = self.request.get('to')
        poll = self.request.get('sensor').upper()
        # Optional parameter
        # daily for 24 hour averages, otherwise will output 1 hour averages
        average = self.request.get('avg')

        # Initialise GraphData with name of the station
        dataToShow = GraphData(stationID)
        # Convert the datetime parameters to date/time format
        rfrom = datetime.datetime.strptime(datetimeFrom, "%Y%m%d-%H%M")
        rto = datetime.datetime.strptime(datetimeTo, "%Y%m%d-%H%M")

        # Requires an ancestor, the pollutant hourly
        #  and EndTime index in index.yaml
        hourly_poll = poll + '_1hour '
        # Specific case for NOx, as it requires two pollutant columns
        # Need a specific index for NOx with both NO and NO2
        if poll == "NOX":
            hourly_poll = 'NO2_1hour, NO_1hour '
        # GQL query to return the endtimes and hourly pollutant values for
        #  the station and for the defined time period
        # The dates input should be GMT
        # The database EndTimes contain GMT (but during BST they are mis-stored as BST)
        # The query has to include the hour before, to overcome this
        value_query = ndb.gql('SELECT EndTime, ' + hourly_poll +
                              'FROM ' + StationHourValueKind +
                              ' WHERE ANCESTOR IS :1 '
                              'AND EndTime >= :2 '
                              'AND EndTime <= :3 '
                              'ORDER BY EndTime',
                              ndb.Key(StationKind, stationID), (rfrom + timedelta(hours=-1)), rto)
        # Maximum number of records allowed is 366 days x 24 hours x 2 years
        # This can be extended if the project is extended, but may still limit it to a year in a graph
        results = value_query.fetch(366 * 24 * 2)

        version_query = ndb.gql('SELECT * FROM ' + StationScalingVersionKind)
        version_results = version_query.fetch(1)
        for version in version_results:
            current_version = version.CurrentVersion
        # version_results = version_query.fetch(1)
        # current_version = version_results[0].CurrentVersion
        # GQL query to get all of the StationSettings for this time period
        # So we can get the related slope and offset
        settings_query = ndb.gql('SELECT * FROM ' + StationScalingKind +
                                 ' WHERE ANCESTOR IS :1 '
                                 'AND TBTimestamp <= :2 '
                                 'AND Pollutant = :3 '
                                 'AND Version = :4 '
                                 'ORDER BY TBTimestamp desc',
                                 ndb.Key(StationKind, stationID), rto, poll,current_version)
        settings_results = settings_query.fetch(250)

        # list to store the hourly values
        hours = list(())
        previousRecord = rfrom
        has_data = False
        for result in results:
            # TODO - Need to replicate changes from the hourly graphs for daily graphs
            # self.response.write(result.EndTime.strftime("%Y-%m-%d %H:%M"))
            # self.response.write(',')
            # self.response.write(result.NO2_1hour)
            # self.response.write(';')
            if average == "daily":
                # If this isn't the first entry
                # and if the previous record has a different date
                # calculate the daily average for the previous record's day
                if has_data and result.EndTime.date() > previousRecord.date():
                    # Calculate and Store the currentDay average,
                    # and start recording the new day
                    pt = calculateDailyAverage(hours, previousRecord.date())
                    dataToShow.add_point(pt.__dict__)
                    del hours[:]

                # If the previous record is more than 1 day older than the new
                #  Add a "None" point for the day after the previous record
                #   - to ensure gaps in the line for missing data
                if has_data and (abs((previousRecord - result.EndTime).days) > 1):
                    pt = GraphPoint(None, (previousRecord + timedelta(days=1)).strftime("%Y-%m-%d 12:%M"))
                    dataToShow.add_point(pt.__dict__)
                    # self.response.write('addition')
                has_data = True
                previousRecord = result.EndTime

                # Find the suitable settings for this station and date
                for settings in settings_results:
                    if settings.TBTimestamp < result.EndTime:
                        # Get the hourly records for this day
                        avg = getPollutantHourlyAverage(poll, result, settings)
                        if avg is not None:
                            hours.append(avg)
                        break

            else:
                for settings in settings_results:
                    if settings.TBTimestamp < result.EndTime:
                        # The EndTime stores the GMT time in winter, but the BST time recorded as GMT in the summer
                        # The key, however, does contain the consistent GMT time
                        keyString = result.key.string_id()
                        cforty, station, keyTime = keyString.split("_")
                        # keyTime is in dd/mm/yyyy hh:mm:ss format e.g. 10/01/2019 00:00:00
                        newEndTime = datetime.datetime.strptime(keyTime, '%d/%m/%Y %H:%M:%S')
                        # newEndTime is the UTC time for the hour end record
                        # all calculations should be done in UTC, the interface will convert to BST, if required
                        # If there is a previous record and it is
                        #  more than 1 hour older than the new record
                        #  add a None record for the hour after the previous
                        #  record to ensure gaps for missing data
                        if has_data and ((previousRecord + timedelta(seconds=3600)) != newEndTime):
                            pt = GraphPoint(None,
                                            (previousRecord
                                             + timedelta(seconds=3600)).strftime("%Y-%m-%d %H:%M"))
                            dataToShow.add_point(pt.__dict__)
                            # self.response.write('addition2')
                        has_data = True
                        avg = getPollutantHourlyAverage(poll, result, settings)
                        previousRecord = newEndTime
                        if avg is None:
                            # None record as there is
                            #  no valid hourly average for this hour
                            pt = GraphPoint(None,
                                            newEndTime.strftime("%Y-%m-%d %H:%M"))
                        else:
                            # Hourly average for this hour
                            pt = GraphPoint(round(avg, 3),
                                            newEndTime.strftime("%Y-%m-%d %H:%M"))
                        if ((newEndTime >= rfrom) and (newEndTime <= rto)):
                            # Add the point to the XML
                            dataToShow.add_point(pt.__dict__)
                        break
        if average == "daily" and has_data:
            # Add the last day's data
            pt = calculateDailyAverage(hours, previousRecord)
            dataToShow.add_point(pt.__dict__)
            # self.response.write('addition3')
        self.response.write(json.dumps(dataToShow.__dict__))
        # self.response.write('end')


# Check the converted hourly average is within the acceptable range
def validateValue(unvalidatedValue, poll):
    # if the unvalidatedValue is outside of the range return None otherwise return the input value
    returnValue = None
    if unvalidatedValue >= pollutantInfo[poll]['lowerBound'] and unvalidatedValue < pollutantInfo[poll]['upperBound']:
        returnValue = unvalidatedValue
    return returnValue


def calculateDailyAverage(hours, currentDay):
    # If 20 hours are recorded for a day, then store the average,
    #  if less then record null
    # 85% of 24 hours is 20.4
    if len(hours) >= 20:
        total = 0
        for hour in hours:
            total = total+hour
        pt = GraphPoint(round((total / len(hours)), 3),
                        currentDay.strftime("%Y-%m-%d 12:%M"))
    else:
        pt = GraphPoint(None, currentDay.strftime("%Y-%m-%d 12:%M"))
    return pt


def canPollutantShow_real(poll, settings):
    # If the <pollutant>_Suppress poroperty is set to True, then we don't show the value
    value = True
    if getattr(settings, "Suppress") is True:
        value = False
    return value


def canPollutantShow(poll, settings):
    # If the <pollutant>_Suppress poroperty is set to True, then we don't show the value
    value = True
    if getattr(settings, "Suppress") is True:
        value = False
    if getattr(settings, "Hide", False) is True:
        value = True
    return value


def getPollutantHourlyAverage(poll, result, settings):
    value = None
    hourAverage = None
    slope = 1
    offset = 0
    if poll == "NOX":
        # TO DO
        if canPollutantShow("NO2", settings) and canPollutantShow('NO', settings):
            if (result.NO2_1hour is not None) and (result.NO_1hour is not None):
                hourAverage = (((result.NO2_1hour * settings.NO2_Slope)
                                + settings.NO2_Offset)
                               + ((result.NO_1hour * settings.NO_Slope)
                                  + settings.NO_Offset))
    else:
        if canPollutantShow(poll, settings):
            hourAverage = getattr(result, poll + "_1hour")
            if hourAverage is not None:
                # if poll not in ['PM1', 'PM2_5', 'PM4', 'PM10']:
                slope = getattr(settings, "Slope")
                offset = getattr(settings, "Offset")

    if hourAverage is not None:
        unvalidatedValue = ((hourAverage * slope) + offset) * pollutantInfo[poll].get('conversionFactor', 1)
        value = validateValue(unvalidatedValue, poll)
    return value


app = webapp2.WSGIApplication([
    ('/data5', MainPage),

], debug=True)
